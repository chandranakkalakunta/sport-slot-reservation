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
- 1.2 Local Toolchain (Python + Node) ← CURRENT
- 1.3 GCP Project + Firebase Initialization
- 1.4 Terraform Foundation + Makefile + Docs

### Phase 0 — Foundation Decisions (complete)
- ADR-0001: Tech Stack & Software Versions
- ADR-0002: Database Technology Selection
- ADR-0003: Build Tooling Interface
- ADR-0004: Tenant Isolation Strategy
- ADR-0005: Cost Baseline & Budget Alerts
