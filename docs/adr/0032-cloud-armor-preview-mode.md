# ADR-0032 — Cloud Armor WAF, Preview Mode

**Status:** Accepted  
**Date:** 2026-07-05  
**Phase:** 8b.5

---

## Context

The Global External HTTPS Load Balancer (ADR-0031) fronts two distinct
backend types:

| Backend | Resource type | Cloud Armor policy type |
|---------|--------------|------------------------|
| API (Cloud Run NEG) | `google_compute_backend_service` | `CLOUD_ARMOR` |
| Frontend (GCS bucket) | `google_compute_backend_bucket` | `CLOUD_ARMOR_EDGE` |

GCP requires different policy types for these two resource kinds.
`security_policy` on a `google_compute_backend_service` accepts a
`CLOUD_ARMOR` policy. `edge_security_policy` on a
`google_compute_backend_bucket` accepts a `CLOUD_ARMOR_EDGE` policy.
Using `security_policy` on a backend bucket is not supported by the
GCP provider (confirmed via provider 6.50.0 schema).

### DDoS clarification

Base L3/L4 DDoS protection is already provided automatically and at no
additional cost by GCP's Global External HTTPS Load Balancer
infrastructure, regardless of whether Cloud Armor is attached. This
phase adds L7 WAF inspection only — it does not replace or supplement
L3/L4 DDoS protection.

### WAF rule set selection

Google's current recommendation for new deployments is CRS 4.22
(`sqli-v422-stable`, `xss-v422-stable`). The older CRS 3.3 sets
(`sqli-v33-stable`, `xss-v33-stable`) are still supported but
explicitly discouraged for new policies. CRS 4.22 was chosen here.

Sensitivity level 1 is the most conservative starting point per
Google's own preview-rollout tuning guidance — it minimises false
positives while the policy is in preview and logs are being reviewed.

### Rate limiting

Rate limiting was considered and explicitly deferred. SlotsenseAI has a
known booking-window flash-traffic pattern (the 20:00 IST nightly rush).
Setting a rate threshold without real traffic baselines risks blocking
legitimate users during that spike. This will be revisited after at
least one full booking-window cycle of preview logs is available.

### Adaptive Protection

Cloud Armor Adaptive Protection requires a Cloud Armor Enterprise
subscription (paid tier). This has not been decided for this project.
Adaptive Protection is out of scope until a subscription decision is
made.

---

## Decision

1. **Two separate Cloud Armor policies** are created:
   - `google_compute_security_policy.api` — type `CLOUD_ARMOR`,
     attached to `google_compute_backend_service.api` via
     `security_policy`.
   - `google_compute_security_policy.frontend_edge` — type
     `CLOUD_ARMOR_EDGE`, attached to `google_compute_backend_bucket.frontend`
     via `edge_security_policy`.

2. **Preview mode only** — every WAF rule has `preview = true`. No
   traffic is blocked. All rule matches are logged to Cloud Logging
   for review. This is a deliberate, reversible first step before any
   enforcement decision.

3. **Default rule** — both policies include a priority 2147483647
   default rule (`match "*"`, action `"allow"`). We are not adopting a
   default-deny posture at this stage; that is a larger separate
   decision requiring explicit sign-off.

4. **WAF rules** — `sqli-v422-stable` and `xss-v422-stable` (CRS 4.22),
   sensitivity level 1, priority 1000 and 2000 respectively, on both
   policies.

5. **No rate limiting** — deferred pending real traffic data (see above).

6. **No Adaptive Protection** — deferred pending subscription decision
   (see above).

---

## Consequences

### Positive

- L7 WAF inspection is activated in log-only mode. SQL injection and
  XSS patterns detected by CRS 4.22 will appear in Cloud Logging under
  `jsonPayload.enforcedSecurityPolicy` (action `"PREVIEW"` not `"DENY"`).
- Zero risk of blocking legitimate traffic during preview.
- The DDoS layer (L3/L4) continues to operate independently of this
  policy, as it always has.
- Both policies can be promoted to enforcement independently, at
  different times, if log review supports it.

### Negative / risks

- Preview produces logs but blocks nothing — any attack succeeding
  during this window is not stopped at the WAF layer (though the API
  itself must still defend against it).
- Two separate policies to manage; rule updates must be applied to both
  unless a shared rule structure is introduced later.

---

## Next steps (before enforcement)

1. After `terraform apply`, monitor Cloud Logging for Cloud Armor
   preview hits, especially around a real 20:00 IST booking-window
   event.
2. Review false-positive rate. If sensitivity 1 produces no false
   positives after several booking windows, consider raising to
   sensitivity 2.
3. Collect peak booking-window RPS data before sizing any rate-limiting
   threshold.
4. Obtain baseline before deciding on Cloud Armor Enterprise /
   Adaptive Protection.
5. When ready to enforce, set `preview = false` on specific rules one
   at a time, not as a bulk change.
