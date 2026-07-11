"""Tests for Phase 15.6 — read-only agent invoice tools: get_my_invoices
(recent generated-invoice history) and get_my_current_month_charges (live
"so far this month" preview).

Both tools dispatch directly (no propose-confirm-execute — they mutate
nothing) via `_dispatch_readonly`, mirroring list_my_bookings/
get_my_preferences's exact pattern.

get_my_invoices' household-isolation test uses a small hand-written fake
Firestore query object (mirrors test_invoices_api.py's pattern) — real
filtering logic, not a mock that "happens to" return the right thing.
get_my_current_month_charges reuses preview_current_month_charge, whose
OWN household-filtering is already exhaustively tested in
test_invoicing_service.py — here we instead assert the dispatch WIRING
passes ctx.household_id through correctly (mocked, call-args asserted),
per the operational directive not to duplicate coverage without adding value.

End-to-end run_agent tests mirror test_get_my_preferences_tool_returns_
formatted_map's pattern exactly: mock the immediate function the dispatch
calls, not a full Firestore fixture — consistent with that existing test's
own precedent for get_my_preferences.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.services.agent.orchestrator import _dispatch_readonly, run_agent
from sport_slot.services.agent.vertex_client import AgentResponse

CTX_H1 = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                        role="resident", household_id="h-1")
CTX_H2 = TenantContext(uid="u2", tenant_id="t-1", tenant_slug="demo",
                        role="resident", household_id="h-2")

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FACILITY = {
    "id": "f-court1", "name": "Tennis Court 1",
    "active": True, "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "08:00", "end": "10:00"}] for day in _DAYS},
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
    """Minimal but properly wired Firestore mock for run_agent's early
    steps (facility list + tenant policy/timezone) — mirrors test_agent.py's
    own fixture of the same name exactly."""
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


# ── fake Firestore for get_my_invoices (real filtering, mirrors
# test_invoices_api.py's _FakeInvoicesQuery/_client_with_invoices) ───────────

class _FakeInvoiceSnap:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeInvoicesQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, field, op, value):
        assert op == "=="
        return _FakeInvoicesQuery([d for d in self._docs if d.get(field) == value])

    def order_by(self, field, direction=None):
        from google.cloud import firestore
        reverse = direction == firestore.Query.DESCENDING
        return _FakeInvoicesQuery(sorted(self._docs, key=lambda d: d[field], reverse=reverse))

    def limit(self, n):
        return _FakeInvoicesQuery(self._docs[:n])

    def stream(self):
        return [_FakeInvoiceSnap(d) for d in self._docs]


def _client_with_invoices(docs):
    client = MagicMock()
    tenant_doc = client.collection.return_value.document.return_value

    def _sub_collection(name):
        if name == "invoices":
            return _FakeInvoicesQuery(docs)
        return MagicMock()

    tenant_doc.collection.side_effect = _sub_collection
    return client


INVOICES_TWO_HOUSEHOLDS = [
    {"invoice_id": "h-1_2026-05", "household_id": "h-1", "period": "2026-05", "total_paise": 10000},
    {"invoice_id": "h-1_2026-06", "household_id": "h-1", "period": "2026-06", "total_paise": 150050},
    {"invoice_id": "h-2_2026-06", "household_id": "h-2", "period": "2026-06", "total_paise": 999900},
]


# ── get_my_invoices: direct dispatch ─────────────────────────────────────────

def test_get_my_invoices_returns_compact_summary_in_rupees():
    client = _client_with_invoices([INVOICES_TWO_HOUSEHOLDS[1]])

    result = _dispatch_readonly(CTX_H1, client, "get_my_invoices", {}, set(), [])

    assert "period=2026-06" in result
    assert "₹1500.50" in result
    assert "150050" not in result  # never raw paise


def test_get_my_invoices_household_isolation_two_sided():
    """Two households' invoices are present in the SAME fake collection —
    the caller (h-1) must see only its own, h-2's must never appear."""
    client = _client_with_invoices(INVOICES_TWO_HOUSEHOLDS)

    result = _dispatch_readonly(CTX_H1, client, "get_my_invoices", {}, set(), [])

    assert "2026-05" in result and "2026-06" in result
    assert "₹9999.00" not in result  # h-2's total (999900 paise) never appears
    assert "total_invoices=2" in result  # only h-1's two invoices


