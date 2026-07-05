# Phase 8b Retrospective: Production Networking

**Status:** Complete  
**Duration:** July 2026  
**PR range:** #80 – #91 (12 PRs)  
**ADRs added:** 0031 (Load Balancer + Wildcard Subdomains), 0032 (Cloud Armor Preview Mode), 0033 (Cloud Run Ingress Restriction / web.app path deprecated)  
**Final state:** Global External HTTPS Load Balancer live at `*.slotsense.chandraailabs.com`; wildcard TLS via Certificate Manager; Cloud Armor WAF in preview mode; Cloud Run ingress restricted to `internal-and-cloud-load-balancing`; root-path GCS bucket listing fixed via URL map rewrite; 378 backend tests green throughout.

---

## What this phase was

Phase 8b tackled the production networking stack that was deferred when Phases 9 and 10
were prioritised for product-story reasons. The goal was to move from Firebase Hosting's
implicit infrastructure (rewrites, CDN, TLS, wildcard subdomains) to an explicit,
Terraform-managed GCP stack that could be replicated cleanly into TEST and PROD
environments.

The phase was deliberately staged: 8b.1 provisioned the static IP and wildcard
certificate; 8b.2 built the backend resources (NEG, backend service, GCS bucket,
backend bucket) and routing; 8b.2b wired CI to sync the frontend build to GCS; 8b.4
propagated the new domain through config; 8b.5 added Cloud Armor WAF in preview mode;
8b.6 restricted Cloud Run ingress and deprecated the Firebase Hosting rewrite path;
and a final fix eliminated a GCS root-path bucket-listing bug surfaced by live testing.

Every sub-phase included an investigation round before implementation — this discipline
caught several incompatibilities before they were written into code.

---

## What shipped

- **Global External HTTPS Load Balancer** (`slotsense-https-url-map`) routing
  `*.slotsense.chandraailabs.com` — API traffic to Cloud Run via Serverless NEG;
  frontend traffic to GCS via backend bucket with Cloud CDN (`USE_ORIGIN_HEADERS`
  mode, respecting per-object `Cache-Control` metadata set at CI upload time).
- **Wildcard TLS certificate** via Certificate Manager + DNS authorization
  (`slotsense-dns-auth`, `slotsense-wildcard-cert`, `slotsense-cert-map`) — covering
  every tenant subdomain without per-tenant cert provisioning.
- **HTTP → HTTPS redirect** at port 80 via a separate URL map with `default_url_redirect`.
- **SPA 404 catch-all** via `default_custom_error_response_policy` on the path_matcher:
  GCS 404s (for client-side routes with no matching object) re-served as `/index.html`
  with HTTP 200 — replicating Firebase Hosting's `source: "**"` catch-all.
- **Root-path rewrite** via an explicit `path_rule` for `"/"` with `route_action {
  url_rewrite { path_prefix_rewrite = "/index.html" } }` — fixing GCS bucket-listing
  exposure on bare root requests (ADR-0031; confirmed against provider 6.50.0 schema).
- **Cloud Armor WAF** in preview mode (ADR-0032): `CLOUD_ARMOR` policy on the API
  backend service with SQLi and XSS CRS 4.22 rules at sensitivity 1; `CLOUD_ARMOR_EDGE`
  policy (default-allow only) on the frontend backend bucket. All rules `preview = true`
  — log-only, non-blocking.
- **Cloud Run ingress restricted** to `internal-and-cloud-load-balancing` (ADR-0033),
  closing the `X-Forwarded-Host` spoofing surface identified in ADR-0012. Explicitly
  codified in `scripts/deploy_cloud_run.sh` with `--ingress=internal-and-cloud-load-balancing`
  because `gcloud run deploy` defaults `--ingress` to `all` if omitted.
- **Email deep-links updated**: `reset_continue_url` and `welcome_login_url` in
  `config.py` moved from `sport-slot-dev.web.app` to `slotsense.chandraailabs.com`.
- **GCS frontend CI sync**: `frontend/dist/` uploaded to `gs://sport-slot-dev-frontend`
  via `gsutil rsync` in the CI workflow, with `Cache-Control` metadata set per file type.
