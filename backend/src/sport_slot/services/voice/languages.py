"""Tenant voice-language resolution — the ADR-0037 D3′ staging seam.

ADR-0037 D3′ decided that each tenant will eventually carry a configured
list of up to 3 BCP-47 candidate languages (`voice_languages` on tenant
config), used for both STT candidate-list auto-detection and — per D2′ —
combined confirm/deny lexicon checking. That per-tenant configuration
(storage field + admin UI) is explicitly a LATER sub-phase; ADR-0037's
own follow-ups list it as not yet built.

This sub-phase (1c) ships English-only. Rather than inline a hardcoded
`["en-IN"]` at every call site, this function is the single seam the
future multi-language sub-phase will change: it will start reading the
tenant's configured `voice_languages` field here, and nothing else in
the voice pipeline needs to change, because every caller already goes
through this resolver instead of assuming a fixed language list.
"""

from __future__ import annotations

from sport_slot.auth.context import TenantContext

# English-first (ADR-0037 model/endpoint decision): chirp_2 is GA and
# single-language-only at the asia-southeast1 endpoint this sub-phase
# targets — see services/voice/stt.py. Multi-language auto-detection is
# deferred to the future multi-language sub-phase (ADR-0037 D3′), which
# would also need to revisit the STT endpoint (eu/global/us).
_ENGLISH_ONLY: list[str] = ["en-IN"]


def resolve_tenant_voice_languages(ctx: TenantContext) -> list[str]:
    """Return the candidate BCP-47 language codes for this resident's tenant.

    `ctx` is intentionally unused today — English-first ships one fixed
    language for every tenant, so there is nothing tenant-specific to
    resolve yet. It is already part of the signature so the future
    multi-language sub-phase's implementation (reading `ctx.tenant_id`'s
    configured `voice_languages`) is a body-only change here, not a
    signature change propagated through the whole pipeline.
    """
    del ctx  # staged for the multi-language sub-phase; unused today
    return list(_ENGLISH_ONLY)
