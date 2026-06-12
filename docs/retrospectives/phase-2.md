# Phase 2 Retrospective — Backend API Foundation

**Phase:** 2.0 – 2.7  
**Completed:** 2026-06-12  
**Author:** Chandra Nakkalakunta

## What Was Built

| Sub-phase | Deliverable |
|-----------|-------------|
| 2.1 | ADR-0006 (API design) + ADR-0007 (auth & authorization) |
| 2.2 | Security charter v1.1 committed to `docs/security/charter.md` |
| 2.3 | FastAPI scaffold: app factory, request-ID middleware, error envelope, structlog, TenantContext auth dependency |
| 2.4 | Repository pattern (TenantRepository/PlatformRepository), deny-all Firestore rules formalized, ADR-0008 |
| 2.5 | `GET /api/v1/users/me`, slowapi rate limiting (30/min), dev seed tooling |
| 2.6 | Multi-stage Dockerfile, Cloud Build + Artifact Registry, Cloud Run deploy scripts |
| 2.7 | Documentation closure: README, retrospective, runbook, charter v1.2 |

**Final metrics:** 31 tests · 89.25% coverage · 0 Bandit findings · ShellCheck clean

---

## What Went Well

### Architecture held up under implementation pressure

The ADR-first approach (ADR-0006/0007 written before a single line of code) kept
decisions visible and reversible. When the Firestore layout pre-flight found an
existing `infrastructure/firestore.rules` from Phase 1.3.3, having ADR-0008 as the
source of truth made the resolution unambiguous: keep the file, update the content,
don't restructure.

### 5-layer tenant isolation is real, not just documented

Each layer forced a concrete engineering choice:
- Rules → permanent deny-all (no client path at all)
- Repository → TenantRepository rejects non-tenant contexts at construction time
- Auth dependency → `_slug_from_host` fail-closed in production
- Tests → cross-tenant 403 assertions in the pytest suite
- CI gate → `test_architecture.py` prevents Firestore imports leaking into handlers

### Error envelope is consistent end-to-end

Every response — success, 4xx, 5xx, rate limit — uses the same
`{code, message, request_id, timestamp}` envelope. This required solving the
slowapi middleware bypass problem (see Issues section), but the result is a
client that never has to handle two different error shapes.

### Zero-credential discipline maintained

No JSON keys were generated at any point. All local dev uses ADC, CI/CD uses WIF,
Cloud Run uses the attached service account. The org policy
(`iam.disableServiceAccountKeyCreation`) was confirmed enforced throughout.

---

## Issues Encountered and Resolved

### 1 — slowapi 429 not in error envelope (two rounds)

**Round 1 diagnosis (wrong):** `raise ApiError(429, ...)` inside a
`@app.exception_handler(RateLimitExceeded)` handler. FastAPI exception handlers
don't chain — raising inside a handler doesn't dispatch to another handler.
Switched to `return JSONResponse(...)`.

**Round 2 diagnosis (root cause):** `SlowAPIMiddleware.dispatch()` catches
`RateLimitExceeded` internally and calls `slowapi.errors._rate_limit_exceeded_handler`
before FastAPI's exception-handler pipeline is ever entered. The `@app.exception_handler`
decorator is dead code for this exception.

**Resolution:** `EnvelopeRateLimitMiddleware(SlowAPIMiddleware)` — post-processes any
429 response from the middleware layer into the envelope. No handler registration needed.
Dead handler removed from `errors.py`.

### 2 — Health probes not exempt from rate limit

`SlowAPIMiddleware.default_limits` applied to ALL routes including `/healthz`.
Added `@limiter.exempt` decorators under the route decorators in `health.py`.
Changed from a `build_limiter()` factory to a module-level `limiter` singleton
with a `_current_limit()` callable so tests can monkeypatch the limit per-request.

### 3 — uv editable-install .pth not on sys.path

