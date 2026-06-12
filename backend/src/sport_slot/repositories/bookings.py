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
