# Phase 17 — Production Readiness: Close-Out & Retrospective

**Status:** Build COMPLETE (2026-07-21). Remaining: timed DR drill /
TEST-env (formal phase close).
**Span:** 2026-07-14 → 2026-07-21.

## Audit findings scoreboard (2026-07-13 baseline → now)

| # | Finding | Resolution | Where |
|---|---|---|---|
| 1 | Firestore zero recovery (PITR off, no backups) | CLOSED — PITR + delete protection + daily backup schedule | PR-1a / ADR-0038 |
| 2 | No alerting, no uptime checks | CLOSED — uptime check, 4 alert policies, channels fire-tested live | PR-2 / ADR-0040 |
| 3 | Redis SPOF (BASIC, fail-closed) | CLOSED as DECISION — BASIC accepted w/ triggers; fail-closed affirmed correct | PR-3 / ADR-0041 D16 |
| 4 | Rebuild-from-Terraform incomplete | CLOSED — SAs, IAM, Cloud Run, Redis, AR all codified | PR-1b / ADR-0038 L3 |
| 5 | No cost guardrail | CLOSED — billing budget, 5 graduated thresholds, alert-only | PR-4 / ADR-0042 |
| 6 | Unversioned state/invoice buckets | CLOSED — versioning + lifecycle (tfstate found already-versioned) | PR-1a |
| 7 | Cloud Armor non-enforcing | CLOSED — API WAF enforce w/ scoped voice exemption (preview-log gate caught a would-be voice outage) | PR-5c / ADR-0043 |
| 8 | Thin Cloud Run headroom, no liveness | CLOSED — maxScale 10, HTTP startup + liveness probes | PR-3 / ADR-0041 D15 |
| 9 | Minimal CI scanning; WIF over-privileged | CLOSED — Trivy + dep audit + gitleaks + pip-audit; WIF → task-scoped | DOC-TRUTH, PR-5a, PR-5b |
| 10 | BinAuthz off, no rotation, Error Reporting off | PARTIAL — Error Reporting on, rotation policy documented; BinAuthz deliberately deferred to Phase 18 | PR-2, PR-5a, ADR-0043 |

Plus the third-party review's headline finding — **doc drift** (claims
outrunning enforcement) — closed in DOC-TRUTH.

## Sub-phase ledger

- **Stop-gap** (2026-07-14): PITR + delete protection, Coordinator-run.
- **PR-1a** (#141): backup foundations — schedule, bucket versioning, secret shells, DR runbook skeleton, ADR-0038.
- **PR-1b** (#142): IAM-TF-CODIFY — 4 SAs, 16 IAM bindings, Cloud Run, Redis, Artifact Registry imported; closed the project's oldest HIGH item.
- **DOC-TRUTH** (#143): doc/CI reconciliation, ADR-0039 residuals, Phase 16/17 numbering, pip-audit + gitleaks, review snapshots.
- **PR-2** (#144–#147): observability — channels, uptime check, 4 alert policies, 3 log metrics, Error Reporting, edge-only after ingress correction.
- **PR-3** (#148–#150): availability — maxScale 10, health probes, SLO definition, Ops dashboard, Redis decision.
- **PR-4** (#151 + hotfixes): cost — billing budget, 5 thresholds, alert-only. Hardest API of the phase.
- **PR-5a** (#153): security headers, CI container/dep scanning, registry cleanup, rotation policy.
- **PR-5b** (#154): WIF least-privilege (evidence-driven custom role) + the Armor preview-log review.
- **PR-5c** (#155): Cloud Armor enforce with scoped voice exemption.

## Lessons earned → protocol v3.8 candidates

API-shape (all invisible to plan/validate; only apply/live reveals):
- Blank gcloud `--format` column = key-not-found, not "false" (§5.38).
- MQL `ratio` is a table op, not a function; use `sum(if())/sum()`.
- `notification_rate_limit` legal only on log-match alert policies.
- Log-metric alert filters must pair with the metric's real resource type.
- Cloud Run ingress `internal-and-cloud-load-balancing` rejects direct `*.run.app` probes — probe the edge, not the service URL.
- Monitoring resources can't be destroyed while an alert policy references them.
- Cloud Run probe conversions must preserve TOTAL startup budget (threshold × period), not translate fields 1-for-1 — a 1×10s probe killed a revision.
- `google_monitoring_dashboard` perma-diffs on API-normalized JSON (injects targetAxis, omits zero positions) — align config to canonical form.
- Billing Budget API: opaque 400s; isolate by removing optional blocks until base creates, then re-add ONE at a time; SUSPECT `data`-source-resolved and SMS channels as budget targets specifically. **Meta: for a bare "invalid argument", `TF_LOG=JSON` to a file + grep `fieldViolations` is the authoritative first move, not the last.**
- `run.developer` lacks `run.services.setIamPolicy` (needed for `--allow-unauthenticated`) — verify role sufficiency LIVE before swapping.

Process:
- **merge ≠ applied for infra PRs.** Twice this phase a merged PR's apply was skipped, surfacing later as unexplained plan drift. Sub-phase close checklist must include "apply confirmed + clean plan from main," not just "merged."
- Config-driven `import` blocks over CLI imports for bulk adoption.
- Never plan/apply from main during an import window; `prevent_destroy` doesn't protect a resource whose config block is absent.
- Shell chains don't stop on failure — order-dependent Coordinator steps issued discretely with gates.
- Worker/Coordinator forensically indistinguishable (shared creds); command logs + state-generation timestamps are the arbiters.
- `.claude/settings.json` deny rules enforce protocol command-class bans structurally — instructions drift, config enforces.
- The `set-quota-project` step belongs in the §5.22 auth ritual (user-ADC + quota-gated APIs like billingbudgets).
- WIF/Armor "look before you leap" gates paid off concretely — the Armor preview-log review caught a would-be live voice outage before any flip.

## Open threads carried forward

1. **PR-4 channel note** — confirm which channel (email vs SMS) is wired to the budget; amend ADR-0042's "backup emails stay" line (already known false — API made recipients mutually exclusive).
2. **VOICE-INPUT-VALIDATION** (backlog, Phase 18) — the durable SQLi/XSS defense for the WAF-exempt voice path. Not optional; the Armor exemption's honest counterpart.
3. **Timed DR drill / TEST-env** — the last item to formally close Phase 17; doubles as the slot-sense-test environment build (Coordinator half-day).
4. **frontend_edge** Armor — documented as intentional pass-through (edge policy type can't hold WAF rules); no action.
5. **CI-AUDIT-RATCHET** — flip Trivy/pip-audit/dep-audit warn→blocking after a triage pass (note: Trivy already surfaced a critical in the eslint/js-yaml chain — confirm dev-only).
