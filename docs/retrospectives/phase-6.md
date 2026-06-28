# Phase 6 Retrospective: Keyless CI/CD via Workload Identity Federation

**Status:** Complete
**Duration:** ~3 weeks (mid-May through mid-June 2026)
**Outcome:** Fully keyless, least-privilege, Terraform-managed CI/CD pipeline.
On merge to `main`, GitHub Actions authenticates to GCP via Workload
Identity Federation (no exported service-account keys), runs quality gates,
builds and deploys the backend to Cloud Run, and deploys the frontend to
Firebase Hosting — with zero manual commands.
**Validation:** PR #1 (the pipeline-validation PR) closed Phase 6
end-to-end: gates green, auto-deploy green, both surfaces live.

---

## What this phase was

Phase 6 made `committed = deployed` both *true* and *mandatory* for
SlotSense. Before Phase 6, deployment was a manual loop — locally
authenticated developer commands, sometimes from a feature branch,
sometimes against `main`, with no enforcement that what shipped to dev
matched what was reviewed. The "works on my machine" problem was real
in CI/CD itself.

The phase had three interlocking goals:

1. **Keyless authentication from GitHub Actions to GCP** — no exported
   service-account JSON keys anywhere in the repository, no secrets in
   GitHub that could leak, no developer credentials in the deploy path.
2. **Least-privilege IAM** — every permission the pipeline needs
   discovered explicitly and codified in Terraform, rather than granted
   broadly and hoped for the best.
3. **Enforced PR flow** — branch protection on `main` requires a pull
   request plus passing checks, making the deploy path the *only* path.

The interesting hard part — and the part the retrospective spends most
of its space on — was the third goal's interaction with the first: how
to deploy Firebase Hosting *keylessly* from CI when neither Firebase's
own tooling nor the official GitHub Action supports keyless
authentication. The resolution required abandoning `firebase-tools`
entirely for the deploy and driving the Firebase Hosting REST API
directly with an SA-impersonated OAuth2 token. The convergence trail
(401 → 400 → 403 → success) and what each error taught is the heart of
this retrospective.

This document is written for a portfolio reader who wants to understand
not just *what* Phase 6 delivered, but the engineering thinking that
shaped it — particularly the lesson about how least-privilege IAM is
*discovered* rather than designed, and the lesson about how identity
shifts under service-account impersonation. Both are reusable across
any future project doing keyless GCP authentication from CI.

---

## What shipped

### Authentication architecture

Phase 6 ended with two distinct authentication paths sharing one
Workload Identity Federation provider:

| Surface | Identity path | Token type |
|---------|--------------|------------|
| Cloud Build / Artifact Registry / Cloud Run | Direct WIF → principalSet IAM | `gcloud` federated credential (~1484 chars, used by `gcloud` internally) |
| Firebase Hosting (REST API) | WIF → impersonate `sa-firebase-admin` | OAuth2 access token (~1024 chars, accepted by REST APIs) |

The two-path design is deliberate: the federated credential works
seamlessly for `gcloud`-based steps (the build-and-deploy path), but
cannot be used as a bearer token for Google REST APIs. The Firebase
Hosting deploy required minting a *real* OAuth2 access token via
service-account impersonation. Both paths use the same WIF pool and
provider; the second `google-github-actions/auth@v3` step in the
workflow performs the impersonation.

### Deploy flow (on `push` to `main`)

1. **gates** — backend (`ruff`, `bandit`, `pytest` ≥90% coverage) and
   frontend (lint, test, build) run in parallel. Either failing blocks
   the deploy.
2. **build-push** — Cloud Build builds the backend image and pushes
   to Artifact Registry. Identity: principalSet via direct WIF.
3. **deploy-dev** — Cloud Run deploy. Runtime identity:
   `sa-cloud-run`.
4. **mint token** — second `auth@v3` step impersonates
   `sa-firebase-admin` with `token_format: access_token` →
   `FIREBASE_ACCESS_TOKEN`.
