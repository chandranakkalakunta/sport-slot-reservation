# ADR-0036: Voice I/O for the AI Booking Assistant

**Status:** Approved
**Date:** 2026-07-11
**Deciders:** Coordinator (Chandra), Strategist
**Extends (never edits in place, per protocol §7.1):** ADR-0021 (Agent Architecture), ADR-0023 (Propose-Confirm-Execute Gate), ADR-0026 (Deterministic Python Guards over LLM Judgment)
**References:** ADR-0022 (Guardrails), ADR-0025 (Pending Action Store), ADR-0005 (Cost Baseline), ADR-0034 (DPDP-compliant erasure)

---

## Context

Residents interact with the AI Booking Assistant today via text only, through a
single-turn endpoint `POST /agent/query` (residents-only). Two shapes exist on
that endpoint:

- **Propose:** `{ message }` → `{ reply, pending_action_id }`
- **Execute:** `{ confirm: true, pending_action_id }` → `{ reply }`

The execute path (`run_agent_confirm`) makes **no Vertex call** and takes booking
parameters verbatim from the consumed pending action. Confirmation is therefore
**structural, not linguistic** — the text UI's `ProposalCard` sends a structured
`confirm: true` boolean on a button tap; the backend never interprets a
natural-language "yes."

We want spoken input and spoken output, in the resident's own language, without
weakening any property of the existing agent — specifically the foundational
propose-confirm-execute safety gate (ADR-0023).

The pipeline was pre-agreed as: speech → STT → translate to English → **existing
agent pipeline, unchanged** → translate reply back → TTS → playback. Translation
sits at the edges precisely so the agent core needs zero changes.

Two facts discovered during design shape the decisions below:

1. **The confirmation turn cannot be a translate turn.** A voice user cannot tap
   a button, so voice must bridge *spoken affirmation → the structured
   `confirm: true` call*. That bridge is a new natural-language → confirm path
   that does not exist in the text UI. If a spoken "no" were mistranslated to
   "yes," it would breach ADR-0023. The confirmation turn must therefore be
   handled deterministically, outside the LLM translate path.
2. **The natural voice tier is not region-resident.** Chirp 3: HD voices (the
   tier with natural Telugu/Hindi/English voices) run on the global/eu/us
   endpoints and are out of scope for asia-south1 data residency. This project
   is asia-south1 + DPDP-conscious, so this is a deliberate exception, not an
   oversight.

---

## Decision

### D1 — Translation at the edges; agent core unchanged

STT output is translated to English, run through the **existing** `run_agent`
service function, and the English reply is translated back to the detected
language for TTS. The agent orchestrator and its ADR-0021–0027 guarantees are
not modified. Voice is a new edge, implemented as a new endpoint (`D7`).

### D2 — The confirmation turn is deterministic, not translated (safety-critical)

When the previous turn returned a live `pending_action_id`, the next spoken
utterance is **not** sent through Gemini translation or the agent. It is routed
through a **deterministic, per-language confirm/deny lexicon**, fail-closed:

- clear affirmative → call the existing execute path (`run_agent_confirm`)
- clear negative → abandon the pending action, no mutation
- anything ambiguous, empty, or low-confidence → **re-prompt**, never guess

No LLM participates in the yes/no decision. This extends ADR-0026 (deterministic
Python guards over LLM judgment) to a new case — *confirmation interpretation* —
and reuses the established "deterministic Python before Vertex" pattern already
present in the orchestrator (Phase 15 invoice router; cancel disambiguation).

The guard lives **backend-side**, not in the client, so it is unit-testable and
not bypassable. The agent's own confirm path is untouched: it still receives a
structured `confirm: true` and takes params verbatim from the pending action.

### D3 — Supported languages: generous-curated set + English fallback

Supported for full round-trip (STT candidate + a TTS voice + a curated confirm/
deny lexicon): **English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi,
Gujarati, Bengali.** Input detection is best-effort across this candidate set.

Detection outside the set, low-confidence detection, or heavy code-mixing →
**English reply, fail-closed on confirmation.** This reconciles "don't
artificially limit input" with the D2 safety requirement: the confirm lexicon
cannot be pre-built for an unanticipated language, so unsupported languages get
a safe English degradation rather than an unguarded confirmation.

### D4 — Batch STT/TTS, not streaming

Booking utterances are short and the agent turn is synchronous. Record-then-send
STT and synthesize-then-play TTS match the existing turn model, are cheaper, and
are materially simpler than streaming. Streaming is explicitly deferred; revisit
only if measured turn latency proves unacceptable.

### D5 — Data residency: global-endpoint voices, documented exception

Chirp 3: HD voices are used via the global endpoint, accepting that voice audio
(STT input / TTS output) is processed outside asia-south1. Rationale: voice is a
convenience feature over transient audio, not a new system of record. This
exception is logged into the **Phase 16 DPDP self-assessment data map** and the
consent/notice language is checked there. STT regional residency (asia-south1)
is used where the chosen model supports it; where it does not, the same exception
applies and is documented at build time.

### D6 — Cost and abuse controls

Per verified 2026 pricing, a voice turn past the free tier is ≈ ₹1, split roughly
evenly between STT (~$0.016/min) and TTS (Chirp 3 HD, ~$0.00003/char), with the
two Gemini translate legs negligible. Dev/test volume sits inside the STT
(60 min/mo) and TTS (1M char/mo) free tiers — effectively ₹0 — comfortably within
ADR-0005's ₹5K/mo dev baseline. A PROD per-tenant projection (expected turns ×
₹1) is produced before any PROD enablement.

Controls: a max STT utterance-length cap (default 30s) and a per-resident
voice-turn rate limit. Both are enforced backend-side.

### D7 — Surface: new `/agent/voice` endpoint; `/agent/query` untouched

A new residents-only endpoint `POST /agent/voice` accepts audio plus the client's
current `pending_action_id` (if any). It orchestrates STT → (D2 branch OR
translate→`run_agent`→translate) → TTS by calling the existing `run_agent` /
`run_agent_confirm` **service functions directly**. The text endpoint
`/agent/query` and its contract are not changed. The feature ships behind a flag,
default off.

---

## Consequences

**Positive**

- The agent core and every ADR-0021–0027 guarantee are preserved verbatim; voice
  adds no risk to the text path.
- The most dangerous seam (spoken confirmation) is deterministic and fail-closed,
  consistent with the project's existing safety posture rather than a new
  exception to it.
- Free-tier economics make dev/test effectively free; cost risk is bounded and
  only relevant at PROD per-tenant scale.

**Negative / accepted trade-offs**

- Voice audio is processed outside asia-south1 (D5) — an accepted, documented
  residency exception carried into Phase 16.
- The confirm/deny lexicon is manual per-language curation work and must be
  maintained as languages are added; a language without a curated lexicon does
  not get voice confirmation (D3 fallback).
- Up to four paid API calls per turn vs. one today — bounded in magnitude (D6)
  but a real new billable surface requiring the rate limit and length cap.

**Follow-ups / open items**

- PROD per-tenant cost projection before PROD enablement.
- Confirm STT model's asia-south1 residency support at build; document if absent.
- Live-testing round (real Telugu/Hindi/code-mixed speech, confirm-guard edge
  cases) is a planned slice per protocol §4.9, not an afterthought.
