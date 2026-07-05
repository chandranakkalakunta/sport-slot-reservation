# ADR-0033 — Deprecate sport-slot-dev.web.app API Path; Restrict Cloud Run Ingress

**Status:** Accepted  
**Date:** 2026-07-05  
**Phase:** 8b.6

---

## Context

SlotsenseAI has two paths that could reach the Cloud Run API:

| Path | How traffic reaches Cloud Run |
|------|-------------------------------|
| `*.slotsense.chandraailabs.com` | GCP Global External HTTPS Load Balancer → Serverless NEG → Cloud Run |
| `sport-slot-dev.web.app/api/**` | Firebase Hosting rewrite → Cloud Run via the `*.run.app` URL |

Phase 8b introduced the LB path (ADR-0031). Firebase Hosting's rewrite path pre-dates it and
remained active alongside it.

### The X-Forwarded-Host spoofing surface

ADR-0012 noted an open VERIFY-ITEM: with Cloud Run ingress set to `all` (the default),
anyone knowing the `*.run.app` URL can send arbitrary `X-Forwarded-Host` headers directly
to Cloud Run, bypassing the LB's validated host. Restricting ingress to
`internal-and-cloud-load-balancing` closes this surface — traffic that reaches Cloud Run
via the LB has its `X-Forwarded-Host` set by the LB itself (trusted), while direct
`*.run.app` calls are dropped at the ingress layer before reaching the application.

### Firebase Hosting incompatibility (confirmed)

Firebase Hosting's rewrite mechanism reaches Cloud Run via the public `*.run.app` URL from
Firebase's own network. GCP's Cloud Run ingress documentation explicitly classifies the
following services as internal traffic: Cloud Scheduler, Cloud Tasks, Dialogflow CX,
Eventarc, Pub/Sub, Synthetic monitors, Workflows, BigQuery. **Firebase Hosting is not
in this list.** It is instead listed under "services that break when the run.app URL is
disabled", confirming its external routing path.

Therefore, restricting ingress to `internal-and-cloud-load-balancing` categorically blocks
Firebase Hosting rewrites. The `sport-slot-dev.web.app/api/**`, `/health`, and `/readyz`
rewrite paths in `firebase.json` become non-functional after this change.

### Cloud Tasks compatibility (confirmed)

Cloud Tasks is explicitly listed in GCP's internal-traffic list for Cloud Run ingress,
provided it is in the same project and dispatches to the `*.run.app` URL. Both conditions
hold: the `notifications` queue is in `sport-slot-dev`, and `SPORTSLOT_WORKER_BASE_URL`
is set to `status.url` (the `*.run.app` URL) at deploy time. Notification emails are
unaffected.

### gcloud run deploy ingress persistence

`gcloud run deploy --help` shows `--ingress` with `default="all"`. This means every deploy
without an explicit flag resets ingress to `all`. To prevent CI from silently undoing the
restriction on every deploy, `--ingress=internal-and-cloud-load-balancing` was added
explicitly to `scripts/deploy_cloud_run.sh`.

---

## Decision

1. **Restrict Cloud Run ingress** to `internal-and-cloud-load-balancing` (applied via
   `gcloud run services update` by the Coordinator; locked in for future deploys via the
   `--ingress` flag in `deploy_cloud_run.sh`).

2. **Accept Firebase Hosting path breakage.** This is a DEV environment. No real tenant
   traffic depends on `sport-slot-dev.web.app` today. The intentional production path is
   `*.slotsense.chandraailabs.com` via the LB.

3. **Update `reset_continue_url` and `welcome_login_url`** in `config.py` from
   `sport-slot-dev.web.app` to `slotsense.chandraailabs.com`. These are public auth routes
   (password reset, welcome email sign-in link) — no tenant subdomain in the URL shape
   because the token carries all user context.

4. **`firebase.json` rewrites are left in place** — removing them is a separate cleanup
   decision. They are inert once ingress is restricted but do not cause harm.

---

## Consequences

### Positive

- Closes the `X-Forwarded-Host` spoofing surface identified in ADR-0012: direct
  `*.run.app` access is rejected at the network layer before reaching the application.
- Email deep-links (password reset, welcome) now point to the canonical production domain.
- Ingress restriction is codified in the deploy script — it survives CI deploys without
  manual intervention.
- Cloud Tasks notification pipeline is unaffected.

### Negative / risks

- `sport-slot-dev.web.app/api/**` returns 404 after the ingress change is applied.
  Any developer or tool still testing against the Firebase Hosting URL will see failures.
- `sport-slot-dev.web.app/health` and `/readyz` probes also stop working (though no
  automated monitoring targets these).

---

## Future production note

On a live system with real tenant traffic, this restriction should only be applied **after**
confirming that 100% of tenant traffic flows through the LB domain
(`*.slotsense.chandraailabs.com` or its eventual `*.slotsense.in` successor) and zero
clients are using the Firebase Hosting or raw `*.run.app` path. Applying this change
prematurely on a live multi-tenant system would silently break any client still routed
through Firebase Hosting.
