"""Tests for Phase 15.4 (family invoice summary UI) — GET /invoices/mine
and InvoiceRepository.list_for_household.

Cross-household isolation is a security-adjacent boundary: tested directly
against real query-filtering logic (a small hand-written fake Firestore
query object, not a MagicMock that "happens to" return the right thing),
per the operational directive not to just assume correct filtering.
"""
from unittest.mock import MagicMock, patch

from google.cloud import firestore

from sport_slot.auth.context import TenantContext
from sport_slot.dependencies import get_firestore_client
from sport_slot.repositories.invoices import InvoiceRepository

VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}

RESIDENT_H1 = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
               "tenant_slug": "demo", "household_id": "h-1"}
RESIDENT_H2 = {"uid": "u2", "role": "resident", "tenant_id": "t-1",
               "tenant_slug": "demo", "household_id": "h-2"}
RESIDENT_NO_HOUSEHOLD = {"uid": "u3", "role": "resident", "tenant_id": "t-1",
                          "tenant_slug": "demo"}  # no household_id claim at all

INVOICES = [
    {"invoice_id": "h-1_2026-05", "household_id": "h-1", "period": "2026-05",
     "total_paise": 10000, "line_items": []},
    {"invoice_id": "h-1_2026-06", "household_id": "h-1", "period": "2026-06",
     "total_paise": 20000, "line_items": []},
    {"invoice_id": "h-2_2026-06", "household_id": "h-2", "period": "2026-06",
     "total_paise": 99900, "line_items": []},
]


class _FakeInvoiceSnap:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeInvoicesQuery:
    """Mimics the subset of the Firestore query builder that
    InvoiceRepository.list_for_household actually calls, applying real
    equality-filter + order_by + limit semantics against seeded docs."""

    def __init__(self, docs):
        self._docs = docs

    def where(self, field, op, value):
        assert op == "=="
        return _FakeInvoicesQuery([d for d in self._docs if d.get(field) == value])

    def order_by(self, field, direction=None):
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


# ── Repository-level: real filtering logic, not an assumption ────────────────

def test_list_for_household_returns_only_own_household_most_recent_first():
    ctx = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                         role="resident", household_id="h-1")
    client = _client_with_invoices(INVOICES)
    repo = InvoiceRepository(ctx, client)

    result = repo.list_for_household("h-1")

    ids = [d["invoice_id"] for d in result]
    assert ids == ["h-1_2026-06", "h-1_2026-05"]  # most-recent-period-first
    assert all(d["household_id"] == "h-1" for d in result)
    assert "h-2_2026-06" not in ids  # the other household's invoice never appears


def test_list_for_household_other_household_isolated_too():
    ctx = TenantContext(uid="u2", tenant_id="t-1", tenant_slug="demo",
                         role="resident", household_id="h-2")
    client = _client_with_invoices(INVOICES)
    repo = InvoiceRepository(ctx, client)

    result = repo.list_for_household("h-2")

    ids = [d["invoice_id"] for d in result]
    assert ids == ["h-2_2026-06"]
    assert "h-1_2026-05" not in ids
    assert "h-1_2026-06" not in ids


def test_list_for_household_guards_missing_household_id_without_querying():
    ctx = TenantContext(uid="u3", tenant_id="t-1", tenant_slug="demo",
                         role="resident", household_id=None)
    client = _client_with_invoices(INVOICES)
    repo = InvoiceRepository(ctx, client)

    assert repo.list_for_household(None) == []
    assert repo.list_for_household("") == []
    # Guard fires before touching Firestore at all.
    client.collection.assert_not_called()


# ── Route-level: GET /invoices/mine, scoped by the auth-derived ctx ──────────

async def test_invoices_mine_returns_only_callers_household(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_H1):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/mine", headers={**AUTH, **HOST})

    assert resp.status_code == 200
    ids = [i["invoice_id"] for i in resp.json()["items"]]
    assert ids == ["h-1_2026-06", "h-1_2026-05"]
    assert "h-2_2026-06" not in ids


async def test_invoices_mine_different_caller_sees_different_household(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_H2):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/mine", headers={**AUTH, **HOST})

    assert resp.status_code == 200
    ids = [i["invoice_id"] for i in resp.json()["items"]]
    assert ids == ["h-2_2026-06"]
    assert "h-1_2026-05" not in ids
    assert "h-1_2026-06" not in ids


async def test_invoices_mine_no_household_id_returns_empty(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_NO_HOUSEHOLD):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/mine", headers={**AUTH, **HOST})

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    client_fake.collection.assert_not_called()
