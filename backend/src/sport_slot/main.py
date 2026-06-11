import firebase_admin
import structlog
from fastapi import APIRouter, FastAPI

from sport_slot.api.errors import register_exception_handlers
from sport_slot.config import get_settings
from sport_slot.health import router as health_router
from sport_slot.logging import configure_logging
from sport_slot.middleware.request_id import RequestIdMiddleware

log = structlog.get_logger()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    # Fail closed: if ADC is absent, verification errors surface as 401s.
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
    except Exception:
        log.warning("firebase_admin_not_initialized", hint="auth will fail until ADC exists")

    app = FastAPI(title="SportSlotReservation API", version="0.2.0")
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router)

    v1 = APIRouter(prefix="/api/v1")
    app.include_router(v1)
    return app


app = create_app()
