# Phase 1 Retrospective — Workspace Bootstrap

**Phase:** 1 — Workspace Bootstrap
**Completion Date:** 2026-06-10
**Duration:** Multiple sessions across one day

## Outcomes Achieved

- Public GitHub repository established with proper structure
- Complete local development toolchain (Python 3.12, Node 22, etc.)
- GCP project under chandraailabs.com organization
- 18 APIs enabled, 4 service accounts created
- Workload Identity Federation operational (zero JSON keys)
- Firebase + Firestore initialized and verified
- Terraform foundation with module-ready structure
- Makefile + bash scripts following ADR-0003
- 5 Phase 0 ADRs (architectural documentation)
- Multiple runbooks for operations

## What Worked Well

### 1. Discussion-First ADRs

Architecture discussion before any code commitment paid off.
Decisions were documented with full reasoning, trade-offs were
explicit, and no "we should have thought about this" moments
emerged during implementation.

### 2. Phase Gating

Splitting Phase 1 into sub-phases (1.1, 1.2, 1.3.1, 1.3.2,
1.3.3, 1.4.1, 1.4.2, 1.4.3) with independent validation between
each caught issues immediately rather than compounding them:

- Old Firebase CLI conflict caught in Phase 1.2
- Shell environment isolation issue caught in Phase 1.2
- SIGPIPE bug in verification script caught and fixed
- Wrong commit email caught and corrected early

### 3. Embracing Org Policies

The "Secure by Default" policy blocked service account JSON key
creation. Instead of overriding the policy, we adapted to
Application Default Credentials (ADC). The result is more secure
and aligned with industry best practice.

### 4. Pragmatic Choices Over Perfectionism

When choosing Terraform structure, the temptation was to go full
modular from day one. Choosing "module-ready flat" (Option B+)
saved significant time without compromising future flexibility.

When facing resource imports, choosing "document + data sources"
(Option C) avoided a risky 2-3 hour operation while capturing all
the architectural value. Data sources resolve correctly and provide
live references for Phase 2 resources.

## What We Learned

### Shell Environment Isolation

Each terminal session reads ~/.zshrc independently. Changes made
by one tool don't propagate to other open terminals. **Lesson:**
Always start fresh terminals after installation operations.

### Pipefail + SIGPIPE

The combination of `set -euo pipefail` and `command | head -1`
is fragile — SIGPIPE terminates the writer when head closes the
pipe. **Lesson:** Use `sed -n '1p'` instead, which reads all
input before producing output.

### Provider Data Source Gaps

Not all GCP resources have data source equivalents in the stable
Terraform provider. `google_firestore_database` data source is
absent from hashicorp/google v6. **Lesson:** Have locals with
known-stable values as a fallback before assuming data sources exist.

## Old SportBook Root Cause Comparison

Old SportBook (G17): Firebase was never initialized because the
`firebase projects:addfirebase` command was assumed to have run
but actually failed silently. 40% of features cascaded into failure.

Phase 1.3.3 fix: Explicit verification at every step. The Firebase
project enable was run and immediately verified via multiple methods
before proceeding. No assumption-based success.

This single discipline change — verify, don't assume — is the
difference between the old and new approach.

## Decisions That Need Future Review

### Phase 4 (CI/CD): First WIF Validation

GitHub Actions WIF pool is configured (Phase 1.3.2) but not yet
exercised by a real deployment. First CI pipeline run will validate
the full WIF chain end-to-end.

### Phase 4 or 8: Terraform Import

Resources currently documented as data sources. Should be imported
into Terraform management before PROD. Estimated 2-3 hours.
Best done when Firestore, Cloud Run, and IAM are all stable.

### Phase 2: Real Application Begins

- First Python code (FastAPI scaffold)
- First React component
- Firestore Security Rules expand beyond deny-all (per ADR-0004)
- Repository pattern for tenant isolation

## Metrics

| Metric | Value |
|--------|-------|
| Sub-phases completed | 8 |
| ADRs written | 5 |
| Lines of Terraform HCL | ~250 |
| GCP resources created | ~30 |
| Service account JSON keys generated | 0 |
| ShellCheck errors at commit | 0 |
| Production-impacting bugs | 0 |

## Next Phase

Phase 2 — Backend API Foundation begins with:
- FastAPI application skeleton with structured logging
- TenantContext + Repository pattern (ADR-0004 Layer 2)
- Firebase Admin SDK integration via ADC
- First protected endpoint with JWT verification
- Unit tests with Firestore isolation verification
