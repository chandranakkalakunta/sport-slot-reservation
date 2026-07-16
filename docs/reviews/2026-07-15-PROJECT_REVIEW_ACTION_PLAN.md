> SNAPSHOT (2026-07-15 third-party review). Statuses in this file
> are frozen as of the review date — the living record is
> docs/backlog.md. Dispositions: Strategist validation 2026-07-16.

# SlotSense — Project Review Action Plan

**Date:** 2026-07-15  
**Full report:** [`PROJECT_REVIEW.md`](2026-07-15-PROJECT_REVIEW.md) · **Summary:** [`PROJECT_REVIEW_SUMMARY.md`](2026-07-15-PROJECT_REVIEW_SUMMARY.md)

This checklist maps review findings to actionable work. Where backlog IDs already exist in `docs/backlog.md`, they are noted. Status should be updated as items close.

**Status legend:** `OPEN` · `IN PROGRESS` · `DONE` · `DEFERRED`

---

## P0 — Before resident-facing / production deploy

| # | Action | Backlog / ref | Status | Notes |
|---|--------|---------------|--------|-------|
| P0.1 | Server-side max utterance duration (~30s) for `/agent/voice` | `VOICE-HARDEN-01` | OPEN | Client already auto-stops; enforce on server |
| P0.2 | Voice-specific (stricter) per-resident rate limit | `VOICE-HARDEN-02` | OPEN | Cost ~₹1/turn surface |
| P0.3 | Runtime or deploy gate for voice until P0.1–P0.2 land | `VOICE-PROD-GATE` | OPEN | Flag was removed 2026-07-13 |
| P0.4 | DPDP cross-border check for STT/TTS regions | `SEC-01` | BLOCKED | Counsel / current rules verification |
| P0.5 | Codify baseline SAs + IAM bindings in Terraform | `IAM-TF-CODIFY` | IN PROGRESS | PR-1b; rebuild risk if skipped |
| P0.6 | Uptime checks + error/p95/availability alerts | `PR-2-OBSERVABILITY` | OPEN | Minimum production ops bar |
| P0.7 | Alert on Firestore backup failure | `BACKUP-ALERT` | OPEN | Pairs with ADR-0038 |
| P0.8 | Add pip-audit (or uv audit) to PR gates | `PR-5-SECURITY` | OPEN | Docs claim done; CI missing |
| P0.9 | Secret scanning in CI (gitleaks / detect-secrets) | `PR-5-SECURITY` | OPEN | |
| P0.10 | Binary Auth: implement **or** downgrade Phase 5 claims | README / charter / REQUIREMENTS | OPEN | Honesty > aspirational “done” |
| P0.11 | Doc reconciliation: model name, roadmap, phase table | README, `docs/roadmap.md`, ADRs | OPEN | `gemini-2.5-flash` vs “1.5 Pro” |

---

## P1 — Production maturity

| # | Action | Backlog / ref | Status | Notes |
|---|--------|---------------|--------|-------|
| P1.1 | CMEK for Firestore / secrets / storage | Phase 8 / security charter | OPEN | |
| P1.2 | VPC for Cloud Run + Cloud NAT | Phase 8 | OPEN | |
| P1.3 | MFA for tenant_admin and platform_admin | Phase 8 | OPEN | |
| P1.4 | Penetration testing | Phase 8 | OPEN | |
| P1.5 | Cloud Armor enforce-vs-preview decision | `PR-5-SECURITY` | OPEN | |
| P1.6 | Tighten GitHub WIF principal privileges | `WIF-LEAST-PRIV` | OPEN | |
| P1.7 | Formalize 99% SLO + maxScale / probes | `PR-3-AVAILABILITY` | OPEN | |
| P1.8 | Redis SPOF decision | `PR-3-AVAILABILITY` | OPEN | Fail-closed already on lock path |
| P1.9 | Load / perf test to validate SLO | `SLO-LOAD-TEST` | OPEN | |
| P1.10 | Billing budgets + thresholds (incl. voice) | `PR-4-COST` | OPEN | ADR-0005 |
| P1.11 | Automate weekly Firebase Auth export | `AUTH-EXPORT-AUTO` | OPEN | Manual until then |
| P1.12 | Formal DPDP self-assessment | Phase 8 / SEC-01 | OPEN | |

---

## P2 — Engineering quality

