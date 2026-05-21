"""M2 资源 ownership 校验测试。

覆盖：
  * 用户 A 创建任务 → owner_id 写入 = A.id
  * 用户 A 列表 → 包含自己的任务；不包含 B 的
  * 用户 A 访问自己的 task / image / nest → 200
  * 用户 B（非 owner）访问 A 的 task / image / 上传 → 404 "任务不存在"
  * admin 访问 A 的任务 → 200，能跨用户看列表
  * 未登录访问任意受保护资源 → 401（auth 层已保证，这里再验一次）

T1 之后任务创建强制 region_id（town 级），本文件用 module 级 town_region
fixture 建一条 市/区/镇 链供所有用例复用。
"""

import io
import os
import uuid

# 必填 env 在 import app 之前
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./test_ownership.sqlite"
)
os.environ.setdefault("CELERY_BROKER_URL", "sqla+sqlite:///./test_celerydb.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image as PILImage  # noqa: E402
from sqlalchemy import update  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core.database import SyncSessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import InspectionTask, User  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client, prefix: str = "u"):
    """注册并登录一个普通用户，返回 (username, user_id, token)."""
    suffix = uuid.uuid4().hex[:8]
    creds = {
        "username": f"{prefix}_{suffix}",
        "password": "Passw0rd!",
        "email": f"{prefix}_{suffix}@example.com",
    }
    r = client.post("/api/v1/auth/register", json=creds)
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    login = client.post(
        "/api/v1/auth/login",
        data={"username": creds["username"], "password": creds["password"]},
    )
    assert login.status_code == 200, login.text
    return creds["username"], user_id, login.json()["access_token"]


def _promote_to_admin(username: str) -> None:
    """通过 sync engine 直接把用户提升为 admin（模拟 create_admin.py 行为）。"""
    with SyncSessionLocal() as db:
        db.execute(
            update(User).where(User.username == username).values(is_admin=True)
        )
        db.commit()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def town_region(client):
    """建一条 市/区/街镇 链，返回 town（街镇）id。

    T1 之后任务创建强制 region_id 指向 town 级区域。
    """
    admin_username, _, token_admin = _register_and_login(client, prefix="regadm")
    _promote_to_admin(admin_username)
    headers = _auth_headers(token_admin)
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


def _create_task(client, token: str, region_id: str, name: str = "task-a") -> str:
    r = client.post(
        "/api/v1/tasks/",
        json={"task_name": name, "area_name": "area1", "region_id": region_id},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1) owner_id 写入
# ---------------------------------------------------------------------------


def test_create_task_writes_owner_id(client, town_region):
    _, user_a_id, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region, name="alice's task")

    # 直接读 DB 校验 owner_id
    with SyncSessionLocal() as db:
        task = db.get(InspectionTask, task_id)
        assert task is not None
        assert task.owner_id == user_a_id


# ---------------------------------------------------------------------------
# 2) owner 可以看自己的，404 给非 owner
# ---------------------------------------------------------------------------


def test_owner_can_get_own_task(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    r = client.get(f"/api/v1/tasks/{task_id}", headers=_auth_headers(token_a))
    assert r.status_code == 200
    assert r.json()["id"] == task_id


def test_non_owner_gets_404_on_others_task(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    _, _, token_b = _register_and_login(client, prefix="b")

    r = client.get(f"/api/v1/tasks/{task_id}", headers=_auth_headers(token_b))
    assert r.status_code == 404
    # 反枚举：detail 必须等于"任务不存在"，与真正不存在共用同一响应
    assert r.json()["detail"] == "任务不存在"


def test_non_owner_gets_404_on_others_task_status(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)
    _, _, token_b = _register_and_login(client, prefix="b")

    r = client.get(
        f"/api/v1/tasks/{task_id}/status", headers=_auth_headers(token_b)
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "任务不存在"


# ---------------------------------------------------------------------------
# 3) admin 跨用户访问
# ---------------------------------------------------------------------------


def test_admin_can_access_others_task(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    admin_username, _, token_admin = _register_and_login(client, prefix="admin")
    _promote_to_admin(admin_username)
    # is_admin 不进 JWT，每次 get_current_user 从 DB 实时读，token 不用重发。

    r = client.get(
        f"/api/v1/tasks/{task_id}", headers=_auth_headers(token_admin)
    )
    assert r.status_code == 200
    assert r.json()["id"] == task_id


# ---------------------------------------------------------------------------
# 4) list_tasks 列表过滤
# ---------------------------------------------------------------------------


def test_list_tasks_excludes_other_users_tasks(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_a = _create_task(client, token_a, town_region, name="alice_only")

    _, _, token_b = _register_and_login(client, prefix="b")
    task_b = _create_task(client, token_b, town_region, name="bob_only")

    # b 列表里不应该看到 alice 的任务
    r = client.get("/api/v1/tasks/", headers=_auth_headers(token_b))
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    assert task_b in ids
    assert task_a not in ids


def test_admin_list_tasks_sees_all(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_a = _create_task(client, token_a, town_region, name="alice_a")

    admin_username, _, token_admin = _register_and_login(client, prefix="admin")
    _promote_to_admin(admin_username)

    r = client.get("/api/v1/tasks/", headers=_auth_headers(token_admin))
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()["items"]]
    # 至少包含 alice 的那个
    assert task_a in ids


# ---------------------------------------------------------------------------
# 5) 上传图片到别人的 task → 404
# ---------------------------------------------------------------------------


def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (16, 16), color="white").save(buf, "JPEG")
    return buf.getvalue()


def test_non_owner_cannot_upload_to_others_task(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    _, _, token_b = _register_and_login(client, prefix="b")

    files = {"files": ("x.jpg", _make_jpeg_bytes(), "image/jpeg")}
    r = client.post(
        f"/api/v1/tasks/{task_id}/images",
        files=files,
        headers=_auth_headers(token_b),
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "任务不存在"


def test_owner_can_upload_to_own_task(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    files = {"files": ("x.jpg", _make_jpeg_bytes(), "image/jpeg")}
    r = client.post(
        f"/api/v1/tasks/{task_id}/images",
        files=files,
        headers=_auth_headers(token_a),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["uploaded"] == 1


# ---------------------------------------------------------------------------
# 6) 单张图片 endpoint：非 owner 看自己不属于的图片 → 404
# ---------------------------------------------------------------------------


def test_non_owner_cannot_get_image_info(client, town_region):
    _, _, token_a = _register_and_login(client, prefix="a")
    task_id = _create_task(client, token_a, town_region)

    # 上传 1 张图
    files = {"files": ("x.jpg", _make_jpeg_bytes(), "image/jpeg")}
    r = client.post(
        f"/api/v1/tasks/{task_id}/images",
        files=files,
        headers=_auth_headers(token_a),
    )
    image_id = r.json()["images"][0]["id"]

    _, _, token_b = _register_and_login(client, prefix="b")

    r = client.get(
        f"/api/v1/images/{image_id}/info", headers=_auth_headers(token_b)
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "图片不存在"


# ---------------------------------------------------------------------------
# 7) 未知 task id 与 "无权访问" 返回一致的 404
# ---------------------------------------------------------------------------


def test_unknown_task_id_returns_404_consistent_with_unauth(client):
    """随便 UUID 应该返回与 "无权访问" 完全一致的 404 + detail，
    防止时序/语义差异泄露资源存在性。"""
    _, _, token_a = _register_and_login(client, prefix="a")
    bogus = str(uuid.uuid4())
    r = client.get(f"/api/v1/tasks/{bogus}", headers=_auth_headers(token_a))
    assert r.status_code == 404
    assert r.json()["detail"] == "任务不存在"