- **Learning document**: `docs/learnings/gcp-wildcard-domain-limitations.md` capturing
  the wildcard-support investigation findings for future reference.

---

## What went wrong and was caught before causing harm

### 1. Classic managed SSL certificates reject wildcards entirely

`google_compute_managed_ssl_certificate` (the classic type) does not support wildcard
domains. The initial Phase 8b.1 implementation used this resource. The error surfaced
at plan/apply time rather than silently provisioning a cert that wouldn't work.

**Fix (PR #81):** Replaced with Certificate Manager (`google_certificate_manager_certificate`,
`google_certificate_manager_dns_authorization`, `google_certificate_manager_certificate_map`,
`google_certificate_manager_certificate_map_entry`) and updated the target HTTPS proxy to
use `certificate_map` instead of `ssl_certificates`. Documented in
`docs/learnings/gcp-wildcard-domain-limitations.md` (PR #83).

### 2. `evaluatePreconfiguredExpr` vs `evaluatePreconfiguredWaf` in Cloud Armor

Cloud Armor's WAF rules require `evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 1})`.
The initial implementation used `evaluatePreconfiguredExpr(...)`, which does not accept a
map argument for sensitivity (API error: `candidates: (string),(string, list(string))`).
`terraform validate` did not catch this — only `terraform apply` against the real API did.

**Fix (PR #87):** Renamed to `evaluatePreconfiguredWaf` across all 4 occurrences (SQLi
and XSS rules in both the API and frontend_edge policies).

### 3. Default security policy rule rejects `preview = true`

GCP rejects `preview = true` on the mandatory default rule (priority 2147483647): *"Cannot
preview the default rule, consider creating another rule that matches all to simulate the
default rule."* The initial implementation set `preview = true` on the default allow rule
in both policies.

**Fix (PR #88):** Removed `preview = true` from both default rule blocks (2 lines removed).
The SQLi/XSS deny rules retained `preview = true` unchanged.

### 4. `CLOUD_ARMOR_EDGE` policies do not support preconfigured WAF expressions at all

The initial investigation assumed `CLOUD_ARMOR_EDGE` policies supported preconfigured WAF
expressions. The API confirmed this is categorically unsupported — not partially supported,
not limited to certain rule sets, but entirely absent. The SQLi and XSS rule blocks in
`google_compute_security_policy.frontend_edge` failed on apply.

**Fix (PR #89):** Removed both WAF rule blocks from `frontend_edge` entirely, leaving only
the mandatory default allow rule. Custom CEL-based edge rules deferred as a deliberate
future addition. The `api` policy (type `CLOUD_ARMOR`, not edge) was unaffected and had
already applied successfully.

### 5. Cloud CDN's `CACHE_ALL_STATIC` silently overrides origin `Cache-Control` headers

The initial `cdn_policy` used `cache_mode = "CACHE_ALL_STATIC"`, which ignores origin
headers and applies Cloud CDN's default TTL (3600s) to static assets — including
`index.html`, `sw.js`, and `manifest.webmanifest`, which must not be cached for
deployments to propagate immediately. This was caught during the Phase 8b.2b
implementation before any real production traffic relied on it.

**Fix (PR #84):** Changed to `cache_mode = "USE_ORIGIN_HEADERS"`, which passes `Cache-Control`
metadata set at CI upload time through to CDN. `no-cache` files stay uncached; immutable
hashed assets cache with `max-age=31536000`.

### 6. Cloud Run ingress restriction breaks Firebase Hosting rewrites — caught via investigation before implementation

Before implementing the ingress restriction, an explicit investigation step confirmed that
Firebase Hosting's rewrite mechanism reaches Cloud Run via the public `*.run.app` URL from
Firebase's own network. GCP's ingress documentation lists Cloud Tasks, Cloud Scheduler,
Eventarc, Pub/Sub, and others as internal traffic — but not Firebase Hosting. Restricting
ingress to `internal-and-cloud-load-balancing` would silently break `sport-slot-dev.web.app/api/**`.

The investigation also confirmed that `gcloud run deploy` resets `--ingress` to `all` on
every deploy if the flag is omitted — meaning any live restriction would be silently undone
by the next CI deploy.

**Resolution (PR #90):** Both findings were addressed explicitly before implementation:
the Firebase Hosting path breakage was accepted as a DEV-only tradeoff (no real tenant
traffic depended on it); `--ingress=internal-and-cloud-load-balancing` was codified in
the deploy script so CI preserves it.

### 7. GCS bucket-listing XML returned on bare root path "/"

After the LB was live, testing revealed that `https://rvrg.slotsense.chandraailabs.com/`
returned raw XML (GCS bucket listing) instead of `index.html`. The existing
`default_custom_error_response_policy` (404 → `index.html`) never engaged because GCS
returns HTTP 200 for a root-path list request — `allUsers` holds `roles/storage.objectViewer`,
which includes `storage.objects.list`. There was no 404 to intercept.

A dedicated investigation confirmed the correct fix (URL map `path_rule` with `route_action
{ url_rewrite { path_prefix_rewrite = "/index.html" } }`) by extracting the exact attribute
structure from `terraform providers schema -json` against provider 6.50.0 before writing
any code.

**Fix (PR #91):** Added `path_rule` for `paths = ["/"]` to the `slotsense-paths`
path_matcher. GCS now receives `/index.html` instead of an ambiguous root request.

---

## Hard-won lessons

**Wildcard TLS support is inconsistently available across GCP services — always verify
explicitly.** Firebase Hosting supports wildcard subdomains implicitly. Classic managed
SSL certs do not. Certificate Manager does, but requires DNS authorization. Never carry
an assumption about wildcard support from one GCP service to another; always check the
specific resource's documentation before designing the cert strategy.
→ See also: `docs/learnings/gcp-wildcard-domain-limitations.md`

**`terraform validate` cannot catch live API semantic constraints.** Function signature
mismatches (e.g. `evaluatePreconfiguredExpr` vs `evaluatePreconfiguredWaf`),
mutually-exclusive field combinations, and resource-type capability gaps (e.g.
`CLOUD_ARMOR_EDGE` WAF expression support) are all invisible to `terraform validate`. They
only surface at `terraform apply` against the real API. For genuinely new resource types,
budget explicitly for iteration rounds.

**GCS backend buckets require explicit equivalents for every behavior Firebase Hosting
handled implicitly.** Firebase Hosting's `source: "**"` catch-all, root-path SPA serving,
and SPA 404 fallback were all automatic. A GCS+LB backend requires: a `path_rule` for
`"/"` with a `url_rewrite`, and a `default_custom_error_response_policy` for 404s. Each
implicit Firebase Hosting behaviour is a separate explicit LB rule. Discovery by live testing
is the only reliable way to find all the gaps.

**Cross-service ingress and traffic-classification compatibility must be verified
per-service against current docs.** Cloud Tasks is classified as internal GCP traffic.
Firebase Hosting is not. These are documented separately and are not inferrable from one
to the other. Always read the specific ingress documentation for each calling service
before restricting access.

**Cloud Run service-level settings are not sticky across `gcloud run deploy` without an
explicit flag.** `--ingress` defaults to `"all"` on every invocation. Any setting
applied manually (via console or a one-off `gcloud` command) will be silently reset the
next time CI deploys. Every Cloud Run service-level setting that is not Terraform-managed
must be codified as an explicit flag in the deploy script.

---

## Open items carried forward

- **Cloud Run service not Terraform-managed.** `sport-slot-api` is deployed via `gcloud`
  in CI (per ADR-0018). Phase 8b.6 required a manual one-time `gcloud run services update`
  to apply the ingress restriction — a step that cannot be automated via `terraform apply`.
  This is a real operational gap, especially relevant for replicating the stack into TEST
  and PROD environments with minimal manual steps.

- **CMEK and VPC Service Controls** were reasoned through and deferred during planning but
  never formally committed as ADRs. The decisions remain undocumented.

- **Cloud Armor rate limiting** is explicitly deferred (ADR-0032): requires real
  booking-window traffic baselines before safe thresholds can be set.

- **Cloud Armor enforcement** (changing `preview = true` → `false` on WAF rules) requires
  a review of Cloud Armor logs across at least one 20:00 IST booking-window event before
  any rule is promoted to enforcement.

- **Pen testing (OWASP ZAP + Trivy) and DPDP formalization** remain deferred, lowest
  priority per Coordinator instruction.
