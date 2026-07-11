"""Tests for the deterministic pre-Vertex invoice-keyword routing fix.

CONTEXT: confirmed via live reproduction (not theorized) that Gemini's
tool-selection for the 15.6 invoice tools is genuinely non-deterministic —
identical phrasing worked in one fresh session and failed in another, with
the exact same system-prompt routing instructions in place both times. This
adds a second pre-Vertex interception block (same shape as the existing
cancel-disambiguation check) that deterministically routes high-confidence
invoice phrasings directly to the existing 15.6 dispatch functions, skipping
Vertex entirely for that turn.

The four phrasings below are the literal ones confirmed failing live this
session — not synthetic keyword checks. The Vertex-call-count assertions are
the actual regression proof: the matched path must call Vertex ZERO times;
the non-matched (fallback) path must still call it, confirming this change
is purely additive and never touches the existing flow for anything that
already worked.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import (
    _is_current_month_phrasing,
    _matches_invoice_keyword,
    run_agent,
)
from sport_slot.services.agent.vertex_client import AgentResponse

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                     role="resident", household_id="h-1")

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FACILITY = {
    "id": "f-court1", "name": "Tennis Court 1",
    "active": True, "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "08:00", "end": "22:00"}] for day in _DAYS},
}
POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "booking_horizon_days": 3650,
        "booking_window_open_time": "00:00",
        "cancellation_buffer_hours": 1,
    },
}


def _firestore_client() -> MagicMock:
    client = MagicMock()
    fac_doc = MagicMock()
    fac_doc.to_dict.return_value = FACILITY
    fac_doc.id = FACILITY["id"]
    (client.collection.return_value.document.return_value
     .collection.return_value.order_by.return_value.limit.return_value
     .stream.return_value) = [fac_doc]
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = FACILITY
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


class _NoopStore:
    async def propose(self, *a, **k):
        return "noop"

    async def consume(self, *a, **k):
        return None

    async def get_latest_for_user(self, *a, **k):
        return None


INVOICE_ITEMS = [
    {"invoice_id": "h-1_2026-06", "household_id": "h-1", "period": "2026-06", "total_paise": 150050},
]
PREVIEW = "sport_slot.services.agent.orchestrator.preview_current_month_charge"
REPO = "sport_slot.services.agent.orchestrator.InvoiceRepository"


# ── unit tests: keyword/phrasing matchers ────────────────────────────────────

@pytest.mark.parametrize("message", [
    "my invoice please",
    "my last invoice please",
    "what did I owe last month",
    "my latest invoice please",
    "what's my bill this month",
    "MY INVOICE",  # case-insensitive
])
def test_matches_invoice_keyword_true_cases(message):
    assert _matches_invoice_keyword(message) is True


@pytest.mark.parametrize("message", [
    "book tennis tomorrow",
    "what's available today",
    "cancel my badminton booking",
    "what's my usual court",
    "is billiards court free",  # "bill" must NOT match inside "billiards"
])
def test_matches_invoice_keyword_false_cases(message):
    assert _matches_invoice_keyword(message) is False


@pytest.mark.parametrize("message", [
    "what do I owe so far this month",
    "my bill till date",
    "current month charges please",
    "how much to date",
])
def test_is_current_month_phrasing_true_cases(message):
    assert _is_current_month_phrasing(message) is True


@pytest.mark.parametrize("message", [
    "what did I owe last month",
    "my last invoice please",
    "my invoice for June",
])
def test_is_current_month_phrasing_false_cases(message):
    assert _is_current_month_phrasing(message) is False


# ── the four real, live-confirmed-failing phrasings ──────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("message", [
    "my invoice please",
    "my last invoice please",
    "my latest invoice please",
])
async def test_real_failing_phrasing_routes_to_get_my_invoices_never_calls_vertex(message):
    with (
        patch(REPO) as mock_repo_cls,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
    ):
        mock_repo_cls.return_value.list_for_household.return_value = INVOICE_ITEMS
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), message)

    mock_gen.assert_not_called()  # Vertex skipped entirely — both turns
    assert turn.pending_action_id is None
    assert "period=2026-06" in turn.reply
    assert "₹1500.50" in turn.reply
    mock_repo_cls.return_value.list_for_household.assert_called_once_with("h-1", limit=3)


@pytest.mark.asyncio
async def test_real_failing_phrasing_what_did_i_owe_last_month_routes_to_history():
    """'last month' must route to history (get_my_invoices), NOT the
    current-month preview — it's asking about a PAST, already-billed month."""
    with (
        patch(REPO) as mock_repo_cls,
        patch(PREVIEW) as mock_preview,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
    ):
        mock_repo_cls.return_value.list_for_household.return_value = INVOICE_ITEMS
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), "what did I owe last month")

    mock_gen.assert_not_called()
    mock_preview.assert_not_called()  # must NOT go to the current-month tool
    assert "period=2026-06" in turn.reply
    mock_repo_cls.return_value.list_for_household.assert_called_once_with("h-1", limit=3)


# ── current-month sub-classification ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_current_month_phrasing_routes_to_preview_never_calls_vertex():
    fake_preview = {
        "household_id": "h-1", "period": "2026-07", "flat_number": "A-1",
        "line_items": [{"booking_id": "b1"}], "total_paise": 4200, "preview": True,
    }
    with (
        patch(PREVIEW, return_value=fake_preview) as mock_preview,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
    ):
        turn = await run_agent(
            CTX, _firestore_client(), _NoopStore(), "what do I owe so far this month",
        )

    mock_gen.assert_not_called()
    assert turn.pending_action_id is None
    assert "LIVE PREVIEW" in turn.reply
    assert "₹42.00" in turn.reply
    call_args = mock_preview.call_args.args
    assert call_args[1] == CTX
    assert call_args[2] == "t-1"
    assert call_args[3] == "h-1"


# ── error handling: dispatch failure falls back gracefully, still no Vertex ──

async def test_dispatch_error_returns_safe_fallback_without_calling_vertex():
    with (
        patch(REPO) as mock_repo_cls,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock) as mock_gen,
    ):
        mock_repo_cls.return_value.list_for_household.side_effect = RuntimeError("firestore down")
        turn = await run_agent(CTX, _firestore_client(), _NoopStore(), "my invoice please")

    mock_gen.assert_not_called()
    assert "error" not in turn.reply.lower() or "{" not in turn.reply  # never leaks raw JSON
    assert json.dumps({"error": "firestore down"}) != turn.reply


# ── non-matching messages fall through unchanged — Vertex IS called ─────────

@pytest.mark.asyncio
@pytest.mark.parametrize("message", [
    "book tennis tomorrow",
    "what's available today",
])
async def test_non_matching_message_falls_through_to_vertex(message):
    """Regression proof: a message that should NOT match the new keywords
    must still reach Vertex exactly like today — this change is additive
    only, never a restructuring of the existing flow."""
    text_response = AgentResponse(function_call=None, text="Okay.")
    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences", return_value={}),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX, _firestore_client(), _NoopStore(), message)

    mock_gen.assert_called_once()  # Vertex WAS called — unaffected fallback path
