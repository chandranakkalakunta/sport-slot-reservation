"""Booking service functions (ADR-0021 §2 agent foundation)."""

import datetime
import zoneinfo

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import BookingRepository
from sport_slot.services.policy import PolicyService


def _is_cancellable(booking: dict, now_local: datetime.datetime, buffer_hours: int) -> bool:
    if booking.get("status") != "confirmed":
        return False
    slot_start = datetime.datetime.combine(
        datetime.date.fromisoformat(booking["date"]),
        datetime.time.fromisoformat(booking["start"]),
    )
    deadline = slot_start - datetime.timedelta(hours=buffer_hours)
    return now_local < deadline


def list_my_bookings(
    ctx: TenantContext, client, limit: int = 20, cursor: str | None = None
) -> dict:
    """Return paginated bookings for the calling user with cancellable annotation."""
    items, next_cursor = BookingRepository(ctx, client).list_for_uid(
        ctx.uid, limit=limit, cursor=cursor
    )
    policy = PolicyService(ctx, client)
    tz = zoneinfo.ZoneInfo(policy.tenant_timezone())
    now_local = datetime.datetime.now(tz).replace(tzinfo=None)
    buffer_hours = int(policy.get("cancellation_buffer_hours"))
    annotated = [
        {**item, "cancellable": _is_cancellable(item, now_local, buffer_hours)}
        for item in items
    ]
    return {"items": annotated, "next_cursor": next_cursor}
