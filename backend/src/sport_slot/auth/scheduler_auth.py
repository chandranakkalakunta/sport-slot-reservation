"""OIDC verification for Cloud Scheduler -> invoicing worker calls.

Mirrors tasks_auth.py's verify_tasks_oidc exactly, checking a distinct SA
identity (sa-scheduler-invoker, not sa-tasks-invoker — separate trust
boundary per this project's one-SA-per-boundary convention). Cloud
Scheduler signs each HTTP call with a Google-minted OIDC ID token for the
configured invoker SA; verified the way any Google OIDC consumer would:
signature + issuer via google-auth, then pin audience and the calling
SA's email. No shared secret — the verified identity is the credential.
"""

from fastapi import Depends, Request
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.config import Settings, get_settings

_google_request = google_auth_requests.Request()


def verify_scheduler_oidc(request: Request, settings: Settings = Depends(get_settings)) -> None:
    if not settings.worker_base_url or not settings.scheduler_invoker_sa:
        raise ApiError(500, error_codes.INTERNAL_ERROR, "Scheduler OIDC verification not configured")

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise ApiError(401, error_codes.TASK_UNAUTHORIZED, "Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        claims = id_token.verify_oauth2_token(
            token, _google_request, audience=settings.worker_base_url
        )
    except Exception as exc:
        raise ApiError(403, error_codes.TASK_UNAUTHORIZED, "OIDC verification failed") from exc

    if claims.get("email") != settings.scheduler_invoker_sa or not claims.get("email_verified"):
        raise ApiError(403, error_codes.TASK_UNAUTHORIZED, "Unexpected caller identity")
