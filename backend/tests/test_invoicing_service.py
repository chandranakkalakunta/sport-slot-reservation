"""Service-level tests for services/invoicing.generate_invoices (Phase 15.3).

Uses small hand-written fake Firestore classes (not MagicMock chaining) so
each collection/document call routes to the right seeded fixture data —
clearer than deep MagicMock attribute-chaining for a client this shape-
sensitive (tenants -> per-tenant facilities/bookings/invoices).
"""
import datetime

from google.api_core.exceptions import AlreadyExists

from sport_slot.services.invoicing import _previous_month_range, generate_invoices


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


class _FakeTenantDoc:
    def __init__(self, tenant_id, facilities, bookings, invoice_store, fail_ids):
        self._tenant_id = tenant_id
        self._facilities = facilities
        self._bookings = bookings
        self._invoice_store = invoice_store
        self._fail_ids = fail_ids

    def collection(self, name):
        if name == "facilities":
            return _FakeStream(self._facilities)
        if name == "bookings":
            return _FakeStream(self._bookings)
        if name == "invoices":
            return _FakeInvoicesCollection(self._invoice_store, self._tenant_id, self._fail_ids)
        raise AssertionError(f"unexpected collection: {name}")


class _FakeTenantsCollection:
    def __init__(self, tenants, facilities_by_tenant, bookings_by_tenant, invoice_store, fail_ids):
        self._tenants = tenants
        self._facilities_by_tenant = facilities_by_tenant
        self._bookings_by_tenant = bookings_by_tenant
        self._invoice_store = invoice_store
        self._fail_ids = fail_ids

    def where(self, field, op, value):
        assert (field, op) == ("status", "==")
        return _FakeStream([t for t in self._tenants if t.get("status") == value])

    def document(self, tenant_id):
        return _FakeTenantDoc(
            tenant_id,
            self._facilities_by_tenant.get(tenant_id, []),
            self._bookings_by_tenant.get(tenant_id, []),
            self._invoice_store,
            self._fail_ids,
        )


class _FakeClient:
    def __init__(self, tenants, facilities_by_tenant, bookings_by_tenant,
                 existing_invoices=None, fail_household_ids=None):
        self.invoice_store: dict = dict(existing_invoices or {})
        self._tenants_col = _FakeTenantsCollection(
            tenants, facilities_by_tenant, bookings_by_tenant,
            self.invoice_store, fail_household_ids or set(),
        )

    def collection(self, name):
        assert name == "tenants"
        return self._tenants_col


TENANT = {"tenant_id": "t-1", "slug": "demo", "status": "active"}


def _booking(booking_id, household_id, facility_id, date="2026-06-15"):
    return {
        "id": booking_id, "household_id": household_id, "facility_id": facility_id,
        "date": date, "status": "confirmed",
    }


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
