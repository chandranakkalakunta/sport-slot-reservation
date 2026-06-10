# Changelog

All notable changes to SportSlotReservation are documented in this
file. The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- verify_toolchain.sh exited with code 120 due to SIGPIPE when gcloud --version
  output was piped to `head -1`; `head` closed the pipe after line 1 and gcloud
  received SIGPIPE on subsequent writes — under `set -euo pipefail` this aborted
  the script mid-execution, skipping gcloud, Git, and gh CLI checks
- Replaced all `| head -1` patterns with `| sed -n '1p'` across Homebrew,
  Terraform, ShellCheck, gcloud, and gh CLI version checks; sed reads all input
  before producing output, eliminating SIGPIPE risk

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

### Phase 1 — Workspace Bootstrap (in progress)
- 1.1 GitHub + Local Workspace ✓ COMPLETE
- 1.2 Local Toolchain (Python + Node) ✓ COMPLETE
- 1.3 GCP Project + Firebase Initialization ✓ COMPLETE
  - 1.3.1 GCP Project Foundation ✓ COMPLETE
  - 1.3.2 Service Accounts + Workload Identity ✓ COMPLETE
  - 1.3.3 Firebase + Firestore Initialization ✓ COMPLETE
- 1.4 Terraform Foundation + Makefile + Docs ← NEXT

### Phase 0 — Foundation Decisions (complete)
- ADR-0001: Tech Stack & Software Versions
- ADR-0002: Database Technology Selection
- ADR-0003: Build Tooling Interface
- ADR-0004: Tenant Isolation Strategy
- ADR-0005: Cost Baseline & Budget Alerts
