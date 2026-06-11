import logging

import structlog

from sport_slot.middleware.request_id import get_request_id

REDACTED_KEYS = {"email", "authorization", "token", "id_token", "password", "phone"}


def _redact(logger, method_name, event_dict):
    """Charter Phase 2 control: no PII / credentials in logs."""
    for key in list(event_dict):
        if key.lower() in REDACTED_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def _bind_request_id(logger, method_name, event_dict):
    rid = get_request_id()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _bind_request_id,
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
    )
