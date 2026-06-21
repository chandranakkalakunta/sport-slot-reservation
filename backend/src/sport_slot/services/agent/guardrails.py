"""Output guard for agent replies.

Two-stage: fast rules-based check first, then LLM classifier (if enabled).
Fail closed — any guard failure returns False (block the reply).
"""

from __future__ import annotations

import re

import structlog

log = structlog.get_logger()

# Hard-block patterns: things that must never appear in an agent reply.
_BLOCK_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(password|secret|token|api.?key)\b", re.IGNORECASE),
    re.compile(r"uid\s*[:=]\s*\S", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", re.IGNORECASE),  # email address
]

# Replies longer than this are suspicious — truncate before LLM classify.
_MAX_LEN = 2000


def rules_pass(reply: str) -> bool:
    """Fast deterministic check. Returns False if any hard-block pattern fires."""
    if len(reply) > _MAX_LEN:
        log.warning("agent_reply_too_long", length=len(reply))
        return False
    for pattern in _BLOCK_PATTERNS:
        if pattern.search(reply):
            log.warning("agent_reply_blocked_by_rules", pattern=pattern.pattern)
            return False
    return True


async def output_is_safe(reply: str) -> bool:
    """Full output guard: rules first, then LLM classifier (if enabled + rules pass)."""
    from sport_slot.config import get_settings
    from sport_slot.services.agent import vertex_client

    if not rules_pass(reply):
        return False

    settings = get_settings()
    if not settings.agent_output_guard_enabled:
        return True

    return await vertex_client.classify_output(reply)
