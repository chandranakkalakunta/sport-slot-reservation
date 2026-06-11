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
TENANT_HOST = {"host": "demo.sportbook.chandraailabs.com"}
OTHER_TENANT_HOST = {"host": "other.sportbook.chandraailabs.com"}
ADMIN_HOST = {"host": "admin.sportbook.chandraailabs.com"}

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


async def test_dev_override_allows_localhost_in_development(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:  # base_url host = testserver
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 200


async def test_dev_override_ignored_in_production_fail_closed(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client(
            {"SPORTSLOT_ENVIRONMENT": "production"}
        ) as client:
            resp = await client.get("/api/v1/_test/whoami", headers=AUTH)
    assert resp.status_code == 403
    assert resp.json()["code"] == "TENANT_MISMATCH"


async def test_platform_admin_on_admin_host_ok(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **ADMIN_HOST}
            )
    assert resp.status_code == 200
    assert resp.json()["role"] == "platform_admin"


async def test_platform_admin_on_tenant_host_403_no_bypass(make_client):
    with patch(VERIFY, return_value=ADMIN_CLAIMS):
        async with make_client() as client:
            resp = await client.get(
                "/api/v1/_test/whoami", headers={**AUTH, **TENANT_HOST}
            )
    assert resp.status_code == 403
    assert resp.json()["code"] == "TENANT_MISMATCH"


async def test_resident_token_on_admin_host_403(make_client):
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