| # | Action | Backlog / ref | Status | Notes |
|---|--------|---------------|--------|-------|
| P2.1 | Widen mypy gradually (repos → services → api) | — | OPEN | Ratchet; don’t big-bang |
| P2.2 | Measure frontend coverage; set gate − 2% buffer | — | OPEN | Match backend discipline |
| P2.3 | Playwright (or similar) smoke E2E on deploy | — | OPEN | Sign-in → book → cancel |
| P2.4 | Two-tenant cross-tenant suite in CI | ADR-0004 | OPEN | Second instance catches isolation bugs |
| P2.5 | Revoke voice reply blob URLs | `VOICE-BLOB-CLEANUP` | OPEN | Memory leak on long sessions |
| P2.6 | Disable mic while agent turn in flight | `VOICE-INPUT-LOCK` | OPEN | Race prevention |
| P2.7 | Decide deterministic router expansion | `AGENT-ROUTER` | OPEN | Only if tools emit resident-ready prose |
| P2.8 | Fix Firestore positional-filter deprecation warnings | `INFRA-02` | OPEN | Cosmetic but noisy |
| P2.9 | Deploy/runbook for voice env vars + IAM roles | `OPS-RUNBOOK` | OPEN | Saved hours in voice debug |

---

## P3 — Product growth

| # | Action | Backlog / ref | Status | Notes |
|---|--------|---------------|--------|-------|
| P3.1 | WhatsApp / SMS notifications | Phase 7.3+ deferred | OPEN | India distribution critical |
| P3.2 | Push / in-app notifications | Phase 7 deferred | OPEN | |
| P3.3 | Payments (UPI / Razorpay etc.) | Requirements | OPEN | Prepaid / collection |
| P3.4 | Multi-language voice (hi/te/…) | `VOICE-ML` | BLOCKED | STT auto-detect limits |
| P3.5 | Tenant-admin voice language config UI | `TADM-01` | OPEN | ADR-0037 |
| P3.6 | Native-speaker confirm lexicon review | `VOICE-LEX` | OPEN | Fail-closed makes gaps safe |
| P3.7 | iOS Safari voice device testing | `VOICE-IOS` | OPEN | Before iOS as supported target |
| P3.8 | Invite / self-service onboarding completeness | REQUIREMENTS | OPEN | |
| P3.9 | Admin list scalability (search/filter/pagination) | Phase 5 deferrals | OPEN | |
| P3.10 | Multi-tenant admin (one admin → many tenants) | Phase 8+ | OPEN | Needs auth-model ADR |
| P3.11 | GCS logo upload (URL-only today) | Phase 5 deferrals | OPEN | |
| P3.12 | Facility catalog management UI | Phase 5 deferrals | OPEN | |

---

## P4 — Portfolio / maintainability polish

| # | Action | Status | Notes |
|---|--------|--------|-------|
| P4.1 | Update README architecture diagram after each major phase | OPEN | Keep mermaid + stack current |
| P4.2 | Archive or rewrite stale `docs/roadmap.md` | OPEN | Points at old phase order |
| P4.3 | Consistent public naming (SlotSense vs sport_slot) | OPEN | Repo name kept for URL stability |
| P4.4 | Stand up TEST env before first real tenant | OPEN | Three-env non-negotiable in REQUIREMENTS |
| P4.5 | Keep `docs/backlog.md` as canonical tracked work | OPEN | Prefer one living list |
| P4.6 | Broad production-maturity assessment after PR-2 | `PROJECT-ASSESSMENT` | OPEN | Evidence-cited findings |

---

## Suggested sequencing (next 30 days)

```text
Week 1:  P0.1–P0.3 (voice gates) + P0.5 (IAM TF) + P0.11 (doc truth)
Week 2:  P0.6–P0.7 (observability + backup alert) + P0.8–P0.10 (CI security honesty)
Week 3:  P1.5–P1.6 (Armor + WIF) + P2.3 smoke E2E + P2.5–P2.6 voice hygiene
Week 4:  P1.7–P1.10 (availability/cost) planning ADRs; start P1.1 CMEK design if prod target fixed
```

Adjust order if a hard prod cutover date appears earlier.

---

## Definition of “production-ready enough”

Treat production readiness as met only when **all** of the following are true:

- [ ] Voice hard gates (duration + rate limit) enforced server-side  
- [ ] Baseline IAM fully codified and importable  
- [ ] Uptime + error + backup failure alerts firing to a human inbox  
- [ ] CI security controls match (or docs no longer claim) Binary Auth / audit / secret scan  
- [ ] CMEK + MFA for admins + pen-test plan accepted (or residual risk signed)  
- [ ] DPDP notice/purpose for voice + transfer status documented  
- [ ] Smoke E2E green on every main deploy  
- [ ] Billing budget + maxScale decision documented  

Until then, keep environment labeled **dev / pre-prod** and avoid resident-facing promises.

---

## How to use this file

1. Tick statuses as work lands (and mirror into `docs/backlog.md`).  
2. Do not invent “done” without CI or Terraform evidence.  
3. Prefer measured gates (coverage, latency, cost) over aspirational thresholds.  
4. Link closing PRs in the Notes column when merging.
