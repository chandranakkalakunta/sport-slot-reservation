# Runbook: Local Development

## Daily loop
1. Fresh terminal (always after toolchain/config changes).
2. `make run-dev` → uvicorn on :8000 with reload.
3. Config changes (.env) require a server restart — settings are
   cached per process (lru_cache).

## First-time setup
`make install` → `make verify-env` → `make dev-env` → fill
SPORTSLOT_WEB_API_KEY in backend/.env (Firebase Console → Project
settings → General; public client identifier, still never commit) →
`make seed-dev` (prints demo user password ONCE — store it).

## Getting a token
`TOKEN=$(./scripts/get_dev_token.sh demo-resident@chandraailabs.com '<password>')`
Tokens expire after 1 hour (ADR-0007 §3). 401 AUTH_INVALID_TOKEN
on a previously working token = expiry; re-mint.

## Credentials model (charter: Identity & Credential Model)
- Human gcloud: admin@chandraailabs.com
- Application (local): impersonated ADC →
  `gcloud auth application-default login --impersonate-service-account=sa-firebase-admin@sport-slot-dev.iam.gserviceaccount.com`
- Never raw admin ADC; never JSON keys (org policy blocks them).

## Container testing
`make docker-build` → local arm64 image (Apple Silicon); testing
only — deployable images come ONLY from `make build-push`
(Cloud Build, amd64, git-SHA tag, clean tree required).
`make docker-run` mounts ~/.config/gcloud read-only.
KNOWN ISSUE: /readyz inside the local container may hang (ADC
mount/HOME path for the non-root user) — /health and the 401
envelope still validate; live Firestore checks are proven via
uvicorn and cloud Ready status.

## Gotchas (each one happened)
- Old terminals don't see new PATH/zshrc changes → fresh terminal.
- `.env` lives at backend/.env (anchored in code since 2.6) —
  never edit `.env.example` with real values; it's tracked.
- grep exit 1 = "no matches", which is the PASS for negative tests.
- Port in use → `lsof -ti :PORT` to find the stale server.
- Pager "(END)" isn't a hang — press q.
