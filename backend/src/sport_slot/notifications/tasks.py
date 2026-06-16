"""Cloud Tasks enqueue helper (ADR-0019 §2).

Builds an HTTP task targeting the worker endpoint, OIDC-signed as the
invoker SA, and submits it to the configured queue. Queue, location,
worker URL, and invoker SA all come from Settings so dev and prod
resolve the same way. The booking/welcome write has already succeeded
by the time this is called (ADR-0019 §2 non-blocking constraint), so a
failure here must be loud, not silently swallowed — Cloud Tasks' own
retry/backoff covers transient delivery problems once a task exists,
but this call enqueues that task in the first place.
"""

import json

from google.cloud import tasks_v2

from sport_slot.config import get_settings


class TasksConfigError(Exception):
    """Raised when Settings required to enqueue a task are missing."""


def enqueue_notification(*, event_type: str, to: str, params: dict[str, str | None]) -> str:
    """Enqueue one notification task. Returns the created task's resource name."""
    settings = get_settings()
    if not settings.worker_base_url or not settings.tasks_invoker_sa:
        raise TasksConfigError("worker_base_url / tasks_invoker_sa not configured")

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(settings.gcp_project, settings.tasks_location, settings.tasks_queue)
    url = f"{settings.worker_base_url}/internal/tasks/notify"
    body = json.dumps({"event_type": event_type, "to": to, "params": params}).encode()

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "body": body,
            "oidc_token": {
                "service_account_email": settings.tasks_invoker_sa,
                "audience": settings.worker_base_url,
            },
        }
    }
    response = client.create_task(parent=parent, task=task)
    return response.name
