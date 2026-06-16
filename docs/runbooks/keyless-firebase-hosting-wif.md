# Runbook: Keyless Firebase Hosting Deploy via WIF + REST API

## Context

This runbook documents the keyless CI path for deploying Firebase Hosting in
an environment where static service-account JSON keys are forbidden (org policy
`iam.disableServiceAccountKeyCreation`). It covers the design decision, the
required IAM setup, the deploy script, and the known failure modes with their
root causes and fixes — derived from the Phase 6 CI/CD build.

**See also:** `docs/adr/0018-cicd-security-model.md`

---

## Why not firebase-tools?

firebase-tools 15.x cannot consume a WIF `external_account` ADC credential for
deploys. Its internal token manager only recognises:
- `firebase login` — interactive user OAuth2 token
- `firebase login:ci` — deprecated refresh token

When `GOOGLE_APPLICATION_CREDENTIALS` points to a WIF `external_account` file,
firebase-tools logs "No OAuth tokens found" and crashes on
`undefined.access_token`. This is a hard tool limitation, not a configuration
error. `--debug` is required to see it; without it the symptom is "unexpected
error."

**Consequence:** use the Firebase Hosting REST API directly for CI. firebase-tools
remains correct for local interactive use where `firebase login` works.

---

## Why not a direct-WIF token for the REST API?

`gcloud auth print-access-token` when the active credential is a WIF
`external_account` returns a *federated identity token* (~1484 chars), not a
standard OAuth2 access token. The Firebase Hosting REST API rejects federated
tokens with **401 UNAUTHENTICATED**.

A real OAuth2 access token (~1024 chars) requires SA impersonation.

---

## Architecture

```
GitHub Actions OIDC token
        │
        ▼
  WIF pool/provider (github-actions-pool)
  attribute_condition: repo == this repo AND ref == refs/heads/main
        │
        ├──► direct WIF credential ──► gcloud build/push/run (Cloud Run deploy)
        │
        └──► SA impersonation ──► sa-firebase-admin OAuth2 token
                                         │
                                         ▼
                              Firebase Hosting REST API
                              (firebasehosting.googleapis.com/v1beta1)
```

Both paths are keyless. The SA impersonation path is an exception for the
Hosting REST API only — the main auth step for gcloud remains direct-WIF.

---

## Required IAM (Terraform: `terraform/wif_iam.tf`)

### On the WIF principalSet

| Resource name | Role | Why |
|--------------|------|-----|
| `ci_token_creator_firebase` | `roles/iam.serviceAccountTokenCreator` on `sa-firebase-admin` | Allows CI to impersonate the SA to mint an OAuth2 token |

### On `sa-firebase-admin` (the impersonated SA, project-level)

| Resource name | Role | Why |
|--------------|------|-----|
| `firebase_admin_service_usage_consumer` | `roles/serviceusage.serviceUsageConsumer` | `X-Goog-User-Project` causes the Hosting REST API to check `serviceusage.services.use` against the *impersonated SA*'s own IAM — not the WIF principalSet |

`sa-firebase-admin` must also hold `roles/firebase.admin` or
`roles/firebasehosting.admin` (typically granted at project creation). Verify:

```bash
gcloud projects get-iam-policy sport-slot-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:sa-firebase-admin@sport-slot-dev.iam.gserviceaccount.com" \
  --format="table(bindings.role)"
```

---

## GitHub Actions workflow steps (`.github/workflows/deploy.yml`)

```yaml
# Step 1: Main WIF auth — used by gcloud (build, push, Cloud Run)
- name: Authenticate to Google Cloud (WIF, keyless)
  uses: google-github-actions/auth@v3
  with:
    workload_identity_provider: ${{ env.WIF_PROVIDER }}

# Step 2: Mint a real OAuth2 token via SA impersonation
- name: Mint Firebase access token (SA impersonation)
  id: fb_auth
  uses: google-github-actions/auth@v3
  with:
    workload_identity_provider: ${{ env.WIF_PROVIDER }}
    service_account: sa-firebase-admin@sport-slot-dev.iam.gserviceaccount.com
    token_format: access_token
    access_token_scopes: https://www.googleapis.com/auth/cloud-platform

# Step 3: Build frontend and deploy via REST script
- name: Deploy Firebase Hosting (REST API, SA-impersonated token)
  env:
    FIREBASE_ACCESS_TOKEN: ${{ steps.fb_auth.outputs.access_token }}
    FIREBASE_PROJECT: sport-slot-dev
  run: |
    (cd frontend && pnpm build)
    ./scripts/deploy_hosting_rest.sh
```

Do NOT use `application-default` variant of `gcloud auth` mid-job — it
re-exchanges the already-consumed OIDC subject token and fails "Connection
refused."

---

## deploy_hosting_rest.sh: REST API sequence

