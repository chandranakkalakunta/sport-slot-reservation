# Phase 8b Engineering Report: Production Networking

**Phase:** 8b — Production Networking  
**Date:** July 2026  
**PR range:** #80 – #91 (12 PRs)  
**Terraform lines added:** 384 insertions across 5 `.tf` files  
**Backend tests:** 378 passed throughout (no regressions)

---

## Terraform file structure added

| File | Purpose |
|------|---------|
| `terraform/load_balancer_network.tf` | Static global IP + Certificate Manager wildcard TLS cert, DNS authorization, cert map, cert map entry |
| `terraform/load_balancer_backends.tf` | GCS frontend bucket, backend bucket (CDN enabled), Cloud Run serverless NEG, API backend service; Cloud Armor policy attachments |
| `terraform/load_balancer_routing.tf` | HTTPS URL map (host rule, path matcher, path rules, SPA fallback, root-path rewrite); HTTPS target proxy; HTTP redirect URL map + proxy; global forwarding rules (ports 80 + 443) |
| `terraform/cloud_armor.tf` | `CLOUD_ARMOR` policy for API backend (`slotsense-api-armor`); `CLOUD_ARMOR_EDGE` policy for frontend bucket (`slotsense-frontend-edge-armor`) |
| `terraform/apis.tf` | Added `compute.googleapis.com` and `networksecurity.googleapis.com` to enabled APIs |

---

## Final resource inventory

### `google_certificate_manager_*`

| Resource | Name in GCP | Purpose |
|----------|-------------|---------|
| `google_certificate_manager_dns_authorization.slotsense` | `slotsense-dns-auth` | DNS authorization record for Certificate Manager wildcard cert validation |
| `google_certificate_manager_certificate.slotsense_wildcard_cert` | `slotsense-wildcard-cert` | Wildcard TLS cert covering `*.slotsense.chandraailabs.com` |
| `google_certificate_manager_certificate_map.slotsense` | `slotsense-cert-map` | Certificate map referenced by the HTTPS target proxy |
| `google_certificate_manager_certificate_map_entry.slotsense_wildcard` | `slotsense-wildcard-entry` | Binds the wildcard cert into the cert map |

### `google_compute_*`

| Resource | Name in GCP | Purpose |
|----------|-------------|---------|
| `google_compute_global_address.slotsense_lb_ip` | `slotsense-lb-ip` | Static global anycast IP shared by ports 80 and 443 forwarding rules |
| `google_compute_backend_bucket.frontend` | `slotsense-frontend-bucket` | LB attachment for GCS bucket; Cloud CDN enabled with `USE_ORIGIN_HEADERS`; `edge_security_policy` attached |
| `google_compute_region_network_endpoint_group.api_neg` | `slotsense-api-neg` | Serverless NEG (asia-south1) pointing at the `sport-slot-api` Cloud Run service |
| `google_compute_backend_service.api` | `slotsense-api-backend` | Global backend service wrapping the NEG; `security_policy` (Cloud Armor) attached; request logging enabled (100% sample rate) |
| `google_compute_url_map.slotsense_https` | `slotsense-https-url-map` | Main HTTPS routing: host rule for `*.slotsense.chandraailabs.com`, path rules for `/`, `/api/*`, `/health`, `/readyz`, SPA 404 catch-all |
| `google_compute_url_map.slotsense_http_redirect` | `slotsense-http-redirect` | HTTP → HTTPS 301 redirect for all traffic on port 80 |
| `google_compute_target_https_proxy.slotsense` | `slotsense-https-proxy` | Terminates TLS using the Certificate Manager cert map |
| `google_compute_target_http_proxy.slotsense_redirect` | `slotsense-http-proxy` | Proxy for HTTP redirect URL map |
| `google_compute_global_forwarding_rule.slotsense_https` | `slotsense-https-forwarding-rule` | Port 443 → HTTPS proxy; `EXTERNAL_MANAGED` scheme |
| `google_compute_global_forwarding_rule.slotsense_http` | `slotsense-http-forwarding-rule` | Port 80 → HTTP redirect proxy; `EXTERNAL_MANAGED` scheme |
| `google_compute_security_policy.api` | `slotsense-api-armor` | `CLOUD_ARMOR` WAF policy: SQLi + XSS CRS 4.22 sensitivity 1, all rules `preview = true` |
| `google_compute_security_policy.frontend_edge` | `slotsense-frontend-edge-armor` | `CLOUD_ARMOR_EDGE` policy: default allow only (WAF expressions not supported on edge policies) |

### `google_storage_*`

| Resource | Name in GCP | Purpose |
|----------|-------------|---------|
| `google_storage_bucket.frontend` | `sport-slot-dev-frontend` | GCS bucket storing `frontend/dist/` output; `uniform_bucket_level_access = true`; `ASIA-SOUTH1` |
| `google_storage_bucket_iam_member.frontend_public_read` | — | `allUsers:roles/storage.objectViewer` — public read for static asset serving |

---

## URL map routing logic

The `slotsense-paths` path_matcher within `google_compute_url_map.slotsense_https`
evaluates rules in this order (most specific match wins):

| Priority | Path(s) | Action | Backend |
|----------|---------|--------|---------|
| 1 | `/` | `route_action { url_rewrite { path_prefix_rewrite = "/index.html" } }` | `frontend` bucket |
| 2 | `/api/*`, `/health`, `/readyz` | Forward | `api` backend service (Cloud Run) |
| 3 (default) | everything else | Forward | `frontend` bucket |
| 3 (error policy) | 404 responses from GCS | Re-serve `/index.html` with HTTP 200 | `frontend` bucket |

