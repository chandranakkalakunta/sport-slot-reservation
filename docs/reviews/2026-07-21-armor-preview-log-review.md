# Cloud Armor API Policy — Preview-Log Review (ADR-0043 PR-5b Gate)

- **Date:** 2026-07-21
- **Purpose:** the evidence base for the preview→enforce decision on
  `google_compute_security_policy.api` (`slotsense-api-armor`,
  `terraform/cloud_armor.tf`). Per ADR-0043 PR-5b item 1, this review
  is the **gate** — enforce is authored only if it comes back clean.
- **Window:** 14 days (`--freshness=14d`), read at 2026-07-21 09:4x UTC.
- **Query (read-only):**
  ```
  gcloud logging read 'resource.type="http_load_balancer" AND
    jsonPayload.enforcedSecurityPolicy.name!="" AND
    jsonPayload.enforcedSecurityPolicy.outcome="ACCEPT" AND
    jsonPayload.previewSecurityPolicy.outcome="DENY"'
    --project=sport-slot-dev --freshness=14d --limit=100 --format=json
  ```
  This finds every request the preview rules would have **denied**
  that was nonetheless **accepted** live (preview mode logs, doesn't
  block) — exactly the population this gate needs. The field names in
  the task prompt matched the live LB log schema on the first try; no
  adjustment needed.

## Result: 75 matching entries (well under the 100 limit — this is the
## complete population for the window, not a truncated sample)

## Finding: 100% of flagged requests are legitimate traffic on one endpoint

| Dimension | Result |
|---|---|
| Distinct hosts | **1** — `rvrg.slotsense.chandraailabs.com` (a real, live tenant subdomain) |
| Distinct paths | **1** — `/api/v1/agent/voice` (the voice-agent endpoint) |
| HTTP method | **100% POST** |
| HTTP status | 57× `200`, 18× `404` (no 5xx; nothing indicating a probe/scan pattern) |
| User agents | 66× real desktop Chrome/Mac UA, 9× real mobile Chrome/Android UA — **zero** scanner/bot/curl/sqlmap-style UAs |
| Remote IPs | 3 distinct IPs, all India-region residential ASN (24560) — 68/75 from one IP, consistent with one or two real users testing repeatedly, not a botnet spread |
| Request size | 20,684–115,217 bytes, **median 53,759 bytes** — far larger than a typical form field, consistent with base64-encoded voice-audio payloads |
| Rules matched per request | Exactly 1 (never stacked) |

### Rule IDs flagged (all CRS 4.22 generic pattern rules, both preview rules in the policy)

| Rule ID | Count | CRS category |
|---|---|---|
| `owasp-crs-v042200-id942100-sqli` | 22 | SQLi |
| `owasp-crs-v042200-id941100-xss` | 19 | XSS |
| `owasp-crs-v042200-id942190-sqli` | 17 | SQLi |
| `owasp-crs-v042200-id941310-xss` | 12 | XSS |
| `owasp-crs-v042200-id942540-sqli` | 3 | SQLi |
| `owasp-crs-v042200-id942290-sqli` | 2 | SQLi |

## Analysis

Both preview rules on the API policy (`sqli-v422-stable`,
`xss-v422-stable`, `terraform/cloud_armor.tf:35-58`) are **generic
OWASP CRS pattern-match rules**, calibrated against typical small
text-field inputs (form fields, query strings, JSON with short string
values). `/api/v1/agent/voice` sends large POST bodies carrying
audio/voice content (median 54KB — consistent with base64-encoded
audio, not a form submission). Generic SQLi/XSS signatures are
well-documented to false-positive against dense binary-as-text or
natural-language payloads of this size and shape — byte sequences or
transcribed speech can incidentally resemble the character patterns
these signatures key on (quotes, angle brackets, SQL keywords,
etc.), without containing any actual attack.

Every one of the 75 entries in the 14-day window is this exact
pattern: same tenant, same endpoint, same method, real browser UAs,
real residential IPs, mostly-200 status. **There is no attack traffic
of any kind in this population** — not "mostly legitimate with some
noise," literally 100%. Enforcing the policy as-is today would return
403 to real residents using the shipped voice-booking-assistant
feature.

## Decision gate outcome: **NOT CLEAR — legitimate traffic flagged**

Per ADR-0043 PR-5b's own gate condition: legitimate traffic is
flagged → **do not author a blind enforce**. This review recommends
**against** flipping `preview = true` → enforce on the current rule
set without one of:

1. **Tune first:** exclude `/api/v1/agent/voice` from SQLi/XSS body
   inspection (Cloud Armor supports per-path rule exclusion via a
   dedicated allow/exclude rule at a higher priority than the WAF
   rules, or an `evaluatePreconfiguredWaf` request-path exclusion
   parameter), then re-observe a window before enforcing globally.
2. **Enforce with an explicit exception:** add a higher-priority
   `allow` rule scoped to `request.path.matches('/api/v1/agent/voice')`
   ahead of the two WAF rules, then flip the WAF rules to enforce —
   the voice endpoint keeps flowing through unaffected, every other
   path gets real SQLi/XSS enforcement immediately.
3. **Extend the observation window** if there's reason to think 14
   days under-samples real attack traffic (unlikely here, given the
   window already captured real usage cleanly, but the Coordinator's
   call).

**This Worker did not author the Terraform change for the API
policy's preview→enforce flip.** `terraform/cloud_armor.tf` is
unmodified by this PR. Awaiting Coordinator direction on which of
the above (or a different option) to take.
