from unittest.mock import MagicMock

import pytest

from sport_slot.auth.context import TenantContext
from sport_slot.repositories.base import (
    PlatformRepository,
    TenantRepository,
    _decode_cursor,
    _encode_cursor,
)
from sport_slot.repositories.user_profiles import UserProfileRepository

RESIDENT = TenantContext(
    uid="u1", tenant_id="t1", tenant_slug="demo", role="resident", household_id="h1"
)
ADMIN = TenantContext(
    uid="a1", tenant_id=None, tenant_slug=None, role="platform_admin"
)


class _TenantsRepo(PlatformRepository):
    collection_name = "tenants"


def test_tenant_repo_rejects_context_without_tenant():
    with pytest.raises(ValueError):
        UserProfileRepository(ADMIN, MagicMock())


def test_tenant_repo_rejects_missing_collection_name():
    with pytest.raises(ValueError):
        TenantRepository(RESIDENT, MagicMock())


def test_collection_path_is_tenant_scoped():
    client = MagicMock()
    repo = UserProfileRepository(RESIDENT, client)
    _ = repo._collection
    client.collection.assert_called_once_with("tenants")
    client.collection.return_value.document.assert_called_once_with("t1")
    client.collection.return_value.document.return_value.collection.assert_called_once_with(
        "users"
    )


def test_get_returns_none_when_absent():
    client = MagicMock()
    snap = client.collection.return_value.document.return_value.collection.return_value
    snap = snap.document.return_value.get.return_value
    snap.exists = False
    repo = UserProfileRepository(RESIDENT, client)
    assert repo.get("nope") is None


def test_get_returns_dict_when_present():
    client = MagicMock()
    doc = client.collection.return_value.document.return_value.collection.return_value
    doc = doc.document.return_value.get.return_value
    doc.exists = True
    doc.to_dict.return_value = {"uid": "u1"}
    repo = UserProfileRepository(RESIDENT, client)
    assert repo.get("u1") == {"uid": "u1"}


def _snap(doc_id):
    s = MagicMock()
    s.id = doc_id
    s.to_dict.return_value = {"id": doc_id}
    return s


def test_list_no_more_pages():
    client = MagicMock()
    col = client.collection.return_value.document.return_value.collection.return_value
    col.order_by.return_value.limit.return_value.stream.return_value = [
        _snap("a"), _snap("b")
    ]
    repo = UserProfileRepository(RESIDENT, client)
    items, cursor = repo.list(limit=5)
    assert [i["id"] for i in items] == ["a", "b"]
    assert cursor is None


def test_list_has_more_returns_cursor():
    client = MagicMock()
    col = client.collection.return_value.document.return_value.collection.return_value
    col.order_by.return_value.limit.return_value.stream.return_value = [
        _snap("a"), _snap("b"), _snap("c")
    ]
    repo = UserProfileRepository(RESIDENT, client)
    items, cursor = repo.list(limit=2)
    assert [i["id"] for i in items] == ["a", "b"]
    assert cursor == _encode_cursor("b")
    assert _decode_cursor(cursor) == "b"


def test_platform_repo_rejects_non_admin():
    with pytest.raises(PermissionError):
        _TenantsRepo(RESIDENT, MagicMock())


def test_platform_repo_accepts_admin():
    repo = _TenantsRepo(ADMIN, MagicMock())
    assert repo._ctx.uid == "a1"