The script drives the Firebase Hosting REST API in five steps:

1. **Build file manifest** — for each file in `frontend/dist`, gzip + SHA-256.
2. **Translate config** — `firebase.json` uses CLI schema (`source`/`destination`);
   REST API `Version.config` requires `glob`/`path`. The `translate()` python
   function converts:
   - `source` → `glob`
   - `destination` → `path`
   - `run` → `run` (passthrough)
   - redirects: `destination` → `location`, `type` → `statusCode`
   - headers: `source` → `glob`
3. **Create version** — `POST /v1beta1/sites/{site}/versions` with the translated
   config JSON. Returns a version name.
4. **Populate files** — `POST /v1beta1/{version}:populateFiles` with the manifest.
   Response lists which file hashes need uploading (already-uploaded files are
   skipped).
5. **Upload required files** — `POST` each required gzip to the upload endpoint.
6. **Finalize** — `PATCH /v1beta1/{version}?update_mask=status` with
   `{"status":"FINALIZED"}`.
7. **Release** — `POST /v1beta1/sites/{site}/releases?versionName={version}`.

Token source (in order of precedence):
- CI: `$FIREBASE_ACCESS_TOKEN` (SA-impersonated OAuth2, ~1024 chars)
- Local: `gcloud auth print-access-token` (requires `firebase login` or
  `gcloud auth login` with firebase permissions)

The `X-Goog-User-Project: {PROJECT}` header is sent on every call — required for
quota/billing attribution. This is what triggers the `serviceUsageConsumer` check
on the SA.

---

## Known failure modes

### 401 UNAUTHENTICATED

**Cause A:** token is a WIF federated token (~1484 chars), not a real OAuth2
token. Happens when `gcloud auth print-access-token` is called with a WIF
external_account credential.
**Fix:** use SA impersonation (`token_format: access_token` in auth@v3).

**Cause B:** `FIREBASE_ACCESS_TOKEN` is empty or the auth@v3 step failed.
**Fix:** check the "Mint Firebase access token" step output; verify
`ci_token_creator_firebase` binding is applied in Terraform.

### 400 INVALID_ARGUMENT on version-create

**Cause:** `firebase.json` CLI schema fields (`source`, `destination`) sent
directly to the REST API which requires `glob`/`path`.
**Fix:** the `translate()` function in `deploy_hosting_rest.sh` handles this.
If the error reappears, verify `firebase.json` doesn't use an undocumented CLI
field that the translate function doesn't handle.

### 403 USER_PROJECT_DENIED

**Cause:** `X-Goog-User-Project` is set and `sa-firebase-admin` lacks
`roles/serviceusage.serviceUsageConsumer` on the project.
**Fix:** apply `google_project_iam_member.firebase_admin_service_usage_consumer`
from `terraform/wif_iam.tf`.

### 403 on Hosting API calls (version-create, populateFiles, release)

**Cause:** `sa-firebase-admin` lacks `roles/firebasehosting.admin` (or
`roles/firebase.admin` which includes it).
**Fix:** grant the role to the SA. This is typically pre-existing from project
setup; if it was removed, re-grant and document.

### "No such file or directory: frontend/dist"

**Cause:** `pnpm build` step didn't run or ran in the wrong working directory
before the REST script.
**Fix:** ensure `(cd frontend && pnpm build)` completes successfully before
calling the script. Check the build step output for TypeScript/Vite errors.

### `gha-creds-*.json` appearing in `git status`

**Cause:** `google-github-actions/auth@v3` writes a credential file to the
workspace root; it shows up as an untracked file and breaks clean-working-tree
checks.
**Fix:** `gha-creds-*.json` is in `.gitignore`. If this reappears, verify the
gitignore entry is present.

---

## Local deploy (non-CI)

```bash
# Requires firebase login (interactive)
make deploy-hosting
# or directly:
./scripts/deploy_hosting.sh
```

Local still uses firebase-tools (interactive `firebase login` works). The REST
script also works locally if `gcloud auth login` is active:

```bash
PUBLIC_DIR=frontend/dist FIREBASE_PROJECT=sport-slot-dev \
  ./scripts/deploy_hosting_rest.sh
```

---

## Terraform apply (Coordinator-run)

When adding or changing IAM bindings in `wif_iam.tf`:

```bash
make tf-plan-dev   # review the diff
make tf-apply-dev  # apply
```

Worker writes the `.tf` file; Coordinator applies. Never apply from CI — all
cloud mutations live in version-controlled scripts run by the Coordinator.

---

## Reference

- Firebase Hosting REST API: https://firebase.google.com/docs/hosting/api-deploy
- WIF + SA impersonation (google-github-actions/auth): token_format docs
- ADR-0018: `docs/adr/0018-cicd-security-model.md`
- Phase 6 retrospective: `docs/retrospectives/phase-6.md`
