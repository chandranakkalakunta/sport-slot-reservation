import firebase_admin
import structlog
from fastapi import APIRouter, FastAPI

from sport_slot.api.errors import register_exception_handlers
from sport_slot.api.internal.tasks import router as tasks_router
from sport_slot.api.v1.admin import router as admin_router
from sport_slot.api.v1.agent import router as agent_router
from sport_slot.api.v1.auth import router as auth_router
from sport_slot.api.v1.bookings import router as bookings_router
from sport_slot.api.v1.branding import router as branding_router
from sport_slot.api.v1.daily_overview import router as daily_overview_router
from sport_slot.api.v1.facility_catalog import router as catalog_router
from sport_slot.api.v1.facilities import router as facilities_router
from sport_slot.api.v1.facilities import tenant_facilities_router
from sport_slot.api.v1.tenant_config import router as tenant_config_router
from sport_slot.api.v1.users import router as users_router
from sport_slot.config import get_settings
from sport_slot.health import router as health_router
from sport_slot.logging import configure_logging
from sport_slot.middleware.request_id import RequestIdMiddleware
from sport_slot.ratelimit import EnvelopeRateLimitMiddleware, limiter

log = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
    except Exception:
        log.warning("firebase_admin_not_initialized", hint="auth will fail until ADC exists")

    app = FastAPI(title="SportSlotReservation API", version="0.2.0")

    app.state.limiter = limiter

    app.add_middleware(EnvelopeRateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(tasks_router)

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(users_router)
    v1.include_router(catalog_router)
    v1.include_router(facilities_router)
    v1.include_router(tenant_facilities_router)
    v1.include_router(tenant_config_router)
    v1.include_router(bookings_router)
    v1.include_router(branding_router)
    v1.include_router(admin_router)
    v1.include_router(auth_router)
    v1.include_router(agent_router)
    v1.include_router(daily_overview_router)
    app.include_router(v1)
    return app


app = create_app()
