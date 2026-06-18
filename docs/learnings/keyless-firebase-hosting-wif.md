# Keyless Firebase Hosting Deploys via Workload Identity Federation

**Status:** Resolved (Phase 6.2 / 6.1.x) · **Project:** sport-slot-dev · **Region:** asia-south1
**Repo:** chandranakkalakunta/sport-slot-reservation

This document is a permanent reference for how SportSlotReservation deploys its
frontend to Firebase Hosting from GitHub Actions **without any service-account
JSON key** — and the full reasoning trail that got us there. It exists so that
nobody (including future-us, and the test/prod environments) has to rediscover
this. Read the "Final architecture" and "Runbook" sections to *use* it; read the
"Decision trail" to understand *why* it is shaped this way.

---

## 1. The problem in one paragraph

The CI/CD pipeline authenticates to Google Cloud using **direct Workload Identity
Federation (WIF)**: GitHub's OIDC token is exchanged for GCP access, and the
repository's `principalSet` holds IAM roles directly — there is no intermediate
service account and no exported key. This works cleanly for `gcloud`-based steps
(Cloud Build, Artifact Registry, Cloud Run). It does **not** work for
`firebase deploy`, because the Firebase CLI (`firebase-tools`) cannot consume a
WIF *external_account* credential. Getting Hosting to deploy keylessly required
abandoning `firebase-tools` for the deploy and driving the **Firebase Hosting
REST API** with a **service-account-impersonated OAuth2 access token**.

---

## 2. Key facts to internalize

- **Direct WIF (no SA)** gives `gcloud` a *federated* credential. It works for
  gcloud commands, but `gcloud auth print-access-token` on it returns a token
  (~1484 chars) that Google REST APIs reject as "not an OAuth 2 access token."
- **A REST-usable OAuth2 access token can only be minted by impersonating a
  service account.** `google-github-actions/auth` does this when given
  `service_account:` + `token_format: 'access_token'`. The resulting token is
  ~1024 chars and is accepted by REST APIs.
- **`firebase-tools` (v15.x) cannot use WIF external_account ADC for deploys.**
  Its internal token manager only understands interactive-login user tokens or
  the deprecated `login:ci` refresh token. With ADC it logs *"No OAuth tokens
  found"* and crashes on `undefined.access_token`. Proven via `--debug`.
- **The official `FirebaseExtended/action-hosting-deploy` requires a JSON key**
  (`firebaseServiceAccount` is a required input). It is incompatible with
  keyless WIF. Do not use it for this setup.
- **Impersonation shifts the effective caller identity.** Once we mint a token
  by impersonating `sa-firebase-admin`, the *SA* — not the principalSet — is the
  caller for the REST API. IAM roles required by those calls must be granted to
  the **service account**, not (only) to the principalSet.
- **`gcloud auth application-default print-access-token` does NOT work mid-job.**
  It tries to re-exchange the GitHub OIDC subject token, which was already
  consumed by `auth@v3` at job start → "Unable to retrieve Identity Pool subject
  token / connection refused."
- **firebase.json config syntax ≠ Hosting REST API schema.**
  CLI uses `{source, destination}`; REST uses `{glob, path}` (and
  `{glob, location, statusCode}` for redirects, `{glob, headers}` for headers).
  These must be translated when building the REST `version.config` body.

---

## 3. Final architecture

### Authentication
| Surface | Identity path | Token |
|---|---|---|
| Cloud Build / Artifact Registry / Cloud Run | Direct WIF → principalSet IAM | gcloud federated credential (used by gcloud directly) |
| Firebase Hosting (REST) | WIF → impersonate `sa-firebase-admin` → minted access_token | OAuth2 access token (~1024 chars), passed to the deploy script via env |

### IAM (all Terraform-managed in `terraform/wif_iam.tf`)
Granted to the **WIF principalSet** (direct-WIF, for gcloud steps):
- `roles/run.admin`, `roles/artifactregistry.writer`, `roles/cloudbuild.builds.editor`
- `roles/serviceusage.serviceUsageConsumer`, `roles/storage.admin` *(broad; tighten in Phase 9)*
- `roles/redis.viewer`
- `roles/iam.serviceAccountUser` on `sa-cloud-run` and `sa-cloud-build`
- `roles/iam.serviceAccountTokenCreator` on `sa-firebase-admin` *(lets WIF mint the Hosting token)*

Granted to **`sa-firebase-admin`** (the impersonated caller for the Hosting REST API):
- `roles/serviceusage.serviceUsageConsumer`
- `roles/firebasehosting.admin` *(pre-existing from earlier phase — the reason Hosting calls themselves were authorized once auth worked)*

### Deploy flow (GitHub Actions `deploy.yml`, `push` to `main`)
1. **gates** — backend (ruff/bandit/pytest ≥90%) + frontend (lint/test/build).
2. **deploy** job:
   - `google-github-actions/auth@v3` (direct WIF) → for build/run.
   - `make build-push` (Cloud Build → Artifact Registry).
   - `make deploy-dev` (Cloud Run, runs as `sa-cloud-run`).
   - **Mint Firebase token** step: a *second* `auth@v3` with
     `service_account: sa-firebase-admin`, `token_format: access_token`,
     `access_token_scopes: cloud-platform` → outputs `access_token`.
   - **Deploy Hosting** step: builds frontend, then runs
     `scripts/deploy_hosting_rest.sh` with `FIREBASE_ACCESS_TOKEN` set to the
     minted token and `FIREBASE_PROJECT=sport-slot-dev`.

