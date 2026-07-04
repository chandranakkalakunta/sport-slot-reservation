# ADR-0030: Booking-Model v2 — Weekly Multi-Range Facility Schedule

## Status
Accepted

## Context
Facilities previously supported one continuous open_time/close_time range
per day, applied identically every day of the week. Real facilities need
split hours (e.g. a pool open 06:00-09:00 and 16:00-21:00, closed midday)
and different hours on different days (e.g. closed Sundays).

## Decision
1. Facility documents replace `open_time`/`close_time` (flat strings) with
   `weekly_schedule: dict[str, list[TimeRange]]`, keyed by lowercase day
   name (`monday`..`sunday`). Each `TimeRange` is `{start: "HH:MM", end: "HH:MM"}`.
   An empty list for a day means closed. This is a hard cutover — no
   backward-compatible field, no migration script — since the project is
   still in dev with no production data (superseded consideration:
   revisit if pre-launch data ever needs preserving).
2. `slot_duration_minutes` remains a single facility-wide value, unchanged.
3. Day-of-week resolution happens **inside** `compute_slots`, not at the
   caller level. The function's signature (`facility: dict, date, ...`)
   is unchanged; internally it resolves `date`'s weekday in the tenant's
   timezone, looks up that day's ranges, and loops the existing
   slot-increment logic once per range. `create_booking` and the agent
   orchestrator require zero changes, since both consume `compute_slots`/
   `get_availability` as a black box.
4. `FacilityUpdate.weekly_schedule` is a whole-object field — PATCH
   requests must submit the complete 7-day schedule, not a partial day.
   This avoids Firestore map-merge ambiguity.
5. `TimeRange` values are validated: HH:MM format, `start < end`
   (same-day ranges only — no midnight-spanning ranges), and ranges
   within a day must be non-overlapping and chronologically ordered.

## Alternatives Considered
- **Explicit per-slot list instead of ranges**: rejected — more data to
  store and edit, less natural for the admin's day-by-day range-picker UX.
- **Resolve weekday at the caller level**: rejected — would duplicate
  timezone/weekday logic across `create_booking` and the orchestrator
  instead of keeping it in the single function both already depend on.
- **Per-day slot_duration**: deferred — not requested, larger scope.

## Consequences
- All backend test fixtures using `open_time`/`close_time` need updating
  to `weekly_schedule` (see sub-phase v2.1 test list).
- The two frontend Facility interfaces (`bookingHooks.ts`, `tenantAdminHooks.ts`)
  are updated independently, not consolidated — tracked as backlog cleanup.
- Tenant-admin facility create/edit form breaks between v2.1 and v2.2
  merging (expected, dev-only, no external users).
