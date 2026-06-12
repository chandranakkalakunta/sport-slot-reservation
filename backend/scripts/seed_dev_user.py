"""Dev-only seed v2: resident + tenant_admin users, claims,
profiles, and the t-demo tenant registry document (ADR-0010).

Refuses outside development. Superseded by Phase 3+ provisioning.
Run: make seed-dev
"""

import datetime
import os
import secrets
import sys

import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore

TENANT_ID = "t-demo"
TENANT_SLUG = "demo"
HOUSEHOLD_ID = "h-demo-1"

USERS = [
    {"email": "demo-resident@chandraailabs.com", "role": "resident",
     "display_name": "Demo Resident", "flat_number": "A-101"},
    {"email": "demo-admin@chandraailabs.com", "role": "tenant_admin",
     "display_name": "Demo Admin", "flat_number": "A-001"},
]


def _ensure_user(client, spec) -> str:
    try:
        user = fb_auth.get_user_by_email(spec["email"])
        print(f"Auth user exists: {spec['email']} ({user.uid})")
    except fb_auth.UserNotFoundError:
        password = secrets.token_urlsafe(16)
        user = fb_auth.create_user(email=spec["email"], password=password)
        print(f"Created {spec['email']} ({user.uid})")
        print(f"PASSWORD for {spec['email']} (shown once): {password}")

    fb_auth.set_custom_user_claims(
        user.uid,
        {"tenant_id": TENANT_ID, "tenant_slug": TENANT_SLUG,
         "role": spec["role"], "household_id": HOUSEHOLD_ID},
    )

    doc_ref = (client.collection("tenants").document(TENANT_ID)
               .collection("users").document(user.uid))
    if not doc_ref.get().exists:
        doc_ref.create({
            "uid": user.uid, "tenant_id": TENANT_ID,
            "household_id": HOUSEHOLD_ID,
            "flat_number": spec["flat_number"],
            "display_name": spec["display_name"], "role": spec["role"],
            "created_at": datetime.datetime.now(datetime.UTC),
        })
        print(f"Profile created for {spec['email']}")
    return user.uid


def main() -> int:
    if os.environ.get("SPORTSLOT_ENVIRONMENT", "development") != "development":
        print("REFUSED: seed script runs only in development")
        return 1

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    client = firestore.Client(
        project=os.environ.get("SPORTSLOT_GCP_PROJECT", "sport-slot-dev")
    )

    tenant_ref = client.collection("tenants").document(TENANT_ID)
    if not tenant_ref.get().exists:
        tenant_ref.create({
            "tenant_id": TENANT_ID, "slug": TENANT_SLUG,
            "name": "Demo Society", "active": True, "policies": {},
            "timezone": "Asia/Kolkata",
            "created_at": datetime.datetime.now(datetime.UTC),
        })
        print(f"Tenant registry document created: /tenants/{TENANT_ID}")
    else:
        print("Tenant registry document exists")
        if "timezone" not in (tenant_ref.get().to_dict() or {}):
            tenant_ref.update({"timezone": "Asia/Kolkata"})
            print("Backfilled tenant timezone")

    for spec in USERS:
        _ensure_user(client, spec)
    print("Seed v2 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
