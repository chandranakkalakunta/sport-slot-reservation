# Phase 3 Retrospective — Booking Engine

Period: 2026-06-12 · Sub-phases 3.1–3.6
Outcome: full booking lifecycle live — computed availability,
Redis-locked transactional creation, buffer-enforced cancellation
with attribution, synchronous Firestore audit trail. Every guard
(role, window, horizon, quota, contention, fail-closed) validated
live by the Coordinator.

## Issue log

| # | Symptom | Root cause | Resolution | Rule adopted |
|---|---------|-----------|------------|--------------|
| 1 | Worker reports repeatedly proposed off-roadmap next steps (BigQuery audit, email hooks) | Worker editorializing beyond its role | Strategist trims each report against the roadmap | Worker "next" suggestions are input, never plan |
| 2 | In-progress slots were silently bookable for remaining time | compute_slots marks past at slot END; behavior was emergent, not decided | Decided: keep, mark reason=IN_PROGRESS + booking notice (ADR-0010 behavior, 3.6) | Emergent behaviors found in validation get an explicit ruling, never silence |
| 3 | Live validation curls returned empty bodies and could read as passes | curl -s hides connection failure; dev server was down | Re-run with -w "%{http_code}" | Validation curls always print the status code |
| 4 | Sync-audit / no-BigQuery decision existed only in conversation | Decision made mid-discussion without a home | ADR-0011 written same sub-phase | Every decision lands in an ADR or it does not exist |

## Design observations
- Cancelled bookings free slots and quota automatically because
  both queries filter on status=confirmed — one filter, two
  correct behaviors, zero extra code.
- The tenant-clock decision (3.3) proved itself in validation:
  past/window states tracked IST while the server ran UTC.
- Fail Closed demonstrated live: Redis stopped → 503
  LOCK_UNAVAILABLE, never a lock bypass.

## Carried forward
- Concurrency proof script ships in 3.6; run against local now,
  against the deployed service after Phase 4 DNS.
- Cloud redeploy with VPC egress + Secret Manager wiring pending
  (Coordinator: build-push + deploy-dev).
- In-progress booking UI warning is a Phase 4 frontend task
  (backend notice field ready).
- Memorystore cost clock started 2026-06-12 12:47 UTC
  (~₹2.5–3K/month, trial-funded).