`_editable_impl_sport_slot_backend.pth` exists in site-packages but `backend/src`
is not added to `sys.path` by the uv Python symlink on macOS. Fixed:
`pythonpath = ["src"]` in `[tool.pytest.ini_options]`. For uvicorn: `PYTHONPATH=src`
(set in Makefile `run-dev` target).

### 4 — Cloud Build 403 on staging bucket

Build submitted without `--service-account`, so it ran as the default Compute SA
which lacked `storage.objectAdmin` on the staging bucket. Fixed: explicit
`--service-account` flag in `build_push.sh` + `roles/storage.objectAdmin` grant
scripted in `setup_build_infra.sh`.

### 5 — `--logging=CLOUD_LOGGING_ONLY` not a valid gcloud flag

`gcloud builds submit` in SDK version 571 does not have a `--logging` flag.
Fixed: moved to `options.logging: CLOUD_LOGGING_ONLY` in `backend/cloudbuild.yaml`.

### 6 — Cloud Run external serving hold (open)

Service deployed successfully (Ready=True, IAM, ingress=all, org-policy override
all verified correct), but external requests receive 404. This is an account-level
serving hold on new Google organization domains. Support case filed.
Service `sport-slot-api-b` kept as live repro. Worker has no action here.

### 7 — Firestore pre-flight: existing file from Phase 1.3.3

`infrastructure/firestore.rules` already existed in the flat layout established by
Phase 1.3.3 (`firebase.json` references it directly). Phase 2.4 prompt assumed
this was absent. Resolution: keep the existing layout, replace only the file content,
update the path reference in ADR-0008 and the deploy script. No `infrastructure/firestore/`
subdirectory created.

---

## Key Decisions

### python-jose prohibited permanently

CVE-2024-33663 and CVE-2024-33664 affect python-jose. Decision: Firebase Admin SDK
is the only JWT verifier in this codebase. Documented in ADR-0007 and enforced by
`test_architecture.py` import scan. Any future contributor adding python-jose to
`pyproject.toml` will break the architecture gate.

### Fail-closed dev override

`_slug_from_host` allows tenant slug override only when `environment == "development"`
AND the host is in `{"localhost", "127.0.0.1", "testserver"}`. In production,
any host not matching the `base_domain` pattern returns 400. There is no runtime
flag that relaxes this — the environment field is set at deploy time via env vars.

### Callable rate limit for test overrides

`Limiter(default_limits=[_current_limit])` passes a callable, not a string.
slowapi calls it per request. Tests monkeypatch `get_settings()` return value;
the callable picks up the override without requiring limiter reconstruction.

---

## Lessons Learned

1. **Read middleware source before registering exception handlers.** Middleware
   that catches exceptions internally is invisible to `@app.exception_handler`.
   Check the library's `dispatch()` before assuming handler registration will work.

2. **uv editable installs on macOS need an explicit `pythonpath` setting.**
   Don't assume `.pth` files work — verify `sys.path` in the test environment.

3. **Pre-flight the filesystem before each phase.** Phase 1 artifacts survived into
   Phase 2 (`firestore.rules`, `local-development.md`). A 30-second pre-flight
   that confirms expected state prevents 30-minute backtrack sessions.

4. **Three-agent protocol forces complete designs.** Having the Strategist produce
   all file contents before the Worker writes a single byte prevents the "I'll figure
   out the details as I go" pattern that causes mid-task architectural drift.

5. **Cloud Build config belongs in a file, not CLI flags.** `cloudbuild.yaml` is
   version-controlled and deterministic. CLI flags depend on the SDK version installed
   on the machine that runs the script.

---

## Phase 3 Preview

- Redis distributed lock for double-booking prevention (ADR-0002)
- Per-user/household booking quotas (anti-hoarding)
- Booking cancellation rate limiting
- Audit logging for all booking mutations to BigQuery
- `POST /api/v1/bookings`, `DELETE /api/v1/bookings/{id}`
- `GET /api/v1/slots` with availability projection
