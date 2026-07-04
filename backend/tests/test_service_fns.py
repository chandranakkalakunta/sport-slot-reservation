"""Unit tests for get_availability and list_my_bookings service functions (ADR-0021 §2)."""
import datetime
from unittest.mock import MagicMock, patch

import pytest

from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.services.availability import get_availability
from sport_slot.services.bookings import _is_cancellable, list_my_bookings

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                    role="resident", household_id="h-1")

_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
FACILITY = {
    "id": "f1", "active": True, "slot_duration_minutes": 60,
    "weekly_schedule": {day: [{"start": "06:00", "end": "10:00"}] for day in _DAYS},
}

POLICY_SNAP = {"timezone": "UTC",
               "policies": {"booking_horizon_days": 3650,
                            "booking_window_open_time": "00:00",
                            "cancellation_buffer_hours": 1}}


def _client(facility=FACILITY):
    client = MagicMock()
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value
                .get.return_value)
    fac_snap.exists = facility is not None
    fac_snap.to_dict.return_value = facility
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


# ── get_availability ─────────────────────────────────────────────────────────

def test_get_availability_invalid_date_raises_422():
    with pytest.raises(ApiError) as exc_info:
        get_availability(CTX, _client(), "f1", "not-a-date")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "INVALID_DATE"


def test_get_availability_missing_facility_raises_404():
    with pytest.raises(ApiError) as exc_info:
        get_availability(CTX, _client(facility=None), "f1", "2027-01-15")
    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "FACILITY_NOT_FOUND"


def test_get_availability_inactive_facility_raises_404():
    inactive = {**FACILITY, "active": False}
    with pytest.raises(ApiError) as exc_info:
        get_availability(CTX, _client(facility=inactive), "f1", "2027-01-15")
    assert exc_info.value.status_code == 404


def test_get_availability_returns_correct_shape():
    with patch("sport_slot.services.availability.BookingRepository.booked_starts",
               return_value=set()):
        result = get_availability(CTX, _client(), "f1", "2027-01-15")
    assert result["facility_id"] == "f1"
    assert result["date"] == "2027-01-15"
    assert len(result["slots"]) == 4  # 06:00–10:00 at 60 min = 4 slots
    assert {"start", "end", "status", "bookable", "reason"} <= set(result["slots"][0])


# ── _is_cancellable ──────────────────────────────────────────────────────────

def test_is_cancellable_true_when_before_deadline():
    booking = {"status": "confirmed", "date": "2030-01-01", "start": "10:00"}
    now = datetime.datetime(2029, 12, 31, 12, 0)
    assert _is_cancellable(booking, now, buffer_hours=1) is True


def test_is_cancellable_false_when_past_deadline():
    booking = {"status": "confirmed", "date": "2026-06-01", "start": "10:00"}
    now = datetime.datetime(2026, 6, 1, 10, 0)  # exactly at slot start
    assert _is_cancellable(booking, now, buffer_hours=1) is False


def test_is_cancellable_false_for_non_confirmed():
    booking = {"status": "cancelled", "date": "2030-01-01", "start": "10:00"}
    now = datetime.datetime(2029, 1, 1)
    assert _is_cancellable(booking, now, buffer_hours=1) is False


# ── list_my_bookings ─────────────────────────────────────────────────────────

def test_list_my_bookings_returns_annotated_items():
    far_future_booking = {
        "id": "b1", "status": "confirmed",
        "date": "2030-01-01", "start": "10:00",
    }
    with patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
               return_value=([far_future_booking], None)):
        result = list_my_bookings(CTX, _client(), limit=20)
    assert len(result["items"]) == 1
    assert result["items"][0]["cancellable"] is True
    assert result["next_cursor"] is None


def test_list_my_bookings_cancellable_false_for_past_buffer():
    past_booking = {
        "id": "b2", "status": "confirmed",
        "date": "2020-01-01", "start": "10:00",
    }
    with patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
               return_value=([past_booking], None)):
        result = list_my_bookings(CTX, _client(), limit=20)
    assert result["items"][0]["cancellable"] is False


# ── Bug 1: from_date forwarded to repository ──────────────────────────────────

def test_list_my_bookings_passes_from_date_to_repo():
    """from_date must be forwarded so the Firestore query includes the date filter."""
    upcoming = {"id": "b1", "status": "confirmed", "date": "2030-01-01", "start": "10:00"}
    with patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
               return_value=([upcoming], None)) as mock_list:
        result = list_my_bookings(CTX, _client(), limit=20, from_date="2027-01-01")
    mock_list.assert_called_once_with(CTX.uid, limit=20, cursor=None, from_date="2027-01-01")
    assert result["items"][0]["id"] == "b1"


def test_list_my_bookings_without_from_date_passes_none_to_repo():
    """Default call (no from_date) must keep existing repo behaviour — from_date=None."""
    upcoming = {"id": "b1", "status": "confirmed", "date": "2030-01-01", "start": "10:00"}
    with patch("sport_slot.services.bookings.BookingRepository.list_for_uid",
               return_value=([upcoming], None)) as mock_list:
        list_my_bookings(CTX, _client(), limit=100)
    mock_list.assert_called_once_with(CTX.uid, limit=100, cursor=None, from_date=None)