5. **deploy hosting** — frontend build, then
   `scripts/deploy_hosting_rest.sh` deploys via Hosting REST API using
   the minted token.

### IAM layout (Terraform-managed in `terraform/wif_iam.tf`)

Granted to the **WIF principalSet** (for direct-WIF gcloud steps):
- `roles/run.admin`
- `roles/artifactregistry.writer`
- `roles/cloudbuild.builds.editor`
- `roles/serviceusage.serviceUsageConsumer`
- `roles/storage.admin` *(broad; flagged for Phase 9+ tightening to
  bucket-scoped Cloud Build staging bucket)*
- `roles/redis.viewer`
- `roles/iam.serviceAccountUser` on `sa-cloud-run` and `sa-cloud-build`
- `roles/iam.serviceAccountTokenCreator` on `sa-firebase-admin`
  *(enables the impersonation that mints the Hosting token)*

Granted to **`sa-firebase-admin`** (the impersonated caller for the
Hosting REST API):
- `roles/serviceusage.serviceUsageConsumer`
- `roles/firebasehosting.admin`

### Branch protection

`main` is protected by GitHub branch protection rules requiring:
- A pull request before merge
- Both PR Gates checks passing (`backend-gates`, `frontend-gates`)
- Conversation resolution before merge

There is no direct-to-main push path. The deploy workflow runs on
`push` to `main`, but the only way to get a commit to `main` is
through a merged PR with passing gates.

### Custom Firebase Hosting deploy script

`scripts/deploy_hosting_rest.sh` (~150 lines, shellcheck-clean)
implements the keyless Hosting deploy:
- Token: `$FIREBASE_ACCESS_TOKEN` (CI) or `gcloud auth print-access-token`
  fallback (local interactive use)
- Sends `Authorization: Bearer <token>` and `X-Goog-User-Project:
  <project>` headers on every call
- Translates `firebase.json` hosting config (`source/destination`,
  CLI schema) → REST schema (`glob/path`)
- Sequence: create version → `populateFiles` (path → sha256-of-gzip
  map) → upload required gzipped files by hash → finalize version →
  release to `live`
- Surfaces full API error bodies on any `>=400` (loud failures, no
  silent `2>/dev/null`)

This script is operational documentation. It exists as a permanent
reference for how SlotSense deploys its frontend keylessly, and the
patterns generalize to any Google REST API whose CLI/SDK resists WIF
ADC.

---

## The convergence trail (the heart of this phase)

Most of Phase 6 was straightforward infrastructure work. The hard
part — the part that taught the most — was getting Firebase Hosting
to deploy keylessly. Eight approaches were tried before the ninth
succeeded. The progression of error messages (`UNAUTHENTICATED` →
`INVALID_ARGUMENT` → `USER_PROJECT_DENIED` → success) is the
signature of correctly-diagnosed, least-privilege convergence: each
error named exactly the next fix.

| # | Attempt | Result |
|---|---------|--------|
| 1 | `firebase-tools` with `--project --non-interactive` | Vague "unexpected error" — not a TTY issue |
| 2 | `firebase-tools` with `FIREBASE_TOKEN=` access token | 401; the CLI treats access tokens as refresh tokens (deprecated path) |
| 3 | Official `FirebaseExtended/action-hosting-deploy` | Requires `firebaseServiceAccount` JSON key — incompatible with keyless |
| 4 | `firebase-tools` with pure ADC + `GOOGLE_CLOUD_PROJECT` + `--debug` | **Diagnostic win:** "No OAuth tokens found" → crash on `undefined.access_token`. Proves `firebase-tools` cannot use WIF external_account ADC |
| 5 | REST API with `gcloud auth print-access-token` | 401 — federated token is not a valid OAuth2 access token (proven by length: ~1484 chars, not ~1024) |
| 6 | REST API with `application-default print-access-token` | Worse — tries to re-exchange the OIDC subject token mid-job → "Unable to retrieve Identity Pool subject token / connection refused" |
| 7 | REST API + plain token + `X-Goog-User-Project` + loud errors | Still 401, but full error body confirmed token rejection at the API layer |
| 8 | REST + **SA-impersonated** access token (`auth@v3` `token_format: access_token`) | 401 → **400** — auth solved; now a request-body issue |
| 9 | Translate `firebase.json` `source/destination` → REST `glob/path` | 400 → **403 USER_PROJECT_DENIED** — config fixed; now a permission issue on the SA |
| 10 | Grant `roles/serviceusage.serviceUsageConsumer` to **`sa-firebase-admin`** | **Success** — full pipeline green |

