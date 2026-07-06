"""Cloud Tasks worker endpoint (ADR-0019 §3).

Consumes notification tasks and dispatches to the configured
EmailProvider. Not part of the tenant-facing API surface (no Firebase
JWT / TenantContext here) — authenticated solely via Cloud Tasks OIDC
(see auth/tasks_auth.py). Returns 2xx on success so Cloud Tasks marks
the dispatch done, 5xx on a provider failure so Cloud Tasks retries
per the queue's retry_config, 4xx on a malformed/unknown payload so
Cloud Tasks does NOT retry (retrying a bad payload forever is pointless).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.auth.tasks_auth import verify_tasks_oidc
from sport_slot.dependencies import get_email_provider
from sport_slot.notifications.email.provider import EmailProvider, EmailSendError
from sport_slot.notifications.email.templates import (
    render_booking_cancelled,
    render_booking_confirmed,
    render_password_reset,
    render_user_welcome,
)
from sport_slot.ratelimit import limiter

router = APIRouter(prefix="/internal/tasks", tags=["internal"])

_RENDERERS = {
    "booking_cancelled": render_booking_cancelled,
    "booking_confirmed": render_booking_confirmed,
    "user_welcome": render_user_welcome,
    "password_reset": render_password_reset,
}


class NotificationTask(BaseModel):
    event_type: str
    to: str
    params: dict[str, str | None]


@router.post("/notify", dependencies=[Depends(verify_tasks_oidc)])
@limiter.exempt
async def notify(
    task: NotificationTask,
    provider: EmailProvider = Depends(get_email_provider),
):
    renderer = _RENDERERS.get(task.event_type)
    if renderer is None:
        raise ApiError(
            422, error_codes.TASK_INVALID_PAYLOAD, f"Unknown event_type: {task.event_type}"
        )

    try:
        rendered = renderer(**task.params)
    except TypeError as exc:
        raise ApiError(422, error_codes.TASK_INVALID_PAYLOAD, f"Invalid params: {exc}") from exc

    try:
        await run_in_threadpool(
            provider.send,
            to=task.to,
            subject=rendered.subject,
            html=rendered.html,
            text=rendered.text,
            tags={"type": task.event_type},
        )
    except EmailSendError as exc:
        raise ApiError(503, error_codes.TASK_SEND_FAILED, str(exc)) from exc

    return {"status": "sent"}
