"""Cloud Scheduler worker endpoint for monthly invoice generation (Phase 15.3).

Not part of the tenant-facing API surface (no Firebase JWT / TenantContext
here) — authenticated solely via Cloud Scheduler OIDC (see
auth/scheduler_auth.py). Kept separate from api/internal/tasks.py, which
is notification-specific — a different internal-trigger domain.
"""

from fastapi import APIRouter, Depends

from sport_slot.auth.scheduler_auth import verify_scheduler_oidc
from sport_slot.dependencies import get_firestore_client
from sport_slot.ratelimit import limiter
from sport_slot.services.invoicing import generate_invoices

router = APIRouter(prefix="/internal/invoicing", tags=["internal"])


@router.post("/generate", dependencies=[Depends(verify_scheduler_oidc)])
@limiter.exempt
async def generate(client=Depends(get_firestore_client)):
    return generate_invoices(client)
