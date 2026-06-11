"""Dev-only seed: Firebase Auth user + claims + profile doc.

Refuses outside development. Disposable: superseded by Phase 3
provisioning, delete then. Run: make seed-dev
"""

import datetime
import os
import secrets
import sys

import firebase_admin
from firebase_admin import auth as fb_auth
from google.cloud import firestore

EMAIL = "demo-resident@chandraailabs.com"
TENANT_ID = "t-demo"
TENANT_SLUG = "demo"
HOUSEHOLD_ID = "h-demo-1"


def main() -> int:
    if os.environ.get("SPORTSLOT_ENVIRONMENT", "development") != "development":
        print("REFUSED: seed script runs only in development")
        return 1

    if not firebase_admin._apps:
        firebase_admin.initialize_app()

    try:
        user = fb_auth.get_user_by_email(EMAIL)
        print(f"Auth user exists: {user.uid}")
    except fb_auth.UserNotFoundError:
        password = secrets.token_urlsafe(16)
        user = fb_auth.create_user(email=EMAIL, password=password)
        print(f"Created auth user: {user.uid}")
        print(f"PASSWORD (shown once, store it): {password}")

    fb_auth.set_custom_user_claims(
        user.uid,
        {
            "tenant_id": TENANT_ID,
            "tenant_slug": TENANT_SLUG,
            "role": "resident",
            "household_id": HOUSEHOLD_ID,
        },
    )
    print("Custom claims set")

    client = firestore.Client(project=os.environ.get("SPORTSLOT_GCP_PROJECT", "sport-slot-dev"))
    doc_ref = (
        client.collection("tenants").document(TENANT_ID).collection("users").document(user.uid)
    )
    if not doc_ref.get().exists:
        doc_ref.create(
            {
                "uid": user.uid,
                "tenant_id": TENANT_ID,
                "household_id": HOUSEHOLD_ID,
                "flat_number": "A-101",
                "display_name": "Demo Resident",
                "role": "resident",
                "created_at": datetime.datetime.now(datetime.UTC),
            }
        )
        print("Profile document created")
    else:
        print("Profile document exists")
    print(f"Seed complete. uid={user.uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
