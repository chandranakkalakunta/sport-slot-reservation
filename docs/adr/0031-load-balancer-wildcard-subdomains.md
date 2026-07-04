# ADR-0031: Global External HTTPS Load Balancer + Wildcard Subdomain Routing

## Status
Accepted

## Context
ADR-0012 (Phase 4) deferred true wildcard subdomain routing to a
future Global External HTTPS Load Balancer, since classic Firebase
Hosting cannot support wildcard custom domains (20-subdomain cap,
no wildcard cert support). That deferred work was never started —
investigation confirmed zero DNS records, zero GCP compute
resources, and no named-subdomain DEV stage was ever actually built.
This is a clean-slate implementation, not a migration.

Target domain is *.slotsense.chandraailabs.com (not
sportbook.chandraailabs.com as originally named in ADR-0012 — the
product has since been renamed to SlotSense). A future migration to
a dedicated slotsense.in domain is planned but not yet purchased;
this architecture is designed so that migration is DNS/cert-only
(new wildcard record + cert pointing at the same LB), requiring only
a config change to base_domain/admin_host settings, not application
logic changes — confirmed via investigation that tenant resolution
reads these as configured values, not hardcoded strings.

## Decision
1. A single Global External HTTPS Load Balancer serves all
   *.slotsense.chandraailabs.com traffic. It is ADDITIVE to the
   existing Firebase Hosting setup — sport-slot-dev.web.app and
   sport-slot-dev.firebaseapp.com continue to work unchanged. The
   LB is a new, separate ingress path for tenant subdomain traffic
   only.
2. URL map routes /api/**, /health, /readyz to a Cloud Run
   serverless NEG (same sport-slot-api service already in use);
   all other paths route to a GCS bucket backend serving the built
   frontend (the same build output Firebase Hosting already serves),
   preserving the same-origin, zero-CORS property that ADR-0012
   established via Firebase rewrites, achieved here via LB URL map
   path rules instead.
3. Cloud Armor attaches to this LB's backend service(s) as a WAF
   policy, applying uniformly to all tenant traffic through this
   ingress (separate sub-phase).
4. Cloud Run ingress will be restricted to "Internal + Load
   Balancing only" as the FINAL step of this phase, closing the
   X-Forwarded-Host spoofing surface noted as an open VERIFY-ITEM
   in ADR-0012 (direct *.run.app calls could previously set an
   arbitrary X-Forwarded-Host; JWT remains the authoritative tenant
   source regardless, per existing middleware design — this closes
   the surface, it does not fix an existing vulnerability, since
   JWT was never bypassed). This is done last, after the LB path is
   confirmed working end-to-end, to avoid breaking existing direct
   access before the replacement is proven.
5. Terraform (terraform/) manages all new networking resources,
   following the existing one-concern-per-file convention
   (load_balancer_network.tf, load_balancer_backends.tf). APIs
   (compute.googleapis.com, networksecurity.googleapis.com) are
   enabled via gcloud CLI and documented in apis.tf's locals list,
   matching the existing pattern for all prior API enablement — not
   managed as Terraform resources.
6. base_domain and admin_host settings update from
   sportbook.chandraailabs.com to slotsense.chandraailabs.com
   (separate sub-phase, application-layer change).

## Alternatives Considered
- Retiring Firebase Hosting entirely in favor of the LB: rejected —
  unnecessary risk to the currently-working dev access path for no
  benefit; the LB is additive, not a replacement.
- Managing API enablement via Terraform project_service resources:
  rejected — inconsistent with the established, working pattern for
  all 18 existing APIs; would require importing all of them to avoid
  a mixed-management state.

## Consequences
- Real fixed monthly cost (~$18-25+ for LB + Cloud Armor baseline,
  before usage) — a new cost category for this project, distinct
  from the pay-per-use profile of everything built so far. Accepted
  given available budget and portfolio value.
- Two parallel ingress paths exist going forward (Firebase Hosting
  for direct dev access, LB for tenant subdomains) until/unless a
  future decision consolidates them.
- Migrating to slotsense.in later is expected to be DNS/cert-only;
  this assumption should be re-verified when that migration is
  actually planned, not assumed permanently true.
