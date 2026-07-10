"""Auth + endpoint tests for POST /internal/invoicing/generate (Phase 15.3).

Mirrors test_tasks_worker.py's structure exactly, checking the new
sa-scheduler-invoker identity instead of sa-tasks-invoker.
"""
from unittest.mock import patch

WORKER_URL = "https://sport-slot-api-abc123-el.a.run.app"
INVOKER_SA = "sa-scheduler-invoker@sport-slot-dev.iam.gserviceaccount.com"
SCHEDULER_ENV = {
    "SPORTSLOT_WORKER_BASE_URL": WORKER_URL,
    "SPORTSLOT_SCHEDULER_INVOKER_SA": INVOKER_SA,
}
VALID_CLAIMS = {"email": INVOKER_SA, "email_verified": True}
VERIFY = "sport_slot.auth.scheduler_auth.id_token.verify_oauth2_token"
GENERATE = "sport_slot.api.internal.invoicing.generate_invoices"


async def test_generate_500_when_oidc_not_configured(make_client):
    # No SPORTSLOT_WORKER_BASE_URL / SPORTSLOT_SCHEDULER_INVOKER_SA set.
    async with make_client() as client:
        resp = await client.post("/internal/invoicing/generate")
    assert resp.status_code == 500
    assert resp.json()["code"] == "INTERNAL_ERROR"


async def test_generate_rejects_missing_bearer_token(make_client):
    async with make_client(SCHEDULER_ENV) as client:
        resp = await client.post("/internal/invoicing/generate")
    assert resp.status_code == 401
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_generate_rejects_invalid_oidc_token(make_client):
    with patch(VERIFY, side_effect=ValueError("bad signature")):
        async with make_client(SCHEDULER_ENV) as client:
            resp = await client.post(
                "/internal/invoicing/generate",
                headers={"Authorization": "Bearer not-a-real-token"},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_generate_rejects_wrong_caller_identity(make_client):
    """A valid OIDC token for the WRONG SA (e.g. sa-tasks-invoker) must be rejected —
    this is the whole reason sa-scheduler-invoker is a dedicated SA, not a reused one."""
    wrong_claims = {
        "email": "sa-tasks-invoker@sport-slot-dev.iam.gserviceaccount.com",
        "email_verified": True,
    }
    with patch(VERIFY, return_value=wrong_claims):
        async with make_client(SCHEDULER_ENV) as client:
            resp = await client.post(
                "/internal/invoicing/generate",
                headers={"Authorization": "Bearer token"},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_generate_rejects_unverified_email(make_client):
    unverified_claims = {"email": INVOKER_SA, "email_verified": False}
    with patch(VERIFY, return_value=unverified_claims):
        async with make_client(SCHEDULER_ENV) as client:
            resp = await client.post(
                "/internal/invoicing/generate",
                headers={"Authorization": "Bearer token"},
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TASK_UNAUTHORIZED"


async def test_generate_calls_service_and_returns_summary_for_valid_caller(make_client):
    canned_summary = {
        "period": "2026-06", "tenants_processed": 1,
        "households_invoiced": 2, "households_skipped": 0, "households_failed": [],
    }
    with patch(VERIFY, return_value=VALID_CLAIMS), \
         patch(GENERATE, return_value=canned_summary) as mock_generate:
        async with make_client(SCHEDULER_ENV) as client:
            resp = await client.post(
                "/internal/invoicing/generate",
                headers={"Authorization": "Bearer token"},
            )
    assert resp.status_code == 200
    assert resp.json() == canned_summary
    mock_generate.assert_called_once()
