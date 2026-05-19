"""管理员用户管理接口测试 (T8)"""

import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.sqlite")
os.environ.setdefault("CELERY_BROKER_URL", "sqla+sqlite:///./test_celerydb.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select as sync_select  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.main import app  # noqa: E402
from app.core.database import SyncSessionLocal  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register(client, creds: dict) -> dict:
    r = client.post("/api/v1/auth/register", json=creds)
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, username: str, password: str) -> str:
    r = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _promote_admin(user_id: str) -> None:
    with SyncSessionLocal() as db:
        result = db.execute(sync_select(User).where(User.id == user_id))
        user = result.scalar_one()
        user.is_admin = True
        db.commit()


def _fresh_creds(prefix: str = "u") -> dict:
    suffix = uuid.uuid4().hex[:8]
    return {"username": f"{prefix}_{suffix}", "password": "Pass1234!"}


@pytest.fixture()
def admin_token(client):
    creds = _fresh_creds("admin")
    user = _register(client, creds)
    _promote_admin(user["id"])
    return _login(client, creds["username"], creds["password"])


@pytest.fixture()
def user_token(client):
    creds = _fresh_creds("plain")
    _register(client, creds)
    return _login(client, creds["username"], creds["password"])


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── list users ────────────────────────────────────────────────────────────────

def test_list_users_admin_ok(client, admin_token):
    r = client.get("/api/v1/admin/users", headers=_auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["total"], int)


def test_list_users_non_admin_403(client, user_token):
    r = client.get("/api/v1/admin/users", headers=_auth(user_token))
    assert r.status_code == 403


def test_list_users_unauthenticated_401(client):
    r = client.get("/api/v1/admin/users")
    assert r.status_code == 401


# ── create user ───────────────────────────────────────────────────────────────

def test_create_user_by_admin(client, admin_token):
    creds = _fresh_creds("new")
    r = client.post("/api/v1/admin/users", json=creds, headers=_auth(admin_token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["username"] == creds["username"]
    assert body["is_active"] is True
    assert body["is_admin"] is False


def test_create_admin_user_by_admin(client, admin_token):
    creds = {**_fresh_creds("adminnew"), "is_admin": True}
    r = client.post("/api/v1/admin/users", json=creds, headers=_auth(admin_token))
    assert r.status_code == 201
    assert r.json()["is_admin"] is True


def test_create_user_duplicate_username_409(client, admin_token):
    creds = _fresh_creds("dup")
    _register(client, creds)
    r = client.post("/api/v1/admin/users", json=creds, headers=_auth(admin_token))
    assert r.status_code == 409


def test_create_user_non_admin_403(client, user_token):
    creds = _fresh_creds("blocked")
    r = client.post("/api/v1/admin/users", json=creds, headers=_auth(user_token))
    assert r.status_code == 403


# ── update user ───────────────────────────────────────────────────────────────

def test_update_user_disable(client, admin_token):
    creds = _fresh_creds("todisable")
    user = _register(client, creds)
    r = client.put(
        f"/api/v1/admin/users/{user['id']}",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_update_user_promote_to_admin(client, admin_token):
    creds = _fresh_creds("topromote")
    user = _register(client, creds)
    r = client.put(
        f"/api/v1/admin/users/{user['id']}",
        json={"is_admin": True},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_update_user_reset_password(client, admin_token):
    creds = _fresh_creds("pwdreset")
    user = _register(client, creds)
    new_password = "NewPass999!"
    r = client.put(
        f"/api/v1/admin/users/{user['id']}",
        json={"new_password": new_password},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        data={"username": creds["username"], "password": new_password},
    )
    assert login.status_code == 200


def test_update_user_not_found_404(client, admin_token):
    r = client.put(
        "/api/v1/admin/users/nonexistent-id-000",
        json={"is_active": False},
        headers=_auth(admin_token),
    )
    assert r.status_code == 404


def test_update_user_non_admin_403(client, user_token):
    r = client.put(
        "/api/v1/admin/users/any-id",
        json={"is_active": False},
        headers=_auth(user_token),
    )
    assert r.status_code == 403


# ── delete (soft) user ────────────────────────────────────────────────────────

def test_delete_user_soft(client, admin_token):
    creds = _fresh_creds("todelete")
    user = _register(client, creds)
    r = client.delete(
        f"/api/v1/admin/users/{user['id']}", headers=_auth(admin_token)
    )
    assert r.status_code == 204
    # Disabled user cannot log in
    login = client.post(
        "/api/v1/auth/login",
        data={"username": creds["username"], "password": creds["password"]},
    )
    assert login.status_code == 401


def test_delete_user_not_found_404(client, admin_token):
    r = client.delete(
        "/api/v1/admin/users/nonexistent-id-000", headers=_auth(admin_token)
    )
    assert r.status_code == 404


def test_delete_user_non_admin_403(client, user_token):
    creds = _fresh_creds("protecteduser")
    user = _register(client, creds)
    r = client.delete(
        f"/api/v1/admin/users/{user['id']}", headers=_auth(user_token)
    )
    assert r.status_code == 403
