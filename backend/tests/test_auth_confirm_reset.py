"""Hermetic tests for POST /api/v1/auth/forgot-password/confirm (Phase 7.2.2b).

All external I/O (Firebase, Firestore, validate_password) is mocked.
Tests use unique bearer tokens to avoid rate-limit key collisions (same
pattern as test_auth_forgot_password.py).
"""

import datetime
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

from sport_slot.dependencies import get_firestore_client

# Patch targets
FB_UPDATE_USER = "sport_slot.api.v1.auth.fb_auth.update_user"
FB_REVOKE = "sport_slot.api.v1.auth.fb_auth.revoke_refresh_tokens"
VALIDATE_PW = "sport_slot.api.v1.auth.validate_password"
CONSUME = "sport_slot.api.v1.auth.consume_reset_token"  # imported from repositories.password_reset
AUDIT_WRITE = "sport_slot.repositories.bookings.AuditRepository.write_event"

URL = "/api/v1/auth/forgot-password/confirm"

RAW_TOKEN = "validrawtoken-abc-xyz-1234567890-abcdef"
TOKEN_HASH = hashlib.sha256(RAW_TOKEN.encode()).hexdigest()
STRONG_PASSWORD = "Tr0ub4dor&3-correcthorsebatterystaple!"

_TOKENS = [f"bearer-confirm-{i}" for i in range(1, 20)]


def _auth(n: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKENS[n]}"}


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _valid_token_doc(used: bool = False, hours_ahead: float = 1.0) -> dict:
    return {
        "uid": "uid-1",
        "tenant_id": "t-1",
        "used": used,
        "expires_at": _now() + datetime.timedelta(hours=hours_ahead),
    }


def _fs_with_snap(snap_data: dict | None) -> MagicMock:
    """Return a Firestore mock whose first .collection().document().get() returns snap_data.
    If snap_data is None the snapshot does not exist."""
    fs = MagicMock()
    snap = MagicMock()
    snap.exists = snap_data is not None
    if snap_data is not None:
        snap.to_dict.return_value = snap_data
    fs.collection.return_value.document.return_value.get.return_value = snap
    return fs


def _wire(app_client, fs):
    app_client._transport.app.dependency_overrides[get_firestore_client] = lambda: fs


def _ok_validate():
    from sport_slot.auth.password_policy import PasswordPolicyResult
    return AsyncMock(return_value=PasswordPolicyResult(ok=True))


def _fail_validate():
    from sport_slot.auth.password_policy import PasswordPolicyResult
    return AsyncMock(return_value=PasswordPolicyResult(ok=False, errors=["Too weak."]))


# ── (a) token not found ───────────────────────────────────────────────────────

async def test_not_found_token_returns_400(make_client):
    fs = _fs_with_snap(None)
    with patch(FB_UPDATE_USER) as mock_update:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": "junk", "new_password": STRONG_PASSWORD},
                                     headers=_auth(0))
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESET_TOKEN_INVALID"
    mock_update.assert_not_called()


# ── (a) used token ────────────────────────────────────────────────────────────

async def test_used_token_returns_400(make_client):
    fs = _fs_with_snap(_valid_token_doc(used=True))
    with patch(FB_UPDATE_USER) as mock_update:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                                     headers=_auth(1))
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESET_TOKEN_INVALID"
    mock_update.assert_not_called()


# ── (a) expired token ─────────────────────────────────────────────────────────

async def test_expired_token_returns_400(make_client):
    expired_doc = {**_valid_token_doc(), "expires_at": _now() - datetime.timedelta(seconds=1)}
    fs = _fs_with_snap(expired_doc)
    with patch(FB_UPDATE_USER) as mock_update:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                                     headers=_auth(2))
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESET_TOKEN_INVALID"
    mock_update.assert_not_called()


# ── (b) validate-before-consume ───────────────────────────────────────────────

