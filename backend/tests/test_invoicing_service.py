"""Service-level tests for services/invoicing.generate_invoices (Phase 15.3).

Uses small hand-written fake Firestore classes (not MagicMock chaining) so
each collection/document call routes to the right seeded fixture data —
clearer than deep MagicMock attribute-chaining for a client this shape-
sensitive (tenants -> per-tenant facilities/bookings/invoices).

Phase 15.5: `export_invoices_for_period` is mocked (autouse, below) for
EVERY test in this file — it makes a real `storage.Client()`/
`google.auth.default()` call, which must never be attempted in a unit
test regardless of what credentials happen to be present in the
environment running it. Export-specific behavior is tested in
test_invoice_export.py and the wiring/regenerate tests near the bottom
of this file.
"""
import datetime
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import AlreadyExists

from sport_slot.auth.context import TenantContext
from sport_slot.services.invoicing import (
    _current_month_range,
    _month_range_for_period,
    _previous_month_range,
    generate_invoices,
    preview_current_month_charge,
    regenerate_for_tenant,
)


@pytest.fixture(autouse=True)
def mock_export(monkeypatch):
    """Prevents every test in this file from attempting a real GCS/auth
    call via the auto-export wired into _generate_for_tenant (15.5)."""
    mock = MagicMock(return_value={"csv_path": "x.csv", "json_path": "x.json", "row_count": 0})
    monkeypatch.setattr("sport_slot.services.invoicing.export_invoices_for_period", mock)
    return mock


class _FakeSnap:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeStream:
    def __init__(self, docs):
        self._docs = docs

    def where(self, *args, **kwargs):
        return self

    def stream(self):
        return [_FakeSnap(d) for d in self._docs]


class _FakeInvoiceDoc:
    def __init__(self, store, key, fail_ids):
        self._store = store
        self._key = key
        self._fail_ids = fail_ids

    def create(self, data):
        if self._key[1] in self._fail_ids:
            raise RuntimeError("simulated household failure")
        if self._key in self._store:
            raise AlreadyExists("already exists")
        self._store[self._key] = data


class _FakeInvoicesCollection:
    def __init__(self, store, tenant_id, fail_ids):
        self._store = store
        self._tenant_id = tenant_id
        self._fail_ids = fail_ids

    def document(self, invoice_id):
        return _FakeInvoiceDoc(self._store, (self._tenant_id, invoice_id), self._fail_ids)


class _FakeProfileSnap:
    def __init__(self, data):
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _FakeProfileDocRef:
    def __init__(self, data):
        self._data = data

    def get(self):
        return _FakeProfileSnap(self._data)


class _FakeUsersCollection:
    """Tracks .document(uid) calls so tests can assert the profile cache
    fires exactly once per unique resident, not once per booking."""

    def __init__(self, profiles: dict):
        self._profiles = profiles
        self.document_calls: list[str] = []

    def document(self, uid):
        self.document_calls.append(uid)
        return _FakeProfileDocRef(self._profiles.get(uid))


class _FakeTenantDoc:
    def __init__(self, tenant_id, facilities, bookings, invoice_store, fail_ids, profiles):
        self._tenant_id = tenant_id
        self._facilities = facilities
        self._bookings = bookings
        self._invoice_store = invoice_store
        self._fail_ids = fail_ids
        self.users_collection = _FakeUsersCollection(profiles)

    def collection(self, name):
        if name == "facilities":
            return _FakeStream(self._facilities)
        if name == "bookings":
            return _FakeStream(self._bookings)
        if name == "invoices":
            return _FakeInvoicesCollection(self._invoice_store, self._tenant_id, self._fail_ids)
        if name == "users":
            return self.users_collection
        raise AssertionError(f"unexpected collection: {name}")


