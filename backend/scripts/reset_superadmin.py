"""Dev-only: reset the platform superadmin's password. For when the
seeded/changed dev password is lost. Refuses outside development.
Run: make reset-superadmin NEWPW=YourNewPassword123"""

import os
import sys

import firebase_admin
from firebase_admin import auth as fb_auth

EMAIL = "admin@sportbook.chandraailabs.com"


def main() -> int:
    if os.environ.get("SPORTSLOT_ENVIRONMENT", "development") != "development":
        print("REFUSED: runs only in development")
        return 1
    new_pw = os.environ.get("NEWPW")
    if not new_pw or len(new_pw) < 8:
        print("Set NEWPW (>=8 chars): make reset-superadmin NEWPW=...")
        return 1
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    user = fb_auth.get_user_by_email(EMAIL)
    fb_auth.update_user(user.uid, password=new_pw)
    print(f"Reset password for {EMAIL} (uid {user.uid}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