The pattern is worth dwelling on. Each error was *specific* — not
"something is wrong" but "this exact field/role/token is wrong." Each
fix addressed exactly the named problem and produced the *next* specific
error. Nothing was guessed; nothing was over-corrected. The pipeline
arrived at green with the minimum set of changes the errors named.

That pattern is what least-privilege engineering looks like in
practice. It's slower than "grant broad and move on" — each wall
extends the timeline by however long it takes to diagnose — but the
result is an IAM inventory that is *exactly* what the pipeline needs,
and nothing more. The audit trail (what role was granted, why, which
error it resolved) lives in commit history.

---

## Lessons (what Phase 6 taught)

The retrospective groups Phase 6's lessons by theme. These feed the
Three-Agent Engineering Protocol's broader corpus of named patterns and
failure modes.

### Lesson 1: Toolchain drift between local and CI

The first time the Phase 6 pipeline ran in clean CI, five "works on
my machine" issues surfaced that local runs had hidden:

- **Lint scope differed.** Local `ruff` ran against a narrower set of
  files than CI's invocation.
- **A security scanner produced false positives** that the local
  invocation suppressed by default but CI surfaced.
- **A test depended on ambient credentials.** Locally,
  `gcloud auth application-default login` made the credential
  available; CI had no such ambient state.
- **`pnpm` version drift.** Local used pnpm 9; CI installed pnpm 11.
  Lock file format differences caused install failures.
- **Coupled Node version requirement.** A frontend dependency required
  Node 20+; CI had Node 18 by default.

The fix: pin every toolchain version explicitly so local and CI are
byte-identical. The `packageManager` field in `package.json`, the
`engines.node` declaration, the `.python-version` file, the
`packages.json` `pnpm-lock.yaml` consistency — all of these became
mandatory rather than advisory.

**The deeper lesson:** *a clean CI environment is the most rigorous
test of a build's reproducibility.* Local environments accumulate
ambient state (installed tools, cached credentials, environment
variables sourced from `.zshrc`) that hides reproducibility issues
until the work goes somewhere clean. The first run in CI is rarely
green; treat the first-run failures as discovery rather than as bugs.

This lesson surfaced again, in a different form, in Phase 9: hermetic
tests are necessary but not sufficient, because realistic-data
patterns aren't in fixtures unless deliberately engineered. Different
domain, same underlying principle — clean execution environments
surface bugs that ambient environments hide.

### Lesson 2: Least privilege is *discovered*, not designed

The conventional approach to IAM is "grant the role that the
documentation says is needed for this operation." That works for
well-trodden paths. For unusual paths (like minting a Hosting REST
API token via SA impersonation under direct WIF), there is no
documentation that says "these are the exact roles you need." The
correct posture is to grant *nothing* extra, run the operation, and
let the failure name the missing role.

Phase 6 used this discipline throughout. The IAM list in
`terraform/wif_iam.tf` reads as an exact inventory of what CI does
and nothing more — because each entry was added in response to a
specific permission error, with a commit message naming the failing
operation. The audit trail is built into git history.

