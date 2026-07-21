# SlotSense — Project Backlog

Canonical record of tracked-but-not-scheduled work, per Three-Agent
Protocol §7.7. Organized by requirement-category block (who it serves),
not a flat list. The Strategist keeps this current: every deferral is
logged here the moment it's decided; every item is marked done with the
phase/PR that shipped it, and left in place as a requirement→phase
traceability record.

**Entry convention:** `[ID] status — one-line what & why. Blocker. Ref.`
Status ∈ `OPEN` · `BLOCKED` · `IN PROGRESS` · `✓ DONE — Phase X / PR #n`.

_Last updated: 2026-07-21_

---

## Security & Compliance

- **SEC-01 · BLOCKED (pre-production)** — Confirm India DPDP cross-border
  transfer status before production. Voice audio processes outside India
  (STT asia-southeast1; TTS global); treated as notice-and-purpose, in the
  privacy notice + Phase 16 DPDP self-assessment. DPDP default-permits
  transfer absent a notified blacklist, but this was NOT re-verified vs.
  current rules — needs counsel / current check. Ref: ADR-0037 D5′.
- **VOICE-PROD-GATE · OPEN (before prod/resident-facing deploy) — HIGH** —
  The `SPORTSLOT_VOICE_ENABLED` flag was removed (2026-07-13); /agent/voice
  is now unconditionally live with no runtime gate. VOICE-HARDEN-01,
  VOICE-HARDEN-02, and SEC-01 must be resolved before the deploy pipeline
  targets a resident-facing prod/test environment.
- **PR-5-SECURITY · OPEN** — Cloud Armor enforce-vs-preview review, CI
  container/dependency/secret scanning, BinAuthz decision, secret rotation
  policy.
- **WIF-LEAST-PRIV · OPEN (into PR-5)** — GitHub WIF principal holds
  project-level storage.admin + run.admin; tighten. TF-managed already
  (ci_* bindings).

## Platform Admin

- _(none tracked)_

## Tenant Admin

- **TADM-01 · OPEN (part of VOICE-ML)** — Tenant-admin UI to configure up
  to 3 voice languages per tenant (ADR-0037 D3′). Storage field + read
  pattern + settings screen. Currently staged behind
  `resolve_tenant_voice_languages()` (hardcoded en-IN).
- **TADM-02 · OPEN (cosmetic)** — Bulk-import `reason` field inconsistency
  (message vs. code) between admin and tenant-admin endpoints.

## Resident

- **RES-01 · OPEN (cosmetic)** — FacilityAvailability page missing a
  facility-name header.

## Agent / AI Assistant

- **AGENT-ROUTER · OPEN (undecided)** — Whether to extend the deterministic
  pre-Vertex router (ADR-0026) from the 2 invoice tools to other agent
  tools. Constraint (1c-pre): any tool on the deterministic path MUST
  return resident-ready prose (list_my_bookings / get_my_preferences emit
  raw key=value + Markdown today, laundered only by Gemini Turn-2 — they'd
  leak if routed deterministically). Decide if their reliability matters.
- **VOICE-ML · BLOCKED** — Non-English voice (Telugu, Hindi, …). Blocked
  NOT by translation (Gemini translate is trivial) but by STT language
  auto-detection: capped at 3 langs, only at us/eu/global endpoints;
  chirp_2 (shipped) has no auto-detect; chirp_3 STT was withdrawn.
  Needs: pick detection mechanism → wire Gemini translate legs →
  real-speech Indic validation. Re-probe live first
  (scripts/voice/stt_model_probe.py, fixed — see VOICE-PROBE).
  After English E2E. Ref: ADR-0037 D3′.
- **VOICE-LEX · OPEN (part of VOICE-ML)** — Native-speaker review of the 6
  non-English confirm lexicons (ta/kn/ml/mr/gu/bn); te/hi by Coordinator.
  Fail-closed makes gaps safe, but each needs a pass before that language
  ships.
- **VOICE-BLOB-CLEANUP · OPEN (low)** — Reply-audio object URLs
  (base64→Blob→createObjectURL) are never revoked; older messages hold
  stale blob URLs on long sessions — a slow memory leak. Pre-existing
  (not introduced by barge-in). Add URL.revokeObjectURL on unmount /
  when audio is replaced. Frontend, MessageBubble/AudioReply.
