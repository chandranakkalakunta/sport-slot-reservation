import json

import structlog

from sport_slot.logging import _redact, configure_logging


def test_configure_logging_emits_json_to_stdout(capsys):
    """PrintLoggerFactory routes events to stdout — verifies Cloud Run visibility."""
    configure_logging("WARNING")
    log = structlog.get_logger()
    log.warning("test_stdout_event", canary="ping")
    captured = capsys.readouterr()
    assert captured.out != "", "expected a JSON line on stdout"
    parsed = json.loads(captured.out.strip())
    assert parsed["event"] == "test_stdout_event"
    assert parsed["canary"] == "ping"
    assert parsed["level"] == "warning"


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
