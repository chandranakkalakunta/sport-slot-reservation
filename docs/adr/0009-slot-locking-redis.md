# ADR-0009: Slot Locking — Memorystore Redis

Status: Accepted | Date: 2026-06-12 | Author: Chandra Nakkalakunta

## Context
ADR-0002 mandates Redis distributed locks against double-booking.
Phase 3 implements booking creation; the lock backend must be
fixed now. A Firestore-transaction-only alternative was considered
to defer Redis cost.

## Decision
Memorystore Redis, Basic tier, 1 GB, asia-south1, provisioned in
Phase 3 (DEV). Cloud Run reaches it via Direct VPC egress (or a
Serverless VPC Access connector if Direct egress is unavailable in
region). Lock pattern: SET key NX PX <ttl> on the deterministic
booking key {tenant}:{facility}:{date}:{start}; release on
completion; TTL guards against orphaned locks (Fail Closed: Redis
unreachable → booking creation pauses with 503 envelope, never
bypasses the lock).
Cost: ~₹2,500–3,000/month, fully absorbed by trial credits through
Sep 2026; post-trial DEV burn ~₹3K against the ₹5K ADR-0005
ceiling. A LockService interface isolates the implementation.

## Alternatives
Firestore-transaction-only locking: zero new infra and atomically
safe at DEV traffic, but hot-document contention degrades under
the 20:00 flash; deferring Redis would rebuild the booking path on
different machinery later. Rejected in favor of prod parity now,
funded by trial credits.

## Consequences
+ Booking path built once, on its production locking mechanism.
+ Redis available for Phase 3 rate-limit upgrade (ADR-0007 §5).
− Always-on instance; first recurring infra cost.
− VPC egress configuration added to deploy surface.

## References
ADR-0002, ADR-0005, ADR-0007 §5, Charter (Fail Closed).