**The deeper lesson:** *codify what you discover; don't pre-grant
what you imagine.* Pre-granting broad roles ("just give it Editor and
move on") is the path to over-permissioned CI principals that become
audit findings later. Discovery-based grants take longer up front but
produce a permission set that is defensible because each role's
justification is recoverable from history.

A practical consequence: this approach requires *loud* failures.
Silent failures (a try/catch that swallows errors, a script that
exits 0 even on partial failure) defeat the discovery process because
the next wall is hidden. Phase 6's `deploy_hosting_rest.sh` is
deliberately loud — it surfaces full API error bodies, never `2>/dev/null`s
an HTTP error. The same principle applies to Terraform plans, gcloud
invocations, and any CI step where a permission error might otherwise
look like generic failure.

### Lesson 3: Identity shifts under impersonation

This was the lesson Phase 6's keyless Hosting work delivered most
sharply, and it generalizes to any pattern that mixes direct WIF with
service-account impersonation.

In Phase 6's setup, the WIF principalSet (the GitHub repo's federated
identity) holds most of the project's IAM directly. For Cloud Run
deploys, the principalSet acts directly — there's no service account
in the picture during the gcloud-based deploy steps. But for Firebase
Hosting, an intermediate impersonation happens: the principalSet
impersonates `sa-firebase-admin` to mint an OAuth2 access token, and
the *SA* — not the principalSet — becomes the effective caller for
the REST API.

This means IAM required by the Hosting REST API calls must be granted
to the **service account**, not (only) to the principalSet. The 403
in attempt #10 of the convergence trail was exactly this: the
principalSet had `serviceUsageConsumer`, but the impersonated SA did
not. The Hosting REST API call was authenticating as the SA and
denying based on the SA's IAM.

**The deeper lesson:** *when you impersonate, the identity changes,
and IAM must follow the new identity.* It's an obvious lesson stated
plainly, but it's easy to miss in a codebase where most IAM lives on
one identity (the principalSet) and only one path uses a different
one (the impersonated SA). The mental model has to track which
identity is the caller for each operation.

A practical consequence: when adding new operations that require
impersonation, ask "what IAM does the *impersonated identity* need?"
not "what IAM does the principalSet need?" The principalSet only needs
`tokenCreator` to perform the impersonation; everything else follows
the impersonated identity.

### Lesson 4: When the official tooling doesn't fit, build the integration

The official Firebase Hosting deploy paths (the `firebase` CLI, the
`action-hosting-deploy` GitHub Action) both assumed either an
interactive login or a JSON service-account key. Neither was
compatible with the keyless WIF posture. Three approaches were
considered for resolving this:

- **Accept a JSON key.** Lower keyless purity but uses official
  tooling. Rejected: violated Phase 6's core goal of zero exported
  keys, and reintroduced a credential to manage.
- **Wait for `firebase-tools` to support WIF.** Indefinite timeline;
  external dependency. Rejected.
- **Build a custom REST-API-based deploy.** Higher up-front
  engineering cost; full control over the deploy semantics. Chosen.

The custom deploy script (`scripts/deploy_hosting_rest.sh`) is
~150 lines, shellcheck-clean, and has handled every deploy since.
The deeper benefit: the script's existence proves the pattern
(mint an SA access token, call a Google REST API directly) is
viable for *any* Google API whose CLI/SDK resists WIF ADC. It's a
reusable architectural pattern, not a Firebase-specific workaround.

**The deeper lesson:** *when official tooling and architectural
posture conflict, the cost of building a small custom integration is
often lower than the cost of compromising the posture.* The custom
script is ~150 lines; the JSON-key approach would have introduced an
indefinite credential-management responsibility. The right cost
comparison includes the lifetime cost of the compromised path, not
just the up-front engineering cost.

### Lesson 5: Loud failures, structured errors

A recurring pattern in Phase 6's diagnostic work: each failure
produced enough information to name the next fix, but only because
the calls were instrumented to surface full error bodies. The default
`curl` behavior (silent on errors, exit code 0 unless the network
itself fails) actively hid the information needed for diagnosis.

`scripts/deploy_hosting_rest.sh` has an `api()` helper that:
- Captures the full response body on any HTTP status ≥400
- Prints the status code, the operation, and the body before exiting
- Never `2>/dev/null`s the error stream

