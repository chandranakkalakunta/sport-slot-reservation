"""Unit tests for the cancel_booking service function (ADR-0021 §2, Slice 3a).

All dependencies (repositories, PolicyService) are mocked.
Tests document: happy path, all ApiError paths, source audit differentiation,
and ownership / admin attribution.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.services.bookings import cancel_booking

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                    role="resident", household_id="h-1")
CTX_ADMIN = TenantContext(uid="a1", tenant_id="t-1", tenant_slug="demo",
                          role="tenant_admin", household_id="h-0")
CTX_OTHER = TenantContext(uid="u2", tenant_id="t-1", tenant_slug="demo",
                          role="resident", household_id="h-2")

POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "cancellation_buffer_hours": 2,
    },
}


def _booking(uid="u1", status="confirmed", days_ahead=5):
    date = (datetime.date.today() + datetime.timedelta(days=days_ahead)).isoformat()
    return {
        "id": f"f1_{date}_18:00", "uid": uid, "status": status,
        "date": date, "start": "18:00", "facility_id": "f1",
    }


def _fs_client():
    """Firestore mock wired for cancel tests (policy snap only)."""
    client = MagicMock()
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


# ── happy path ────────────────────────────────────────────────────────────────

def test_cancel_booking_owner_success():
    booking = _booking()
    cancelled = {**booking, "status": "cancelled"}
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, cancelled]), \
         patch("sport_slot.services.bookings.BookingRepository.update") as mock_upd, \
         patch("sport_slot.services.bookings.AuditRepository.write_event"):
        result = cancel_booking(CTX, _fs_client(), booking["id"])

    mock_upd.assert_called_once()
    changes = mock_upd.call_args.args[1]
    assert changes["status"] == "cancelled"
    assert changes["cancelled_by"] == "self"
    assert changes["cancelled_by_uid"] == CTX.uid
    assert result == cancelled


def test_cancel_booking_admin_attribution():
    booking = _booking(uid="u1")
    cancelled = {**booking, "status": "cancelled"}
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, cancelled]), \
         patch("sport_slot.services.bookings.BookingRepository.update") as mock_upd, \
         patch("sport_slot.services.bookings.AuditRepository.write_event"):
        cancel_booking(CTX_ADMIN, _fs_client(), booking["id"])

    changes = mock_upd.call_args.args[1]
    assert changes["cancelled_by"] == "tenant_admin"
    assert changes["cancelled_by_uid"] == CTX_ADMIN.uid


# ── source / audit differentiation ───────────────────────────────────────────

def test_cancel_booking_manual_source_writes_booking_cancelled():
    booking = _booking()
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch("sport_slot.services.bookings.BookingRepository.update"), \
         patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit:
        cancel_booking(CTX, _fs_client(), booking["id"])

    assert mock_audit.call_args.args[0] == "booking.cancelled"


def test_cancel_booking_agent_source_writes_agent_booking_cancelled():
    booking = _booking()
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch("sport_slot.services.bookings.BookingRepository.update"), \
         patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit:
        cancel_booking(CTX, _fs_client(), booking["id"], source="agent")

    assert mock_audit.call_args.args[0] == "agent.booking_cancelled"


def test_cancel_booking_default_source_is_manual():
    """Calling without source= must default to manual behavior (event_type unchanged)."""
    booking = _booking()
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch("sport_slot.services.bookings.BookingRepository.update"), \
         patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit:
        cancel_booking(CTX, _fs_client(), booking["id"])  # no source kwarg

    assert mock_audit.call_args.args[0] == "booking.cancelled"


# ── error paths ───────────────────────────────────────────────────────────────

def test_cancel_booking_not_found_404():
    with patch("sport_slot.services.bookings.BookingRepository.get", return_value=None):
        with pytest.raises(ApiError) as exc:
            cancel_booking(CTX, _fs_client(), "nonexistent")
    assert exc.value.status_code == 404
    assert exc.value.code == "BOOKING_NOT_FOUND"


def test_cancel_booking_other_resident_forbidden_403():
    booking = _booking(uid="u1")  # owned by u1
    with patch("sport_slot.services.bookings.BookingRepository.get", return_value=booking):
        with pytest.raises(ApiError) as exc:
            cancel_booking(CTX_OTHER, _fs_client(), booking["id"])  # u2 trying to cancel
    assert exc.value.status_code == 403
    assert exc.value.code == "CANCELLATION_FORBIDDEN"


def test_cancel_booking_already_cancelled_409():
    booking = _booking(status="cancelled")
    with patch("sport_slot.services.bookings.BookingRepository.get", return_value=booking):
        with pytest.raises(ApiError) as exc:
            cancel_booking(CTX, _fs_client(), booking["id"])
    assert exc.value.status_code == 409
    assert exc.value.code == "ALREADY_CANCELLED"


def test_cancel_booking_too_late_422():
    # buffer 9999h makes any slot in the future within the buffer
    policy_snap = {
        "timezone": "UTC",
        "policies": {"cancellation_buffer_hours": 9999},
    }
    client = MagicMock()
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = policy_snap

    booking = _booking(days_ahead=0)  # today at 18:00
    with patch("sport_slot.services.bookings.BookingRepository.get", return_value=booking):
        with pytest.raises(ApiError) as exc:
            cancel_booking(CTX, client, booking["id"])
    assert exc.value.status_code == 422
    assert exc.value.code == "CANCELLATION_TOO_LATE"


# ── audit details ─────────────────────────────────────────────────────────────

def test_cancel_booking_audit_details_include_cancelled_by():
    booking = _booking()
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, {**booking, "status": "cancelled"}]), \
         patch("sport_slot.services.bookings.BookingRepository.update"), \
         patch("sport_slot.services.bookings.AuditRepository.write_event") as mock_audit:
        cancel_booking(CTX, _fs_client(), booking["id"])

    # write_event(event_type, actor_uid, actor_role, booking_id, request_id, details)
    assert mock_audit.call_args.args[1] == CTX.uid         # actor_uid
    assert mock_audit.call_args.args[2] == CTX.role        # actor_role
    assert mock_audit.call_args.args[3] == booking["id"]   # booking_id
    details = mock_audit.call_args.args[5]
    assert details == {"cancelled_by": "self"}


def test_cancel_booking_returns_post_update_doc():
    """Return value is the post-update booking read-back."""
    booking = _booking()
    post_update = {**booking, "status": "cancelled", "cancelled_by": "self"}
    with patch("sport_slot.services.bookings.BookingRepository.get",
               side_effect=[booking, post_update]), \
         patch("sport_slot.services.bookings.BookingRepository.update"), \
         patch("sport_slot.services.bookings.AuditRepository.write_event"):
        result = cancel_booking(CTX, _fs_client(), booking["id"])

    assert result == post_update
    assert result["status"] == "cancelled"
