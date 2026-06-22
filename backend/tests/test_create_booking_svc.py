"""Unit tests for the create_booking service function (ADR-0021 §2, Slice 2a).

All dependencies (repositories, lock, PolicyService) are mocked.
Tests document: happy path, every ApiError path, and lock-release semantics.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import AlreadyBookedError, QuotaExceededError
from sport_slot.services.bookings import create_booking

CTX = TenantContext(uid="u1", tenant_id="t-1", tenant_slug="demo",
                    role="resident", household_id="h-1")

FACILITY = {
    "id": "f1", "active": True, "slot_duration_minutes": 60,
    "open_time": "06:00", "close_time": "22:00",
}
POLICY_SNAP = {
    "timezone": "UTC",
    "policies": {
        "booking_horizon_days": 3650,
        "booking_window_open_time": "00:00",
        "max_slots_per_user_per_sport_per_day": 1,
        "cancellation_buffer_hours": 1,
    },
}


class FakeLock:
    def __init__(self, token="tok", unavailable=False, contended=False):
        self._token = None if contended else token
        self._unavailable = unavailable
        self.released = False
        self.release_calls: list = []

    @staticmethod
    def slot_key(*args):
        return ":".join(args)

    async def acquire(self, key, ttl_ms=10_000):
        from sport_slot.services.lock import LockUnavailableError
        if self._unavailable:
            raise LockUnavailableError("down")
        return self._token

    async def release(self, key, token):
        self.released = True
        self.release_calls.append((key, token))


def _fs_client():
    """Firestore mock wired for the test facility + policy."""
    client = MagicMock()
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = True
    fac_snap.to_dict.return_value = FACILITY
    ten_snap = client.collection.return_value.document.return_value.get.return_value
    ten_snap.exists = True
    ten_snap.to_dict.return_value = POLICY_SNAP
    return client


# ── happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_booking_happy_path():
    lock = FakeLock()
    mock_quota_create = MagicMock()
    mock_audit = MagicMock()

    with patch("sport_slot.services.bookings.AuditRepository.write_event", mock_audit), \
         patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        result = await create_booking(
            CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
            _quota_create_fn=mock_quota_create,
        )

    assert result["id"] == "f1_2027-01-15_18:00"
    assert result["status"] == "confirmed"
    assert result["end"] == "19:00"
    mock_quota_create.assert_called_once()
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[0] == "booking.created"
    assert lock.released


# ── error paths ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_date_raises_422():
    with pytest.raises(ApiError) as exc:
        await create_booking(CTX, _fs_client(), FakeLock(), "f1", "not-a-date", "18:00")
    assert exc.value.status_code == 422
    assert exc.value.code == "INVALID_DATE"


@pytest.mark.asyncio
async def test_missing_facility_raises_404():
    client = _fs_client()
    fac_snap = (client.collection.return_value.document.return_value
                .collection.return_value.document.return_value.get.return_value)
    fac_snap.exists = False
    fac_snap.to_dict.return_value = None

    with pytest.raises(ApiError) as exc:
        await create_booking(CTX, client, FakeLock(), "f1", "2027-01-15", "18:00")
    assert exc.value.status_code == 404
    assert exc.value.code == "FACILITY_NOT_FOUND"


@pytest.mark.asyncio
async def test_off_grid_start_raises_422():
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError) as exc:
            await create_booking(CTX, _fs_client(), FakeLock(), "f1", "2027-01-15", "18:30")
    assert exc.value.status_code == 422
    assert exc.value.code == "SLOT_NOT_BOOKABLE"


@pytest.mark.asyncio
async def test_booked_slot_raises_422():
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value={"18:00"}):
        with pytest.raises(ApiError) as exc:
            await create_booking(CTX, _fs_client(), FakeLock(), "f1", "2027-01-15", "18:00")
    assert exc.value.status_code == 422
    assert exc.value.code == "SLOT_NOT_BOOKABLE"


@pytest.mark.asyncio
async def test_lock_unavailable_raises_503():
    lock = FakeLock(unavailable=True)
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError) as exc:
            await create_booking(CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00")
    assert exc.value.status_code == 503
    assert exc.value.code == "LOCK_UNAVAILABLE"


@pytest.mark.asyncio
async def test_contended_slot_raises_409():
    lock = FakeLock(contended=True)
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError) as exc:
            await create_booking(CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00")
    assert exc.value.status_code == 409
    assert exc.value.code == "SLOT_CONTENDED"


@pytest.mark.asyncio
async def test_quota_exceeded_raises_409_and_releases_lock():
    lock = FakeLock()
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError) as exc:
            await create_booking(
                CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
                _quota_create_fn=MagicMock(side_effect=QuotaExceededError),
            )
    assert exc.value.status_code == 409
    assert exc.value.code == "BOOKING_QUOTA_EXCEEDED"
    assert lock.released, "lock MUST be released even on quota error"


@pytest.mark.asyncio
async def test_already_booked_raises_409_and_releases_lock():
    lock = FakeLock()
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError) as exc:
            await create_booking(
                CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
                _quota_create_fn=MagicMock(side_effect=AlreadyBookedError),
            )
    assert exc.value.status_code == 409
    assert exc.value.code == "ALREADY_BOOKED"
    assert lock.released, "lock MUST be released even on already-booked error"


# ── lock-release semantics ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lock_released_on_success():
    """Lock is released on every path — success included."""
    lock = FakeLock()
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()), \
         patch("sport_slot.services.bookings.AuditRepository.write_event"):
        await create_booking(
            CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
            _quota_create_fn=MagicMock(),
        )
    assert lock.released
    assert len(lock.release_calls) == 1


@pytest.mark.asyncio
async def test_lock_released_exactly_once_on_quota_error():
    """Lock must NOT be double-released on quota error."""
    lock = FakeLock()
    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()):
        with pytest.raises(ApiError):
            await create_booking(
                CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
                _quota_create_fn=MagicMock(side_effect=QuotaExceededError),
            )
    assert len(lock.release_calls) == 1, "lock must be released exactly once"


@pytest.mark.asyncio
async def test_audit_written_after_lock_release():
    """Audit write happens AFTER the finally block — lock is not held during audit."""
    lock = FakeLock()
    call_order: list[str] = []

    def _track_release(*args):
        call_order.append("release")

    def _track_audit(*args, **kwargs):
        call_order.append("audit")

    lock.release = AsyncMock(side_effect=_track_release)

    with patch("sport_slot.services.bookings.BookingRepository.booked_starts",
               return_value=set()), \
         patch("sport_slot.services.bookings.AuditRepository.write_event",
               side_effect=_track_audit):
        await create_booking(
            CTX, _fs_client(), lock, "f1", "2027-01-15", "18:00",
            _quota_create_fn=MagicMock(),
        )

    assert call_order == ["release", "audit"], (
        "audit must be written AFTER lock release, not before"
    )
