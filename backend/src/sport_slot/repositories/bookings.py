from sport_slot.repositories.base import TenantRepository


class BookingRepository(TenantRepository):
    """/tenants/{tenant_id}/bookings/{id} (ADR-0010 §2).

    Read-side arrives in 3.3 (availability); writes arrive in 3.4.
    Deterministic IDs: {facility_id}_{date}_{start}.
    """

    collection_name = "bookings"

    def booked_starts(self, facility_id: str, date: str) -> set[str]:
        """Start times (HH:MM) of confirmed bookings for one
        facility+date. Equality-only filters — no composite index
        needed (Firestore merges single-field indexes)."""
        query = (
            self._collection
            .where("facility_id", "==", facility_id)
            .where("date", "==", date)
            .where("status", "==", "confirmed")
        )
        return {snap.to_dict().get("start") for snap in query.stream()}

    def list_for_uid(
        self, uid: str, limit: int = 20, cursor: str | None = None
    ) -> tuple[list[dict], str | None]:
        """Caller's own bookings, cursor-paginated by document ID
        (deterministic IDs sort facility/date/start naturally)."""
        from sport_slot.repositories.base import _decode_cursor, _encode_cursor

        query = (
            self._collection
            .where("uid", "==", uid)
            .order_by("__name__")
            .limit(limit + 1)
        )
        if cursor:
            start_ref = self._collection.document(_decode_cursor(cursor))
            query = query.start_after({"__name__": start_ref})
        snaps = list(query.stream())
        has_more = len(snaps) > limit
        snaps = snaps[:limit]
        items = [s.to_dict() for s in snaps]
        next_cursor = _encode_cursor(snaps[-1].id) if has_more and snaps else None
        return items, next_cursor


class QuotaExceededError(Exception):
    pass


class AlreadyBookedError(Exception):
    pass


def create_booking_with_quota(
    repo: "BookingRepository",
    booking_id: str,
    doc: dict,
    uid: str,
    date: str,
    quota: int,
) -> None:
    """Atomic quota-check + create (ADR-0010 §4). The Redis lock
    guards the SLOT; quota races ACROSS slots are settled here."""
    from google.cloud import firestore

    collection = repo._collection
    transaction = repo._client.transaction()

    @firestore.transactional
    def _run(txn):
        query = (
            collection
            .where("uid", "==", uid)
            .where("date", "==", date)
            .where("status", "==", "confirmed")
        )
        count = len(list(txn.get(query)))
        if count >= quota:
            raise QuotaExceededError()
        ref = collection.document(booking_id)
        snapshot = next(iter(txn.get(ref)), None)
        if snapshot is not None and snapshot.exists:
            raise AlreadyBookedError()
        txn.create(ref, doc)

    _run(transaction)


class AuditRepository(TenantRepository):
    """/tenants/{tenant_id}/audit/{event_id} (ADR-0011).
    Append-only; synchronous by design."""

    collection_name = "audit"

    def write_event(
        self, event_type: str, actor_uid: str, actor_role: str,
        booking_id: str, request_id: str, details: dict,
    ) -> str:
        import datetime
        import uuid

        event_id = uuid.uuid4().hex
        self.create(event_id, {
            "event_id": event_id, "type": event_type,
            "actor_uid": actor_uid, "actor_role": actor_role,
            "booking_id": booking_id, "request_id": request_id,
            "details": details,
            "ts": datetime.datetime.now(datetime.UTC),
        })
        return event_id
