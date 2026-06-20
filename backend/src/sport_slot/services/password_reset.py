"""Password-reset token minting and per-email cooldown (ADR-0020 A2).

Fail-closed: Redis unavailable → LockUnavailableError → 503 at the route.
Token stored SHA-256-hashed only; raw token returned to caller for URL
construction and is never persisted or logged.
"""

import datetime
import hashlib
import secrets

from redis import exceptions as redis_exceptions

from sport_slot.services.lock import LockUnavailableError


async def enforce_cooldown(redis_client, email: str, ttl: int) -> bool:
    """Set-NX a cooldown key for the email (hashed). Fail-closed.

    Returns True when the cooldown was freshly set (caller may proceed),
    False when it was already active (caller should return UNIFORM_OK silently).
    Raises LockUnavailableError on any Redis/network failure.
    """
    key = "reset_cooldown:" + hashlib.sha256(email.lower().encode()).hexdigest()
    try:
        ok = await redis_client.set(key, "1", nx=True, ex=ttl)
    except (redis_exceptions.RedisError, OSError) as exc:
        raise LockUnavailableError(str(exc)) from exc
    return ok is not None


def mint_and_store_token(fs_client, uid: str, tenant_id: str, ttl: int) -> str:
    """Create a single-use reset token document. Returns the raw (unhashed) token."""
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    now_utc = datetime.datetime.now(datetime.UTC)
    fs_client.collection("password_reset_tokens").document(token_hash).create({
        "uid": uid,
        "tenant_id": tenant_id,
        "used": False,
        "created_at": now_utc,
        "expires_at": now_utc + datetime.timedelta(seconds=ttl),
    })
    return raw
