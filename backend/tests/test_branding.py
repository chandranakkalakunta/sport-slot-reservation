from unittest.mock import MagicMock

from sport_slot.dependencies import get_firestore_client

BRANDING = {
    "brand_name": "Demo Society",
    "brand_primary_color": "#0f7b6c",
    "brand_secondary_color": "#1a4d8f",
}


def _client_with_doc(data: dict | None):
    doc_mock = MagicMock()
    doc_mock.to_dict.return_value = data
    client_mock = MagicMock()
    stream = [doc_mock] if data is not None else []
    (client_mock.collection.return_value
     .where.return_value.limit.return_value.stream.return_value) = stream
    return client_mock


async def test_branding_returns_colors(make_client):
    tenant_data = {"name": "Demo Society", "slug": "demo", "branding": BRANDING}
    async with make_client() as client:
        client._transport.app.dependency_overrides[get_firestore_client] = (
            lambda: _client_with_doc(tenant_data)
        )
        resp = await client.get("/api/v1/tenants/demo/branding")
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_primary_color"] == "#0f7b6c"
    assert data["brand_secondary_color"] == "#1a4d8f"
    assert data["slug"] == "demo"


async def test_branding_unknown_slug_404(make_client):
    async with make_client() as client:
        client._transport.app.dependency_overrides[get_firestore_client] = (
            lambda: _client_with_doc(None)
        )
        resp = await client.get("/api/v1/tenants/nonexistent/branding")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


async def test_branding_no_auth_required(make_client):
    # Endpoint is public — must succeed without Authorization header.
    tenant_data = {"name": "Demo Society", "slug": "demo", "branding": BRANDING}
    async with make_client() as client:
        client._transport.app.dependency_overrides[get_firestore_client] = (
            lambda: _client_with_doc(tenant_data)
        )
        resp = await client.get("/api/v1/tenants/demo/branding")  # no auth header
    assert resp.status_code == 200


async def test_branding_defaults_when_no_branding_field(make_client):
    # Tenant exists but has no branding subdoc → falls back to defaults.
    tenant_data = {"name": "Plain Tenant", "slug": "plain"}
    async with make_client() as client:
        client._transport.app.dependency_overrides[get_firestore_client] = (
            lambda: _client_with_doc(tenant_data)
        )
        resp = await client.get("/api/v1/tenants/plain/branding")
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_name"] == "Plain Tenant"  # falls back to tenant name
    assert data["brand_primary_color"] == "#1a4d8f"  # default