async def test_weak_password_returns_422_token_not_consumed(make_client):
    """FALSIFIABLE CRITERION: weak password → 422 and consume_reset_token NOT called
    (token doc's 'used' remains False; update_user NOT called)."""
    fs = _fs_with_snap(_valid_token_doc())
    with patch(VALIDATE_PW, _fail_validate()), \
         patch(CONSUME) as mock_consume, \
         patch(FB_UPDATE_USER) as mock_update:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": "weak"},
                                     headers=_auth(3))
    assert resp.status_code == 422
    assert resp.json()["code"] == "WEAK_PASSWORD"
    mock_consume.assert_not_called()
    mock_update.assert_not_called()


# ── (c) single-use race ───────────────────────────────────────────────────────

async def test_single_use_race_loser_gets_400(make_client):
    """Concurrent winner already consumed the token; txn re-read sees used=True
    → consume_reset_token raises ResetTokenInvalid → loser gets 400, update_user NOT called."""
    from sport_slot.repositories.password_reset import ResetTokenInvalid
    fs = _fs_with_snap(_valid_token_doc())
    with patch(VALIDATE_PW, _ok_validate()), \
         patch(CONSUME, side_effect=ResetTokenInvalid()), \
         patch(FB_UPDATE_USER) as mock_update:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                                     headers=_auth(4))
    assert resp.status_code == 400
    assert resp.json()["code"] == "RESET_TOKEN_INVALID"
    mock_update.assert_not_called()


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_happy_path(make_client):
    """200; update_user called once with new password; revoke called; flag cleared; audit written."""
    fs = _fs_with_snap(_valid_token_doc())

    # Track .update() calls on the profile document (separate collection chain)
    profile_update_mock = MagicMock()

    def _col_side_effect(name):
        if name == "password_reset_tokens":
            return fs.collection.return_value  # already set up via _fs_with_snap
        if name == "tenants":
            # Return a chain that leads to .collection("users").document(uid).update(...)
            tenants_mock = MagicMock()
            users_col = MagicMock()
            profile_doc = MagicMock()
            profile_doc.update = profile_update_mock
            users_col.document.return_value = profile_doc
            tenants_mock.document.return_value.collection.return_value = users_col
            return tenants_mock
        return fs.collection.return_value

    fs.collection.side_effect = _col_side_effect

    with patch(VALIDATE_PW, _ok_validate()), \
         patch(CONSUME, return_value={"uid": "uid-1", "tenant_id": "t-1"}), \
         patch(FB_UPDATE_USER) as mock_update, \
         patch(FB_REVOKE) as mock_revoke, \
         patch(AUDIT_WRITE) as mock_audit:
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                                     headers=_auth(5))

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message": "Password has been reset."}

    # update_user called with the new password
    mock_update.assert_called_once_with("uid-1", password=STRONG_PASSWORD)

    # revoke_refresh_tokens called
    mock_revoke.assert_called_once_with("uid-1")

    # must_change_password cleared
    profile_update_mock.assert_called_once_with({"must_change_password": False})

    # audit written with correct event type
    mock_audit.assert_called_once()
    assert mock_audit.call_args.args[0] == "auth.password_reset_completed"
    assert mock_audit.call_args.args[3] == ""  # booking_id is ""


# ── Post-step resilience ──────────────────────────────────────────────────────

async def test_revoke_failure_still_returns_200(make_client):
    """update_user succeeds but revoke_refresh_tokens raises → still 200."""
    fs = _fs_with_snap(_valid_token_doc())
    with patch(VALIDATE_PW, _ok_validate()), \
         patch(CONSUME, return_value={"uid": "uid-1", "tenant_id": "t-1"}), \
         patch(FB_UPDATE_USER), \
         patch(FB_REVOKE, side_effect=Exception("Firebase error")), \
         patch(AUDIT_WRITE):
        async with make_client() as client:
            _wire(client, fs)
            resp = await client.post(URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                                     headers=_auth(6))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password has been reset."


# ── Anti-oracle: not-found, used, expired are byte-identical ─────────────────

