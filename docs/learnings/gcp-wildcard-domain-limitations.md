# Learning Notes: Wildcard Domain Limitations on Google Cloud

*Captured during SlotSense Phase 8b (Load Balancer + wildcard subdomain routing), July 2026.*

## Summary

We hit the same class of problem twice on this project, in two different GCP services, months apart: **an "obvious" or default approach silently doesn't support wildcard domains at all**, with no partial degradation — it's a hard rejection, not a limitation you discover gradually. Both times, the fix required switching to a different, less-obvious service built specifically for the wildcard case.

The general lesson: **when a design depends on wildcard domain/subdomain support, verify that specific capability explicitly and early — don't assume a "hosting" or "certificate" product supports wildcards just because it supports custom domains.** These are treated as separate capabilities by GCP (and, per our research, by other clouds too), and the gap between them is not always documented prominently.

---

## Case 1: Firebase Hosting cannot do wildcard custom domains

**Where this surfaced:** Phase 4, while designing multi-tenant subdomain routing (`{tenant}.sportbook.chandraailabs.com`).

**The limitation:** Classic Firebase Hosting supports custom domains, but:
- No wildcard custom domain support at all (`*.example.com` cannot be added as a Hosting custom domain)
- A hard cap of ~20 custom domains per Hosting site, each requiring its own SSL certificate provisioning

**Why this matters for multi-tenant SaaS:** "One new tenant = one new DNS + hosting config step" doesn't scale, and hits a hard ceiling at 20 tenants regardless.

**The fix (deferred until Phase 8b):** True wildcard routing requires a Global External HTTPS Load Balancer, which supports wildcard certificates and host-based routing patterns that Hosting cannot express.

**What we did in the meantime:** DEV used named subdomains added manually per tenant — an accepted, deliberate stopgap, documented in ADR-0012, understood from the start as temporary.

---

## Case 2: Classic Compute Engine Managed SSL Certificates cannot do wildcards

**Where this surfaced:** Phase 8b.1, while provisioning the actual wildcard certificate for the Load Balancer built to solve Case 1.

**The limitation:** `google_compute_managed_ssl_certificate` — the "default," most commonly documented way to attach a Google-managed cert to a Load Balancer — rejects wildcard domains outright:
Error 400: Invalid value for field 'resource.managed.domains[0]':
'*.slotsense.chandraailabs.com'. Wildcard domains not supported.

This is not a quota or permissions issue. It is a hard feature limitation of this specific certificate type, full stop.

**The fix:** **Certificate Manager** — a separate, newer GCP service — supports wildcard domains via **DNS Authorization**: instead of proving domain control through the load balancer receiving traffic (which can't express "I own this entire wildcard"), you add a specific CNAME record that only the real domain owner could add. That DNS-based proof is what unlocks wildcard issuance.

**Practical differences this introduces:**
- One extra one-time DNS record (the DNS authorization CNAME) beyond the eventual routing record — and it must **stay in place permanently**, since Google re-validates it periodically to auto-renew the certificate. Removing it breaks future renewals.
- A different attachment mechanism to the Load Balancer: Certificate Manager certs attach via a **certificate map** (`google_certificate_manager_certificate_map` + `_map_entry`), not the classic proxy's direct `ssl_certificates` list.
- Validation is not instant. Google's managed-cert validation uses **Multi-Perspective Issuance Corroboration** — checking DNS from multiple independent vantage points. A check that runs before your DNS has propagated everywhere will show a `FAILED` authorization attempt even though your own `dig` already shows the correct record — this is a stale/premature check, not a real misconfiguration. Wait for a fresh validation attempt (new timestamp) before troubleshooting further.

---

## General takeaways for future projects

1. **"Custom domain support" and "wildcard domain support" are different capabilities.** Never assume one implies the other — check explicitly.
2. **When something rejects a wildcard, look for a dedicated, newer service rather than a workaround on the same service.** Both cases here had a real, well-supported first-party solution (Load Balancer for Hosting's gap; Certificate Manager for classic certs' gap) — the fix was "use the right tool," not "hack around the limitation."
3. **DNS-based domain validation (vs. traffic-based validation) is generally what unlocks wildcard support**, across services and even across clouds — it's a pattern, not a GCP quirk.
4. **A `FAILED` state immediately after creating a DNS-dependent resource may just mean "checked before you finished setup," not "broken."** Check the timestamp of the failure against when you actually completed the DNS change before troubleshooting.
