# Changelog

All notable changes to SportSlotReservation are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
