from sport_slot.logging import _redact


def test_redaction_masks_sensitive_keys():
    event = {"event": "login", "email": "x@y.com", "Authorization": "Bearer abc", "ok": 1}
    result = _redact(None, None, event)
    assert result["email"] == "[REDACTED]"
    assert result["Authorization"] == "[REDACTED]"
    assert result["ok"] == 1
