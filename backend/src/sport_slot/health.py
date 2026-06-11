from fastapi import APIRouter
from google.cloud import firestore

from sport_slot.api import error_codes
from sport_slot.api.errors import ApiError
from sport_slot.config import get_settings
from sport_slot.ratelimit import limiter

router = APIRouter()


@router.get("/healthz")
@limiter.exempt
async def healthz():
    """Liveness: process is up. No dependency calls (ADR-0006 Decision 4)."""
    return {"status": "ok"}


def _firestore_ping() -> None:
    settings = get_settings()
    client = firestore.Client(project=settings.gcp_project)
    client.collection("_health").limit(1).get(timeout=5)


@router.get("/readyz")
@limiter.exempt
async def readyz():
    """Readiness: verifies Firestore reachability (ADR-0006 Decision 4)."""
    try:
        _firestore_ping()
    except Exception as exc:
        raise ApiError(503, error_codes.NOT_READY, "Firestore unreachable") from exc
    return {"status": "ready"}