def test_get_my_invoices_other_household_sees_only_its_own():
    client = _client_with_invoices(INVOICES_TWO_HOUSEHOLDS)

    result = _dispatch_readonly(CTX_H2, client, "get_my_invoices", {}, set(), [])

    assert "total_invoices=1" in result
    assert "₹9999.00" in result
    assert "₹1500.50" not in result  # h-1's data never appears for h-2


def test_get_my_invoices_empty_household_graceful_not_error():
    client = _client_with_invoices([])

    result = _dispatch_readonly(CTX_H1, client, "get_my_invoices", {}, set(), [])

    assert result == "user has no generated invoices yet."
    assert "error" not in result.lower()


def test_get_my_invoices_respects_explicit_count_argument():
    many = [
        {"invoice_id": f"h-1_2026-0{m}", "household_id": "h-1", "period": f"2026-0{m}",
         "total_paise": 1000 * m}
        for m in range(1, 5)
    ]
    client = _client_with_invoices(many)

    result = _dispatch_readonly(CTX_H1, client, "get_my_invoices", {"count": 1}, set(), [])

    assert result.count("period=") == 1
    assert "total_invoices=1" in result


def test_get_my_invoices_error_returns_json_error_not_raise():
    client = MagicMock()
    client.collection.side_effect = RuntimeError("firestore down")

    result = _dispatch_readonly(CTX_H1, client, "get_my_invoices", {}, set(), [])

    assert json.loads(result) == {"error": "firestore down"}


# ── get_my_current_month_charges: direct dispatch ────────────────────────────

PREVIEW = "sport_slot.services.agent.orchestrator.preview_current_month_charge"


def test_get_my_current_month_charges_frames_itself_as_a_preview():
    fake_preview = {
        "household_id": "h-1", "period": "2026-07", "flat_number": "A-1",
        "line_items": [{"booking_id": "b1"}], "total_paise": 4200, "preview": True,
    }
    with patch(PREVIEW, return_value=fake_preview):
        result = _dispatch_readonly(CTX_H1, MagicMock(), "get_my_current_month_charges", {}, set(), [])

    assert "LIVE PREVIEW" in result
    assert "not a final invoice" in result
    assert "₹42.00" in result
    assert "4200" not in result  # never raw paise
    assert "bookings_so_far=1" in result


def test_get_my_current_month_charges_empty_state_still_frames_as_preview():
    fake_preview = {
        "household_id": "h-1", "period": "2026-07", "flat_number": None,
        "line_items": [], "total_paise": 0, "preview": True,
    }
    with patch(PREVIEW, return_value=fake_preview):
        result = _dispatch_readonly(CTX_H1, MagicMock(), "get_my_current_month_charges", {}, set(), [])

    assert "No bookings charged yet" in result
    assert "LIVE PREVIEW" in result
    assert "error" not in result.lower()


def test_get_my_current_month_charges_wiring_passes_callers_own_household():
    """Isolation at the WIRING level: preview_current_month_charge's own
    household-filtering is already exhaustively tested in
    test_invoicing_service.py — here we assert this dispatch calls it with
    ctx.household_id specifically for EACH distinct caller, never a fixed
    or wrong value."""
    fake_preview = {"household_id": "?", "period": "2026-07", "flat_number": None,
                     "line_items": [], "total_paise": 0, "preview": True}
    with patch(PREVIEW, return_value=fake_preview) as mock_preview:
        _dispatch_readonly(CTX_H1, MagicMock(), "get_my_current_month_charges", {}, set(), [])
        _dispatch_readonly(CTX_H2, MagicMock(), "get_my_current_month_charges", {}, set(), [])

    first_call_args = mock_preview.call_args_list[0].args
    second_call_args = mock_preview.call_args_list[1].args
    assert first_call_args[3] == "h-1"
    assert second_call_args[3] == "h-2"


