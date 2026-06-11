import hashlib

from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request

from sport_slot.api import error_codes
from sport_slot.api.errors import _envelope
from sport_slot.config import get_settings


def rate_limit_key(request: Request) -> str:
    """Per-user when a bearer token is present (hashed, never the
    token itself), else per-IP. ADR-0007 §5."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
        return "u:" + hashlib.sha256(token.encode()).hexdigest()[:16]
    return "ip:" + (get_remote_address(request) or "unknown")


def _current_limit() -> str:
    # Callable limit: resolved per request, so env overrides in
    # tests (which clear the settings cache) take effect.
    return get_settings().rate_limit


limiter = Limiter(key_func=rate_limit_key, default_limits=[_current_limit])


class EnvelopeRateLimitMiddleware(SlowAPIMiddleware):
    """slowapi 0.1.9's middleware hardcodes its default 429 body
    and never reaches FastAPI's exception handlers. We let it do
    its work, then rewrite any 429 it produced into the ADR-0006
    error envelope. Depends only on '429 from this layer means
    rate limited', not on slowapi internals."""

    async def dispatch(self, request, call_next):
        response = await super().dispatch(request, call_next)
        if response.status_code == 429:
            envelope = JSONResponse(
                status_code=429,
                content=_envelope(error_codes.RATE_LIMITED, "Too many requests"),
            )
            retry_after = response.headers.get("retry-after")
            if retry_after:
                envelope.headers["Retry-After"] = retry_after
            return envelope
        return response
