"""共享 pytest fixtures（基于 SQLite，适配 P0 之后的鉴权体系）。

放在 tests/ 下，pytest 会在收集任何测试前先加载本文件，因此这里负责：
  1. 在 import app 之前把必填环境变量设好（SECRET_KEY / DATABASE_URL / ...）
  2. 提供 client / 用户注册登录 / 带 token 的 headers 等通用 fixture

test_auth.py 自带一份等价的 env 设置（早于本文件存在），两者用 setdefault
所以不会互相覆盖，最终都落到同一个 SQLite 测试库。
"""

import os
import uuid

# --- 必须在 import app 之前设置必填配置 ---
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.sqlite")
os.environ.setdefault("CELERY_BROKER_URL", "sqla+sqlite:///./test_celerydb.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402

# env 在 import app 前可能已被 lru_cache 缓存，清掉确保生效
get_settings.cache_clear()

from app.core.database import SyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _clean_test_db():
    """session 开始前清掉上一次残留的 SQLite 测试库。

    否则旧库里是过期 schema（少 owner_id / plot_area_mu 等列），
    init_db 的 create_all 不会 ALTER 已存在的表，测试就会 OperationalError。
    autouse + session 域保证它早于任何 client fixture 执行。
    """
    for fname in ("test_auth.sqlite", "test_celerydb.sqlite", "test_ci.sqlite"):
        try:
            os.remove(fname)
        except FileNotFoundError:
            pass
    yield


@pytest.fixture(scope="session")
def client():
    """会话级 TestClient。with 块触发 lifespan -> init_db 建表。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def unique_user():
    """每个测试一个独立用户名/邮箱，避免 409 冲突。"""
    suffix = uuid.uuid4().hex[:8]
    return {
        "username": f"user_{suffix}",
        "password": "Passw0rd!",
        "email": f"u_{suffix}@example.com",
    }


def register_and_login(client, user):
    """注册并登录 user，返回 access_token。"""
    r = client.post("/api/v1/auth/register", json=user)
    assert r.status_code == 201, r.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": user["username"], "password": user["password"]},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.fixture()
def auth_headers(client, unique_user):
    """注册+登录一个普通用户，返回带 Bearer token 的 headers dict。"""
    token = register_and_login(client, unique_user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def second_auth_headers(client):
    """再造一个独立用户（用于 ownership 隔离测试）。"""
    suffix = uuid.uuid4().hex[:8]
    user = {
        "username": f"other_{suffix}",
        "password": "Passw0rd!",
        "email": f"o_{suffix}@example.com",
    }
    token = register_and_login(client, user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_auth_headers(client):
    """注册一个用户、直接改 DB 提升为 admin、返回带 token 的 headers。

    token 在提升前签发也无妨：is_admin 不编码进 token，每次请求由
    get_current_user 重新查 DB，提升后立即生效。
    """
    suffix = uuid.uuid4().hex[:8]
    user = {
        "username": f"admin_{suffix}",
        "password": "Passw0rd!",
        "email": f"a_{suffix}@example.com",
    }
    token = register_and_login(client, user)
    with SyncSessionLocal() as db:
        u = db.execute(
            select(User).where(User.username == user["username"])
        ).scalar_one()
        u.is_admin = True
        db.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def town_region_id(client):
    """session 级：建一条完整 市/区/街镇 链，返回 town（街镇）id。

    T1 之后任务创建强制 region_id 指向 town 级区域，凡是要建任务的测试
    都需要一个合法 town id。session 域建一次复用，避免重复建树。
    """
    suffix = uuid.uuid4().hex[:8]
    user = {
        "username": f"regadmin_{suffix}",
        "password": "Passw0rd!",
        "email": f"ra_{suffix}@example.com",
    }
    token = register_and_login(client, user)
    with SyncSessionLocal() as db:
        u = db.execute(
            select(User).where(User.username == user["username"])
        ).scalar_one()
        u.is_admin = True
        db.commit()
    headers = {"Authorization": f"Bearer {token}"}

    sfx = uuid.uuid4().hex[:6]
    city = client.post(
        "/api/v1/regions/",
        json={"name": f"市{sfx}", "level": "city"},
        headers=headers,
    ).json()
    district = client.post(
        "/api/v1/regions/",
        json={"name": f"区{sfx}", "level": "district", "parent_id": city["id"]},
        headers=headers,
    ).json()
    town = client.post(
        "/api/v1/regions/",
        json={"name": f"镇{sfx}", "level": "town", "parent_id": district["id"]},
        headers=headers,
    ).json()
    return town["id"]