class _FakeTenantsCollection:
    def __init__(self, tenants, facilities_by_tenant, bookings_by_tenant, invoice_store,
                 fail_ids, profiles_by_tenant):
        self._tenants = tenants
        self._facilities_by_tenant = facilities_by_tenant
        self._bookings_by_tenant = bookings_by_tenant
        self._invoice_store = invoice_store
        self._fail_ids = fail_ids
        self._profiles_by_tenant = profiles_by_tenant
        self.tenant_docs: dict[str, "_FakeTenantDoc"] = {}

    def where(self, field, op, value):
        assert (field, op) == ("status", "==")
        return _FakeStream([t for t in self._tenants if t.get("status") == value])

    def document(self, tenant_id):
        if tenant_id not in self.tenant_docs:
            self.tenant_docs[tenant_id] = _FakeTenantDoc(
                tenant_id,
                self._facilities_by_tenant.get(tenant_id, []),
                self._bookings_by_tenant.get(tenant_id, []),
                self._invoice_store,
                self._fail_ids,
                self._profiles_by_tenant.get(tenant_id, {}),
            )
        return self.tenant_docs[tenant_id]


class _FakeClient:
    def __init__(self, tenants, facilities_by_tenant, bookings_by_tenant,
                 existing_invoices=None, fail_household_ids=None, profiles_by_tenant=None):
        self.invoice_store: dict = dict(existing_invoices or {})
        self._tenants_col = _FakeTenantsCollection(
            tenants, facilities_by_tenant, bookings_by_tenant,
            self.invoice_store, fail_household_ids or set(),
            profiles_by_tenant or {},
        )

    def collection(self, name):
        assert name == "tenants"
        return self._tenants_col


TENANT = {"tenant_id": "t-1", "slug": "demo", "status": "active"}


def _booking(booking_id, household_id, facility_id, date="2026-06-15", uid=None):
    return {
        "id": booking_id, "household_id": household_id, "facility_id": facility_id,
        "date": date, "status": "confirmed", "uid": uid,
    }


def _profile(display_name, flat_number=None):
    return {"display_name": display_name, "flat_number": flat_number}


def _facility(facility_id, name, price_paise):
    return {"id": facility_id, "name": name, "price_paise": price_paise}


TODAY = datetime.date(2026, 7, 10)  # -> previous month = 2026-06


def test_previous_month_range_mid_year():
    start, end, label = _previous_month_range(datetime.date(2026, 7, 10))
    assert (start, end, label) == ("2026-06-01", "2026-06-30", "2026-06")


def test_previous_month_range_january_wraps_to_prior_december():
    start, end, label = _previous_month_range(datetime.date(2026, 1, 15))
    assert (start, end, label) == ("2025-12-01", "2025-12-31", "2025-12")


def test_groups_and_sums_across_multiple_households_and_facilities():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000), _facility("fac-B", "Court B", 3000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A"),
        _booking("b2", "h-1", "fac-A"),
        _booking("b3", "h-1", "fac-B"),
        _booking("b4", "h-2", "fac-A"),
    ]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["tenants_processed"] == 1
    assert summary["households_invoiced"] == 2
    assert summary["households_failed"] == []

    inv_h1 = client.invoice_store[("t-1", "h-1_2026-06")]
    assert inv_h1["total_paise"] == 13000
    assert inv_h1["household_id"] == "h-1"
    assert inv_h1["tenant_id"] == "t-1"
    assert inv_h1["period"] == "2026-06"
    assert len(inv_h1["line_items"]) == 3

    inv_h2 = client.invoice_store[("t-1", "h-2_2026-06")]
    assert inv_h2["total_paise"] == 5000
    assert len(inv_h2["line_items"]) == 1


def test_unpriced_facility_bookings_excluded_entirely_not_zero_line_items():
    facilities = {"t-1": [
        _facility("fac-A", "Court A", 5000),
        _facility("fac-C", "Unpriced Court", None),
    ]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A"),
        _booking("b2", "h-1", "fac-C"),  # unpriced — must be excluded, not a Rs.0 line item
    ]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 1
    inv = client.invoice_store[("t-1", "h-1_2026-06")]
    assert inv["total_paise"] == 5000
    assert len(inv["line_items"]) == 1
    assert inv["line_items"][0]["facility_id"] == "fac-A"


