import json
from unittest.mock import MagicMock, patch

import pytest

from sport_slot.config import get_settings
from sport_slot.notifications.tasks import TasksConfigError, enqueue_notification

WORKER_URL = "https://sport-slot-api-abc123-el.a.run.app"
INVOKER_SA = "sa-tasks-invoker@sport-slot-dev.iam.gserviceaccount.com"


@pytest.fixture()
def configured_settings(monkeypatch):
    monkeypatch.setenv("SPORTSLOT_WORKER_BASE_URL", WORKER_URL)
    monkeypatch.setenv("SPORTSLOT_TASKS_INVOKER_SA", INVOKER_SA)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_enqueue_raises_when_not_configured(monkeypatch):
    monkeypatch.delenv("SPORTSLOT_WORKER_BASE_URL", raising=False)
    monkeypatch.delenv("SPORTSLOT_TASKS_INVOKER_SA", raising=False)
    get_settings.cache_clear()
    with pytest.raises(TasksConfigError):
        enqueue_notification(event_type="booking_confirmed", to="u@example.com", params={})
    get_settings.cache_clear()


def test_enqueue_builds_expected_task(configured_settings):
    fake_client = MagicMock()
    fake_client.queue_path.return_value = (
        "projects/sport-slot-dev/locations/asia-south1/queues/notifications"
    )
    fake_response = MagicMock()
    fake_response.name = "task-name-1"
    fake_client.create_task.return_value = fake_response

    with patch("sport_slot.notifications.tasks.tasks_v2.CloudTasksClient", return_value=fake_client):
        result = enqueue_notification(
            event_type="booking_confirmed",
            to="u@example.com",
            params={"facility": "Court 1"},
        )

    assert result == "task-name-1"

    fake_client.queue_path.assert_called_once_with("sport-slot-dev", "asia-south1", "notifications")
    create_kwargs = fake_client.create_task.call_args.kwargs
    assert create_kwargs["parent"] == (
        "projects/sport-slot-dev/locations/asia-south1/queues/notifications"
    )
    http_request = create_kwargs["task"]["http_request"]
    assert http_request["url"] == f"{WORKER_URL}/internal/tasks/notify"
    assert http_request["oidc_token"] == {
        "service_account_email": INVOKER_SA,
        "audience": WORKER_URL,
    }
    body = json.loads(http_request["body"])
    assert body == {
        "event_type": "booking_confirmed",
        "to": "u@example.com",
        "params": {"facility": "Court 1"},
    }