- **VOICE-INPUT-LOCK · OPEN (low)** — Nothing prevents a voice/mic
  recording from starting while a prior /agent/query (text) or
  /agent/voice request is still in flight — a possible race. Consider
  disabling the mic while a turn is pending (the text input already
  disables via inputDisabled). Frontend.
## Infrastructure & Technical

- **IAM-TF-CODIFY · ✓ DONE — Phase 17 / PR #142** —
  The 4 baseline service accounts' roles (sa-cloud-run, sa-firebase-admin,
  sa-cloud-build, sa-monitoring) are documented only as commented-out
  resource templates in `terraform/iam.tf` (Phase 1.4.2 Option C) — the
  SAs themselves and every role binding were granted imperatively via
  `gcloud iam` in Phase 1.3.2/1.3.3 and are not real Terraform resources.
  Drifts/vanishes on infra rebuild. Separate from VOICE-IAM-TF (a single
  feature-scoped grant, now codified) — this covers the baseline set.
  Ref: ADR-0038 Layer 3. Closed by PR-1b (#142): SAs converted to managed
  resources, ~14 IAM bindings imported, Cloud Run service/Redis/Artifact
  Registry codified.
- **ROADMAP-STALE · ✓ DONE — Phase 17 / DOC-TRUTH** — `docs/roadmap.md`
  archived to `docs/archive/roadmap-2026-06.md`; a stub now points to
  `docs/backlog.md` (canonical) and `CHANGELOG.md` (phase progress).
- **PR-2-OBSERVABILITY · IMPLEMENTED, PENDING APPLY/VALIDATION** —
  Uptime checks (edge + service path), 4 alert policies (5xx rate,
  p95 latency, uptime failure, backup failure), 2 email+SMS
  notification channels, Error Reporting, voice/agent turn-counter
  metrics — all in `terraform/observability.tf` (ADR-0040). Awaiting
  Coordinator SMS-number substitution, plan/apply, and the post-apply
  validation list in `docs/runbooks/observability.md`. Ref: ADR-0040,
  PR-2.
- **PR-3-AVAILABILITY · IMPLEMENTED, PENDING APPLY** — maxScale 2→10,
  HTTP startup + liveness probes on `/health`, "SlotSense Ops"
  dashboard — `terraform/cloud_run.tf` / `terraform/dashboard.tf`
  (ADR-0041 D15/D17). SLO defined at doc-level only (D14 — no
  Monitoring SLO API resources yet). Redis SPOF decision: BASIC tier
  accepted with triggers (see `REDIS-HA-TRIGGERS`). Awaiting
  Coordinator plan/apply and the post-apply revision watchlist in the
  PR body. Ref: ADR-0041, PR-3.
- **PR-4-COST · IMPLEMENTED, PENDING APPLY/VALIDATION** — Billing budget
  + five graduated thresholds (50/80/100/120% actual + 100% forecasted)
  per ADR-0005's ₹5K/mo dev ceiling, incl. the voice per-turn surface —
  `terraform/cost.tf` (new), `billingbudgets.googleapis.com` enabled via
  Terraform for the first time. Project-filtered to `sport-slot-dev`
  only; notifications reuse the existing ADR-0040 channels. Alert-only
  by design (ADR-0042 D18) — no automated billing-disable/service-cap
  actuator. Awaiting Coordinator plan/apply and the post-apply
  validation list in the PR body. Ref: ADR-0042, PR-4.
- **TEST-PROJECT-BUDGET · OPEN (Phase 18)** — `slot-sense-test` has no
  billing budget yet because the project doesn't exist yet (ADR-0042
  D19 scopes PR-4's budget to `sport-slot-dev` only, by project filter,
  precisely so a future TEST project doesn't muddy the dev signal).
  Add an equivalent `google_billing_budget` once `slot-sense-test` is
  provisioned. Ref: ADR-0042 D19.
- **BACKUP-ALERT · IMPLEMENTED, PENDING APPLY/VALIDATION** — Alert on
  Firestore backup failure shipped as
  `google_monitoring_alert_policy.firestore_backup_failure` (PR-2,
  ADR-0040); log filter is defensive/provisional — validate at drill
  or first real failure. Ref: ADR-0038.
- **BACKUP-ABSENCE-ALERT · OPEN (low)** — The PR-2 backup alert detects
  *failed* backup operations, not a schedule that silently never runs.
  A "no successful backup in 36h" absence-detection condition is a
  named refinement, not shipped in PR-2. Ref: ADR-0040 D11.
- **ALERT-THRESHOLD-TUNE · OPEN (after SLO-LOAD-TEST)** — PR-2's alert
  thresholds (5xx > 5%/5min, p95 > 2500ms/15min) are provisional,
  set loose per the measured-gates principle. Tighten once
  SLO-LOAD-TEST produces real traffic distributions. Ref: ADR-0040.
- **AGENT-TURN-EVENT · OPEN (low)** — PR-2's `voice_turns` /
  `agent_text_turns` counters are built on Cloud Run platform request
  logs, not application logs, because `/agent/query` has no
  unconditional per-turn structured log event (unlike `/agent/voice`'s
  `voice_request_received`). Add one inside `run_agent`
  (tenant/latency/model dimensions) for per-tenant cost attribution
  when PR-4 wants it; platform request logs remain the volume-counter
  of record until then. Ref: ADR-0040 D12, PR-2.
- **AUTH-EXPORT-AUTO · OPEN (low)** — Automate weekly Firebase Auth
  export to GCS. Manual runbook procedure until then. Ref: ADR-0038
  Layer 6.
- **SLO-LOAD-TEST · OPEN (follow-on to PR-3)** — Load/perf test to
  validate the 99% SLO; the proof, not part of the PR-3 ADR. Also
  re-validates D15's probe/scale settings under real traffic and gates
  D14's SLO-API upgrade (Monitoring SLO / error-budget burn-rate
  resources, deferred until real traffic distributions exist). Ref:
  ADR-0041.
- **REDIS-HA-TRIGGERS · DEFERRED (ADR-0041 D16)** — BASIC tier Redis
  accepted as a documented residual; STANDARD_HA rejected at this
  stage (roughly doubles Redis cost against the ₹5K ceiling to protect
  an SLO that already tolerates ~7.3h/month, for a dev-stage system
  with no paying tenants). Revisit triggers (any one reopens the
  decision): first paying tenant / Phase 18 production launch gate; a
  measured Redis-attributed SLO breach or repeated Redis incidents;
  Memorystore maintenance windows observed impacting bookings. Ref:
  ADR-0041 D16.
- **PROJECT-ASSESSMENT · ✓ DONE — Phase 17 / third-party review
  2026-07-15 + Strategist validation 2026-07-16; artifacts:
  docs/reviews/**.
- **HARDENING-RESIDUALS · DEFERRED (ADR-0039)** — CMEK, VPC/NAT, admin
  MFA, pen test; revisit triggers in the ADR.
- **CI-AUDIT-RATCHET · OPEN (low)** — Flip pip-audit to blocking after
  first triage. Ref: DOC-TRUTH.
- **SMOKE-E2E · OPEN** — Playwright (or similar) deploy smoke: sign-in
  → availability → book → cancel. Ref: review P2.3.
- **CONTAINERREGISTRY-CLEANUP · OPEN (low)** — Legacy
  containerregistry.googleapis.com API enabled, no images; disable
  during PR-5.
- **SEC-HEADERS · OPEN** — Server-side security headers (HSTS, CSP,
  X-Frame-Options, X-Content-Type-Options) claimed in the security
  charter but absent from app middleware (confirmed via grep,
  2026-07-16 DOC-TRUTH). Ref: Phase 17 PR-5. Scope amended 2026-07-17
  (PR-2): also audit the charter's CORS-strict-policy claim — flagged
  during DOC-TRUTH as noticed-but-out-of-scope (that pass only grepped
  for security headers, not CORS).
- **VOICE-HARDEN-01 · OPEN (hard gate before prod enablement)** — Enforce a
  30s max-utterance duration cap server-side (ADR-0036 D6). 1c ships only a
  2MB byte cap (~8-11 min at typical bitrates); STT's 60s sync limit is a
  loose backstop. Client-side 30s auto-stop is built (sub-phase 2 UX); this
  is the server-side enforcement.
- **VOICE-HARDEN-02 · OPEN (hard gate before prod enablement)** — Add a
  voice-specific (stricter) per-resident rate limit for /agent/voice
  reflecting its ≈₹1/turn cost (ADR-0036 D6). 1c inherits the generic
  per-user default (functional, not cost-tuned).
- **VOICE-IOS · OPEN (before iOS launch, not day-one)** — Verify & harden
  iOS Safari voice capture. Safari MediaRecorder emits MP4/AAC (backend STT
  auto-decode already tolerates it); sub-phase 2 attempts compatibility via
  mimeType feature-detection but is NOT tested on iOS devices. Needs real
  iOS device testing before iOS is a supported target. Android/desktop is
  primary.
- **INFRA-01 · BLOCKED (revisit if recurs)** — 13.6 CDN cache-fill
  0-byte-response bug. Reproduced once, root cause never confirmed.
- **INFRA-02 · OPEN (cosmetic)** — Firestore positional-filter deprecation
  warnings (`filter=` keyword vs. positional args) across the codebase.
- **OPS-RUNBOOK · OPEN (low)** — Config-var names (e.g.
  SPORTSLOT_VOICE_ENABLED) and required IAM roles live only in code
  docstrings; a deploy/runbook doc listing voice env vars + roles would
  have saved hours 2026-07-13.

---

## Completed (traceability record)

- **VOICE-1a · ✓ DONE — Phase Voice / PR #128** — Deterministic fail-closed
  confirm/deny guard, 9-language seed lexicon (data/logic split).
- **VOICE-1b · ✓ DONE — Phase Voice / PR #129** — STT ingestion + language
  detection; chirp_2 @ asia-southeast1, single-code English-first.
  Ref: ADR-0036, ADR-0037.
- **VOICE-1c · ✓ DONE — Phase Voice / PR #131** — /agent/voice endpoint,
  English-only pipeline (STT → confirm-guard | agent → TTS). Feature flag
  (SPORTSLOT_VOICE_ENABLED). Ref: ADR-0036, ADR-0037.
- **AGENT-INVOICE-FMT · ✓ DONE — Phase Voice/1c-pre / PR #130** —
  Professional prose for agent invoice replies (was raw key=value);
  presentation-only, TTS-safe.
- **AGENT-UX-01 · ✓ DONE — Phase Voice / PR #132** — Up-arrow recalls the
  previous user message for edit/resend. Enhanced to shell-style
  multi-level history (walk back/forward through all prior messages,
  draft-restore) in AGENT-UX-01b, PR #140.
- **AGENT-UX-02 · ✓ DONE — Phase Voice / PR #132** — `/clear` slash command
  clears thread + session state (UI-only).
- **VOICE-2 · ✓ DONE — Phase Voice / PR #132** — Mic capture + playback UI;
  spoken-confirm routing; auto-play with fallback.
- **VOICE-LOGGING · ✓ DONE — Phase Voice / PR #134** — Fixed structlog
  event→message rendering (EventRenamer) so structured logs are visible in
  Cloud Logging (was a project-wide prod-logging bug); added voice-path
  instrumentation. Permanent, keep.
- **VOICE-STT-403 · ✓ DONE — 2026-07-13 (imperative; see VOICE-IAM-TF to
  codify)** — Granted roles/speech.client to sa-cloud-run@; voice now
  transcribes end-to-end. Full round-trip working.
- **VOICE-IAM-TF · ✓ DONE — infra/voice-speech-iam (terraform/voice_stt.tf)**
  — Codified the imperative roles/speech.client grant (VOICE-STT-403) as
  a real `google_project_iam_member` resource, matching the
  invoice_export.tf / cloud_tasks.tf pattern. Import/plan/apply is
  Coordinator-run and not yet applied as of PR open — see PR for the
  exact commands.
- **AGENT-MD-TTS · ✓ DONE — Phase Voice / PR #135** — Markdown stripped from
  agent replies (`services/agent/text_format.to_plain_text`), applied once
  at the `run_agent` / `run_agent_confirm` boundary so both `/agent/query`
  and `/agent/voice` get clean prose. Formatting-only.
- **VOICE-BARGE-IN · ✓ DONE — Phase Voice / PR #138** — User takes
  priority: starting a recording now stops any in-progress TTS reply
  playback immediately (auto-played or fallback-button-resumed).
  Frontend-only; `isRecording` flows `MessageInput` → `Assistant` →
  `MessageThread` → `MessageBubble`'s `AudioReply`, which pauses its own
  `<audio>` ref on the rising edge.
- **VOICE-PROBE · ✓ DONE — Phase Voice / PR #139** — Fixed
  `scripts/voice/stt_model_probe.py`: replaced the 1b 9-language matrix
  (always 400s, API caps at 3 codes) with a case matrix that validates
  the shipped config first (chirp_2 @ asia-southeast1, en-IN only) plus
  regional-reachability and future-VOICE-ML cases, all ≤3 codes; missing
  --audio (including the default, gitignored fixture) now prints clear
  guidance instead of a bare "file not found". `resources/voice_fixtures/
  .gitkeep` already existed (PR #129) — nothing to add there.
