# ADR-0013: Error Presentation & i18n Strategy

Status: Accepted | Date: 2026-06-13 | Author: Chandra Nakkalakunta

## Context
The backend returns canonical error codes (ADR-0006 envelope:
code, message, request_id). The frontend must show human text.
Two needs were conflated and are now separated: error SEMANTICS
(the code — canonical, backend-owned, never varies) versus error
PRESENTATION (the sentence shown — varies by language, and
potentially by tenant).

## Decision
Presentation resolves through a chain, simplest layer shipped now,
later layers designed-for but not built:

  tenant_override[code] → locale_catalog[code]
    → english_catalog[code] → code (raw fallback)

- Layer 1 (Phase 4.3): a single frontend catalog keyed by code, in
  i18n-ready shape (locale → { code: text }). English only now.
  The resolver signature accepts (code, locale, overrides) even
  though only the English default is wired — call sites never
  change when later layers arrive.
- Layer 2 (localization, future phase): additional locale catalogs
  (hi, te, ta…) added as files; no refactor.
- Layer 3 (per-tenant overrides, with tenant-admin UI): optional
  message_overrides map on the tenant document, resolved exactly
  like PolicyService (tenant override → default). Delivered with
  branding; no new infrastructure.

Fail-safe: an unmapped code renders the code itself, never an
empty string — the UI degrades to "BOOKING_QUOTA_EXCEEDED" rather
than silence.

## Alternatives
- Hardcoded switch in components: rejected — wording becomes a
  code change; no i18n path.
- Backend-rendered messages: rejected — couples backend to locale/
  presentation; the code+envelope contract stays presentation-free.
- Building per-tenant overrides now: rejected — dead config until
  tenant-admin screens exist; only the SHAPE is built now.

## Consequences
+ Wording changes are data, not code; i18n is additive.
+ One resolver, one catalog file, anticipating future layers in ~10 lines.
− Slightly more structure than a single language strictly needs today.

## References
ADR-0006 (error envelope), ADR-0010 (Tenant Override → Default
pattern), ADR-0012.