async def test_anti_oracle_token_errors_identical(make_client):
    not_found_fs = _fs_with_snap(None)
    used_fs = _fs_with_snap(_valid_token_doc(used=True))
    expired_doc = {**_valid_token_doc(), "expires_at": _now() - datetime.timedelta(seconds=1)}
    expired_fs = _fs_with_snap(expired_doc)

    responses = []
    for i, fs in enumerate([not_found_fs, used_fs, expired_fs]):
        with patch(FB_UPDATE_USER):
            async with make_client() as client:
                _wire(client, fs)
                resp = await client.post(
                    URL, json={"token": RAW_TOKEN, "new_password": STRONG_PASSWORD},
                    headers=_auth(7 + i),
                )
        responses.append(resp)

    statuses = [r.status_code for r in responses]
    assert all(s == 400 for s in statuses), f"Expected all 400, got {statuses}"
    # request_id and timestamp differ per request — compare the stable fields only
    codes = [r.json()["code"] for r in responses]
    messages = [r.json()["message"] for r in responses]
    assert codes[0] == codes[1] == codes[2] == "RESET_TOKEN_INVALID"
    assert messages[0] == messages[1] == messages[2]


# ── consume_reset_token unit tests ────────────────────────────────────────────

def test_consume_flips_used_true():
    """Txn re-reads a valid token and sets used=True; returns uid+tenant_id."""
    from sport_slot.repositories.password_reset import consume_reset_token  # noqa: PLC0415

    fs = MagicMock()
    txn = MagicMock()
    fs.transaction.return_value = txn

    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "uid": "uid-1",
        "tenant_id": "t-1",
        "used": False,
        "expires_at": _now() + datetime.timedelta(hours=1),
    }
    ref = fs.collection.return_value.document.return_value
    ref.get.return_value = snap

    with patch("google.cloud.firestore.transactional", lambda f: f):
        result = consume_reset_token(fs, TOKEN_HASH)

    assert result == {"uid": "uid-1", "tenant_id": "t-1"}
    txn.update.assert_called_once_with(ref, {"used": True})


def test_consume_raises_when_missing():
    from sport_slot.repositories.password_reset import consume_reset_token, ResetTokenInvalid  # noqa: PLC0415

    fs = MagicMock()
    txn = MagicMock()
    fs.transaction.return_value = txn

    snap = MagicMock()
    snap.exists = False
    fs.collection.return_value.document.return_value.get.return_value = snap

    import pytest
    with patch("google.cloud.firestore.transactional", lambda f: f):
        with pytest.raises(ResetTokenInvalid):
            consume_reset_token(fs, TOKEN_HASH)


def test_consume_raises_when_already_used():
    from sport_slot.repositories.password_reset import consume_reset_token, ResetTokenInvalid  # noqa: PLC0415

    fs = MagicMock()
    txn = MagicMock()
    fs.transaction.return_value = txn

    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "uid": "uid-1", "tenant_id": "t-1", "used": True,
        "expires_at": _now() + datetime.timedelta(hours=1),
    }
    fs.collection.return_value.document.return_value.get.return_value = snap

    import pytest
    with patch("google.cloud.firestore.transactional", lambda f: f):
        with pytest.raises(ResetTokenInvalid):
            consume_reset_token(fs, TOKEN_HASH)


def test_consume_raises_when_expired():
    from sport_slot.repositories.password_reset import consume_reset_token, ResetTokenInvalid  # noqa: PLC0415

    fs = MagicMock()
    txn = MagicMock()
    fs.transaction.return_value = txn

    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {
        "uid": "uid-1", "tenant_id": "t-1", "used": False,
        "expires_at": _now() - datetime.timedelta(seconds=1),
    }
    fs.collection.return_value.document.return_value.get.return_value = snap

    import pytest
    with patch("google.cloud.firestore.transactional", lambda f: f):
        with pytest.raises(ResetTokenInvalid):
            consume_reset_token(fs, TOKEN_HASH)
