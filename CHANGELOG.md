# Changelog

All notable changes to SportSlotReservation are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed (Add User field order)

- UX: reorder Add User form so Role precedes the (resident-only) Flat
  number field.

### Fixed (flat-number resident-only)

- Fix: flat_number is resident-only. API model made flat_number optional
  (was required str -> 422 when creating a tenant_admin without a flat —
  the tenant-creation 422). Frontend hides/omits the flat field unless
  role=resident. Service already enforced resident-only; now consistent
  across all three layers. Tracker: fixes the flat-field UX +
  tenant-creation 422.

### Fixed (Phase 7.x)

- Phase 7.x: forced-password gate re-prompting after a successful change.
  Root cause was NOT a query-key mismatch (`usePasswordGate.ts` and
  `ForcePasswordChange.tsx` both already used `["profile"]`) — invalidate/
  refetch defaulted to active observers; the standalone /force-password
  route has none, so the refresh was a no-op and ProtectedRoute read stale
  cached must_change_password=true on mount. Fixed by forcing type:'all'
  refetch + optimistic setQueryData before navigation. `usePasswordGate.ts`
  now exports `PASSWORD_GATE_QUERY_KEY` as the single shared key constant.
  Regression test seeds the cache with `must_change_password:true` and no
  active gate observer (mirroring the real standalone route), runs the
  change-password flow, then mounts a brand-new `ProtectedRoute` observer
  and asserts the value is correct on its very first render (no `waitFor`,
  which would mask a transient bounce back to /force-password) — confirmed
  to fail against the pre-fix code (plain `invalidateQueries`) and pass
  against the fix, per the Phase 5 false-positive lesson. Tracker: 7.x ✓.

### Added (Phase 7.1.3)

- Phase 7.1.3: wire booking-confirmed and user-welcome notification enqueues
  at their event sites; best-effort (never blocks the user action); hermetic
  tests incl. enqueue-failure isolation. `api/v1/bookings.py::create_booking`
  calls `enqueue_notification(event_type="booking_confirmed", ...)` after the
  booking is durably written (after `create_booking_with_quota` + the audit
  write, before `return doc`), resolving the booking user's email/display name
  via `UserProfileRepository(ctx, client).get(ctx.uid)` (the same pattern as
  `/users/me`) and the tenant's `display_name` via a direct tenant-doc fetch.
  `services/provisioning.py::UserProvisioningService.create_user` calls
  `enqueue_notification(event_type="user_welcome", ...)` after the existing
  create/profile/audit try-except block succeeds (deliberately outside that
  block, so an enqueue failure can never trigger the `fb_auth.delete_user`
  rollback path) — `login_url` is built from `Settings.base_domain` +
  `tenant_slug`; `temp_password` is included since it's already surfaced
  in-app via `CredentialDisplay`, the profile is created with
  `must_change_password=True` bounding its exposure window, and it's never
  logged anywhere in the enqueue/worker path. Both call sites wrap enqueue in
  a `try/except Exception` that logs a `structlog` warning and never
  re-raises — Cloud Tasks delivery failures are covered by the queue's own
  retry policy (7.1.2); this guard is only for enqueue-time failures, and the
  booking/provisioning write has already succeeded by the time it runs.
  Testability follows the codebase's existing convention for plain-function
  collaborators (matching `fb_auth.create_user`/`create_booking_with_quota`):
  `enqueue_notification` is imported directly and patched by module path in
  tests, rather than introducing a new dependency-injection wrapper. 5 new
  tests: booking-confirmed enqueue with correct `to`/params (params also fed
  through the real `render_booking_confirmed` to prove worker-side
  acceptance), booking succeeds when the enqueuer raises, enqueue skipped
  (not crashed) when no profile/email is resolvable, user-welcome enqueue
  with correct `to`/params (params fed through `render_user_welcome`), and
  provisioning succeeds when the enqueuer raises (rollback NOT triggered).
  ruff clean · bandit clean · 157 passed · coverage 92.94% (gate 90%). No
  infra/Terraform change — pure application wiring. Tracker: 7.1.3 ✓.

### Added (Phase 7.1.2)