### `scripts/deploy_hosting_rest.sh` (keyless REST deployer)
- Token: uses `$FIREBASE_ACCESS_TOKEN` if present (CI), else falls back to
  `gcloud auth print-access-token` (local interactive use).
- Sends `Authorization: Bearer <token>` **and** `X-Goog-User-Project: <project>`
  on every call.
- Translates `firebase.json` hosting config (`source/destination`) → REST schema
  (`glob/path`) before the version-create call.
- Sequence: create version → `populateFiles` (path→sha256-of-gzip map) → upload
  required gzipped files by hash → finalize → release to `live`.
- Surfaces full API error bodies on any `>=400` (loud failures, no silent
  `2>/dev/null`).

---

## 4. Decision trail (what we tried, and why each failed)

| # | Attempt | Result / why rejected |
|---|---|---|
| 1 | firebase-tools `--project --non-interactive` | Vague "unexpected error" — not a TTY issue |
| 2 | firebase-tools `FIREBASE_TOKEN`=access token | 401; CLI mis-uses access token as refresh token; deprecated |
| 3 | Official `action-hosting-deploy` | Requires `firebaseServiceAccount` JSON key — incompatible with keyless |
| 4 | firebase-tools pure ADC + `GOOGLE_CLOUD_PROJECT` + `--debug` | **Diagnostic win:** "No OAuth tokens found" → crash. Proves firebase-tools can't use WIF ADC |
| 5 | REST API + `gcloud auth print-access-token` | 401 — federated token not a valid OAuth2 access token |
| 6 | REST API + `application-default print-access-token` | Worse — re-exchanges OIDC mid-job, connection refused |
| 7 | REST + plain token + `X-Goog-User-Project` + loud errors | Still 401, but full error body confirmed token rejection |
| 8 | REST + **SA-impersonated** access token (auth@v3 `token_format`) | 401 → **400** — auth solved; now a request-body issue |
| 9 | Translate firebase.json `source/destination` → REST `glob/path` | 400 → **403** — config fixed; now a permission on the SA |
| 10 | Grant `serviceUsageConsumer` to **`sa-firebase-admin`** | **Success** — full pipeline green |

The progression 401 → 400 → 403 → success is the signature of correctly
diagnosed, least-privilege convergence: each error named exactly the next fix.

---

## 5. Runbook — reproduce for a new environment (e.g. test / prod)

1. **WIF pool/provider + principalSet bindings**: `terraform apply` with the new
   environment's tfvars (`project_id`, `project_number`, `github_repository`).
   The provider attribute condition already restricts to repo + `main`.
2. **Token-creator binding**: ensure
   `principalSet → roles/iam.serviceAccountTokenCreator` on the env's Firebase
   admin SA exists (in `wif_iam.tf`).
3. **SA roles for the Hosting caller**: the Firebase admin SA needs
   `roles/serviceusage.serviceUsageConsumer` **and** `roles/firebasehosting.admin`.
4. **Workflow**: `deploy.yml` already has the two-auth-step pattern (direct WIF
   for build/run; SA-impersonation mint for Hosting). Update project IDs/SA email
   per environment.
5. **Apply, then trigger**: `make tf-plan` → verify expected `+N, 0 destroy`
   (never an import or recreate of the pool/provider) → `make tf-apply-dev` →
   push or `gh run rerun`.

### Quick diagnostics
- **401 UNAUTHENTICATED on a REST call** → token isn't a real OAuth2 access token.
  Confirm the Hosting step uses the **SA-impersonated** `FIREBASE_ACCESS_TOKEN`
  (token length ~1024, not ~1484). 1484 = fallback/federated token = wrong.
- **400 INVALID_ARGUMENT, "Unknown name 'source'"** → config not translated to
  REST schema (`glob/path`).
- **403 USER_PROJECT_DENIED, serviceUsageConsumer** → the *impersonated SA*
  lacks `serviceusage.serviceUsageConsumer`. Grant it to the SA (not just the
  principalSet).
- **403 on `firebasehosting.sites.update`** → grant `firebasehosting.admin` to
  the SA.
- **"Unable to retrieve Identity Pool subject token"** → something tried
  `application-default print-access-token` (re-exchanges OIDC). Use plain
  `print-access-token` locally, or the minted `FIREBASE_ACCESS_TOKEN` in CI.

### Verifying an SA's roles
```
gcloud projects get-iam-policy sport-slot-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-firebase-admin@sport-slot-dev.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

---

## 6. Operational notes & follow-ups

- **`--debug` in `deploy_hosting_rest.sh`** (added during diagnosis) can be
  removed now that the path is green; keep the loud `api()` error-surfacing.
- **Makefile target name** is `make tf-plan` (there is no `tf-plan-dev`).
- **WIF pool/provider are already imported and Terraform-managed** — never
  re-import them; plans should show `0 to destroy` and no pool/provider changes.
- **Phase 9 hardening**: tighten project-level `roles/storage.admin` on the
  principalSet to a bucket-scoped grant on the Cloud Build staging bucket.
- This pattern (mint an SA access token via `auth@v3`, call a Google REST API
  directly) generalizes to any Google API whose CLI/SDK resists WIF ADC.
