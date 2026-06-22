"""Agent preference reads (ADR-0021 §3 preference read-side)."""

from __future__ import annotations

import structlog

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.user_profiles import UserProfileRepository

log = structlog.get_logger()


def get_preferences(ctx: TenantContext, client) -> dict:
    """Return the user's last_booked preference map, or {} on any failure.

    Shape: {sport_str: {"facility_id": str, "start_time": str}, ...}
    Written by _write_preference_memory in orchestrator.py on every successful
    agent booking. Read here to enrich system prompts and availability replies.
    """
    try:
        profile = UserProfileRepository(ctx, client).get(ctx.uid) or {}
        return profile.get("preferences", {}).get("last_booked", {}) or {}
    except Exception as exc:
        log.warning("agent_preferences_read_failed", error=str(exc))
        return {}