def test_zero_total_households_produce_no_invoice_two_sided():
    facilities = {"t-1": [
        _facility("fac-A", "Court A", 5000),
        _facility("fac-C", "Unpriced Court", None),
    ]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A"),   # eligible — gets an invoice
        _booking("b2", "h-2", "fac-C"),   # only unpriced booking — no invoice at all
    ]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 1
    assert ("t-1", "h-1_2026-06") in client.invoice_store
    assert ("t-1", "h-2_2026-06") not in client.invoice_store  # skipped, no invoice — not Rs.0


def test_household_with_existing_invoice_is_skipped_idempotent_no_error():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A")]}
    original_doc = {"invoice_id": "h-1_2026-06", "total_paise": 5000, "generated_at": "sentinel"}
    client = _FakeClient(
        [TENANT], facilities, bookings,
        existing_invoices={("t-1", "h-1_2026-06"): original_doc},
    )

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 0
    assert summary["households_skipped"] == 1
    assert summary["households_failed"] == []
    # Original document is untouched — not overwritten.
    assert client.invoice_store[("t-1", "h-1_2026-06")] == original_doc


def test_rerunning_the_job_for_the_same_period_does_not_duplicate_or_error():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A")]}
    client = _FakeClient([TENANT], facilities, bookings)

    first = generate_invoices(client, today=TODAY)
    second = generate_invoices(client, today=TODAY)

    assert first["households_invoiced"] == 1
    assert second["households_invoiced"] == 0
    assert second["households_skipped"] == 1
    assert second["households_failed"] == []
    assert len(client.invoice_store) == 1


def test_one_household_failure_does_not_block_others_partial_failure_two_sided():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A"),  # will fail
        _booking("b2", "h-2", "fac-A"),  # must still succeed
    ]}
    client = _FakeClient(
        [TENANT], facilities, bookings,
        fail_household_ids={"h-1_2026-06"},
    )

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 1
    assert ("t-1", "h-2_2026-06") in client.invoice_store
    assert len(summary["households_failed"]) == 1
    assert summary["households_failed"][0]["household_id"] == "h-1"
    assert summary["households_failed"][0]["tenant_id"] == "t-1"
    assert "simulated household failure" in summary["households_failed"][0]["reason"]
    assert ("t-1", "h-1_2026-06") not in client.invoice_store


