# Phase 6 Retrospective — CI/CD (Keyless Deployment Pipeline)

Period: 2026-06-15–16 · Sub-phases 6.1–6.3
Outcome: Complete end-to-end keyless CI/CD pipeline. Every push to main
lints, tests, and deploys both surfaces (Cloud Run backend + Firebase
Hosting frontend) without a single static credential — WIF throughout,
SA impersonation only where the third-party API demands a real OAuth2
token. Pipeline validated green: run 27562387259 (Phase 6.1.3) confirmed
both surfaces live and correct after merge.

## What shipped

- **ADR-0018** (CI/CD security model): direct WIF, no JSON keys, SA
  impersonation exception for Firebase Hosting REST, impersonation IAM
  rule.
- **Terraform** (`wif_iam.tf`): WIF pool/provider imported and managed;
  7 project-level IAM bindings + 3 SA-level bindings for the CI
  principalSet; `firebase_admin_service_usage_consumer` for the
  impersonated SA itself.
- **`.github/workflows/pr-gates.yml`**: ruff + bandit + pytest (≥90%
  coverage) + ESLint + Vitest + pnpm build — blocks PRs on failure.
- **`.github/workflows/deploy.yml`**: gates-first; then keyless build →
  push → Cloud Run deploy; then SA-impersonated Firebase Hosting REST
  deploy; triggers only on push to main.
- **`scripts/deploy_hosting_rest.sh`**: full REST API deploy sequence
  (version-create with translated config → populateFiles → per-file
  upload → FINALIZE → release); no firebase-tools dependency.
- **Branch protection** on main: PR + passing `backend-gates` +
  `frontend-gates` required; no direct push.
- **`scripts/deploy_cloud_run.sh`** Redis describe fix: loud failure
  instead of silenced `2>/dev/null || true`.
- **`frontend/package.json`**: `packageManager: pnpm@11.5.2` +
  `engines.node: >=22.13` — single source of truth for CI pnpm/Node
  selection.
- **`backend/tests/test_tenant_config.py`**: hermetic test via
  `dependency_overrides[get_firestore_client]`.

## Issue log (the instructive part)

| # | Symptom | Root cause | Fix | Rule |
|---|---------|-----------|-----|------|
| 1 | ruff missed `src/` imports | bandit/ruff ran from repo root, not `backend/` | `working-directory: backend` in gates job | Always run language-specific linters from the package root |
| 2 | pytest `DefaultCredentialsError` in CI | `test_validation_failed_includes_field_detail` constructed a real Firestore client; FastAPI resolves deps before Pydantic 422 | `dependency_overrides[get_firestore_client]` in the test | Tests that hit an external dependency by accident are non-hermetic; the CI cold environment reveals it |
| 3 | pnpm `allowBuilds` parse failure in CI | CI used pnpm v9 (from `version: 9`); `allowBuilds` requires pnpm v11; local was already v11 | `package_json_file: frontend/package.json` so the action reads `packageManager: pnpm@11.5.2` | Version drift between local and CI is invisible until a CI run hits it; pin via `packageManager` and let the action read it |
| 4 | Node `node:sqlite` missing in CI | pnpm v11 requires Node ≥22.13; CI was Node 20 | `node-version: 22` | Follow the toolchain's own minimum; read the error before changing the version |
| 5 | `gcloud builds submit` permission denied | CI principal missing `serviceUsageConsumer` and `storage.admin` | Added both to `wif_iam.tf` | Enable all APIs and grants *before* the pipeline needs them — not after the first failure |
| 6 | Redis describe returned empty string silently | `gcloud redis instances describe … 2>/dev/null \|\| true` suppressed the permission error | Single `value(host,port)` call; loud error on failure | Never silence stderr on permission/auth calls; the error message is the diagnosis |
| 7 | firebase-tools "unexpected error" | `--non-interactive` missing; interactive prompts in CI | Added `--non-interactive` | Always add the non-interactive flag in CI |
| 8 | firebase-tools "No OAuth tokens found" crash | firebase-tools 15.x does not support WIF `external_account` ADC; its token manager only knows `firebase login` / `login:ci` tokens | Replaced firebase-tools with the Firebase Hosting REST API entirely | firebase-tools and WIF external_account credentials are fundamentally incompatible; the REST API is the correct keyless path |
| 9 | Firebase Hosting REST API 401 UNAUTHENTICATED | Direct-WIF federated token (1484 chars) is not a standard OAuth2 access token; the REST API rejects it | SA impersonation via `auth@v3` with `token_format: access_token`; mints a real OAuth2 token (1024 chars) | When a third-party REST API demands OAuth2, WIF direct is not sufficient; SA impersonation is the keyless bridge |
| 10 | Firebase Hosting REST API 400 INVALID_ARGUMENT | `firebase.json` uses CLI schema (`source`/`destination`); REST API Version.config requires `glob`/`path` | `translate()` function in `deploy_hosting_rest.sh` | CLI and REST API schemas are not the same; read the API reference, not just the CLI docs |
| 11 | Firebase Hosting REST API 403 USER_PROJECT_DENIED | `X-Goog-User-Project` causes the API to check `serviceusage.services.use` against the *impersonated SA*, not the principalSet | `serviceUsageConsumer` granted to `sa-firebase-admin` (the SA, not just the principalSet) | SA impersonation shifts the effective IAM caller identity for all downstream API checks |
| 12 | `gha-creds-*.json` false-positive in `git status` | `google-github-actions/auth@v3` writes a credential file to the workspace root | Added `gha-creds-*.json` to `.gitignore` | Credential files written by Actions steps must be gitignored proactively |

