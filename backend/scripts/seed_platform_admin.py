"""Seed the first platform-admin user (ADR-0014 §2).

Run once (idempotent — resets password if email already exists):
    uv run python scripts/seed_platform_admin.py

Set PLATFORM_ADMIN_EMAIL env var to override the default address.
"""
import datetime
import os
import secrets

import firebase_admin
import firebase_admin.auth as fb_auth
from google.cloud import firestore

ADMIN_EMAIL = os.environ.get(
    "PLATFORM_ADMIN_EMAIL", "admin@sportbook.chandraailabs.com"
)


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app()

    temp_password = secrets.token_urlsafe(16)

    try:
        user = fb_auth.create_user(
            email=ADMIN_EMAIL, password=temp_password, display_name="Platform Admin"
        )
        print(f"[seed] Created platform admin: {ADMIN_EMAIL}")
    except fb_auth.EmailAlreadyExistsError:
        user = fb_auth.get_user_by_email(ADMIN_EMAIL)
        fb_auth.update_user(user.uid, password=temp_password)
        print(f"[seed] Reset password for existing platform admin: {ADMIN_EMAIL}")

    fb_auth.set_custom_user_claims(user.uid, {
        "role": "platform_admin",
        "tenant_id": None,
        "tenant_slug": None,
        "household_id": None,
    })

    db = firestore.Client()
    db.collection("platform_admins").document(user.uid).set(
        {
            "uid": user.uid,
            "email": ADMIN_EMAIL,
            "role": "platform_admin",
            "must_change_password": False,
            "created_at": datetime.datetime.now(datetime.UTC),
        },
        merge=True,
    )

    print(f"[seed] UID:           {user.uid}")
    print(f"[seed] Temp password: {temp_password}")
    print("[seed] Custom claims: role=platform_admin, tenant_id=null")
    print("[seed] Profile written to platform_admins collection")


if __name__ == "__main__":
    main()
