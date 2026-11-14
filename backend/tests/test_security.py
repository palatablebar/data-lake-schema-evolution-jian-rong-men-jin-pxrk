"""认证与权限工具单测。"""
from __future__ import annotations

from src.constants.roles import has_permission
from src.utils.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_roundtrip():
    hashed = hash_password("Demo@2026")
    assert hashed != "Demo@2026"
    assert verify_password("Demo@2026", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip():
    token, expires_in = create_access_token("admin@schemagate.io", "admin")
    assert expires_in > 0
    payload = decode_access_token(token)
    assert payload["sub"] == "admin@schemagate.io"
    assert payload["role"] == "admin"


def test_invalid_token():
    assert decode_access_token("not-a-token") is None


def test_role_permissions_are_monotonic():
    # admin ⊇ analyst ⊇ viewer；viewer 没有任何写权限
    assert has_permission("admin", "change:approve") is True
    assert has_permission("analyst", "change:approve") is False
    assert has_permission("analyst", "change:create") is True
    assert has_permission("viewer", "change:create") is False
    assert has_permission("viewer", "dataset:read") is True
    for permission in ("dataset:write", "change:create", "change:run", "change:approve", "export:read", "audit:read"):
        assert has_permission("viewer", permission) is False, permission
