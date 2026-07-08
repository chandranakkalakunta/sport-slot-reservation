"""Tests for GET /api/v1/tenant/overview/daily (Daily Booking Overview)."""

from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client

ADMIN = {"uid": "admin-1", "role": "tenant_admin", "tenant_id": "t-1",
         "tenant_slug": "demo", "household_id": "h-0"}
RESIDENT = {"uid": "u1", "role": "resident", "tenant_id": "t-1",
            "tenant_slug": "demo", "household_id": "h-1"}
AUTH = {"authorization": "Bearer fake"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"

# 2026-07-07 is a Tuesday — weekly_schedule keys below are chosen accordingly.
# slot_duration_minutes + weekly_schedule are required by compute_slots (used
# to build each facility's `slots` capacity list); every facility fixture
# needs them now, not just ones under test for slots specifically.
FAC_ALPHA = {"id": "fac-alpha", "name": "Alpha Court", "facility_type_id": "badminton",
             "sport": "badminton", "slot_duration_minutes": 60,
             "weekly_schedule": {"tuesday": [{"start": "09:00", "end": "12:00"}]}}
FAC_ZULU = {"id": "fac-zulu", "name": "Zulu Court", "facility_type_id": "tennis",
            "sport": "tennis", "slot_duration_minutes": 60,
            "weekly_schedule": {"tuesday": [{"start": "08:00", "end": "09:00"}]}}
FAC_BETA = {"id": "fac-beta", "name": "Beta Court", "facility_type_id": "badminton",
            "sport": "badminton", "slot_duration_minutes": 60,
            "weekly_schedule": {"tuesday": [{"start": "14:00", "end": "15:00"}]}}

BOOKING_CONFIRMED = {
    "id": "fac-alpha_2026-07-07_09:00",
    "uid": "u-alice",
    "facility_id": "fac-alpha",
    "date": "2026-07-07",
    "start": "09:00",
    "end": "10:00",
    "status": "confirmed",
    "household_id": "h-1",
    "cancelled_at": None,
}
BOOKING_CANCELLED = {
    "id": "fac-alpha_2026-07-07_10:00",
    "uid": "u-bob",
    "facility_id": "fac-alpha",
    "date": "2026-07-07",
    "start": "10:00",
    "end": "11:00",
    "status": "cancelled",
    "household_id": "h-2",
    "cancelled_at": "2026-07-06T18:00:00Z",
}
PROFILE_ALICE = {
    "uid": "u-alice", "email": "alice@demo.com", "display_name": "Alice",
    "role": "resident", "flat_number": "A-1",
}
PROFILE_BOB = {
    "uid": "u-bob", "email": "bob@demo.com", "display_name": "Bob",
    "role": "resident", "flat_number": "B-2",
}


def _overview_mock(facilities, bookings, profiles):
    """Build a Firestore client mock for the daily overview endpoint."""
    client = MagicMock()

    # Facilities collection (.stream())
    fac_snaps = []
    for f in facilities:
        s = MagicMock()
        s.to_dict.return_value = f
        fac_snaps.append(s)

    # Bookings collection (.where(...).stream())
    bk_snaps = []
    for b in bookings:
        s = MagicMock()
        s.to_dict.return_value = b
        bk_snaps.append(s)

    # Profile get() — keyed by uid
    def _profile_get(uid):
        snap = MagicMock()
        p = profiles.get(uid)
        snap.exists = p is not None
        snap.to_dict.return_value = p
        return snap

    # Build the mock chain:
    # client.collection("tenants").document(tid).collection("facilities").stream()
    # client.collection("tenants").document(tid).collection("bookings").where().stream()
    # client.collection("tenants").document(tid).collection("users").document(uid).get()

    def _sub_col(name):
        sub = MagicMock()
        if name == "facilities":
            sub.stream.return_value = fac_snaps
        elif name == "bookings":
            bk_col = MagicMock()
            bk_col.where.return_value = bk_col
            bk_col.stream.return_value = bk_snaps
            return bk_col
        elif name == "users":
            def _doc(uid):
                d = MagicMock()
                d.get.return_value = _profile_get(uid)
                return d
            sub.document.side_effect = _doc
        return sub

    tenant_doc = MagicMock()
    tenant_doc.collection.side_effect = _sub_col

    tenant_col = MagicMock()
    tenant_col.document.return_value = tenant_doc

    client.collection.return_value = tenant_col
    return client


async def test_daily_overview_returns_facilities_alphabetically(make_client):
    """(a) Two-sided: facilities MUST appear alphabetically, not insertion order.

    RED:  if facilities are returned in insertion order (Zulu, Alpha, Beta),
          the first item name is "Zulu Court" — assertion fails.
    GREEN: sorted by name, order is Alpha, Beta, Zulu.
    """
    client = _overview_mock(
        facilities=[FAC_ZULU, FAC_ALPHA, FAC_BETA],
        bookings=[],
        profiles={},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    names = [f["name"] for f in resp.json()["facilities"]]
    assert names == ["Alpha Court", "Beta Court", "Zulu Court"], (
        f"Expected alphabetical order, got {names}"
    )


async def test_daily_overview_confirmed_booking_appears_with_resident_info(make_client):
    """Confirmed booking is present in the response with resident name and email."""
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[BOOKING_CONFIRMED],
        profiles={"u-alice": PROFILE_ALICE},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    bookings = resp.json()["facilities"][0]["bookings"]
    assert len(bookings) == 1
    b = bookings[0]
    assert b["status"] == "confirmed"
    assert b["start"] == "09:00"
    assert b["resident_name"] == "Alice"
    assert b["resident_email"] == "alice@demo.com"


async def test_daily_overview_cancelled_booking_appears_not_hidden(make_client):
    """(a) Two-sided: cancelled bookings MUST appear in the response — not filtered out.

    RED:  if the endpoint filters status=="confirmed" only, cancelled booking
          is absent and len(bookings) == 0.
    GREEN: cancelled booking is present with status="cancelled".
    """
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[BOOKING_CANCELLED],
        profiles={"u-bob": PROFILE_BOB},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    bookings = resp.json()["facilities"][0]["bookings"]
    assert len(bookings) == 1, "Cancelled booking must not be hidden"
    assert bookings[0]["status"] == "cancelled"
    assert bookings[0]["resident_name"] == "Bob"
    assert bookings[0]["resident_email"] == "bob@demo.com"


async def test_daily_overview_both_statuses_present(make_client):
    """Facility with one confirmed and one cancelled booking returns both."""
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[BOOKING_CONFIRMED, BOOKING_CANCELLED],
        profiles={"u-alice": PROFILE_ALICE, "u-bob": PROFILE_BOB},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    bookings = resp.json()["facilities"][0]["bookings"]
    assert len(bookings) == 2
    statuses = {b["status"] for b in bookings}
    assert statuses == {"confirmed", "cancelled"}


async def test_daily_overview_facility_with_no_bookings_still_appears(make_client):
    """A facility that has no bookings on the date still appears in the response."""
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[],
        profiles={},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    facs = resp.json()["facilities"]
    assert len(facs) == 1
    assert facs[0]["bookings"] == []


async def test_daily_overview_response_includes_date_field(make_client):
    """Response envelope includes the queried date."""
    client = _overview_mock(facilities=[], bookings=[], profiles={})
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    assert resp.json()["date"] == "2026-07-07"


async def test_daily_overview_resident_forbidden(make_client):
    """Residents (non-admin) cannot access the daily overview."""
    client = _overview_mock(facilities=[], bookings=[], profiles={})
    with patch(VERIFY, return_value=RESIDENT):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "FORBIDDEN_ROLE"


async def test_daily_overview_bookings_sorted_by_start_within_facility(make_client):
    """Bookings within a facility are ordered by start time."""
    b_1100 = {**BOOKING_CONFIRMED, "id": "fac-alpha_2026-07-07_11:00",
               "start": "11:00", "end": "12:00"}
    b_0900 = {**BOOKING_CONFIRMED, "start": "09:00", "end": "10:00"}
    b_1000 = {**BOOKING_CANCELLED, "start": "10:00", "end": "11:00",
               "uid": "u-alice"}
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[b_1100, b_0900, b_1000],
        profiles={"u-alice": PROFILE_ALICE},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    starts = [b["start"] for b in resp.json()["facilities"][0]["bookings"]]
    assert starts == sorted(starts), f"Expected time-sorted bookings, got {starts}"


# ── Grid capacity: `slots` (full geometry, not just booked times) ──────────

async def test_daily_overview_slots_all_available_when_no_bookings(make_client):
    """A facility with no bookings still returns its FULL slot geometry,
    every entry marked "available" — not an empty/absent list.

    FAC_ALPHA's weekly_schedule (09:00-12:00, 60min slots) yields 3 valid
    starts: 09:00, 10:00, 11:00.
    """
    client = _overview_mock(facilities=[FAC_ALPHA], bookings=[], profiles={})
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    slots = resp.json()["facilities"][0]["slots"]
    assert [s["start"] for s in slots] == ["09:00", "10:00", "11:00"]
    assert all(s["status"] == "available" for s in slots), slots
    assert all(s["resident_name"] is None and s["resident_email"] is None for s in slots)


async def test_daily_overview_slots_cross_reference_confirmed_and_cancelled(make_client):
    """(a) Two-sided: slot status is derived from the facility's OWN bookings,
    not compute_slots' plain booked-or-not set — confirmed and cancelled must
    be distinguishable, and untouched slots remain "available".

    RED:  if slots merely copied compute_slots' booked/not-booked verdict,
          the cancelled slot would show as "available" (compute_slots has no
          concept of cancellation) instead of "cancelled".
    GREEN: 09:00 -> confirmed (Alice), 10:00 -> cancelled (Bob),
           11:00 -> available (untouched).
    """
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[BOOKING_CONFIRMED, BOOKING_CANCELLED],
        profiles={"u-alice": PROFILE_ALICE, "u-bob": PROFILE_BOB},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    slots = {s["start"]: s for s in resp.json()["facilities"][0]["slots"]}
    assert slots["09:00"]["status"] == "confirmed"
    assert slots["09:00"]["resident_name"] == "Alice"
    assert slots["10:00"]["status"] == "cancelled"
    assert slots["10:00"]["resident_name"] == "Bob"
    assert slots["11:00"]["status"] == "available"
    assert slots["11:00"]["resident_name"] is None


async def test_daily_overview_slots_present_per_facility_independently(make_client):
    """Each facility's `slots` reflects ONLY its own weekly_schedule — a
    facility open 08:00-09:00 does not inherit another facility's 09:00-12:00
    range."""
    client = _overview_mock(
        facilities=[FAC_ALPHA, FAC_ZULU], bookings=[], profiles={},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    facs = {f["name"]: f for f in resp.json()["facilities"]}
    assert [s["start"] for s in facs["Alpha Court"]["slots"]] == ["09:00", "10:00", "11:00"]
    assert [s["start"] for s in facs["Zulu Court"]["slots"]] == ["08:00"]


async def test_daily_overview_invalid_date_returns_422(make_client):
    """Malformed date strings are rejected before compute_slots ever sees them."""
    client = _overview_mock(facilities=[], bookings=[], profiles={})
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=not-a-date",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_DATE"
async def test_daily_overview_same_start_time_confirmed_wins_over_cancelled(make_client):
    """(e) Two-sided: a confirmed booking must never be shadowed by a cancelled
    one at the same facility+date+start time.

    Real scenario: a resident cancels a slot, someone else immediately books
    the same now-open slot. Both bookings share facility_id/date/start. The
    Grid's capacity view must show the ACTIVE booking, never the cancelled one
    — showing "cancelled/available" here would hide the fact that the slot is
    actually occupied right now.

    RED:  before the fix, `booking_by_start` is built by iterating bookings
          sorted by start time only — ties resolve in whatever order the
          (mocked) Firestore stream happens to return them, which is
          insertion order here. Cancelled is inserted AFTER confirmed below,
          so it would win the dict overwrite and the slot would incorrectly
          show status "cancelled".
    GREEN: bookings are sorted by (start, status == "confirmed") before the
           dict is built, so confirmed always overwrites cancelled at a tied
           start time regardless of stream order.
    """
    same_start_cancelled = {
        "id": "fac-alpha_2026-07-07_09:00_old",
        "uid": "u-bob",
        "facility_id": "fac-alpha",
        "date": "2026-07-07",
        "start": "09:00",
        "end": "10:00",
        "status": "cancelled",
        "household_id": "h-2",
        "cancelled_at": "2026-07-07T08:30:00Z",
    }
    same_start_confirmed = {
        "id": "fac-alpha_2026-07-07_09:00_new",
        "uid": "u-alice",
        "facility_id": "fac-alpha",
        "date": "2026-07-07",
        "start": "09:00",
        "end": "10:00",
        "status": "confirmed",
        "household_id": "h-1",
        "cancelled_at": None,
    }
    # Deliberately insert cancelled AFTER confirmed in the mocked stream, so a
    # naive "last one wins" dict build would pick cancelled — proving the fix
    # sorts by status, not stream/insertion order.
    client = _overview_mock(
        facilities=[FAC_ALPHA],
        bookings=[same_start_confirmed, same_start_cancelled],
        profiles={"u-alice": PROFILE_ALICE, "u-bob": PROFILE_BOB},
    )
    with patch(VERIFY, return_value=ADMIN):
        async with make_client() as c:
            c._transport.app.dependency_overrides[get_firestore_client] = lambda: client
            resp = await c.get(
                "/api/v1/tenant/overview/daily?date=2026-07-07",
                headers={**AUTH, **HOST},
            )
    assert resp.status_code == 200
    alpha = next(f for f in resp.json()["facilities"] if f["facility_id"] == "fac-alpha")
    slot_0900 = next(s for s in alpha["slots"] if s["start"] == "09:00")
    assert slot_0900["status"] == "confirmed", (
        f"Expected the confirmed booking to win the same-start-time tie, "
        f"got status={slot_0900['status']!r} — a cancelled booking is "
        f"shadowing an active one."
    )
    assert slot_0900["resident_name"] == "Alice"
    assert slot_0900["resident_email"] == "alice@demo.com"
