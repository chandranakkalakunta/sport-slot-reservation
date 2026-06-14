"""Seed the global facility-type catalog (ADR-0015). Idempotent.
Run: make seed-facility-catalog"""

import os
import sys

import firebase_admin
from google.cloud import firestore

CATALOG = [
    {"type_id": "badminton", "name": "Badminton", "sport": "badminton"},
    {"type_id": "tennis", "name": "Tennis", "sport": "tennis"},
    {"type_id": "swimming", "name": "Swimming Pool", "sport": "swimming"},
    {"type_id": "gym", "name": "Gym", "sport": "gym"},
    {"type_id": "turf-football", "name": "Turf (Football)", "sport": "football"},
    {"type_id": "table-tennis", "name": "Table Tennis", "sport": "table-tennis"},
    {"type_id": "basketball", "name": "Basketball", "sport": "basketball"},
]


def main() -> int:
    if os.environ.get("SPORTSLOT_ENVIRONMENT", "development") != "development":
        print("REFUSED: runs only in development")
        return 1
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    client = firestore.Client(
        project=os.environ.get("SPORTSLOT_GCP_PROJECT", "sport-slot-dev"))

    for entry in CATALOG:
        ref = client.collection("facility_catalog").document(entry["type_id"])
        if ref.get().exists:
            print(f"  catalog exists: {entry['type_id']}")
        else:
            ref.set(entry)
            print(f"  seeded: {entry['type_id']}")

    # Migration (ADR-0015 §4): back-link existing free-form facilities
    # to a catalog type by matching their sport string.
    by_sport = {e["sport"]: e["type_id"] for e in CATALOG}
    tenants = client.collection("tenants").stream()
    migrated = 0
    for t in tenants:
        facs = (client.collection("tenants").document(t.id)
                .collection("facilities").stream())
        for f in facs:
            data = f.to_dict() or {}
            if not data.get("facility_type_id"):
                type_id = by_sport.get(data.get("sport"))
                if type_id:
                    f.reference.update({"facility_type_id": type_id})
                    migrated += 1
                    print(f"  migrated {t.id}/{f.id} → {type_id}")
    print(f"Done. Migrated {migrated} legacy facilities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