## Toolchain-drift cascade (the five local-vs-CI catches)

This phase surfaced five places where local and CI used different
toolchain versions silently:

1. **Linter working directory** — ruff/bandit ran from repo root locally
   (both work); CI's `working-directory` was missing (issue 1).
2. **Test hermeticity** — local dev impersonates ADC and real Firestore
   answers; CI has no credentials (issue 2).
3. **pnpm version** — local was v11 (from corepack); CI action pinned v9
   (issue 3). Fixed by reading `packageManager` from `package.json`.
4. **Node version** — local was 22.x; CI was 20 (issue 4). pnpm v11's
   `node:sqlite` dependency caught it.
5. **Firebase Hosting deploy** — local uses `firebase login` (interactive
   user token); CI needs a non-interactive, keyless path. Exposed the
   entire firebase-tools/WIF incompatibility saga.

Each was invisible in local runs and only became a hard failure in the
clean CI environment. The fix in each case was to make the pinned version
an explicit declaration in the project (not an implicit ambient dependency)
so CI and local read from the same source of truth.

## The firebase-tools/WIF incompatibility saga

The path from "deploy Firebase Hosting in CI" to the working solution
went through six sub-phases:

1. Added `--non-interactive` to `firebase deploy` (6.2.7) — got further.
2. Tried `FIREBASE_TOKEN` bridge (6.2.8) — 401; firebase-tools couldn't
   use the access token correctly.
3. Tried the official Firebase Hosting GitHub Action (6.2.9) — requires
   a JSON service account key; incompatible with keyless WIF.
4. Tried WIF ADC + `GOOGLE_CLOUD_PROJECT` (6.2.10) — `--debug` revealed
   "No OAuth tokens found"; crashes on `undefined.access_token`. Root
   cause confirmed: firebase-tools 15.x's token manager only knows user
   tokens and login:ci refresh tokens. WIF `external_account` ADC is
   simply not supported.
5. Switched to Firebase Hosting REST API (6.2.11–6.2.13) — correct
   approach, but `gcloud auth print-access-token` with a WIF credential
   returns a federated token (1484 chars), not a standard OAuth2 token;
   the REST API returns 401.