def test_get_my_current_month_charges_error_returns_json_error_not_raise():
    with patch(PREVIEW, side_effect=RuntimeError("boom")):
        result = _dispatch_readonly(CTX_H1, MagicMock(), "get_my_current_month_charges", {}, set(), [])

    assert json.loads(result) == {"error": "boom"}


# ── end-to-end run_agent (mirrors test_get_my_preferences_tool_* pattern) ────

@pytest.mark.asyncio
async def test_run_agent_get_my_invoices_end_to_end():
    fc = AgentResponse(function_call=("get_my_invoices", {}), text=None)
    text_reply = AgentResponse(function_call=None, text="Your last invoice was ₹1500.50 for 2026-06.")

    with (
        patch("sport_slot.services.agent.orchestrator.InvoiceRepository") as mock_repo_cls,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        mock_repo_cls.return_value.list_for_household.return_value = [
            {"invoice_id": "h-1_2026-06", "household_id": "h-1", "period": "2026-06",
             "total_paise": 150050},
        ]
        turn = await run_agent(CTX_H1, _firestore_client(), _NoopStore(), "What was my last invoice?")

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "period=2026-06" in turn2_msg
    assert "₹1500.50" in turn2_msg
    assert turn.reply == "Your last invoice was ₹1500.50 for 2026-06."
    mock_repo_cls.return_value.list_for_household.assert_called_once_with("h-1", limit=3)


@pytest.mark.asyncio
async def test_run_agent_get_my_current_month_charges_end_to_end():
    fc = AgentResponse(function_call=("get_my_current_month_charges", {}), text=None)
    text_reply = AgentResponse(
        function_call=None,
        text="So far this month (still in progress, not a final invoice) you owe ₹42.00.",
    )
    fake_preview = {
        "household_id": "h-1", "period": "2026-07", "flat_number": "A-1",
        "line_items": [{"booking_id": "b1"}], "total_paise": 4200, "preview": True,
    }

    with (
        patch(PREVIEW, return_value=fake_preview) as mock_preview,
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, side_effect=[fc, text_reply]) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        turn = await run_agent(
            CTX_H1, _firestore_client(), _NoopStore(), "What do I owe so far this month?"
        )

    turn2_msg = mock_gen.call_args_list[1].kwargs["message"]
    assert "LIVE PREVIEW" in turn2_msg
    assert "₹42.00" in turn2_msg
    assert turn.reply == "So far this month (still in progress, not a final invoice) you owe ₹42.00."
    mock_preview.assert_called_once()
    call_args = mock_preview.call_args.args
    assert call_args[1] == CTX_H1
    assert call_args[2] == "t-1"
    assert call_args[3] == "h-1"


# ── system prompt routing rules ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_system_prompt_includes_invoice_tool_routing_rules():
    text_response = AgentResponse(function_call=None, text="Got it.")
    with (
        patch("sport_slot.services.agent.orchestrator.get_preferences", return_value={}),
        patch("sport_slot.services.agent.vertex_client.generate",
              new_callable=AsyncMock, return_value=text_response) as mock_gen,
        patch("sport_slot.services.agent.vertex_client.classify_output",
              new_callable=AsyncMock, return_value=True),
    ):
        await run_agent(CTX_H1, _firestore_client(), _NoopStore(), "Hello")

    system_instr = mock_gen.call_args_list[0].kwargs["system_instruction"]
    assert "get_my_invoices" in system_instr
    assert "get_my_current_month_charges" in system_instr
    assert "own invoice" in system_instr or "invoice/billing totals" in system_instr
