"""认证相关接口测试 (基于 SQLite)"""

import os
import uuid

# 测试前必须设置必填配置，且要在 import app 之前
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402

# 清理 lru_cache，确保 env 生效
get_settings.cache_clear()

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """模块级别的 TestClient（生命周期会触发 init_db）"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def unique_user():
    """每个测试一个独立的用户名/邮箱，避免冲突"""
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"user_{suffix}",
        "password": "Passw0rd!",
        "email": f"u_{suffix}@example.com",
    }


def test_register_success(client, unique_user):
    resp = client.post("/api/v1/auth/register", json=unique_user)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == unique_user["username"]
    assert body["email"] == unique_user["email"]
    assert body["is_active"] is True
    assert "id" in body


def test_register_duplicate_username_returns_409(client, unique_user):
    r1 = client.post("/api/v1/auth/register", json=unique_user)
    assert r1.status_code == 201

    # 再次用同名注册
    dup = dict(unique_user)
    dup["email"] = f"other_{uuid.uuid4().hex[:6]}@example.com"
    r2 = client.post("/api/v1/auth/register", json=dup)
    assert r2.status_code == 409


def test_login_success_returns_token(client, unique_user):
    r = client.post("/api/v1/auth/register", json=unique_user)
    assert r.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": unique_user["username"],
            "password": unique_user["password"],
        },
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_returns_401(client, unique_user):
    client.post("/api/v1/auth/register", json=unique_user)
    login = client.post(
        "/api/v1/auth/login",
        data={"username": unique_user["username"], "password": "wrongpass"},
    )
    assert login.status_code == 401


def test_protected_endpoint_without_token_returns_401(client):
    r = client.get("/api/v1/tasks/")
    assert r.status_code == 401


def test_me_with_token(client, unique_user):
    client.post("/api/v1/auth/register", json=unique_user)
    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": unique_user["username"],
            "password": unique_user["password"],
        },
    )
    token = login.json()["access_token"]
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == unique_user["username"]


def test_health_still_open(client):
    """健康检查不应该需要鉴权"""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def _register_and_login(client, user):
    r = client.post("/api/v1/auth/register", json=user)
    assert r.status_code == 201, r.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user["username"], "password": user["password"]},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_change_password_success_then_login_with_new(client, unique_user):
    """改密成功后：新密码可登录，旧密码 401"""
    token = _register_and_login(client, unique_user)

    new_password = "NewPassw0rd!"
    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": unique_user["password"], "new_password": new_password},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    # 旧密码登录失败
    old_login = client.post(
        "/api/v1/auth/login",
        data={"username": unique_user["username"], "password": unique_user["password"]},
    )
    assert old_login.status_code == 401

    # 新密码登录成功
    new_login = client.post(
        "/api/v1/auth/login",
        data={"username": unique_user["username"], "password": new_password},
    )
    assert new_login.status_code == 200, new_login.text
    assert new_login.json()["access_token"]


def test_change_password_wrong_old_returns_401(client, unique_user):
    """原密码不匹配应该返回 401，且密码不被修改"""
    token = _register_and_login(client, unique_user)

    r = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "definitely-wrong", "new_password": "AnotherPwd1!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401

    # 原密码仍然可登录（没被改）
    login = client.post(
        "/api/v1/auth/login",
        data={"username": unique_user["username"], "password": unique_user["password"]},
    )
    assert login.status_code == 200