- Phase 7.1.2: Cloud Tasks notification pipeline — queue + OIDC-authenticated
  worker endpoint + enqueue helper + invoker SA/IAM (Terraform) + resend-api-key
  secret wiring. No event triggers yet (7.1.3). `POST /internal/tasks/notify`
  (new `api/internal/` router, mounted outside `/api/v1`) verifies the Cloud
  Tasks OIDC bearer token via `google-auth`'s `id_token.verify_oauth2_token`
  (audience = worker URL, caller email pinned to `sa-tasks-invoker`); dispatches
  to the booking-confirmed/user-welcome templates and the configured
  `EmailProvider` (`ResendEmailProvider` in prod, `FakeEmailProvider` via
  `dependency_overrides` in tests); runs the sync `provider.send()` off the
  event loop via Starlette's `run_in_threadpool`. Returns 2xx on success, 503
  on `EmailSendError` (Cloud Tasks retries per the queue's `retry_config`), 422
  on unknown `event_type`/bad params (no retry), 401/403 on missing/invalid/
  wrong-SA OIDC. `notifications/tasks.py::enqueue_notification()` builds the
  Cloud Tasks HTTP task (OIDC token signed as `sa-tasks-invoker`,
  audience = worker URL); raises `TasksConfigError` loudly if queue/worker
  settings are missing rather than failing silently. Terraform
  (`terraform/cloud_tasks.tf`, Coordinator-applied): `google_cloud_tasks_queue`
  "notifications" (asia-south1, max_attempts=5, 5 dispatches/sec — Resend's
  100/day free-tier cap), new `sa-tasks-invoker` SA, `roles/run.invoker` on
  `sport-slot-api` (gcloud-deployed, not TF-managed, so bound by name/location)
  for that SA, queue-scoped `roles/cloudtasks.enqueuer` + SA-scoped
  `roles/iam.serviceAccountUser` (actAs) for `sa-cloud-run`, and
  `roles/secretmanager.secretAccessor` on the pre-existing `resend-api-key`
  secret for `sa-cloud-run`. `deploy_cloud_run.sh` now reads the service's
  existing URL before deploy (for `SPORTSLOT_WORKER_BASE_URL`) and adds
  `SPORTSLOT_TASKS_QUEUE`/`SPORTSLOT_TASKS_LOCATION`/`SPORTSLOT_TASKS_INVOKER_SA`
  env vars + `SPORTSLOT_RESEND_API_KEY=resend-api-key:latest` to `--set-secrets`.
  Narrowed `test_architecture.py`'s blanket `google.cloud` import check to
  `google.cloud.firestore` specifically (ADR-0008 Decision 3 is Firestore-only;
  the blanket match was a false positive against the new, legitimate
  `google.cloud.tasks_v2` import in `notifications/tasks.py`). 11 new tests,
  all hermetic (OIDC verification mocked, Cloud Tasks client mocked, no
  network, no real GCP). ruff clean · bandit clean · 152 passed · coverage
  92.44% (gate 90%). terraform fmt/validate clean (init-only; no plan/apply —
  Coordinator-run). Tracker: 7.1.2 ✓ (pending Coordinator `terraform apply` +
  redeploy before live).

### Added (Phase 7.1.1)

- Phase 7.1.1: EmailProvider abstraction + ResendEmailProvider + booking-
  confirmed/user-welcome templates + FakeEmailProvider + unit tests (per
  ADR-0019). `EmailProvider` is a structural Protocol (single `send()` method);
  `ResendEmailProvider` posts to the Resend HTTP API via httpx (promoted from
  dev-only to a runtime dependency), raises `EmailSendError` on non-2xx/network
  failure/missing key. Templates are pure functions returning subject+HTML+text,
  HTML-escaped via stdlib `html.escape`. `FakeEmailProvider` records sent
  messages for hermetic tests. 13 new tests, all hermetic (no network, no
  Firestore). ruff clean · bandit clean · coverage 92.05% (gate 90%).
  No Cloud Tasks / event wiring / worker endpoint yet — that's 7.1.2/7.1.3.
  Tracker: 7.1.1 ✓.

### Changed (Phase 6.3.1)

- Phase 6.3.1: remove temporary diagnostic noise from deploy_hosting_rest.sh
  (the token-length echo added during auth investigation 6.2.11–6.2.14). The
  permanent api() loud-error helper is retained. Pipeline confirmed green
  end-to-end (run 27562387259) before this cleanup. Tracker: 6.3.1 ✓.

### Added (Phase 6.1.3)

- Phase 6.1.3: grant serviceUsageConsumer to sa-firebase-admin (the impersonated
  caller for the Hosting REST deploy with X-Goog-User-Project). The principalSet
  already had this role from 6.1.1, but when auth@v3 mints a token via SA
  impersonation, the Firebase Hosting REST API enforces serviceusage.services.use
  against the impersonated SA — not the WIF principalSet. Root cause: X-Goog-User-
  Project triggers quota+billing checks on the SA's own IAM, not the WIF credential.
  Added google_project_iam_member.firebase_admin_service_usage_consumer in wif_iam.tf.
  terraform fmt OK · validate OK. Tracker: 6.1.3 ✓ (pending Coordinator apply).

### Fixed (Phase 6.2.15)

- Phase 6.2.15: translate firebase.json CLI syntax → Firebase Hosting REST API
  schema in deploy_hosting_rest.sh. firebase.json uses `source`/`destination`
  fields (CLI format) but the REST API Version.config requires `glob`/`path`.
  Sending the raw CLI fields caused 400 INVALID_ARGUMENT on version-create.
  Replaced the raw CONFIG_JSON builder with a translate() python function that
  maps source→glob, destination→path, regex→regex (passthrough), run→run
  (passthrough), and handles redirects (destination→location, type→statusCode)
  and headers (source→glob) for completeness. Verified against real firebase.json:
  output has glob/path, no source/destination keys. ShellCheck clean.
  Expected REST config: 3 Cloud Run rewrites (glob+run) + 1 SPA catch-all
  (glob:**→path:/index.html). Tracker: 6.2.15 ✓.

### Added (Phase 6.2.14)

- Phase 6.2.14: mint Firebase Hosting REST access token via sa-firebase-admin
  impersonation (token_format=access_token). Root cause confirmed: direct-WIF
  federated tokens (1484 chars) are rejected by the Firebase Hosting REST API with
  401 UNAUTHENTICATED — a real OAuth2 access token requires SA impersonation.
  Added google_service_account_iam_member.ci_token_creator_firebase in wif_iam.tf
  (principalSet→serviceAccountTokenCreator on sa-firebase-admin). Added dedicated
  auth@v3 step in deploy.yml (service_account + token_format: access_token) before
  the Hosting deploy; token passed as FIREBASE_ACCESS_TOKEN env var. REST script
  uses FIREBASE_ACCESS_TOKEN if set, else falls back to gcloud (local use).
  build/run keep direct WIF. ADR-0018 updated. terraform fmt OK · validate OK.
  ShellCheck clean · YAML valid. Tracker: 6.2.14 ✓ (pending Coordinator tf-apply).

### Fixed (Phase 6.2.13)

- Phase 6.2.13: REST Hosting deploy — revert token command to plain
  `gcloud auth print-access-token` (application-default re-exchanges the OIDC
  subject token mid-job and fails "Connection refused"; the WIF credential is
  already in the active-account store from auth@v3). Keep X-Goog-User-Project
  header (added 6.2.12). Add api() helper that prints HTTP status + response
  body on >=400 so failures are diagnosable; all JSON API calls (version-create,
  populateFiles, finalize, release) routed through it; upload calls also capture
  + print status/body on error. ShellCheck clean · bash -n clean. Tracker: 6.2.13 ✓.

### Fixed (Phase 6.2.12)

- Phase 6.2.12: REST Hosting deploy uses `gcloud auth application-default print-access-token`
  (mint token from WIF ADC, not the empty active-account store that `gcloud auth
  print-access-token` reads in CI). Added X-Goog-User-Project: sport-slot-dev header to AUTH
  array so every API call carries the quota/project context (required for ADC tokens, per
  gcloud docs; firebase-tools --debug also sends x-goog-user-project). Added token-length
  echo for debug visibility (token itself never logged). Fixes the 401 on version-create.
  ShellCheck clean · bash -n clean. Tracker: 6.2.12 ✓.

### Added (Phase 6.2.11)

- Phase 6.2.11: keyless Firebase Hosting deploy via REST API + gcloud access token.
  firebase-tools 15.x cannot consume WIF external_account ADC (confirmed via --debug:
  "No OAuth tokens found", crash on undefined.access_token). Solution: scripts/
  deploy_hosting_rest.sh drives the Firebase Hosting REST API directly with
  `gcloud auth print-access-token` (gcloud authenticates via WIF correctly — proven).
  No JSON key, no FIREBASE_TOKEN, no firebase-tools in CI. SPA rewrites + Cloud Run
  rewrites from firebase.json passed in version-create config (deep links preserved).
  Local make deploy-hosting unchanged (interactive firebase-tools login). ADR-0018
  updated with the firebase-tools WIF incompatibility finding. ShellCheck clean.
  Tracker: 6.2.11 ✓.

### Fixed (Phase 6.2.10)

- Phase 6.2.10: Firebase Hosting CI deploy via pure WIF ADC + GOOGLE_CLOUD_PROJECT.
  Official action (6.2.9) rejected — requires firebaseServiceAccount JSON key (incompatible
  with keyless WIF org policy). Reverted to firebase-tools CLI. Removed FIREBASE_TOKEN bridge
  (6.2.8). Now relies purely on GOOGLE_APPLICATION_CREDENTIALS (WIF external_account ADC, set
  by auth@v3) + GOOGLE_CLOUD_PROJECT=sport-slot-dev (lets firebase-tools resolve the project,
  which external_account files don't embed). --debug enabled until confirmed green.
  ShellCheck clean · YAML valid. Tracker: 6.2.10 ✓.

### Fixed (Phase 6.2.9)

- Phase 6.2.9: CI Firebase Hosting deploy now uses FirebaseExtended/action-hosting-deploy@v0
  (WIF/ADC), replacing the firebase-tools CLI shell invocation that failed to consume the
  WIF external-account credential after 4 attempts. The action is purpose-built for CI and
  honours GOOGLE_APPLICATION_CREDENTIALS from auth@v3; firebaseServiceAccount is empty
  (org policy forbids static JSON keys; action falls through to ADC). build-push + deploy-dev
  remain make targets (working correctly). Local make deploy-hosting unchanged.
  Install firebase-tools step removed from deploy job (no longer needed). Tracker: 6.2.9 ✓.

### Fixed (Phase 6.2.8)

- Phase 6.2.8: firebase Hosting deploy uses a gcloud-minted access token in CI —
  firebase-tools 15.x does not reliably consume the WIF external-account ADC
  (gha-creds JSON) that auth@v3 sets. gcloud authenticates correctly via WIF;
  `gcloud auth print-access-token` mints a short-lived token exported as FIREBASE_TOKEN
  for firebase-tools to consume. Keyless: no JSON service-account key, no deprecated
  login:ci token. Local deploys unchanged (interactive firebase login path). On failure
  a --debug rerun hint is printed. ShellCheck clean. Tracker: 6.2.8 ✓.

### Fixed (Phase 6.2.7)

- Phase 6.2.7: fix firebase Hosting deploy in CI — added --non-interactive so
  firebase-tools doesn't hang or emit "An unexpected error has occurred" when stdin
  is not a TTY (the root cause of the vague CI failure). --project already present;
  parametrised to ${FIREBASE_PROJECT:-sport-slot-dev} for flexibility. Added
  firebase --version echo as a debug aid before each deploy. ShellCheck clean.
  Tracker: 6.2.7 ✓.

### Fixed (Phase 6.1.2)

- Phase 6.1.2: add roles/redis.viewer to CI WIF principal (deploy reads Redis host/port
  to wire SPORTSLOT_REDIS_* env vars on Cloud Run). deploy_cloud_run.sh no longer silences
  the Redis describe error (2>/dev/null || true removed): a permission denial was being
  masked as "not found". Now runs a single describe with value(host,port), fails loudly
  with actionable message if the call fails, and derives both values from one gcloud call.
  ShellCheck clean. terraform fmt OK · validate OK. Tracker: 6.1.2 ✓ (pending Coordinator
  tf-plan + tf-apply-dev).

### Added (Phase 6.1.1)

- Phase 6.1.1: add CI IAM — serviceusage.serviceUsageConsumer + storage.admin (project)
  to the WIF CI principalSet for `gcloud builds submit`. serviceUsageConsumer resolves
  the "serviceusage.services.use permission" denied error; storage.admin resolves the
  "forbidden from accessing the bucket [sport-slot-dev-cloudbuild]" error on source
  tarball upload. Both added as google_project_iam_member in terraform/wif_iam.tf.
  Scope note: storage.admin at project level is broader than strictly necessary; a
  bucket-scoped binding on sport-slot-dev-cloudbuild is the tighter alternative —
  deferred to Phase 9 least-privilege hardening. ADR-0018 updated. Tracker: 6.1.1 ✓
  (pending Coordinator terraform apply).

### Fixed (Phase 6.2.6)

- Phase 6.2.6: gitignore gha-creds-*.json — google-github-actions/auth@v3 writes a
  credential file (gha-creds-<hash>.json) into the repo workspace root, which
  build_push.sh's git status --porcelain clean-tree check saw as an untracked file,
  causing "working tree not clean" error and aborting the deploy. Added gha-creds-*.json
  to .gitignore under the GCP/Firebase section. Tracker: 6.2.6 ✓.

### Fixed (Phase 6.2.5)

- Phase 6.2.5: bump CI Node 20 → 22 — pnpm v11 requires Node >=22.13 (uses node:sqlite
  builtin); CI pinned node-version: 20 caused "ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite".
  Changed all 3 node-version occurrences (pr-gates.yml:47, deploy.yml:40, deploy.yml:66).
  Added "engines": {"node": ">=22.13"} to frontend/package.json as single source of truth,
  mirroring the packageManager approach. Local Node v22.17.1 — no local issue.
  YAML valid; local: install OK · lint 0 errors · 43 tests passed · build OK.
  Clears Node-20 deprecation warning ahead of GitHub's Node-24 default. Tracker: 6.2.5 ✓.

### Fixed (Phase 6.2.4)

- Phase 6.2.4: fix pnpm version mismatch — CI pinned pnpm v9 but the project uses v11
  (allowBuilds syntax in pnpm-workspace.yaml, no packages field, is valid v11 and invalid
  v9). Added "packageManager": "pnpm@11.5.2" to frontend/package.json as the single source
  of truth; both workflows (pr-gates.yml, deploy.yml — 3 occurrences) now use
  pnpm/action-setup@v4 with package_json_file: frontend/package.json instead of
  hardcoded version: 9. Resolves "packages field missing or empty" in CI.
  Local: lint 0 errors · 43 tests passed · build OK. Tracker: 6.2.4 ✓.

### Fixed (Phase 6.2.2)

- Phase 6.2.2: fix non-hermetic test — test_validation_failed_includes_field_detail
  constructed a real Firestore client (failing in CI without ADC); now overrides the
  client dependency via dependency_overrides[get_firestore_client] = lambda: _prov_client()
  like all 20 sibling tests. Test is credential-free: passes with GOOGLE_APPLICATION_CREDENTIALS
  unset and GOOGLE_CLOUD_PROJECT="". Sibling scan: all 21 tests in test_tenant_config.py
  now have the override — zero remaining hermeticity risks. Tracker: 6.2.2 ✓.

### Fixed (Phase 6.2.1)

- Phase 6.2.1: Suppress 4 bandit B105 false positives (must_change_password Firestore field
  names in users.py + provisioning.py ×2, and WEAK_PASSWORD error code constant in
  error_codes.py) via per-line # nosec B105 with explanatory reason. B105 remains active
  elsewhere. CI backend gate now green: bandit 0 issues · ruff clean · 128 passed 91.56%
  coverage ≥ 90%. Tracker: 6.2.1 ✓.

### Added (Phase 6.2)

- Phase 6.2: GitHub Actions — pr-gates.yml (backend: ruff+bandit+pytest ≥90% coverage,
  frontend: lint+test+build, no GCP access on PRs by design) + deploy.yml (same gate suite
  on main for defense-in-depth, then keyless WIF auth + build/push backend via Cloud Build +
  gcloud run deploy + firebase deploy hosting on push to main). Deploy make targets
  (deploy_cloud_run.sh, deploy_hosting.sh) made CI-aware: interactive DEPLOY prompt skipped
  when $CI is set; manual experience unchanged. firebase-tools installed in deploy job
  (not pre-installed on runners, not in devDeps); uses WIF ADC — no interactive login needed.
  Coverage threshold 90% (measured 92% − 2% buffer per global rule). Tracker: 6.2 ✓
  (pipeline validated in 6.3).

### Added (Phase 6.1)

- Phase 6.1: WIF pool + provider activated as managed Terraform resources (imported from
  Phase-1 gcloud-created resources via IMPORT_6.1.md); data sources in wif.tf replaced by
  resource blocks; outputs.tf updated to reference resource addresses. Direct-WIF IAM bindings
  for CI deploy in wif_iam.tf: run.admin, artifactregistry.writer, cloudbuild.builds.editor,
  firebasehosting.admin + serviceAccountUser on sa-cloud-run (CI deploys as runtime SA) +
  serviceAccountUser on sa-cloud-build (flagged for Coordinator confirmation). ADR-0018 CI/CD
  security model: keyless direct WIF, repo+main-only attribute condition enforced at identity
  layer, Cloud Run deployed via gcloud (not Terraform) to avoid image-tag drift.
  Terraform fmt ✓ · validate ✓. Pending: Coordinator import + apply. Tracker: 6.1 ✓ (pending
  Coordinator import+apply).

### Added (Phase 5.6)

- Phase 5.6: Phase 5 retrospective (docs/retrospectives/phase-5.md — issue log, deferrals,
  validation quality note, carried-forward items). ADR-0014 email reconciled: §2 now names
  admin@sportbook.chandraailabs.com as the dev seed email (earlier drafts referenced
  "superadmin@…"). make reset-superadmin target + backend/scripts/reset_superadmin.py: dev-only
  one-command recovery for a lost superadmin password (NEWPW env var, refuses outside
  development). docs/roadmap.md created: phase status table, Phase 5 deferrals tracker,
  Phase 6–9 planned scope. PHASE 5 COMPLETE — Admin & Onboarding. Tracker: Phase 5 ✓.

### Added (Phase 5.5.2)

- Phase 5.5.2: Forced password change is now enforced globally via the route guards
  (`ProtectedRoute` + `TenantAdminRoute`), not just the Landing route — closes the bypass
  where reaching `/tenant/*`, `/bookings`, or `/facilities/*` directly (post-login nav,
  refresh, or direct URL) skipped the mandatory change entirely. New `usePasswordGate` hook
  fetches `/users/me` once (shared `["profile"]` query key, cached across all guards) and
  returns `{ mustChange, loading }`; platform admins excluded. `ForcePasswordChange`
  invalidates `["profile"]` on success before navigating to `/` to prevent a redirect loop
  from the stale cached flag. `/force-password` route remains un-gated. Landing simplified:
  `must_change_password` check removed (guard handles it before Landing renders) — only
  role-based routing remains. 43 frontend tests (+2: TenantAdminRoute password-gate tests).
  Build: 115 kB gzip (128 backend tests unchanged). Tracker: 5.5.2 ✓.

### Added (Phase 5.5.1)

- Phase 5.5.1: Fix forced-password-change routing for tenant_admin + shared `AppHeader` component.
  Bug fix: `enabled: !isAdmin && !isTenantAdmin` in Landing disabled the `/users/me` query for
  tenant_admin, causing `must_change_password` check to be skipped and routing directly to `/tenant`.
  Fixed by `enabled: !isAdmin` (runs for all non-platform-admin roles) with an `isLoading` gate
  before all redirects, ordering `must_change_password` check before the role-based redirect.
  New `AppHeader` component: logo + brand name (Link to "/") + optional children slot + user
  email·role badge + sign-out button. Adopted on all authenticated screens: Facilities, MyBookings,
  TenantDashboard, TenantFacilities, TenantBranding, TenantPolicies, TenantUsers, TenantList.
  41 frontend tests (+4: AppHeader×3, Landing regression guard×1). Build: 115 kB gzip
  (128 backend tests unchanged). Tracker: 5.5.1 ✓.

### Added (Phase 5.5b)

- Phase 5.5b: tenant user management UI (list active users, add, deactivate, reset password,
  bulk CSV import), admin-initiated password reset backend (ADR-0014 amendment — tenant-admin
  or platform-admin resets any user in their scope; returns temp_password once; sets
  must_change_password=true). Factored `CredentialDisplay` component with "Copied!" feedback
  shared by create/bulk/reset flows. Branding fix: GET `/tenants/{slug}/branding` now returns
  `brand_logo_url`; `TenantBranding` form pre-fills from current branding on mount (slug from
  JWT claim per ADR-0012 §2); logo renders in resident header via `getLastBranding()`.
  `flat_number` field hidden when role=tenant_admin on the Add User form (required only for
  resident). VALIDATION_FAILED 422 field detail (loc+msg) now surfaced in user-facing error
  messages. `ApiClientError` extended to carry the `detail` array. 37 frontend tests
  (128 backend tests, 92% coverage, 115 kB gzip). PHASE 5 FEATURE-COMPLETE. Tracker: 5.5b ✓.

### Added (Phase 5.5a)

- Phase 5.5a: tenant-admin UI — role-based landing (`TenantAdminRoute` → `/tenant`), dashboard
  with 4 nav cards, facilities management (catalog-based create/list/deactivate), branding form
  (brand name, primary/secondary hex color, logo URL), booking-policies form. `TenantAdminRoute`
  guards all `/tenant/*` routes; tenant_admin JWT claim redirects to `/tenant` at landing.
  `tenantAdminHooks.ts` wraps all tenant-config and facility API calls via TanStack Query.
  `TenantUsers` stubbed (Phase 5.5b). 7 new frontend tests (29 total). Build: 113 kB gzip.
  Tracker: 5.5a ✓.

### Added (Phase 5.4b)

- Phase 5.4b: tenant-admin config backend — PATCH `/tenant/branding` (hex color + http(s) URL
  validation, merge-into-map semantics), PATCH `/tenant/policies` (bounds: horizon≥1,
  buffer≥0, max_slots≥1, HH:MM time format), `/tenant/users` CRUD (POST/GET/DELETE) + bulk
  import POST `/tenant/users/bulk` (per-row report: created+temp_password or failed+reason,
  500-row cap). `flat_number` now optional for `tenant_admin` role (required for `resident`);
  `ProvisioningError(ApiError)` subclass separates expected from unexpected errors. Request
  validation 422 now includes a `"detail"` array with `loc` + `msg` per field. New
  `api/v1/tenant_config.py`; admin.py `deactivate_user` uses constructor-bound `caller_uid`.
  17 new tests (122 total, 91% coverage). Tenant-admin backend complete. Tracker: 5.4b ✓.

### Added (Phase 5.4a)

- Phase 5.4a: global facility catalog (seed + GET /facility-catalog), catalog-based tenant
  facility CRUD (POST/GET/PATCH/DELETE `/tenant/facilities`) replacing 3.2 free-form creation
  (ADR-0015). `seed_facility_catalog.py` seeds 7 types (badminton, tennis, swimming, gym,
  turf-football, table-tennis, basketball) and back-links legacy free-form facilities via
  sport-string migration. `POST /tenant/facilities` validates `facility_type_id` against
  catalog and copies `sport` from catalog doc. `DELETE /tenant/facilities/{id}` soft-deactivates
  (active=false). Removed free-form `POST /facilities` and `PATCH /facilities/{id}` (superseded).
  Removed orphaned `models/facility.py`. `firebase.json` firestore block added (indexes path
  wired). `make seed-facility-catalog` target added. 7 new tests (105 total, 90% coverage).
  ADR-0015 §1 amended: brand_logo_url is a URL field; Cloud Storage upload deferred to Phase 7.
  Tracker: 5.4a ✓.

### Fixed (Phase 5.3.1)

- Phase 5.3.1: fix — removed dev-tenant-slug pin from `_slug_from_host`; unrecognized
  hosts (localhost, *.web.app, *.run.app) now return None so the JWT tenant_slug claim
  is always authoritative (ADR-0012 §2 / ADR-0007). Previously `SPORTSLOT_DEV_TENANT_SLUG`
  silently overrode the JWT claim, breaking every non-default tenant in local dev.
  Removed `_DEV_HOSTS` (dependency.py) and `dev_tenant_slug` field (config.py); renamed
  `test_dev_override_allows_localhost_in_development` → `test_localhost_no_host_header_trusts_jwt`;
  added 3 regression guards (rvrg-on-localhost-allowed, demo-on-localhost-still-allowed,
  rvrg-subdomain-with-demo-claim-still-403). 102 tests, 90% coverage. Tracker: 5.3.1 ✓.

### Added (Phase 5.3)

- Phase 5.3: platform-admin UI — role-based routing (PlatformRoute guard), tenant list +
  create-tenant + create-user screens, one-time temp-password credential block with copy
  button ("shown only once" warning), forced password-change screen (ForcePasswordChange),
  admin error-catalog entries (6 new codes), Landing component with must_change_password
  gate (fetches /users/me post-login via TanStack Query; platform_admin → /admin redirect).
  7 test files, 22 tests. Build: 411 kB JS / 112 kB gzip. Tracker: 5.3 ✓.

### Fixed (Phase 5.2.1)

- Phase 5.2.1: fix — platform-admin tokens accepted on any host in DEV (ADR-0014
  route+role gating); admin-host segregation deferred to Phase 9 (charter exposure
  logged). Fixes superadmin lockout on localhost. Removed `is_admin_host` gate from
  `auth/dependency.py`; `require_platform_admin` is the sole authorization layer.
  Inverted test `test_platform_admin_on_any_host_allowed_adr0014`; added regression
  guard `test_platform_admin_on_localhost_allowed_regression_5221`. 99 tests, 90% coverage.
  Tracker: 5.2.1 ✓.

### Added (Phase 5.2)

- Phase 5.2: platform-admin backend provisioning — ADR-0017 (deletion/retention lifecycle,
  three-stage ACTIVE→INACTIVE→PURGED, user soft-delete + Firebase disable + cancel future
  bookings, self-deactivation forbidden), `require_platform_admin` dependency, 6 new error
  codes (TENANT_SLUG_TAKEN, INVALID_SLUG, USER_EMAIL_TAKEN, USER_NOT_FOUND,
  SELF_DEACTIVATION_FORBIDDEN, WEAK_PASSWORD), `UserProvisioningService` (create_user with
  tenant_slug lookup + AuditRepository + rollback guard, deactivate_user +
  _cancel_future_bookings), `PlatformRepository.create_tenant / get_tenant_by_slug /
  list_tenants` (collection_name guard removed to allow direct multi-collection access),
  `/api/v1/admin` router (POST /tenants, GET /tenants, POST /tenants/{id}/users,
  POST /tenants/{id}/users/bulk, DELETE /tenants/{id}/users/{uid}),
  POST /api/v1/users/me/change-password (clears must_change_password flag),
  seed_platform_admin.py + `make seed-platform-admin` (idempotent),
  composite Firestore index (bookings: uid+status+date for deactivation cancel-scan).
  13 new tests (98 total, 90% coverage). Tracker: 5.2 ✓.

### Added (Phase 5.1)

- Phase 5.1: ADR-0014 (admin architecture & identity — route gating, seeded superadmin,
  generate+force-change credentials), ADR-0015 (facility catalog → tenant instances),
  ADR-0016 (shared user provisioning, CSV bulk import). PHASE 5 IN PROGRESS.
  Tracker: 5.1 ✓.

### Fixed (Phase 4.6.1)

- Phase 4.6.1: fix — branding resolves on non-subdomain hosts (.web.app) via
  VITE_DEFAULT_TENANT_SLUG, and re-applies post-login from the JWT tenant_slug claim.
  Branding endpoint/data were correct; frontend slug resolution was the gap.
  Tracker: 4.6.1 ✓.

### Added (Phase 4.6)

- Phase 4.6: public per-tenant branding endpoint + CSS-variable application on app load,
  server-computed `cancellable` flag on /bookings/mine (reuses cancellation deadline logic —
  refactored into shared `_is_cancellable()` helper), eye-icon password toggle in sign-in,
  hide-cancel-when-closed (MyBookings shows "Cancellation closed" hint), Phase 4 retrospective,
  branding backfill in seed. PHASE 4 COMPLETE (custom domain deferred to Phase 7).
  Tracker: 4.6 ✓.

### Added (Phase 4.5a)

- Phase 4.5a: Firebase Hosting config (firebase.json rewrites /api/** → Cloud Run, SPA fallback),
  deploy_hosting.sh (Coordinator-run, guarded), X-Forwarded-Host-aware tenant cross-check
  (conditional host enforcement — recognized subdomains enforced, unrecognized hosts trust JWT
  claim; JWT remains authoritative per ADR-0007/ADR-0012 §2), Cloud Run direct ingress logged
  as accepted exposure in security charter (Phase 7 LB closure path documented). Tracker: 4.5a ✓.

### Added (Phase 4.4)

- Phase 4.4: my-bookings list + cancellation (dialog-level error handling, query invalidation
  reopens slots), proactive quota banner on availability page, sign-in show-password toggle.
  Booking dialog errors now surface in-dialog instead of closing dialog (fixes silent 409 UX).
  Tracker: 4.4 ✓.

### Added (Phase 4.3)

- Phase 4.3: ADR-0013 (error presentation/i18n — resolver chain, English catalog, fail-safe),
  TanStack Query booking hooks (useFacilities, useAvailability, useCreateBooking), facility list,
  availability grid with SlotGrid + IN_PROGRESS warning, booking confirm dialog with error
  catalog lookup. Tracker: 4.3 ✓.

### Added (Phase 4.2)

- Phase 4.2: Firebase Auth context (onIdTokenChanged, token-refresh-aware), tenant resolution
  (host subdomain + JWT claim cross-check), typed same-origin API client (apiFetch),
  sign-in page (email/password + Google), ProtectedRoute, Home page with mismatch warning.
  Tracker: 4.2 ✓.

### Added (Phase 4.1) — PHASE 4 IN PROGRESS

- Phase 4.1: ADR-0012 (hosting constraint findings — Firebase Hosting 20-subdomain cap, LB wildcard
  deferred to Phase 7; same-origin API rewrites; CSS-variable theming; Tailwind rejected) + Vite/TS
  strict/PWA scaffold with pnpm, TanStack Query, React Router, vitest + Testing Library. lint/test/build
  gates pass; bundle 209.50 kB / 68.33 kB gzip; PWA service worker generated.

### Fixed (Phase 3.6.1)

- 3.6.1: fix — cancelled bookings can be rebooked (status-aware supersede in transaction).

### Added (Phase 3.6) — PHASE 3 COMPLETE

- Phase 3.6: ADR-0011 synchronous Firestore audit trail, IN_PROGRESS slot marking + booking
  notice, concurrency proof script, Phase 3 retrospective. PHASE 3 COMPLETE
  (cloud redeploy pending Coordinator). Tracker: 3.6 ✓.

### Added (Phase 3.5)

- Phase 3.5: booking cancellation (self or tenant_admin, buffer-enforced on tenant clock,
  attribution fields) + GET /bookings/mine (cursor-paginated). Tracker: 3.5 ✓.

### Added (Phase 3.4)

- Phase 3.4: Memorystore Redis infra script (AUTH → Secret Manager), LockService (SET NX PX,
  owner-checked release, fail-closed), transactional booking creation (quota + deterministic-ID
  guards), Direct VPC egress wiring in deploy. Tracker: 3.4 ✓.

### Added (Phase 3.3)

- Phase 3.3: computed availability endpoint — pure-function slot matrix
  (past/booked/window/horizon), tenant-timezone rule evaluation, BookingRepository
  (read side), tenant timezone seeded.

### Added (Phase 3.2)

- Phase 3.2: PolicyService (override→default), Facility model + CRUD with require_role gate,
  seed v2 (tenant_admin user + tenant registry doc).

### Added (Phase 3.1)

- Phase 3.1: ADR-0009 (Redis slot locking), ADR-0010 (booking domain & policy resolution) accepted.

### Fixed (Phase 2.6.3)

- 2.6.3: retrospective investigation record corrected (omitted STEP 3 of 2.6.2;
  issue #11, audit-log findings).

### Fixed (Phase 2.7.1)

- Corrected fabricated documentation content (issue #10 in retrospective): charter
  had fictional run.allowedIngress override and omitted real allowedPolicyMemberDomains
  exception; retrospective omitted Cloud Run 404 investigation, protocol amendments,
  and issues #1/#6/#9; runbook omitted credential model; README omitted engineering
  method section. Root cause: session interruption + context compaction; Worker
  reconstructed instead of stopping. All five files replaced with verbatim content.

### Added (Phase 2.7) — PHASE 2 COMPLETE

- README.md rewritten: Phase 2 COMPLETE badge, Mermaid architecture diagram, ADR table
  (0001–0008), updated repo structure, security summary
- docs/retrospectives/phase-2.md: full Phase 2 retrospective (what went well, 7 issues
  log, key decisions, lessons learned, Phase 3 preview)
- docs/runbooks/local-development.md: replaced Phase 1 stub with comprehensive Phase 2
  backend runbook (GCP auth, dev server with PYTHONPATH, tests, seed, Docker, tenant
  routing, coordinator-only scripts, troubleshooting)
- docs/security/charter.md: v1.1 → v1.2; Org-Policy Exceptions section added
  (run.allowedIngress override documented with Phase 7 review date)

### Added (Phase 2.6) — Phase 2.6 COMPLETE

- Phase 2.6: Multi-stage Dockerfile (uv builder → slim non-root runtime); .dockerignore;
  guarded Coordinator scripts for AR/bucket setup (setup_build_infra.sh), Cloud Build push
  with git-SHA tags (build_push.sh), Cloud Run deploy min=0/max=2 sa-cloud-run (deploy_cloud_run.sh);
  Makefile: dev-env, run-dev, docker-build, docker-run, build-push, deploy-dev targets;
  config.py .env path anchored to backend/ (CWD-independent); .last_image_tag gitignored.

### Added (Phase 2.5) — Phase 2.5 COMPLETE

- Phase 2.5: GET /api/v1/users/me (TenantContext → UserProfileRepository → Firestore);
  slowapi in-memory rate limiting per ADR-0007 §5 — 429 in error envelope via middleware
  subclass (slowapi middleware bypasses app exception handlers); /healthz + /readyz exempt;
  guarded dev seed script (backend/scripts/seed_dev_user.py), Firebase token helper
  (scripts/get_dev_token.sh), Makefile seed-dev target, architecture gate test. 31 tests,
  coverage 89%.

### Added (Phase 2.4) — Phase 2.4 COMPLETE

- Phase 2.4: ADR-0008 (subcollection layout, permanent deny-all rules, repository contract);
  infrastructure/firestore.rules updated with ADR-0008 comment block + guarded deploy script;
  TenantRepository/PlatformRepository + UserProfile model. Coverage ≥80% (87%).

### Added (Phase 2.3) — Phase 2.3 COMPLETE

- Phase 2.3: FastAPI scaffold — app factory, request-ID middleware, error envelope + code
  registry, structlog with PII redaction, /healthz + /readyz, TenantContext auth dependency
  (ADR-0006/0007). Coverage ≥80% (93%).

### Added (Phase 2.2) — Phase 2.2 COMPLETE

- Phase 2.2: Security charter v1.1 committed to docs/security/charter.md (identity &
  credential model, ADR-0006/0007 alignment)

### Added (Phase 2.1) — Phase 2.1 COMPLETE

- ADR-0006: API Design Patterns accepted — URL path versioning (/api/v1/), UPPER_SNAKE
  error code registry, cursor-based pagination (offset prohibited), split liveness/readiness
  health probes outside versioned surface
- ADR-0007: Authentication & Authorization accepted — firebase-admin-only JWT verification
  (python-jose prohibited: CVE-2024-33663/CVE-2024-33664), custom claims as identity source of
  truth, accepted 1-hour staleness with selective revocation on SENSITIVE endpoints, no admin
  tenant bypass, phased rate limiting (slowapi → Redis → Cloud Armor)
- docs/adr/README.md: Phase 2 section added with index entries for ADR-0006 and ADR-0007

### Fixed
- verify_toolchain.sh exited with code 120 due to SIGPIPE when gcloud --version
  output was piped to `head -1`; `head` closed the pipe after line 1 and gcloud
  received SIGPIPE on subsequent writes — under `set -euo pipefail` this aborted
  the script mid-execution, skipping gcloud, Git, and gh CLI checks
- Replaced all `| head -1` patterns with `| sed -n '1p'` across Homebrew,
  Terraform, ShellCheck, gcloud, and gh CLI version checks; sed reads all input
  before producing output, eliminating SIGPIPE risk

### Added (Phase 1.4.3) — Phase 1 COMPLETE
- Makefile at repo root with 11 self-documenting commands (make help)
- scripts/install.sh — backend + frontend dependency installation
- scripts/tf-init.sh, tf-plan.sh — Terraform workflow helpers
- scripts/tf-apply-dev.sh — apply with single confirmation guardrail
- scripts/tf-destroy-dev.sh — destroy with double confirmation guardrail
- scripts/gcp-whoami.sh — show gcloud auth state + ADC status
- scripts/gcp-set-dev.sh — switch to sport-slot-dev project
- docs/adr/README.md — ADR index with status table for all 5 Phase 0 ADRs
- docs/adr/template.md — template for future ADRs
- docs/runbooks/phase-1-retrospective.md — lessons learned from Phase 1
- README.md updated: Phase 1 COMPLETE badge + Quick Start section
- Removed obsolete .gitkeep placeholders (5 files)
- All 7 new scripts ShellCheck clean

### Added (Phase 1.4.2)
- Documented existing GCP resources in Terraform (Option C — hybrid data sources + commented templates)
- terraform/apis.tf: 18 APIs (9 core + 9 operational) as locals + commented resource template
- terraform/iam.tf: 4 service accounts as data sources + commented resource templates with roles documented
- terraform/wif.tf: WIF pool + provider as data sources + commented resource/binding templates
- terraform/firestore.tf: Firestore documented via locals (no data source in provider v6) + commented resource
- terraform/outputs.tf: 12 outputs covering project, region, SA emails, WIF names, Firestore name/location
- Note: google_firestore_database data source absent from provider v6; using locals with known-stable values

### Added (Phase 1.4.1)
- terraform/ directory with module-ready flat structure (Option B+)
- terraform/backend.tf — remote state in gs://sport-slot-dev-tfstate (prefix: terraform/state)
- terraform/main.tf — Google + Google-beta providers pinned ~> 6.0
- terraform/variables.tf — input variables with validation (project_id, region, environment patterns)
- terraform/outputs.tf — basic variable pass-through outputs
- terraform/apis.tf, iam.tf, wif.tf, firestore.tf — empty placeholders for Phase 1.4.2 import
- terraform/terraform.tfvars.example — committed template for developer onboarding
- terraform/.terraform.lock.hcl — provider version pins (google + google-beta v6.50.0)
- .gitignore updated: scoped to terraform/ prefix, lock file explicitly NOT ignored

### Added (Phase 1.3.3)
- Firebase project enabled on sport-slot-dev (fixes G17 root cause from old SportBook postmortem)
- Firebase Web App "SportSlot Web (React PWA)" created (App ID: 1:707808711911:web:f16ca1570a30f4e5957e42)
- Web app config captured to infrastructure/firebase-web-config.json (local only, not committed)
- .gitignore patterns for Firebase config files (infrastructure/firebase-*.json)
- Email/Password and Google OAuth authentication providers enabled
- Firestore database created (Native Mode, asia-south1 / Mumbai)
- Deny-all security rules deployed via `firebase deploy --only firestore:rules`
- infrastructure/firestore.rules (deny-all baseline; tenant-aware rules added in Phase 2)
- infrastructure/firestore.indexes.json (empty — composite indexes added per query design in Phase 2)
- firebase.json and .firebaserc for Firebase CLI configuration
- sa-firebase-admin granted: roles/firebase.admin, roles/datastore.user, roles/iam.serviceAccountTokenCreator, roles/logging.logWriter
- sa-cloud-run granted roles/datastore.user for direct Firestore access
- sa-cloud-run can impersonate sa-firebase-admin via serviceAccountTokenCreator on SA resource
- infrastructure/iam-config.yaml: added authentication_strategy section documenting ADC pattern
- docs/runbooks/iam-setup.md: added ADC pattern explanation with code examples
- docs/runbooks/local-development.md: new runbook for developer onboarding

### Architecture Decisions Confirmed (Phase 1.3.3)
- Authentication uses Application Default Credentials (ADC) + Workload Identity Federation
- No static service account JSON keys generated (org policy iam.disableServiceAccountKeyCreation enforces this)
- Aligned with Google's "Secure by Default" policy and ADR-0004 5-layer defense-in-depth

### Added (Phase 1.3.2)
- 4 service accounts with least-privilege baseline roles:
  - sa-cloud-run (secretAccessor, logWriter, metricWriter, cloudtrace.agent)
  - sa-firebase-admin (placeholder — roles added in Phase 1.3.3)
  - sa-cloud-build (run.developer, artifactregistry.writer, logWriter + impersonation)
  - sa-monitoring (monitoring.editor, logWriter)
- Workload Identity Federation for GitHub Actions (no JSON keys)
- WIF restricted to main branch of chandranakkalakunta/sport-slot-reservation
- infrastructure/iam-config.yaml documenting IAM setup
- docs/runbooks/iam-setup.md
- .gitignore pattern for phase audit logs (scripts/phase-*.txt)

### Added (Phase 1.3.1)
- GCP project sport-slot-dev created under chandraailabs.com org
- Billing account 014A8C-586310-DE4575 linked
- 18 GCP APIs enabled (core infrastructure + operational)
- infrastructure/project-config.yaml documenting project setup
- docs/runbooks/gcp-project-setup.md

### Added
- Phase 1.2: Local toolchain installed and verified
- Python 3.12.13 via uv (alongside system 3.13)
- Project .venv created at repo root with Python 3.12
- Firebase CLI 15.19.1 reinstalled via pnpm (user-scope, ~/Library/pnpm)
- ShellCheck 0.11.0 installed via Homebrew
- Initial backend/pyproject.toml scaffolding
- Initial frontend/package.json scaffolding
- scripts/verify_toolchain.sh — all 13 checks passing
- Phase 1.1: Repository created with initial structure
- Phase 0 ADRs documented (ADR-0001 through ADR-0005)
- .gitignore covering Python, Node.js, Terraform, GCP, Firebase
- MIT License with Chandra AI Labs copyright
- README.md with project overview and architecture summary

## Phase History

### Phase 1 — Workspace Bootstrap (COMPLETE 2026-06-10)
- 1.1 GitHub + Local Workspace ✓
- 1.2 Local Toolchain (Python + Node) ✓
- 1.3 GCP Project + Firebase Initialization ✓
  - 1.3.1 GCP Project Foundation ✓
  - 1.3.2 Service Accounts + Workload Identity ✓
  - 1.3.3 Firebase + Firestore Initialization ✓
- 1.4 Terraform Foundation + Makefile + Docs ✓
  - 1.4.1 Terraform Foundation ✓
  - 1.4.2 Document Existing Resources ✓
  - 1.4.3 Makefile + Docs Finalization ✓

### Phase 2 — Backend API Foundation (COMPLETE 2026-06-12)
- 2.1 ADR-0006 + ADR-0007 (API design + auth decisions) ✓
- 2.2 Security charter v1.1 committed to docs/security/charter.md ✓
- 2.3 FastAPI scaffold + error envelope + TenantContext auth dependency ✓
- 2.4 Repository pattern + deny-all rules formalized + ADR-0008 ✓
- 2.5 /api/v1/users/me + slowapi rate limiting + dev seed ✓
- 2.6 Dockerfile + Cloud Run deploy scripts + papercut fixes ✓
- 2.7 Documentation closure: README, retrospective, runbook, charter v1.2 ✓

### Phase 3 — Booking Engine (IN PROGRESS)
- 3.1 ADR-0009 (Redis slot locking) + ADR-0010 (booking domain & policy) ✓
- 3.2 PolicyService + Facility CRUD + require_role + seed v2 ✓
- 3.3 Computed availability endpoint + BookingRepository (read side) + tenant timezone ✓

### Phase 0 — Foundation Decisions (complete)
- ADR-0001: Tech Stack & Software Versions
- ADR-0002: Database Technology Selection
- ADR-0003: Build Tooling Interface
- ADR-0004: Tenant Isolation Strategy
- ADR-0005: Cost Baseline & Budget Alerts
