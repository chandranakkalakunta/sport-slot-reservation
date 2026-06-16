from unittest.mock import patch

from sport_slot.dependencies import get_email_provider
from tests.email_fakes import FakeEmailProvider

WORKER_URL = "https://sport-slot-api-abc123-el.a.run.app"
INVOKER_SA = "sa-tasks-invoker@sport-slot-dev.iam.gserviceaccount.com"
TASKS_ENV = {
    "SPORTSLOT_WORKER_BASE_URL": WORKER_URL,
    "SPORTSLOT_TASKS_INVOKER_SA": INVOKER_SA,
}
VALID_CLAIMS = {"email": INVOKER_SA, "email_verified": True}
VERIFY = "sport_slot.auth.tasks_auth.id_token.verify_oauth2_token"

BOOKING_PARAMS = {
    "user_name": "Jane Doe",
    "tenant_name": "Demo Society",
    "facility": "Court 1",
    "sport": "Tennis",
    "date": "2026-06-20",
    "start_time": "18:00",
    "end_time": "19:00",
    "booking_id": "bk-1",
}
WELCOME_PARAMS = {
    "user_name": "Jane Doe",
    "tenant_name": "Demo Society",
    "login_url": "https://demo.example.com/login",
}


def _override_provider(app, fake: FakeEmailProvider) -> None:
    app.dependency_overrides[get_email_provider] = lambda: fake


async def test_notify_500_when_oidc_not_configured(make_client):
    # No SPORTSLOT_WORKER_BASE_URL / SPORTSLOT_TASKS_INVOKER_SA set.
    async with make_client() as client:
        resp = await client.post(
            "/internal/tasks/notify",
            json={"event_type": "booking_confirmed", "to": "u@example.com", "params": {}},
        )
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"


async def test_notify_rejects_missing_bearer_token(make_client):
    async with make_client(TASKS_ENV) as client:
        resp = await client.post(
            "/internal/tasks/notify",
            json={"event_type": "booking_confirmed", "to": "u@example.com", "params": {}},
        )
    assert resp.status_code == 401
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_notify_rejects_invalid_oidc_token(make_client):
    with patch(VERIFY, side_effect=ValueError("bad signature")):
        async with make_client(TASKS_ENV) as client:
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer not-a-real-token"},
                json={"event_type": "booking_confirmed", "to": "u@example.com", "params": {}},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_notify_rejects_wrong_caller_identity(make_client):
    wrong_claims = {"email": "someone-else@example.com", "email_verified": True}
    with patch(VERIFY, return_value=wrong_claims):
        async with make_client(TASKS_ENV) as client:
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={"event_type": "booking_confirmed", "to": "u@example.com", "params": {}},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_notify_sends_booking_confirmed_via_fake_provider(make_client):
    fake = FakeEmailProvider()
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            _override_provider(client._transport.app, fake)
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={
                    "event_type": "booking_confirmed",
                    "to": "u@example.com",
                    "params": BOOKING_PARAMS,
                },
            )
    assert resp.status_code == 200
    assert resp.json() == {"status": "sent"}
    assert len(fake.sent) == 1
    assert fake.sent[0]["to"] == "u@example.com"
    assert fake.sent[0]["tags"] == {"type": "booking_confirmed"}


async def test_notify_sends_user_welcome_via_fake_provider(make_client):
    fake = FakeEmailProvider()
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            _override_provider(client._transport.app, fake)
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={
                    "event_type": "user_welcome",
                    "to": "u@example.com",
                    "params": WELCOME_PARAMS,
                },
            )
    assert resp.status_code == 200
    assert len(fake.sent) == 1


async def test_notify_returns_422_on_unknown_event_type(make_client):
    # Provider dependency is resolved regardless of payload validity (it is
    # a plain FastAPI Depends), so it still needs a working override even
    # though this request never reaches provider.send().
    fake = FakeEmailProvider()
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            _override_provider(client._transport.app, fake)
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={"event_type": "bogus_event", "to": "u@example.com", "params": {}},
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "TASK_INVALID_PAYLOAD"
    assert fake.sent == []


async def test_notify_returns_422_on_invalid_params(make_client):
    incomplete_params = dict(BOOKING_PARAMS)
    del incomplete_params["facility"]
    fake = FakeEmailProvider()
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            _override_provider(client._transport.app, fake)
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={
                    "event_type": "booking_confirmed",
                    "to": "u@example.com",
                    "params": incomplete_params,
                },
            )
    assert resp.status_code == 422
    assert resp.json()["code"] == "TASK_INVALID_PAYLOAD"
    assert fake.sent == []


async def test_notify_returns_503_on_provider_send_failure(make_client):
    fake = FakeEmailProvider(fail=True)
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            _override_provider(client._transport.app, fake)
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={
                    "event_type": "booking_confirmed",
                    "to": "u@example.com",
                    "params": BOOKING_PARAMS,
                },
            )
    assert resp.status_code == 503
    assert resp.json()["code"] == "TASK_SEND_FAILED"
