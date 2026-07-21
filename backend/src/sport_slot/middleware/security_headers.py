from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ADR-0043 PR-5a (SEC-HEADERS). Baseline CSP is default-src 'self' — this
# backend is a JSON API (no Jinja/StaticFiles, no server-rendered HTML;
# verified via grep), so it needs nothing beyond 'self'. Known, accepted
# tradeoff: FastAPI's default /docs and /redoc (Swagger UI) load JS/CSS
# from a CDN and will render degraded under this policy — those are
# dev-facing introspection endpoints, not a production user surface, and
# /openapi.json itself is unaffected. Tunable later (e.g. exempt those
# paths, or self-host the Swagger assets) if that's ever a problem.
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
