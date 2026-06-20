"""Hermetic tests for POST /api/v1/auth/forgot-password (Phase 7.2.2a).

All external I/O (Firebase, Firestore, Redis, enqueue_notification) is mocked.
Each test uses a unique X-Forwarded-For header to avoid rate-limit key collisions
between tests (the rate-limit key is IP-based for unauthenticated requests).
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

from sport_slot.dependencies import get_firestore_client, get_redis_client

# Patch targets
FB_GET_USER = "sport_slot.api.v1.auth.fb_auth.get_user_by_email"
FB_USER_NOT_FOUND = "sport_slot.api.v1.auth.fb_auth.UserNotFoundError"
ENQUEUE = "sport_slot.api.v1.auth.enqueue_notification"
MINT = "sport_slot.api.v1.auth.mint_and_store_token"
AUDIT_WRITE = "sport_slot.repositories.bookings.AuditRepository.write_event"

URL = "/api/v1/auth/forgot-password"
BODY = {"email": "user@example.com"}

# Unique per-test bearer tokens prevent the 5/hour per-route limiter from
# accumulating counts across tests. The rate_limit_key function keys on the
# bearer token hash when present; the forgot-password route ignores it.
_TOKENS = [f"test-token-{i}" for i in range(1, 20)]


def _auth(n: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKENS[n]}"}


def _fs_mock(display_name: str = "Demo Society") -> MagicMock:
    fs = MagicMock()
    snap = fs.collection.return_value.document.return_value.get.return_value
    snap.exists = True
    snap.to_dict.return_value = {"display_name": display_name}
    return fs


def _redis_mock(nx_result=True) -> MagicMock:
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True if nx_result else None)
    return redis


def _user(
    uid="uid-1",
    display_name="Jane Doe",
    disabled=False,
    claims=None,
) -> MagicMock:
    u = MagicMock()
    u.uid = uid
    u.display_name = display_name
    u.disabled = disabled
    u.custom_claims = claims if claims is not None else {
        "tenant_id": "t-1",
        "tenant_slug": "demo",
        "role": "resident",
    }
    return u


def _wire(app_client, fs, redis):
    overrides = app_client._transport.app.dependency_overrides
    overrides[get_firestore_client] = lambda: fs
    overrides[get_redis_client] = lambda: redis


# ── Cooldown active ───────────────────────────────────────────────────────────

async def test_cooldown_active_returns_uniform_ok_silently(make_client):
    fs = _fs_mock()
    redis = _redis_mock(nx_result=False)  # NX fails → already active
    with patch(FB_GET_USER) as mock_get_user, \
         patch(ENQUEUE) as mock_enqueue:
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(0))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "reset link" in resp.json()["message"]
    mock_get_user.assert_not_called()
    mock_enqueue.assert_not_called()
    # No token doc created
    fs.collection.return_value.document.return_value.create.assert_not_called()


# ── Redis down → 503 fail-closed ──────────────────────────────────────────────

async def test_redis_down_returns_503_get_user_not_called(make_client):
    from redis.exceptions import ConnectionError as RedisConnectionError
    fs = _fs_mock()
    redis = MagicMock()
    redis.set = AsyncMock(side_effect=RedisConnectionError("timeout"))
    with patch(FB_GET_USER) as mock_get_user, \
         patch(ENQUEUE):
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(1))
    assert resp.status_code == 503
    assert resp.json()["code"] == "LOCK_UNAVAILABLE"
    mock_get_user.assert_not_called()


# ── Unknown email ─────────────────────────────────────────────────────────────

async def test_unknown_email_returns_uniform_ok(make_client):
    fs = _fs_mock()
    redis = _redis_mock()
    with patch(FB_GET_USER, side_effect=fb_auth_user_not_found()), \
         patch(ENQUEUE) as mock_enqueue:
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(2))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_enqueue.assert_not_called()


# ── Disabled user ─────────────────────────────────────────────────────────────

async def test_disabled_user_returns_uniform_ok(make_client):
    fs = _fs_mock()
    redis = _redis_mock()
    user = _user(disabled=True)
    with patch(FB_GET_USER, return_value=user), \
         patch(ENQUEUE) as mock_enqueue:
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(3))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_enqueue.assert_not_called()


# ── No tenant_id claim ────────────────────────────────────────────────────────

async def test_no_tenant_id_returns_uniform_ok(make_client):
    fs = _fs_mock()
    redis = _redis_mock()
    user = _user(claims={"role": "resident"})  # tenant_id absent
    with patch(FB_GET_USER, return_value=user), \
         patch(ENQUEUE) as mock_enqueue:
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(4))
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_enqueue.assert_not_called()


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_happy_path(make_client):
    """Token doc created (id == sha256 of raw), raw NOT stored; enqueue called;
    audit written; response is UNIFORM_OK."""
    fs = _fs_mock()
    redis = _redis_mock()
    user = _user()

    captured_docs = {}

    def _fake_create(data):
        captured_docs["data"] = data

    token_doc_mock = MagicMock()
    token_doc_mock.create.side_effect = _fake_create

    token_col_mock = MagicMock()
    token_col_mock.document.return_value = token_doc_mock

    # Firestore: first call is password_reset_tokens collection,
    # second is tenants/{tenant_id}.
    def _col_side_effect(name):
        if name == "password_reset_tokens":
            return token_col_mock
        return fs.collection.return_value  # tenants

    fs.collection.side_effect = _col_side_effect

    raw_token_holder = {}

    def _capture_enqueue(*, event_type, to, params):
        raw_token_holder["reset_url"] = params["reset_url"]

    with patch(FB_GET_USER, return_value=user), \
         patch(ENQUEUE, side_effect=_capture_enqueue) as mock_enqueue, \
         patch(AUDIT_WRITE) as mock_audit:
        async with make_client() as client:
            _wire(client, fs, redis)
            resp = await client.post(URL, json=BODY, headers=_auth(5))

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "If an account exists, a reset link was sent."}

    # Token document was created
    assert captured_docs, "mint_and_store_token never called create()"
    stored = captured_docs["data"]

    # raw is NOT in the stored document
    assert "raw" not in stored
    assert stored["used"] is False
    assert stored["uid"] == "uid-1"
    assert stored["tenant_id"] == "t-1"

    # The document key (passed to .document()) should be sha256 of the raw token
    raw_from_url = raw_token_holder["reset_url"].split("?token=")[1]
    expected_hash = hashlib.sha256(raw_from_url.encode()).hexdigest()
    token_col_mock.document.assert_called_once_with(expected_hash)

    # enqueue called once with correct event_type and a reset_url containing ?token=
    mock_enqueue.assert_called_once()
    call_kwargs = mock_enqueue.call_args.kwargs
    assert call_kwargs["event_type"] == "password_reset"
    assert call_kwargs["to"] == "user@example.com"
    assert "?token=" in call_kwargs["params"]["reset_url"]

    # audit written with correct event type and empty booking_id
    mock_audit.assert_called_once()
    audit_args = mock_audit.call_args.args
    assert audit_args[0] == "auth.password_reset_requested"
    assert audit_args[3] == ""  # booking_id


# ── Anti-oracle: unknown-email and happy-path responses are byte-identical ────

async def test_anti_oracle_unknown_vs_happy_path_identical_response(make_client):
    fs = _fs_mock()
    redis_1 = _redis_mock()
    redis_2 = _redis_mock()
    user = _user()

    # Unknown email path
    with patch(FB_GET_USER, side_effect=fb_auth_user_not_found()), \
         patch(ENQUEUE):
        async with make_client() as client:
            _wire(client, fs, redis_1)
            resp_unknown = await client.post(URL, json=BODY, headers=_auth(6))

    # Happy path
    with patch(FB_GET_USER, return_value=user), \
         patch(ENQUEUE), \
         patch(AUDIT_WRITE):
        async with make_client() as client:
            _wire(client, fs, redis_2)
            resp_happy = await client.post(URL, json=BODY, headers=_auth(7))

    assert resp_unknown.status_code == resp_happy.status_code == 200
    assert resp_unknown.json() == resp_happy.json()


# ── render_password_reset unit test ──────────────────────────────────────────

def test_render_password_reset_subject_html_text():
    from sport_slot.notifications.email.templates import render_password_reset

    result = render_password_reset(
        user_name="Jane <Doe>",
        tenant_name="Demo & Society",
        reset_url="https://example.com/reset?token=abc123",
    )

    assert result.subject == "Reset your password"
    # HTML-escaping: < > &
    assert "Jane &lt;Doe&gt;" in result.html
    assert "Demo &amp; Society" in result.html
    # URL appears in both html and text
    assert "https://example.com/reset?token=abc123" in result.html
    assert "https://example.com/reset?token=abc123" in result.text
    # Expiry warning in both
    assert "expires" in result.html
    assert "expires" in result.text


# ── Worker dispatch: password_reset event_type routes to the renderer ─────────

async def test_worker_dispatches_password_reset(make_client):
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

    fake = FakeEmailProvider()
    with patch(VERIFY, return_value=VALID_CLAIMS):
        async with make_client(TASKS_ENV) as client:
            client._transport.app.dependency_overrides[get_email_provider] = lambda: fake
            resp = await client.post(
                "/internal/tasks/notify",
                headers={"Authorization": "Bearer token"},
                json={
                    "event_type": "password_reset",
                    "to": "user@example.com",
                    "params": {
                        "user_name": "Jane",
                        "tenant_name": "Demo",
                        "reset_url": "https://example.com/reset?token=x",
                    },
                },
            )
    assert resp.status_code == 200
    assert resp.json() == {"status": "sent"}
    assert len(fake.sent) == 1
    assert fake.sent[0]["tags"] == {"type": "password_reset"}


# ── Helper ────────────────────────────────────────────────────────────────────

def fb_auth_user_not_found():
    """Return a UserNotFoundError instance for use as side_effect."""
    from firebase_admin import auth as fb_auth
    return fb_auth.UserNotFoundError("not found")
