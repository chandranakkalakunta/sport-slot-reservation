import logging

import structlog

from sport_slot.middleware.request_id import get_request_id

REDACTED_KEYS = {"email", "authorization", "token", "id_token", "password", "phone"}
_REDACT_SUBSTRINGS = ("password", "token")
_REDACT_EXACT = REDACTED_KEYS | {"oobcode"}


def _redact(logger, method_name, event_dict):
    """Charter Phase 2 control: no PII / credentials in logs.

    Redacts any field whose lowercased name matches an exact key OR
    contains a sensitive substring ("password", "token"), covering
    new_password, oobCode, and any future variants automatically.
    """
    for key in list(event_dict):
        k = key.lower()
        if k in _REDACT_EXACT or any(s in k for s in _REDACT_SUBSTRINGS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def _bind_request_id(logger, method_name, event_dict):
    rid = get_request_id()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    # PrintLoggerFactory writes JSON lines to stdout — the stream Cloud Run
    # captures. Without an explicit factory structlog falls back to an
    # implementation-defined destination that doesn't reliably hit stdout
    # in all environments (Cloud Run, uvicorn workers).
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _bind_request_id,
            _redact,
            # Cloud Logging's Logs Explorer (and `gcloud ... logs read`) builds
            # each entry's one-line summary from a top-level "message" field.
            # structlog's event key is "event" by default, so every line was
            # being ingested correctly (full JSON present in jsonPayload) but
            # rendered with a BLANK summary in every view that shows only the
            # summary line. Renaming event->message makes that summary line
            # (and log text search) work.
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )
