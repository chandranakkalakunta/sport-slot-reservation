"""Tests for the ADR-0037 D3' voice-language staging seam."""

from __future__ import annotations

from sport_slot.auth.context import TenantContext
from sport_slot.services.voice.languages import resolve_tenant_voice_languages

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                     role="resident", household_id="h-1")


def test_resolves_to_english_only():
    assert resolve_tenant_voice_languages(CTX) == ["en-IN"]


def test_ignores_tenant_identity_today():
    """English-only ships identically for every tenant today — the
    per-tenant config read is deferred to the multi-language sub-phase."""
    other_ctx = TenantContext(uid="u2", tenant_id="t-2", tenant_slug="other",
                               role="resident", household_id="h-9")
    assert resolve_tenant_voice_languages(other_ctx) == resolve_tenant_voice_languages(CTX)


def test_returns_a_fresh_list_each_call():
    """Callers must not be able to mutate a shared module-level list."""
    result = resolve_tenant_voice_languages(CTX)
    result.append("hi-IN")
    assert resolve_tenant_voice_languages(CTX) == ["en-IN"]
