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

    def list_confirmed_in_range(self, start_date: str, end_date: str) -> list[dict]:
        """Confirmed bookings with date in [start_date, end_date] (inclusive).

        Used by monthly invoice generation (Phase 15.3) to pull the previous
        calendar month's billable bookings. Requires the (status, date)
        composite index in firestore.indexes.json.
        """
        query = (
            self._collection
            .where("status", "==", "confirmed")
            .where("date", ">=", start_date)
            .where("date", "<=", end_date)
        )
        return [snap.to_dict() for snap in query.stream()]

    def list_for_date(self, date: str) -> list[dict]:
        """All bookings (confirmed AND cancelled) for a given date across all
        facilities in this tenant.  Single equality filter on `date` — uses
        Firestore's automatic single-field index; no composite index required.

        # N+1 profile lookups are done by the caller (one per unique resident
        # uid on the day) — acceptable at current tenant scale, matching the
        # pattern documented in repositories/base.py list_tenants().
        """
        query = self._collection.where("date", "==", date)
        return [snap.to_dict() for snap in query.stream()]

    def list_for_uid(
        self, uid: str, limit: int = 20, cursor: str | None = None,
        from_date: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Caller's own bookings, cursor-paginated by document ID
        (deterministic IDs sort facility/date/start naturally).

        If from_date is set, returns only confirmed bookings on or after that
        date, ordered by date then __name__.  Requires the (uid, status, date)
        composite index already present in firestore.indexes.json.
        """
        from sport_slot.repositories.base import _decode_cursor, _encode_cursor

        if from_date:
            query = (
                self._collection
                .where("uid", "==", uid)
                .where("status", "==", "confirmed")
                .where("date", ">=", from_date)
                .order_by("date")
                .order_by("__name__")
                .limit(limit + 1)
            )
            if cursor:
                # Multi-field sort requires a document snapshot for start_after.
                snap = self._collection.document(_decode_cursor(cursor)).get()
                if snap.exists:
                    query = query.start_after(snap)
        else:
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
    sport: str = "",
    facilities: list[dict] | None = None,
) -> None:
    """Atomic quota-check + create (ADR-0010 §4). The Redis lock
    guards the SLOT; quota races ACROSS slots are settled here.

    Quota is per-sport: only confirmed bookings on the same date whose
    facility belongs to the same sport (case-insensitive) count toward
    the limit.  Cross-sport bookings are never charged against each other.
    """
    from google.cloud import firestore

    collection = repo._collection
    transaction = repo._client.transaction()
    fac_by_id: dict[str, dict] = {
        f["id"]: f for f in (facilities or []) if "id" in f
    }
    sport_lower = sport.lower()

    @firestore.transactional
    def _run(txn):
        query = (
            collection
            .where("uid", "==", uid)
            .where("date", "==", date)
            .where("status", "==", "confirmed")
        )
        bookings = list(txn.get(query))
        same_sport_count = 0
        for b in bookings:
            data = b.to_dict() if hasattr(b, "to_dict") else b
            fac = fac_by_id.get(data.get("facility_id", ""))
            if fac is None:
                continue  # facility gone or unknown — defensive skip
            booking_sport = (
                (fac.get("sport") or fac.get("facility_type_id") or "").lower()
            )
            if booking_sport == sport_lower:
                same_sport_count += 1
        if same_sport_count >= quota:
            raise QuotaExceededError()
        ref = collection.document(booking_id)
        snapshot = next(iter(txn.get(ref)), None)
        if snapshot is not None and snapshot.exists:
            if (snapshot.to_dict() or {}).get("status") == "confirmed":
                raise AlreadyBookedError()
            # Cancelled document: supersede with the new booking.
            # Prior lifecycle is preserved in the audit collection
            # (ADR-0011); the booking doc holds current state only.
            txn.set(ref, doc)
        else:
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
