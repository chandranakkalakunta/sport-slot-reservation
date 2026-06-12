# Local Development Runbook

Complete guide for running SportSlotReservation locally after Phase 2.

## Prerequisites

Run the toolchain verification:

```bash
bash scripts/verify_toolchain.sh
```

All 13 checks must pass before proceeding. Required tools: Python 3.12,
uv, Node 18+, Firebase CLI, gcloud, Terraform, ShellCheck, gh CLI.

---

## GCP Authentication (One-Time Setup)

```bash
# 1. Authenticate the gcloud CLI
gcloud auth login
# Follow browser prompts

# 2. Set up Application Default Credentials (used by Firebase Admin SDK)
gcloud auth application-default login

# 3. Set the quota project
gcloud auth application-default set-quota-project sport-slot-dev

# 4. Set default project for gcloud commands
gcloud config set project sport-slot-dev
```

**Verify:**

```bash
gcloud auth list                        # your email shown as ACTIVE
gcloud auth application-default print-access-token > /dev/null && echo "ADC OK"
gcloud config get-value project         # sport-slot-dev
```

No service-account JSON keys are used. The org policy
`iam.disableServiceAccountKeyCreation` blocks their creation.

---

## Backend Dev Server

### Install dependencies

```bash
cd backend
uv sync
```

### Run the server

```bash
# From repo root (Makefile handles PYTHONPATH)
make run-dev

# Equivalent manual command
cd backend
PYTHONPATH=src uv run uvicorn sport_slot.main:app --reload --port 8000
```

The server starts at `http://localhost:8000`.

**Why `PYTHONPATH=src`:** uv's editable-install `.pth` file is not honoured by
the uv Python symlink on macOS. `PYTHONPATH=src` is required for both uvicorn
and pytest.

### Health checks

```bash
curl http://localhost:8000/healthz        # {"status":"ok"}
curl http://localhost:8000/readyz         # {"status":"ready"} or 503 if Firestore unreachable
```

### Environment overrides

Create `backend/.env` (gitignored; `.env.example` is the template):

```bash
cp backend/.env.example backend/.env
```

All variables use the `SPORTSLOT_` prefix:

| Variable | Default | Notes |
|----------|---------|-------|
| `SPORTSLOT_ENVIRONMENT` | `development` | Set `production` to disable dev overrides |
| `SPORTSLOT_GCP_PROJECT` | `sport-slot-dev` | |
| `SPORTSLOT_BASE_DOMAIN` | `sportbook.chandraailabs.com` | |
| `SPORTSLOT_DEV_TENANT_SLUG` | *(unset)* | Override tenant slug for localhost |
| `SPORTSLOT_LOG_LEVEL` | `INFO` | `DEBUG` for verbose output |
| `SPORTSLOT_RATE_LIMIT` | `30/minute` | Lower to `2/minute` to test rate limiting |

---

## Running Tests

```bash
# From repo root
make test

# Equivalent manual command
cd backend
PYTHONPATH=src uv run pytest -v --cov=sport_slot --cov-report=term-missing
```

**Current baseline:** 31 tests · 89.25% coverage.

Coverage threshold is enforced in CI at `actual − 2%` buffer. Never aspirational.

### Architecture gate

`tests/test_architecture.py` statically scans the source tree. It fails if:
- Any handler file (outside `repositories/`, `health.py`, `dependencies.py`)
  imports `google.cloud` directly
- python-jose appears anywhere in the codebase

This gate runs as part of the normal pytest suite — no separate invocation needed.

### Running a single test

```bash
cd backend
PYTHONPATH=src uv run pytest tests/test_auth.py -v
```

---

## Seeding a Dev User

Requires a running server and valid Firebase project credentials.

```bash
# 1. Seed a Firestore user document for local testing
make seed-dev
# Prompts for tenant_slug and uid, writes to /tenants/{slug}/users/{uid}

# 2. Get a Firebase ID token for manual curl testing
bash scripts/get_dev_token.sh
# Prints a token to stdout; copy-paste for Authorization header
```

**Seed script is guarded:** it will not run against a non-development project.

---

## Docker Local Build

```bash
# Build image
make docker-build

# Run locally (mirrors Cloud Run behaviour)
make docker-run
# Starts on http://localhost:8080
```

The Docker image runs as a non-root `app` user (uid/gid defined at build time via
`groupadd -r app && useradd -r -g app app`). This matches the Cloud Run runtime.

---

## Tenant Routing in Dev

In production, tenant slug is derived from the request subdomain
(`{slug}.sportbook.chandraailabs.com`). In local development with `localhost`:

```bash
# In backend/.env
SPORTSLOT_DEV_TENANT_SLUG=greenpark
```

This override is active only when `SPORTSLOT_ENVIRONMENT=development` AND the
request host is in `{localhost, 127.0.0.1, testserver}`. It is **fail-closed**:
any other combination returns HTTP 400.

For per-request override in curl:

```bash
curl -H "Host: greenpark.sportbook.chandraailabs.com" http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer <token>"
```

---

## Coordinator-Only Scripts

These scripts perform cloud mutations and must be run by the Coordinator
(admin@chandraailabs.com with full GCP access):

| Script | Purpose |
|--------|---------|
| `scripts/setup_build_infra.sh` | One-time: creates AR repo + staging bucket, grants SA roles |
| `scripts/build_push.sh` | Build image via Cloud Build, push to Artifact Registry |
| `scripts/deploy_cloud_run.sh` | Deploy tagged image to Cloud Run |
| `scripts/deploy_firestore_rules.sh` | Deploy Firestore security rules |

These scripts are **guarded** — they require typing a confirmation phrase before
executing. They are idempotent and safe to re-run.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'sport_slot'`

`PYTHONPATH=src` is missing. Use `make run-dev` or `make test` which set it
automatically. Do not run `python` or `pytest` directly without it.

### `Default credentials not found`

```bash
gcloud auth application-default login
```

### `Quota project not set`

```bash
gcloud auth application-default set-quota-project sport-slot-dev
```

### `firebase.FirebaseError: Failed to initialize app`

Firebase Admin SDK couldn't find ADC. Run the GCP Authentication steps above.
If the server starts anyway, it logs `firebase_admin_not_initialized` — auth
endpoints will return 401 until credentials are present.

### `Permission denied` on Firestore

Your ADC identity needs `roles/datastore.user` on `sport-slot-dev`. Contact
admin@chandraailabs.com. The Firestore security rules are permanently deny-all
from the client side (ADR-0008 Decision 1) — all access goes through the backend
service account.

### Rate limit hitting unexpectedly during testing

Set `SPORTSLOT_RATE_LIMIT=1000/minute` in `backend/.env`. The `_current_limit()`
callable reads settings per-request, so the override takes effect immediately
without restarting the server.

### Token expired

ADC tokens auto-refresh. If issues persist:

```bash
gcloud auth application-default revoke
gcloud auth application-default login
```

---

## Related Runbooks

- [`gcp-project-setup.md`](gcp-project-setup.md) — how the GCP project was created
- [`iam-setup.md`](iam-setup.md) — service accounts, WIF, ADC pattern
- [`docs/retrospectives/phase-2.md`](../retrospectives/phase-2.md) — Phase 2 issues log
