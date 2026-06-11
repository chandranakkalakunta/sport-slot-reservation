import firebase_admin
import structlog
from fastapi import APIRouter, FastAPI

from sport_slot.api.errors import register_exception_handlers
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

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(users_router)
    app.include_router(v1)
    return app


app = create_app()
