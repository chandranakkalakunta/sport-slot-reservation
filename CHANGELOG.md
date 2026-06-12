# Changelog

All notable changes to SportSlotReservation are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
