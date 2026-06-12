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
