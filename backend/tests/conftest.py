import httpx
import pytest
from fastapi import Depends
from httpx import ASGITransport

from sport_slot.auth.context import TenantContext
from sport_slot.auth.dependency import get_tenant_context
from sport_slot.config import get_settings


@pytest.fixture()
def make_client(monkeypatch):
    """Factory: build an app+client with env overrides; adds a probe route."""

    def _make(env: dict[str, str] | None = None) -> httpx.AsyncClient:
        defaults = {
            "SPORTSLOT_ENVIRONMENT": "development",
            "SPORTSLOT_DEV_TENANT_SLUG": "demo",
        }
        for key, value in {**defaults, **(env or {})}.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()

        from sport_slot.main import create_app

        app = create_app()

        @app.get("/api/v1/_test/whoami")
        async def whoami(ctx: TenantContext = Depends(get_tenant_context)):
            return {"uid": ctx.uid, "tenant_slug": ctx.tenant_slug, "role": ctx.role}

        return httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        )

    yield _make
    get_settings.cache_clear()