def test_explicit_free_facility_zero_total_produces_no_invoice():
    """price_paise=0 (explicit free) is a valid, eligible price — but a household whose
    bookings are ALL against Rs.0 facilities still sums to zero, so per Decision 2 it
    still gets no invoice (never a Rs.0 invoice), even though the bookings were 'eligible'."""
    facilities = {"t-1": [_facility("fac-free", "Free Court", 0)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-free")]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 0
    assert summary["households_skipped"] == 1
    assert ("t-1", "h-1_2026-06") not in client.invoice_store


def test_booking_missing_household_id_is_skipped_not_grouped():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    orphan_booking = {"id": "b1", "household_id": None, "facility_id": "fac-A",
                       "date": "2026-06-15", "status": "confirmed"}
    bookings = {"t-1": [orphan_booking]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 0
    assert client.invoice_store == {}


def test_tenant_id_missing_from_tenant_doc_is_skipped():
    client = _FakeClient([{"slug": "no-id", "status": "active"}], {}, {})

    summary = generate_invoices(client, today=TODAY)

    assert summary["tenants_processed"] == 0
    assert client.invoice_store == {}


def test_one_tenant_failure_does_not_block_other_tenants_partial_failure_two_sided():
    good_tenant = {"tenant_id": "t-good", "slug": "good", "status": "active"}
    bad_tenant = {"tenant_id": "t-bad", "slug": "bad", "status": "active"}
    facilities = {
        "t-good": [_facility("fac-A", "Court A", 5000)],
        "t-bad": [None],  # malformed facility doc — raises inside _priced_facilities
    }
    bookings = {
        "t-good": [_booking("b1", "h-1", "fac-A")],
        "t-bad": [_booking("b2", "h-2", "fac-A")],
    }
    client = _FakeClient([good_tenant, bad_tenant], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["tenants_processed"] == 1
    assert ("t-good", "h-1_2026-06") in client.invoice_store
    assert ("t-bad", "h-2_2026-06") not in client.invoice_store


def test_inactive_tenant_is_not_processed():
    inactive_tenant = {"tenant_id": "t-2", "slug": "gone", "status": "inactive"}
    facilities = {"t-2": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-2": [_booking("b1", "h-1", "fac-A")]}
    client = _FakeClient([inactive_tenant], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["tenants_processed"] == 0
    assert summary["households_invoiced"] == 0
    assert client.invoice_store == {}


# ── Correction: denormalized resident_uid/resident_name + flat_number ───────
# (Phase 15.3 fix — resolved once per unique resident per tenant generation
# pass, at generation time, never at display time.)

def test_line_items_carry_the_correct_resident_not_a_housemates():
    """A two-resident household: each line item's resident_uid/resident_name
    must match the booking that actually produced it, never the other
    resident sharing the same household_id."""
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A", uid="u-alice"),
        _booking("b2", "h-1", "fac-A", uid="u-bob"),
    ]}
    profiles = {"t-1": {
        "u-alice": _profile("Alice", flat_number="A-1"),
        "u-bob": _profile("Bob", flat_number="A-1"),
    }}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    generate_invoices(client, today=TODAY)

    items = client.invoice_store[("t-1", "h-1_2026-06")]["line_items"]
    by_booking = {i["booking_id"]: i for i in items}
    assert by_booking["b1"]["resident_uid"] == "u-alice"
    assert by_booking["b1"]["resident_name"] == "Alice"
    assert by_booking["b2"]["resident_uid"] == "u-bob"
    assert by_booking["b2"]["resident_name"] == "Bob"


def test_profile_lookup_cached_once_per_unique_resident_not_per_booking():
    """The actual point of the correction: 3 bookings from the same resident
    must trigger exactly 1 profile fetch, not 3. Asserts the fake users
    collection's call count directly — does not just infer caching from
    the output."""
    facilities = {"t-1": [_facility("fac-A", "Court A", 1000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A", date="2026-06-01", uid="u-alice"),
        _booking("b2", "h-1", "fac-A", date="2026-06-08", uid="u-alice"),
        _booking("b3", "h-1", "fac-A", date="2026-06-15", uid="u-alice"),
    ]}
    profiles = {"t-1": {"u-alice": _profile("Alice", flat_number="A-1")}}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    generate_invoices(client, today=TODAY)

    users_col = client._tenants_col.tenant_docs["t-1"].users_collection
    assert users_col.document_calls == ["u-alice"]  # one fetch, not three


def test_flat_number_set_on_invoice_from_first_resident_encountered():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A", uid="u-alice"),
        _booking("b2", "h-1", "fac-A", uid="u-bob"),
    ]}
    profiles = {"t-1": {
        "u-alice": _profile("Alice", flat_number="A-1"),
        "u-bob": _profile("Bob", flat_number="A-1"),
    }}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    generate_invoices(client, today=TODAY)

    assert client.invoice_store[("t-1", "h-1_2026-06")]["flat_number"] == "A-1"


def test_flat_number_falls_through_to_a_later_resolvable_resident():
    """CORRECTION (production bug): the FIRST booking's resident (u-deleted)
    has no resolvable profile — the household's flat_number must not get
    stuck on None just because of that. A LATER booking in the same
    household from a currently-active resident (u-bob) DOES resolve, and
    that resolved flat_number must be used, not "Unknown flat"."""
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [
        _booking("b1", "h-1", "fac-A", date="2026-06-01", uid="u-deleted"),
        _booking("b2", "h-1", "fac-A", date="2026-06-15", uid="u-bob"),
    ]}
    profiles = {"t-1": {"u-bob": _profile("Bob", flat_number="A-1")}}  # u-deleted absent
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    generate_invoices(client, today=TODAY)

    assert client.invoice_store[("t-1", "h-1_2026-06")]["flat_number"] == "A-1"


def test_missing_profile_falls_back_without_crashing():
    """A booking's uid with no resolvable profile (deleted resident) must
    not crash generation — resident_name falls back to a sentinel and
    flat_number falls back to None."""
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", uid="u-deleted")]}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant={"t-1": {}})

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_failed"] == []
    inv = client.invoice_store[("t-1", "h-1_2026-06")]
    assert inv["flat_number"] is None
    assert inv["line_items"][0]["resident_uid"] == "u-deleted"
    assert inv["line_items"][0]["resident_name"] == "Unknown resident"


def test_booking_with_no_uid_at_all_does_not_query_profiles():
    """Defensive: a booking somehow missing uid entirely must not attempt
    a profile lookup (would fail on a None document id) — falls back
    the same as a missing profile."""
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A")]}  # uid defaults to None
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant={"t-1": {}})

    generate_invoices(client, today=TODAY)

    users_col = client._tenants_col.tenant_docs["t-1"].users_collection
    assert users_col.document_calls == []  # guarded — never queried
    inv = client.invoice_store[("t-1", "h-1_2026-06")]
    assert inv["line_items"][0]["resident_name"] == "Unknown resident"
    assert inv["flat_number"] is None


# ── Phase 15.4c: current-month range + live preview ──────────────────────────

def test_current_month_range_mid_month():
    start, end, label = _current_month_range(datetime.date(2026, 7, 15))
    assert (start, end, label) == ("2026-07-01", "2026-07-15", "2026-07")


def test_current_month_range_first_of_month():
    start, end, label = _current_month_range(datetime.date(2026, 7, 1))
    assert (start, end, label) == ("2026-07-01", "2026-07-01", "2026-07")


def _preview_ctx() -> TenantContext:
    return TenantContext(uid="admin-1", tenant_id="t-1", tenant_slug="demo",
                          role="tenant_admin", household_id=None)


def test_preview_reflects_a_newly_added_confirmed_booking():
    """A booking confirmed THIS month (not yet invoiced — no document exists
    for it anywhere) must show up in the live preview's total and line items."""
    today = datetime.date(2026, 7, 15)
    facilities = {"t-1": [_facility("fac-A", "Court A", 7500)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", date="2026-07-10", uid="u-alice")]}
    profiles = {"t-1": {"u-alice": _profile("Alice", flat_number="A-1")}}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    result = preview_current_month_charge(client, _preview_ctx(), "t-1", "h-1", today=today)

    assert result["preview"] is True
    assert result["household_id"] == "h-1"
    assert result["period"] == "2026-07"
    assert result["flat_number"] == "A-1"
    assert result["total_paise"] == 7500
    assert len(result["line_items"]) == 1
    assert result["line_items"][0]["booking_id"] == "b1"
    assert result["line_items"][0]["resident_name"] == "Alice"


def test_preview_writes_nothing_to_firestore():
    """The whole point of a preview: it must never create/persist an
    invoice document. Asserted directly against the fake's write-tracking
    store, not just inferred from the response shape."""
    today = datetime.date(2026, 7, 15)
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", date="2026-07-10", uid="u-alice")]}
    profiles = {"t-1": {"u-alice": _profile("Alice", flat_number="A-1")}}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant=profiles)

    preview_current_month_charge(client, _preview_ctx(), "t-1", "h-1", today=today)

    # No invoice document exists anywhere in the fake's backing store —
    # the only way data lands there is via InvoiceRepository.create_if_absent.
    assert client.invoice_store == {}


def test_preview_for_household_with_no_bookings_yet_returns_zero_total_not_error():
    today = datetime.date(2026, 7, 15)
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": []}
    client = _FakeClient([TENANT], facilities, bookings, profiles_by_tenant={"t-1": {}})

    result = preview_current_month_charge(client, _preview_ctx(), "t-1", "h-1", today=today)

    assert result["total_paise"] == 0
    assert result["line_items"] == []
    assert result["flat_number"] is None
    assert result["preview"] is True


# ── Phase 15.5: automatic export wiring + manual regeneration ────────────────

def test_month_range_for_period_mid_year():
    assert _month_range_for_period("2026-06") == ("2026-06-01", "2026-06-30")


def test_month_range_for_period_december_wraps_correctly():
    assert _month_range_for_period("2026-12") == ("2026-12-01", "2026-12-31")


def test_successful_generation_triggers_automatic_export(mock_export):
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A")]}
    client = _FakeClient([TENANT], facilities, bookings)

    generate_invoices(client, today=TODAY)

    mock_export.assert_called_once_with(client, "t-1", "2026-06")


def test_export_failure_does_not_fail_the_generation_summary(mock_export):
    """Export is a non-blocking side effect (mirrors the notification-
    enqueue pattern elsewhere) — its failure must never turn an otherwise
    successful generation into a reported households_failed entry."""
    mock_export.side_effect = RuntimeError("simulated GCS failure")
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A")]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = generate_invoices(client, today=TODAY)

    assert summary["households_invoiced"] == 1
    assert summary["households_failed"] == []
    assert ("t-1", "h-1_2026-06") in client.invoice_store


def _regen_ctx(tenant_id="t-1") -> TenantContext:
    return TenantContext(uid="admin-1", tenant_id=tenant_id, tenant_slug="demo",
                          role="tenant_admin", household_id=None)


def test_regenerate_for_tenant_defaults_to_previous_month():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", date="2026-06-15")]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = regenerate_for_tenant(client, _regen_ctx(), today=datetime.date(2026, 7, 10))

    assert summary["period"] == "2026-06"
    assert summary["households_invoiced"] == 1
    assert ("t-1", "h-1_2026-06") in client.invoice_store


def test_regenerate_for_tenant_with_explicit_period():
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", date="2026-03-15")]}
    client = _FakeClient([TENANT], facilities, bookings)

    summary = regenerate_for_tenant(client, _regen_ctx(), period_label="2026-03")

    assert summary["period"] == "2026-03"
    assert ("t-1", "h-1_2026-03") in client.invoice_store


def test_regenerate_for_tenant_only_touches_caller_own_tenant():
    """Cross-tenant isolation: regenerate_for_tenant has no tenant_id
    parameter to override — seeding a SECOND tenant's data and calling
    regenerate for tenant t-1 must never write anything for t-2."""
    facilities = {
        "t-1": [_facility("fac-A", "Court A", 5000)],
        "t-2": [_facility("fac-B", "Court B", 7000)],
    }
    bookings = {
        "t-1": [_booking("b1", "h-1", "fac-A", date="2026-03-15")],
        "t-2": [_booking("b2", "h-9", "fac-B", date="2026-03-15")],
    }
    client = _FakeClient([TENANT, {"tenant_id": "t-2", "slug": "other", "status": "active"}],
                          facilities, bookings)

    regenerate_for_tenant(client, _regen_ctx("t-1"), period_label="2026-03")

    assert ("t-1", "h-1_2026-03") in client.invoice_store
    assert ("t-2", "h-9_2026-03") not in client.invoice_store


def test_regenerate_for_tenant_also_auto_exports(mock_export):
    facilities = {"t-1": [_facility("fac-A", "Court A", 5000)]}
    bookings = {"t-1": [_booking("b1", "h-1", "fac-A", date="2026-03-15")]}
    client = _FakeClient([TENANT], facilities, bookings)

    regenerate_for_tenant(client, _regen_ctx(), period_label="2026-03")

    mock_export.assert_called_once_with(client, "t-1", "2026-03")
