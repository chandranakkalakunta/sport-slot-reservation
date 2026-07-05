from unittest.mock import MagicMock, patch

from sport_slot.dependencies import get_firestore_client

RESIDENT_CLAIMS = {
    "uid": "user-1",
    "role": "resident",
    "tenant_id": "t-1",
    "tenant_slug": "demo",
    "household_id": "h-9",
}
AUTH = {"authorization": "Bearer fake-token"}
HOST = {"host": "demo.slotsense.chandraailabs.com"}
VERIFY = "sport_slot.auth.dependency.fb_auth.verify_id_token"


def _client_with_profile(profile):
    client = MagicMock()
    doc = client.collection.return_value.document.return_value.collection.return_value
    doc = doc.document.return_value.get.return_value
    doc.exists = profile is not None
    doc.to_dict.return_value = profile
    return client


async def test_me_returns_profile(make_client):
    profile = {"uid": "user-1", "display_name": "Demo", "role": "resident"}
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _client_with_profile(profile)
            )
            resp = await client.get("/api/v1/users/me", headers={**AUTH, **HOST})
    assert resp.status_code == 200
    assert resp.json() == profile


async def test_me_404_when_unprovisioned(make_client):
    with patch(VERIFY, return_value=RESIDENT_CLAIMS):
        async with make_client() as client:
            client._transport.app.dependency_overrides[get_firestore_client] = (
                lambda: _client_with_profile(None)
            )
            resp = await client.get("/api/v1/users/me", headers={**AUTH, **HOST})
    assert resp.status_code == 404
    assert resp.json()["code"] == "USER_PROFILE_NOT_FOUND"


async def test_me_requires_auth(make_client):
    async with make_client() as client:
        resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_rate_limit_429_envelope(make_client):
    async with make_client({"SPORTSLOT_RATE_LIMIT": "2/minute"}) as client:
        r1 = await client.get("/api/v1/users/me")
        r2 = await client.get("/api/v1/users/me")
        r3 = await client.get("/api/v1/users/me")
    assert r1.status_code == 401 and r2.status_code == 401
    assert r3.status_code == 429
    assert r3.json()["code"] == "RATE_LIMITED"
    assert r3.json()["request_id"]
    assert "error" not in r3.json()


async def test_health_exempt_from_rate_limit(make_client):
    async with make_client({"SPORTSLOT_RATE_LIMIT": "2/minute"}) as client:
        codes = [(await client.get("/health")).status_code for _ in range(5)]
    assert codes == [200] * 5
