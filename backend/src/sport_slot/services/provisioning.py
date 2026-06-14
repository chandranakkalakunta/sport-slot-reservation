"""User provisioning service — single path for all user creation (ADR-0016)."""
import datetime
import secrets

import firebase_admin.auth as fb_auth

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.context import TenantContext
from sport_slot.repositories.bookings import AuditRepository
from sport_slot.repositories.user_profiles import UserProfileRepository

_VALID_ROLES = {"resident", "tenant_admin"}


def _derive_household(flat_number: str, household_id: str | None) -> str:
    return household_id if household_id else f"h-{flat_number}"


def _ctx(tenant_id: str | None, uid: str, role: str) -> TenantContext:
    return TenantContext(uid=uid, tenant_id=tenant_id, tenant_slug=None, role=role)


class UserProvisioningService:
    def __init__(self, client) -> None:
        self._client = client

    def create_user(
        self,
        tenant_id: str,
        email: str,
        display_name: str,
        flat_number: str,
        role: str,
        household_id: str | None = None,
    ) -> dict:
        if role not in _VALID_ROLES:
            raise ApiError(422, error_codes.VALIDATION_FAILED, f"Invalid role: {role!r}")

        # Look up tenant slug so the JWT claim allows host-based cross-checks (ADR-0012 §2).
        tenant_snap = self._client.collection("tenants").document(tenant_id).get()
        tenant_slug = (tenant_snap.to_dict() or {}).get("slug") if tenant_snap.exists else None

        temp_password = secrets.token_urlsafe(16)
        try:
            user = fb_auth.create_user(
                email=email, display_name=display_name, password=temp_password
            )
        except fb_auth.EmailAlreadyExistsError:
            raise ApiError(409, error_codes.USER_EMAIL_TAKEN, f"Email {email!r} already registered")

        try:
            hid = _derive_household(flat_number, household_id)
            fb_auth.set_custom_user_claims(user.uid, {
                "tenant_id": tenant_id,
                "tenant_slug": tenant_slug,
                "role": role,
                "household_id": hid,
            })
            ctx = _ctx(tenant_id=tenant_id, uid=user.uid, role=role)
            UserProfileRepository(ctx, self._client).create(user.uid, {
                "uid": user.uid,
                "email": email,
                "display_name": display_name,
                "flat_number": flat_number,
                "household_id": hid,
                "role": role,
                "must_change_password": True,
                "created_at": datetime.datetime.now(datetime.UTC),
            })
            AuditRepository(ctx, self._client).write_event(
                event_type="user_provisioned",
                actor_uid=user.uid,
                actor_role=role,
                booking_id="-",
                request_id="-",
                details={"email": email, "flat_number": flat_number, "role": role},
            )
        except ApiError:
            fb_auth.delete_user(user.uid)
            raise
        except Exception:
            fb_auth.delete_user(user.uid)
            raise ApiError(500, error_codes.INTERNAL_ERROR, "User creation failed") from None

        return {"uid": user.uid, "temp_password": temp_password}

    def deactivate_user(
        self,
        tenant_id: str,
        target_uid: str,
        caller_uid: str,
    ) -> None:
        if target_uid == caller_uid:
            raise ApiError(
                403, error_codes.SELF_DEACTIVATION_FORBIDDEN, "Cannot deactivate yourself"
            )

        ctx = _ctx(tenant_id=tenant_id, uid=caller_uid, role="tenant_admin")
        repo = UserProfileRepository(ctx, self._client)
        profile = repo.get(target_uid)
        if profile is None:
            raise ApiError(404, error_codes.USER_NOT_FOUND, f"User {target_uid!r} not found")

        repo.update(target_uid, {
            "status": "inactive",
            "deactivated_at": datetime.datetime.now(datetime.UTC),
        })
        fb_auth.update_user(target_uid, disabled=True)
        today = datetime.date.today().isoformat()
        self._cancel_future_bookings(tenant_id, target_uid, today)

    def _cancel_future_bookings(self, tenant_id: str, uid: str, today: str) -> int:
        col = (
            self._client.collection("tenants")
            .document(tenant_id)
            .collection("bookings")
        )
        query = (
            col.where("uid", "==", uid)
            .where("status", "==", "confirmed")
            .where("date", ">=", today)
        )
        count = 0
        for snap in query.stream():
            snap.reference.update({
                "status": "cancelled",
                "cancelled_at": datetime.datetime.now(datetime.UTC),
            })
            count += 1
        return count
