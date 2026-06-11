from unittest.mock import patch

import sport_slot.health as health


async def test_healthz_ok(make_client):
    async with make_client() as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ok_when_firestore_reachable(make_client):
    with patch.object(health, "_firestore_ping", return_value=None):
        async with make_client() as client:
            resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}


async def test_readyz_503_when_firestore_down(make_client):
    with patch.object(health, "_firestore_ping", side_effect=RuntimeError("boom")):
        async with make_client() as client:
            resp = await client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "NOT_READY"
    assert body["request_id"]
    assert body["timestamp"]


async def test_request_id_header_on_every_response(make_client):
    async with make_client() as client:
        r1 = await client.get("/healthz")
        r2 = await client.get("/healthz")
    assert r1.headers["x-request-id"]
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


async def test_404_uses_error_envelope(make_client):
    async with make_client() as client:
        resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert body["request_id"] == resp.headers["x-request-id"]
