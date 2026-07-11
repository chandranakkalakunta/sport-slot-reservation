"""Tests for Phase 15.4 (family invoice summary UI) — GET /invoices/mine
and InvoiceRepository.list_for_household — plus Phase 15.4b (tenant-admin
latest invoice per flat) — GET /invoices/tenant/latest and
InvoiceRepository.list_latest_per_household — plus Phase 15.4c (per-flat
history + live current-month preview) — GET /invoices/tenant/history and
GET /invoices/tenant/preview.

Cross-household isolation is a security-adjacent boundary: tested directly
against real query-filtering logic (a small hand-written fake Firestore
query object, not a MagicMock that "happens to" return the right thing),
per the operational directive not to just assume correct filtering. The
resident-rejected-403 tests for the 15.4b/15.4c tenant-admin routes are the
same kind of boundary. Preview-specific tests (writes-nothing, reflects a
new booking) live in test_invoicing_service.py, where the richer fake
Firestore client (facilities/bookings/users, not just invoices) already
exists — this file only checks the /tenant/preview route's own wiring
(pass-through of household_id/tenant_id, and the 403 gate).
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
TENANT_ADMIN = {"uid": "admin-1", "role": "tenant_admin", "tenant_id": "t-1",
                 "tenant_slug": "demo"}

INVOICES = [
    {"invoice_id": "h-1_2026-05", "household_id": "h-1", "period": "2026-05",
     "flat_number": "A-1", "total_paise": 10000, "line_items": []},
    {"invoice_id": "h-1_2026-06", "household_id": "h-1", "period": "2026-06",
     "flat_number": "A-1", "total_paise": 20000, "line_items": []},
    {"invoice_id": "h-2_2026-06", "household_id": "h-2", "period": "2026-06",
     "flat_number": "B-2", "total_paise": 99900, "line_items": []},
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


# ── Repository-level (15.4b): list_latest_per_household ──────────────────────

def test_list_latest_per_household_picks_max_period_not_the_older_one():
    """h-1 has invoices for two periods (2026-05 and 2026-06) — only the
    newer one (2026-06) must be returned, never the older 2026-05."""
    ctx = TenantContext(uid="admin-1", tenant_id="t-1", tenant_slug="demo",
                         role="tenant_admin", household_id=None)
    client = _client_with_invoices(INVOICES)
    repo = InvoiceRepository(ctx, client)

    result = repo.list_latest_per_household()

    by_household = {d["household_id"]: d for d in result}
    assert len(result) == 2  # one entry per household, not per invoice
    assert by_household["h-1"]["invoice_id"] == "h-1_2026-06"
    assert by_household["h-1"]["period"] == "2026-06"
    assert "h-1_2026-05" not in [d["invoice_id"] for d in result]
    assert by_household["h-2"]["invoice_id"] == "h-2_2026-06"


def test_list_latest_per_household_sorted_by_flat_number():
    ctx = TenantContext(uid="admin-1", tenant_id="t-1", tenant_slug="demo",
                         role="tenant_admin", household_id=None)
    client = _client_with_invoices(INVOICES)
    repo = InvoiceRepository(ctx, client)

    result = repo.list_latest_per_household()

    assert [d["flat_number"] for d in result] == ["A-1", "B-2"]


def test_list_latest_per_household_skips_malformed_doc_with_no_household_id():
    ctx = TenantContext(uid="admin-1", tenant_id="t-1", tenant_slug="demo",
                         role="tenant_admin", household_id=None)
    docs = [*INVOICES, {"invoice_id": "orphan_2026-06", "household_id": None,
                         "period": "2026-06", "flat_number": None, "total_paise": 100}]
    client = _client_with_invoices(docs)
    repo = InvoiceRepository(ctx, client)

    result = repo.list_latest_per_household()

    assert "orphan_2026-06" not in [d["invoice_id"] for d in result]
    assert len(result) == 2


def test_list_latest_per_household_empty_tenant_returns_empty_list():
    ctx = TenantContext(uid="admin-1", tenant_id="t-1", tenant_slug="demo",
                         role="tenant_admin", household_id=None)
    client = _client_with_invoices([])
    repo = InvoiceRepository(ctx, client)

    assert repo.list_latest_per_household() == []


# ── Route-level (15.4b): GET /invoices/tenant/latest, tenant-admin only ──────

async def test_tenant_latest_invoices_returns_latest_per_household(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=TENANT_ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/tenant/latest", headers={**AUTH, **HOST})

    assert resp.status_code == 200
    items = resp.json()["items"]
    ids = [i["invoice_id"] for i in items]
    assert len(items) == 2
    assert "h-1_2026-06" in ids
    assert "h-1_2026-05" not in ids  # superseded by the newer period
    assert "h-2_2026-06" in ids


async def test_tenant_latest_invoices_rejects_resident_caller_403(make_client):
    """A resident (non-admin) must never reach this tenant-wide endpoint."""
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_H1):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/tenant/latest", headers={**AUTH, **HOST})

    assert resp.status_code == 403


async def test_tenant_latest_invoices_empty_tenant_returns_empty_list_not_error(make_client):
    client_fake = _client_with_invoices([])
    with patch(VERIFY, return_value=TENANT_ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get("/api/v1/invoices/tenant/latest", headers={**AUTH, **HOST})

    assert resp.status_code == 200
    assert resp.json()["items"] == []


# ── Route-level (15.4c): GET /invoices/tenant/history, tenant-admin only ─────

MANY_PERIODS_H3 = [
    {"invoice_id": f"h-3_2026-{m:02d}", "household_id": "h-3", "period": f"2026-{m:02d}",
     "flat_number": "C-3", "total_paise": 1000 * m, "line_items": []}
    for m in range(1, 6)  # 5 periods: 2026-01 .. 2026-05
]


async def test_tenant_invoice_history_limits_to_3_most_recent(make_client):
    client_fake = _client_with_invoices(MANY_PERIODS_H3)
    with patch(VERIFY, return_value=TENANT_ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get(
                "/api/v1/invoices/tenant/history?household_id=h-3", headers={**AUTH, **HOST},
            )

    assert resp.status_code == 200
    ids = [i["invoice_id"] for i in resp.json()["items"]]
    assert ids == ["h-3_2026-05", "h-3_2026-04", "h-3_2026-03"]  # 3 most recent, newest-first


async def test_tenant_invoice_history_arbitrary_household_not_just_admins_own(make_client):
    """Admin-facing: must accept ANY household_id in the tenant, unlike /mine."""
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=TENANT_ADMIN):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get(
                "/api/v1/invoices/tenant/history?household_id=h-2", headers={**AUTH, **HOST},
            )

    assert resp.status_code == 200
    ids = [i["invoice_id"] for i in resp.json()["items"]]
    assert ids == ["h-2_2026-06"]


async def test_tenant_invoice_history_rejects_resident_caller_403(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_H1):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get(
                "/api/v1/invoices/tenant/history?household_id=h-1", headers={**AUTH, **HOST},
            )

    assert resp.status_code == 403


# ── Route-level (15.4c): GET /invoices/tenant/preview, tenant-admin only ────
# The preview computation itself (writes-nothing, reflects a new booking) is
# tested in test_invoicing_service.py against the richer fake client. Here we
# only check this route's own wiring and its 403 gate.

async def test_tenant_invoice_preview_rejects_resident_caller_403(make_client):
    client_fake = _client_with_invoices(INVOICES)
    with patch(VERIFY, return_value=RESIDENT_H1):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get(
                "/api/v1/invoices/tenant/preview?household_id=h-1", headers={**AUTH, **HOST},
            )

    assert resp.status_code == 403


async def test_tenant_invoice_preview_route_passes_through_to_shared_preview_function(make_client):
    """Confirms the route wires household_id + the admin's own tenant_id
    into preview_current_month_charge and returns its result directly
    (unwrapped, matching the GET /users/me single-resource convention)."""
    client_fake = _client_with_invoices(INVOICES)
    fake_preview = {
        "household_id": "h-1", "period": "2026-07", "period_start": "2026-07-01",
        "period_end": "2026-07-11", "flat_number": "A-1", "line_items": [],
        "total_paise": 4200, "preview": True,
    }
    with patch(VERIFY, return_value=TENANT_ADMIN), \
         patch("sport_slot.api.v1.invoices.preview_current_month_charge",
               return_value=fake_preview) as mock_preview:
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = lambda: client_fake
            resp = await client.get(
                "/api/v1/invoices/tenant/preview?household_id=h-1", headers={**AUTH, **HOST},
            )

    assert resp.status_code == 200
    assert resp.json() == fake_preview
    _, kwargs = mock_preview.call_args
    args = mock_preview.call_args.args
    # Called as (client, ctx, tenant_id, household_id) — tenant_id must be the
    # ADMIN's own tenant (from ctx), household_id the requested query param.
    assert args[2] == "t-1"
    assert args[3] == "h-1"
    assert kwargs == {}