The root-path rule (priority 1) was added post-launch after live testing revealed GCS
returns HTTP 200 with XML bucket listing for bare `/` requests (not 404), bypassing the
error response policy. The rewrite converts the request to `/index.html` before it
reaches GCS, so GCS always receives a request for a real named object.

---

## Verified end-to-end request flow

```
Browser → DNS
  *.slotsense.chandraailabs.com → 34.x.x.x (slotsense-lb-ip, static anycast)

→ Forwarding Rule (port 443)
  EXTERNAL_MANAGED → slotsense-https-proxy

→ TLS Termination
  Certificate Manager cert map → slotsense-wildcard-cert
  (covers *.slotsense.chandraailabs.com; validated via DNS authorization)

→ URL Map (slotsense-https-url-map)
  Host rule: *.slotsense.chandraailabs.com → path_matcher "slotsense-paths"

  Path rule "/" → url_rewrite to /index.html → backend bucket → GCS
  Path rule /api/* → backend service → Cloud Run NEG (asia-south1)
  Path rule /health, /readyz → backend service → Cloud Run NEG
  Default → backend bucket → GCS → CDN (USE_ORIGIN_HEADERS)
  404 from GCS → error_response_policy → /index.html (HTTP 200)

→ Cloud Run (sport-slot-api, asia-south1)
  Ingress: internal-and-cloud-load-balancing
  (direct *.run.app access blocked; LB traffic allowed)

→ FastAPI application
  X-Forwarded-Host validated → tenant slug extracted → TenantContext
  (host: {slug}.slotsense.chandraailabs.com → slug resolved correctly)

→ Response path (API)
  Cloud Run → NEG → backend service → Cloud Armor (preview, log-only) → LB → browser

→ Response path (frontend)
  GCS → backend bucket → Cloud CDN → LB → browser
  Cache-Control respected per object (no-cache on index.html; immutable on hashed assets)
```

All hops confirmed working via live `curl` tests during phase execution:
- `curl https://rvrg.slotsense.chandraailabs.com/health` → HTTP 200 JSON
- `curl https://rvrg.slotsense.chandraailabs.com/api/v1/...` → correct API responses
- `curl https://rvrg.slotsense.chandraailabs.com/` → `text/html` (index.html), not XML
- `curl https://rvrg.slotsense.chandraailabs.com/facilities/abc123` → `text/html` (SPA fallback)
- HTTP → HTTPS redirect on port 80 confirmed

---

## Cloud Armor policy state (as-applied)

Both policies applied with all rules in `preview = true`. No traffic is blocked.
Cloud Armor logs under `jsonPayload.enforcedSecurityPolicy` will show matches with action
`PREVIEW` (not `DENY`). Neither policy will enforce until explicitly changed.

**To promote a rule to enforcement** (future, post log review):
```bash
# Example: enforce SQLi rule on API policy only
# Edit cloud_armor.tf: set preview = false on the specific rule, then apply
```

**Rate limiting:** Deferred — requires booking-window traffic baseline data (ADR-0032).  
**Adaptive Protection:** Deferred — requires Cloud Armor Enterprise subscription decision (ADR-0032).

---

## Cloud Run ingress restriction

Applied via `gcloud run services update` (manual coordinator step, not Terraform-managed):
```bash
gcloud run services update sport-slot-api \
  --region asia-south1 \
  --project sport-slot-dev \
  --ingress=internal-and-cloud-load-balancing
```

Codified for future deploys in `scripts/deploy_cloud_run.sh` (line 66):
```bash
--ingress=internal-and-cloud-load-balancing \
```

**Why explicit in the script:** `gcloud run deploy --ingress` defaults to `"all"` if
omitted. Without the explicit flag, every CI deploy would silently reset the restriction.

**Confirmed compatible:** Cloud Tasks (`notifications` queue, `sa-tasks-invoker`) —
dispatches to `*.run.app` URL, same project, explicitly listed in GCP's internal-traffic
list.  
**Confirmed incompatible (accepted):** Firebase Hosting rewrites — `sport-slot-dev.web.app/api/**`
now returns 404. Accepted DEV-only tradeoff; no real tenant traffic on that path (ADR-0033).

---

## CI changes

`scripts/deploy_cloud_run.sh`: Added `--ingress=internal-and-cloud-load-balancing` flag.  
`.github/workflows/`: Added GCS sync step uploading `frontend/dist/` to
`gs://sport-slot-dev-frontend` with per-file-type `Cache-Control` metadata
(`no-cache` for `index.html`, `manifest.webmanifest`, `sw.js`; `max-age=31536000,immutable`
for hashed assets under `assets/`).

---

## ADRs produced

| ADR | Title | Key decision |
|-----|-------|-------------|
| ADR-0031 | Load Balancer + Wildcard Subdomains | Global External HTTPS LB; Certificate Manager for wildcard TLS; Cloud Run Serverless NEG; GCS backend bucket for frontend |
| ADR-0032 | Cloud Armor Preview Mode | Two-policy design; CRS 4.22 at sensitivity 1; preview-only rollout; rate limiting + Adaptive Protection deferred |
| ADR-0033 | Cloud Run Ingress Restriction | `internal-and-cloud-load-balancing`; Firebase Hosting path accepted as broken (DEV); Cloud Tasks confirmed compatible; ingress codified in deploy script |
