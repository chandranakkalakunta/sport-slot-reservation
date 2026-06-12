# ADR-0010: Booking Domain Model & Policy Resolution

Status: Accepted | Date: 2026-06-12 | Author: Chandra Nakkalakunta

## Context
Phase 3 needs facilities, slots, bookings, configurable tenant
policies, and quota enforcement.

## Decisions

### 1. Computed availability — bookings are the only stored slots
No slot documents are pre-generated. Availability derives at
request time from facility config (open/close, slot duration)
merged with that date's bookings. Booking documents use the
deterministic ID {facility_id}_{date}_{start}; transactional
create on that ID is the second double-booking guard behind the
Redis lock. Facility config changes apply FROM THE NEXT DAY ONLY,
so existing bookings never misalign with a changed grid.

### 2. Models
Facility: name, sport, slot_duration_minutes, open_time,
close_time, active. Booking: deterministic id, uid, household_id,
facility_id, date, start, end, status (confirmed|cancelled),
created_at, cancelled_at. Tenant registry document at
/tenants/{tenant_id} (PlatformRepository's first production use).

### 3. Policy resolution
PolicyService resolves Tenant Override → Global Default. Wired in
Phase 3: max_slots_per_user_per_sport_per_day, booking_horizon_days,
booking_window_open_time, cancellation_buffer_hours. Remaining
parameters get registry entries + defaults, wired as their
features arrive — no dead config surface.

### 4. Quota enforcement inside the transaction
Same-day booking count is read transactionally with the create.
Pre-check-then-create races under flash traffic; one extra
transactional read is the price of correctness. The Redis lock
guards a SLOT; quotas race ACROSS slots, so they are settled in
the Firestore transaction regardless of locking.

## Alternatives
Materialized slot documents: rejected — generation job to operate
plus ~5.8M mostly-empty documents/year at target scale.
Pre-transaction quota checks: rejected — racy.

## Consequences
+ No generation jobs; isolation and locking share one key scheme.
− Availability costs a config read + bookings query per request
  (cacheable in Phase 7).
− Next-day-only config changes must be enforced in code.

## References
ADR-0002, ADR-0006 §3, ADR-0008, ADR-0009.
