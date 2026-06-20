from sport_slot.logging import _redact


def test_redaction_masks_sensitive_keys():
    event = {"event": "login", "email": "x@y.com", "Authorization": "Bearer abc", "ok": 1}
    result = _redact(None, None, event)
    assert result["email"] == "[REDACTED]"
    assert result["Authorization"] == "[REDACTED]"
    assert result["ok"] == 1


def test_redaction_masks_new_password_and_oobcode():
    """new_password (contains 'password') and oobCode must be redacted."""
    event = {
        "event": "change_password",
        "new_password": "s3cr3t!",
        "oobCode": "firebase-oob-token-abc123",
        "uid": "u-1",
    }
    result = _redact(None, None, event)
    assert result["new_password"] == "[REDACTED]"
    assert result["oobCode"] == "[REDACTED]"
    assert result["uid"] == "u-1"  # non-sensitive field untouched
