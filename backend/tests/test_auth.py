from unittest.mock import patch

RESIDENT_CLAIMS = {
    "uid": "user-1",
    "role": "resident",
    "tenant_id": "t-1",
    "tenant_slug": "demo",
    "household_id": "h-9",
}
ADMIN_CLAIMS = {"uid": "admin-1", "role": "platform_admin"}

AUTH = {"authorization": "Bearer fake-token"}
TENANT_HOST = {"host": "demo.slotsense.chandraailabs.com"}
OTHER_TENANT_HOST = {"host": "other.slotsense.chandraailabs.com"}
ADMIN_HOST = {"host": "admin.slotsense.chandraailabs.com"}
RVRG_SUBDOMAIN_HOST = {"host": "rvrg.slotsense.chandraailabs.com"}

RVRG_CLAIMS = {
    "uid": "user-2",
    "role": "resident",
    "tenant_id": "t-2",
    "tenant_slug": "rvrg",
    "household_id": "h-7",
}

XFH_TENANT_HOST = {"x-forwarded-host": "demo.slotsense.chandraailabs.com"}
XFH_OTHER_HOST = {"x-forwarded-host": "other.slotsense.chandraailabs.com"}
XFH_WEBAPP_HOST = {"x-forwarded-host": "sport-slot-dev.web.app"}
RUN_APP_HOST = {"host": "sport-slot-api-xxx.run.app"}

VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"


async def test_missing_token_401(make_client):
    async with make_client() as client:
        resp = await client.get("/api/v1/_test/whoami")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_MISSING_TOKEN"


async def test_invalid_token_401(make_client):
    with patch(VERIFY, side_effect=ValueError("bad token")):
        async with make_client() as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_TOKEN"


async def test_valid_token_on_matching_subdomain(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **TENANT_HOST}
            )
    assert resp.status_code == 200
    assert resp.json() == {"uid": "user-1", "tenant_slug": "demo", "role": "resident"}


async def test_subdomain_mismatch_403(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **OTHER_TENANT_HOST}
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TENANT_MISMATCH"


async def test_localhost_no_host_header_trusts_jwt(make_client):
    # testserver host does not match any tenant subdomain → _slug_from_host
    # returns None → JWT tenant_slug is authoritative (ADR-0012 §2). No dev
    # pin exists after 5.3.1; behavior is identical but reason changed.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:  # base_url host = testserver
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200


async def test_unrecognized_host_in_production_trusts_jwt(make_client):
    # ADR-0012 §2: slug=None (testserver is not a tenant subdomain) → JWT wins.
    # Dev override is inactive in production; host check falls back to JWT.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client(
            {"SPORTSLOT_ENVIRONMENT": "production"}
        ) as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200


async def test_platform_admin_on_admin_host_ok(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **ADMIN_HOST}
            )
    assert resp.status_code == 200
    assert resp.json()["role"] == "platform_admin"


async def test_platform_admin_on_any_host_allowed_adr0014(make_client):
    # ADR-0014 §1: host-segregation deferred to Phase 9. Platform-admin token
    # is accepted on ANY host in DEV; require_platform_admin does route-level
    # authorization. Intentional behavioral change from 5.2.1 — previous test
    # asserted 403 TENANT_MISMATCH on non-admin hosts; that gate is removed.
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **TENANT_HOST}
            )
    assert resp.status_code == 200
    assert resp.json()["role"] == "platform_admin"


async def test_platform_admin_on_localhost_allowed_regression_5221(make_client):
    # Regression guard for phase 5.2.1: superadmin token on localhost (default
    # testserver host — no host header) must not be rejected. This was the
    # primary developer breakage fixed by ADR-0014 §1 relaxation.
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["role"] == "platform_admin"


async def test_resident_token_on_admin_host_403(make_client):
    # Still 403 — but now via the tenant cross-check (slug "admin" from
    # admin.slotsense.chandraailabs.com mismatches JWT tenant_slug "demo"),
    # not the removed admin-host gate.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **ADMIN_HOST}
            )
    assert resp.status_code == 403


async def test_token_missing_claims_401(make_client):
    with patch(VERIFY, return_value={"uid": "user-2", "role": "resident"}):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **TENANT_HOST}
            )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_TOKEN"


# ── Phase 5.3.1 regression guards (dev-tenant pin removed) ────────────────


async def test_rvrg_tenant_on_localhost_allowed_regression_5311(make_client):
    # Before 5.3.1: _slug_from_host returned dev_tenant_slug ("demo") for
    # localhost, so a token with tenant_slug="rvrg" got 403 TENANT_MISMATCH.
    # After fix: localhost is unrecognized → slug=None → JWT wins → 200.
    with patch(VERIFY, return_value=RVRG_CLAIMS):
        async with make_client() as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["tenant_slug"] == "rvrg"


async def test_demo_tenant_on_localhost_still_allowed(make_client):
    # The "default" tenant (demo) was never broken; ensure it stays 200 after
    # the pin removal — JWT trust works for all tenants on localhost.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["tenant_slug"] == "demo"


async def test_rvrg_subdomain_with_demo_claim_still_403(make_client):
    # Tenant enforcement is still intact: rvrg.sportbook... with a "demo" JWT
    # claim must still 403. The pin removal must not weaken subdomain gating.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **RVRG_SUBDOMAIN_HOST}
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TENANT_MISMATCH"


# ── X-Forwarded-Host tests (ADR-0012 §2) ──────────────────────────────────


async def test_xfh_matching_tenant_subdomain_allowed(make_client):
    # X-Forwarded-Host set by Hosting rewrite to real subdomain that matches claim.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **XFH_TENANT_HOST}
            )
    assert resp.status_code == 200
    assert resp.json()["tenant_slug"] == "demo"


async def test_xfh_mismatching_tenant_subdomain_403(make_client):
    # X-Forwarded-Host resolves to a different tenant subdomain → enforce mismatch.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **XFH_OTHER_HOST}
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TENANT_MISMATCH"


async def test_bare_webapp_host_trusts_jwt_claim(make_client):
    # sport-slot-dev.web.app does not match base_domain → slug=None → JWT wins.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **XFH_WEBAPP_HOST}
            )
    assert resp.status_code == 200
    assert resp.json()["tenant_slug"] == "demo"


async def test_xfh_takes_precedence_over_host_header(make_client):
    # Host=run.app (slug=None), X-Forwarded-Host=tenant subdomain (slug=demo).
    # _effective_host must prefer XFH; if it reads Host instead this would pass
    # via the None fallback — but we verify the slug was actually enforced.
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami",
                headers={**AUTH, **RUN_APP_HOST, **XFH_TENANT_HOST},
            )
    assert resp.status_code == 200
    assert resp.json()["tenant_slug"] == "demo"