6. SA impersonation (6.2.14) — `auth@v3` with `service_account` +
   `token_format: access_token` mints a real OAuth2 token (1024 chars).
   REST API accepts it. Then 400 (schema), then 403 (SA IAM). Both fixed
   wall-by-wall. Pipeline green on run 27562387259.

Total: ~9 sub-phases for one deploy target. Each failure was a precise
diagnosis followed by one targeted fix — the 401→400→403→success
progression is least-privilege working as designed.

## What went well

- **Wall-by-wall IAM discovery.** Each permission error was diagnosed
  precisely (error code + message), fixed with a single Terraform
  resource, validated, and documented. The result is an exact, auditable
  inventory of what CI needs and why.
- **Loud error surfacing.** The `api()` helper in `deploy_hosting_rest.sh`
  printing HTTP status + body on ≥400 reduced every REST failure from
  "something went wrong" to a precise HTTP code and API error message.
  Each 401/400/403 was immediately actionable.
- **The `--debug` investment.** Spending a sub-phase (6.2.10) on `--debug`
  output was the right call: it definitively confirmed the firebase-tools
  incompatibility and ended further debugging of that path.
- **Terraform-managed WIF IAM.** Every CI permission grant is in version-
  controlled Terraform. The plan shows exactly what changes; the state is
  the ground truth; no manual gcloud grants to reverse-engineer later.
- **Branch protection from day 1.** Setting up PR gates before Phase 7
  development starts means the next feature phase starts with CI already
  enforcing quality gates.

## What was hard

- **No static credential escape hatch.** Every auth problem had to be
  solved within the keyless WIF model. There was no "just use a key for
  now" fallback (org policy `iam.disableServiceAccountKeyCreation`). This
  is correct security posture, but it means the firebase-tools saga had
  to be resolved completely rather than papered over.
- **firebase-tools as a black box.** The tool's internal token management
  is not documented; the failure mode ("No OAuth tokens found") only
  appears in `--debug` output. Without `--debug`, the error message was
  "unexpected error" — no signal at all.
- **Three-way schema mismatch.** firebase.json (CLI schema) ≠ REST API
  Version.config schema ≠ what we assumed they were. Each of the 400/403
  failures required reading a different part of the Firebase documentation.
- **SA impersonation shifting IAM context.** The mental model "CI WIF
  principal does the deploy" broke the moment SA impersonation entered:
  the *impersonated SA* is the effective caller for all REST API checks
  downstream of the token mint. Required re-reading the IAM model.

## What we'd do differently

- **Start with the REST API.** For any Firebase Hosting deploy in a
  keyless CI context, skip firebase-tools entirely and go straight to the
  REST API. The CLI is for human-interactive use; the REST API is for
  automation.
- **Separate the deploy token step earlier.** The "direct WIF works for
  gcloud; SA impersonation needed for Firebase Hosting REST" split was
  discovered late. Recognize up front that not all Google APIs accept
  WIF federated tokens — check the API's token requirements before
  designing the auth flow.
- **Add `packageManager` and `engines.node` to `package.json` at project
  creation.** The pnpm/Node version drift was entirely preventable with
  two JSON fields. Three lines of config would have saved two sub-phases.

## Decisions of note / deferrals

- **storage.admin is project-scoped (broader than needed).** CI needs
  storage access only for the Cloud Build staging bucket. Tightening to
  bucket-scoped `storage.admin` on `sport-slot-dev-cloudbuild` is
  deferred to Phase 9 least-privilege hardening (documented in ADR-0018
  and wif_iam.tf).
- **deploy_hosting.sh kept for local use.** The CI branch of that script
  is vestigial (CI uses the REST script directly); local still uses
  `firebase deploy` with interactive login. Cleaning up the CI branch is
  low-priority cleanup deferred to Phase 9.
- **Secret Manager integration + detect-secrets** were in the original
  Phase 6 scope. All current secrets are already in Secret Manager
  (wired at app startup); no new secrets were needed for CI. detect-
  secrets is tracked as a Phase 9 hardening item.
