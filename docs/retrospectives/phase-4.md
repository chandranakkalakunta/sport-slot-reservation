# Phase 4 Retrospective — Frontend Foundation

Period: 2026-06-13 · Sub-phases 4.1–4.6 (4.5b custom domain
deferred to Phase 7)
Outcome: React PWA live on sport-slot-dev.web.app — full resident
lifecycle (browse, book, view, cancel) over the public edge,
same-origin API via Hosting rewrites, per-tenant branding from the
tenant document.

## Issue log

| # | Symptom | Root cause | Resolution | Rule adopted |
|---|---------|-----------|------------|--------------|
| 1 | Pre-flight expected absent files; Phase 1 stubs present (4th occurrence) | Phase 1 inventory seeded placeholder files tree-wide | Worker STOP + overwrite confirmation | Pre-flights touching a top-level dir for the first time expect stubs, not absence (generalizes Phase 2 issue 3) |
| 2 | New frontend/src/lib/ silently un-committed | Unanchored .gitignore "lib/" (Python) matched the frontend path | Negation added; anchor properly logged | Gitignore patterns in a polyglot monorepo must be path-anchored |
| 3 | Facilities "Loading…" forever, then 500 | Local ADC impersonation token expired | gcloud auth application-default login re-auth | Dev ADC expires by design (no static keys); re-auth is routine, documented in runbook |
| 4 | Booking 409 produced no user feedback | Dialog closed on error; feedback ambiguous | Errors surface in-dialog, dialog stays open, per-attempt feedback | Validate the error path in the UI, not just the happy path |
| 5 | Public .web.app 403 on every API call | Deployed Cloud Run image predated the X-Forwarded-Host middleware | Redeploy backend | Deployed frontend + backend are independently versioned; redeploy Cloud Run before validating on .web.app |
| 6 | Production fail-closed test inverted | None-candidate-host rule intentionally trusts JWT for unrecognized hosts | Test renamed + expectation updated, flagged | A relaxed guard is acceptable only when a stronger control (JWT) is authoritative — and must be consciously recorded |

## Verify-first wins
- Firebase classic Hosting wildcard limit (20 subdomains/apex)
  caught at design time → named subdomains now, LB wildcard Phase 7.
- X-Forwarded-Host as the rewrite's host carrier confirmed before
  the middleware change, not during debugging.

## Decisions of note
- ADR-0012 (hosting, same-origin rewrites, CSS-variable theming),
  ADR-0013 (error presentation / i18n staging).
- Cloud Run public ingress logged as a time-boxed accepted exposure
  (charter); closed in Phase 7 with the load balancer.
- Custom domain (4.5b) deferred to Phase 7 to pair with the LB +
  wildcard cert + Cloud Armor rather than a one-off named subdomain.

## Carried forward
- 4.5b: custom domain on chandraailabs.com (personal site is also
  Firebase-hosted — connect demo.sportbook subdomain to sport-slot-dev
  WITHOUT touching apex records; verify Firebase cross-project
  subdomain rules first).
- Tenant-admin UI (facility CRUD, policy/branding editing) — earliest
  Phase 5+; branding fields currently seeded/edited manually.
- AuthContext react-refresh lint warning (cosmetic, accepted).
