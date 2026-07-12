# ADR-0037: Voice Language Detection — Per-Tenant Candidate Set

**Status:** Accepted
**Date:** 2026-07-11
**Deciders:** Coordinator (Chandra), Strategist
**Supersedes:** ADR-0036 §D3 (candidate auto-detect across the full 9-language set). **Revises:** ADR-0036 §D5 (residency).
**Leaves intact:** all other ADR-0036 decisions (D1 edges-translation, D2 deterministic confirm guard, D4 batch, D6 cost/abuse, D7 surface).

---

## Context

ADR-0036 §D3 specified one recognition call auto-detecting across all nine
supported Indic locales. Sub-phase 1b measured the live Speech-to-Text V2 API
before building the endpoint on that assumption, and the assumption did not hold:

1. **`chirp_3` (STT) has been withdrawn.** Live calls return
   `403 ... model chirp_3 ... is no longer generally available`, in exactly the
   two regions it was previously scoped to, while the same principal succeeds on
   other models seconds later. This is GA-revocation, not a permission or
   preview-enrollment gate. The residency-favourable option (chirp_3 in
   asia-south1) is therefore unavailable.
2. **Candidate-list auto-detection is capped at 3 language codes**, and is only
   offered at the **eu / global / us multi-region** endpoints. The Asia GA
   endpoints (asia-southeast1, us-central1, europe-west4) accept exactly **one**
   language code per call — no candidate-list detection at all.

So "many languages" and "auto-detect in one call" are mutually exclusive under
this API. A choice was required between (A) explicit single-language per resident
at an Asia endpoint, and (B) auto-detect across a small candidate set at a
multi-region endpoint. (A) requires storing and collecting a per-resident
language preference — materially more work and a poorer resident experience for
a fixed-membership community app. (B) fits the existing per-tenant configuration
model and asks nothing of the resident at call time.

Note: the API has no concept of a tenant. "Per-tenant" here means only that *our*
code selects which ≤3 candidate codes to send on each call, based on the calling
resident's tenant. The tenant boundary is entirely ours; the API sees a list of
≤3 codes and nothing else.

---

## Decision

### D3′ (supersedes D3) — Per-tenant 3-language candidate auto-detection

Each tenant carries a configured list of up to **3** BCP-47 language codes. Every
voice recognition call for a resident of that tenant sends that tenant's trio as
the candidate list; Speech-to-Text auto-detects among them. The **platform**
continues to support the full nine-language set (and any future additions); the
**per-call** candidate list is bounded at three by the API.

- Storage: a `voice_languages` field on tenant config (up to 3 codes).
- Default when unset: **`["en-IN", "hi-IN", "te-IN"]`** — so voice works
  immediately for existing dev tenants without a configuration step.
- Collecting the trio from tenant-admins (a settings UI + validation) is a
  **later sub-phase**, not a blocker for the voice endpoint. Storage field now,
  admin UI later.
- No per-resident language preference is stored or collected.

### D2′ (extends D2) — Confirm turn checks all of the tenant's lexicons

On a confirmation turn, the deterministic confirm/deny guard (ADR-0036 D2)
classifies the utterance against **all** of the tenant's configured languages'
lexicons, not only the language Speech-to-Text detected. Rationale: auto-detect
can mislabel among a tenant's own languages, and the confirm decision must not
depend on that guess. A token affirmative in one of the tenant's languages and
negative in another → AMBIGUOUS (fail-closed). This preserves D2's guarantee
under imperfect detection at near-zero cost.

### Model & endpoint — `chirp_2`, regional; English-first ships single-code at `asia-southeast1`

Live probing established that `chirp_2` is a **regional** model: it is accepted at
asia-southeast1 / us-central1 / europe-west4 and returns *"does not exist"* at the
multi-region endpoints (global, us, eu). Candidate-list **auto-detection**, by
contrast, is offered **only** at the multi-region endpoints. These two facts are
mutually exclusive: there is no single (model, location) that gives both `chirp_2`
and multi-language auto-detect. `chirp_3` (which did offer both in one region) is
withdrawn.

Resolution, staged to match the English-first rollout:

- **Now (English-first):** single language code per call, model `chirp_2`,
  location **`asia-southeast1`** (nearest GA region; proven-accepted). Auto-detect
  is not needed for one language, so the multi-region constraint does not apply.
- **Later (multi-language):** when a second language is added, the multi-language
  detection model/endpoint is an **open decision** — options include a
  multi-region endpoint with a detection-capable model, or a different model
  entirely. **TBD at that sub-phase**, not pre-committed here. The per-tenant
  candidate-set design (D3′) and the all-lexicon confirm check (D2′) stand
  regardless of which detection mechanism is chosen then.
- Real-speech transcription **quality** on Indic locales is validated
  post-deploy (sub-phase 3 live testing), per the Coordinator's English-first
  sequencing — acceptance (HTTP 200) is not evidence of usable transcription, and
  is only claimed for English at this stage.

### D5′ (revises D5) — Residency

For the English-first single-code configuration, audio is processed at
**`asia-southeast1` (Singapore)** — in-region Asia, an improvement over D5's
global-endpoint exception, though still **not asia-south1** (India). If the future
multi-language mechanism requires a multi-region endpoint, audio for those calls
would again process outside Asia; that residency implication is re-decided at that
sub-phase alongside the model/endpoint choice above.

Treatment is unchanged: DPDP handled as a **notice-and-purpose** matter, not a
localization one — the audio is transient inference input, not retained and not a
new system of record. Covered by a line in the resident privacy notice ("voice
input is processed via Google Cloud, may be processed outside India, and is not
retained") and carried into the Phase 16 DPDP self-assessment.

Open item, explicitly not closed this session: India's DPDP cross-border transfer
position (default-permitted absent a notified blacklist) was **not re-verified**
against current rules in this session. To be confirmed with counsel / a current
check before production launch. Not a blocker for dev/test.

---

## Consequences

**Positive**
- No per-resident setup; residents just speak. The full platform language set is
  retained via per-tenant selection.
- The confirm guard stays fail-closed and now robust to STT misdetection among a
  tenant's own languages (D2′).
- Uses a GA model (`chirp_2`) rather than a withdrawn/preview one — stability.
- 1c ships against a detection strategy that provably exists on the live API.

**Negative / accepted**
- The multi-language detection mechanism (model + endpoint) is deferred, not
  solved: `chirp_2` gives no auto-detect, and auto-detect needs a multi-region
  endpoint `chirp_2` doesn't serve. Adding language #2 reopens this and may force
  a non-Asia endpoint (latency + residency cost) — decided then, on evidence.
- Hard ceiling of 3 candidate languages per tenant once auto-detect is in use.
  A tenant needing a 4th must choose which three; no per-call way around the cap.
- English-first means non-English voice does nothing useful until the
  multi-language sub-phase lands — an intentional sequencing choice, not a gap.

**Follow-ups**
- Real-speech validation of `chirp_2` on Indic locales before merge of the STT
  fix.
- Tenant-admin voice-language configuration UI — later sub-phase.
- DPDP cross-border transfer status — confirm before production.
- Sub-phase 1c consumes the tenant trio (default when unset) and applies D2′.