Without this, the convergence trail in the previous section would have
been: "it didn't work, then it didn't work differently, then it
worked." With it, each step was: "got back exactly this error, which
maps to this missing permission, which is granted by this Terraform
change, which produced this next error." The diagnostic value is in
the structure.

**The deeper lesson:** *invest in the diagnostic surface area early.*
The cost of loud, structured error reporting is small; the cost of
quiet failures is paid every time something breaks. For CI/CD
specifically — where iterations are expensive (each retry consumes a
push, runs the workflow, and waits on cloud builds) — the diagnostic
investment pays back in cycles saved.

---

## Phase 6 by sub-phase

Phase 6 shipped across many small sub-phases. The relevant ones for
the retrospective:

| Sub-phase | Scope |
|-----------|-------|
| 6.0 | ADR-0018 (CI/CD security model); planning |
| 6.1.x | WIF pool/provider creation; direct-WIF IAM on principalSet; branch protection on `main` |
| 6.2.x | Quality gates workflow (backend + frontend); Cloud Build + Artifact Registry + Cloud Run deploy; the long sub-phase that did the Firebase Hosting REST API work |
| 6.3.x | Pipeline validation (PR #1 — gates green, deploy green, both surfaces live); removal of diagnostic noise from production scripts |

Many of 6.2's sub-phases corresponded one-to-one with the convergence
trail above: each attempt to deploy Hosting was its own sub-phase,
with a Terraform change, a workflow update, and a deploy validation.
The PR titles and commit messages from that period read as a forensic
record of the discovery process. Future-readers of the git history
can reconstruct exactly what was tried, what failed, and why each
fix was the right one.

---

## Metrics

| Metric | Value |
|--------|-------|
| Sub-phases shipped | ~15 (6.1.x + 6.2.x + 6.3.x) |
| Validation PR | #1 (Phase 6.3.3) |
| Terraform-managed IAM bindings (Phase 6 additions) | ~12 |
| Direct-to-main pushes possible after Phase 6 | 0 (branch-protected) |
| JSON service-account keys in repo or secrets | 0 |
| Authentication paths in CI | 2 (direct WIF + SA impersonation) |
| Workflow files | 2 (`pr-gates.yml`, `deploy.yml`) |
| Custom-built deploy scripts | 1 (`scripts/deploy_hosting_rest.sh`, ~150 lines) |
| Hosting deploy attempts before success | 10 |
| Days from "first attempt at keyless Hosting" to "pipeline green" | ~10 (with intermittent work) |

---

## What's deferred

Phase 6 left a small number of items intentionally deferred to later
phases. None blocked the pipeline's correctness or security posture.

- **Bucket-scoped `storage.admin` for the Cloud Build staging
  bucket.** The principalSet currently holds project-level
  `roles/storage.admin`, which is broader than necessary. Tightening
  to a bucket-scoped IAM binding is on the Phase 8 hardening list.
- **Node 20 → Node 24 action deprecation.** GitHub deprecated Node 20
  in `auth@v3` and related actions; the deprecation warning surfaces
  on each run. Non-blocking; cosmetic. Update during routine
  maintenance.
- **Cosmetic AuthContext fast-refresh lint warning.** A frontend lint
  warning that the React Fast Refresh plugin can't optimize a
  particular context export. Non-blocking; cosmetic.
- **Diagnostic `--debug` flags in `deploy_hosting_rest.sh`.** Added
  during the convergence-trail work to surface the request/response
  details. Could be removed now that the path is green, but the loud
  error surfacing should stay.

---

## Honest reflections

Some things from Phase 6 that are worth being explicit about, in the
spirit of honest retrospective writing.

**The keyless Hosting work took longer than it should have on paper —
but produced something durable.** Ten attempts before success is a
lot of iterations. Each one cost a workflow run, a Terraform plan,
sometimes a deploy retry. In strict timeline terms, this looks
inefficient. But the result is a documented, reproducible, exactly
right pattern that has handled every deploy since. The alternative —
"just use a JSON key and move on" — would have closed the phase
faster but reintroduced exactly the credential-management problem
Phase 6 existed to eliminate.

**The convergence-trail pattern (401 → 400 → 403 → success) is not a
coincidence.** It happened because the diagnostic instrumentation was
in place to surface each error precisely. With silent failures or
generic "deploy failed" messages, the same work would have looked
like ten random attempts. With structured errors, it became a
deterministic walk to the correct configuration. The investment in
loud, structured error reporting *upstream* (in `deploy_hosting_rest.sh`'s
`api()` helper) paid back in days of saved diagnostic time.

**Some of Phase 6's choices were path-dependent.** If the project had
started with Firebase Hosting via a JSON key (the conventional
approach), Phase 6 might never have explored the REST API path.
The keyless posture from the start *forced* the discovery. That
discovery was high-cost up front but yielded a generalizable pattern
(REST + SA-impersonated access token) that applies to any Google API
beyond Firebase Hosting. The constraint produced the architectural
insight.

**The pattern of "official tooling didn't fit" was instructive.** It
happened twice in Phase 6 (the `firebase` CLI couldn't use WIF ADC;
the official Hosting action required a JSON key) and once more in
Phase 9 (LLM tooling couldn't reliably do temporal reasoning). The
shape is similar: when off-the-shelf tooling conflicts with an
architectural posture, the cost of building a small custom
integration is usually lower than the cost of compromising the
posture. Phase 6's custom REST deploy script and Phase 9's
deterministic Python guards (ADR-0026) are the same pattern at
different layers.

**A few things would have been done differently with hindsight.**
The `terraform/wif_iam.tf` file accumulated quickly during the
convergence-trail work; in hindsight, capturing each role grant's
*justification* in an adjacent comment (linking to the specific 403
or PR that motivated it) would have made the file more self-
documenting. A future reader looking at the file sees the roles but
has to reconstruct the rationale from git history. Not a blocker, but
a documentation polish that could have been done in-line.

---

## References

### Pull requests

- #1: Phase 6.3.3 — pipeline validation (the end-to-end validation
  PR that closed Phase 6)
- Phase 6 PRs predate the merged-PR numbering shown above; the
  in-repo Phase 6 work was a sequence of branch-and-merge cycles
  before PR-based discipline was enforced. The CHANGELOG entries
  under "Phase 6.x" are the canonical record.

### Phase 6 ADRs

- **ADR-0018** — CI/CD Security Model

### Related documents

- `docs/runbooks/keyless-firebase-hosting-wif.md` — operational
  runbook authored during Phase 6 closure; the canonical reference
  for reproducing this setup in test/prod environments
- Engineering report PDF distributed alongside Phase 6 closure
- `terraform/wif_iam.tf` — the IAM inventory in code; reads as
  exactly what CI needs
- `scripts/deploy_hosting_rest.sh` — the custom Hosting deploy
  script; ~150 lines, the operational artifact of the convergence
  trail
- `.github/workflows/deploy.yml` — the deploy pipeline
- `.github/workflows/pr-gates.yml` — the PR Gates pipeline

### Connection to later phases

The Phase 6 pipeline carried every subsequent phase's deploys
without modification:
- Phase 7 (notifications + auth): used the pipeline as-is
- Phase 9 (AI agent): used the pipeline as-is; 19 PRs landed
  through it

The pipeline's stability across 25+ subsequent PRs is the strongest
validation: Phase 6 built infrastructure that didn't need to be
revisited.

---

## Document history

- **2026-06-28:** Drafted as part of Phase 9 administrative closure
  (catch-up retrospective for a previously-undocumented phase).
  Source material consolidated from the Phase 6 engineering report
  (PDF) and the operational runbook
  (`docs/runbooks/keyless-firebase-hosting-wif.md`).
  Author: Chandra Nakkalakunta with AI assistance (Claude Opus 4.7).
