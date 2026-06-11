"""任务 / 图片 / 虫巢 / 健康检查 API 测试。

P0 给所有数据接口加了 JWT 鉴权、P1 加了 per-user ownership、T1 让任务创建
强制绑定 town 级区域，本文件按新体系维护：
  - SQLite 测试库（见 conftest.py）
  - 所有受保护接口通过 auth_headers fixture 带 Bearer token
  - 建任务需要合法 region_id —— 用 conftest 的 town_region_id fixture
  - ownership 隔离测试（A 用户看不到 B 用户的任务）

通用 fixture（client / auth_headers / second_auth_headers / admin_auth_headers
/ town_region_id）定义在 tests/conftest.py。
"""

import io
import os

from PIL import Image as PILImage


def _make_jpeg(color="red", size=(120, 120)):
    """生成一张内存里的合法小 JPEG，供上传测试用。"""
    buf = io.BytesIO()
    PILImage.new("RGB", size, color=color).save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _create_task(client, headers, region_id, **overrides):
    """创建一个任务并返回响应 JSON。

    region_id 必填——T1 后端强制任务归属到一个 town 级区域。
    """
    body = {
        "task_name": "测试任务",
        "area_name": "测试公园",
        "operator": "测试员",
        "region_id": region_id,
    }
    body.update(overrides)
    resp = client.post("/api/v1/tasks/", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestTaskAPI:
    """任务 API。"""

    def test_create_task(self, client, auth_headers, town_region_id):
        data = _create_task(
            client, auth_headers, town_region_id, task_name="创建测试"
        )
        assert data["task_name"] == "创建测试"
        assert data["status"] == "uploading"
        assert data["id"]
        # T1：返回带区域信息
        assert data["region_id"] == town_region_id
        assert data["region_path"]

    def test_create_task_with_plot_fields(
        self, client, auth_headers, town_region_id
    ):
        """T2 字段：地块面积 + 林业局小班号能正确写入并回显。"""
        data = _create_task(
            client,
            auth_headers,
            town_region_id,
            task_name="地块字段测试",
            plot_area_mu=12.5,
            forestry_sub_compartment="A-12-3",
        )
        assert data["plot_area_mu"] == 12.5
        assert data["forestry_sub_compartment"] == "A-12-3"

    def test_get_task(self, client, auth_headers, town_region_id):
        created = _create_task(
            client, auth_headers, town_region_id, task_name="查询测试"
        )
        resp = client.get(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_name"] == "查询测试"
        assert body["region_path"]

    def test_list_tasks(self, client, auth_headers, town_region_id):
        for i in range(3):
            _create_task(
                client, auth_headers, town_region_id, task_name=f"列表任务{i}"
            )
        resp = client.get("/api/v1/tasks/", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert len(body["items"]) >= 3

    def test_get_task_status(self, client, auth_headers, town_region_id):
        created = _create_task(
            client, auth_headers, town_region_id, task_name="状态测试"
        )
        resp = client.get(
            f"/api/v1/tasks/{created['id']}/status", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "uploading"
        assert "progress" in body

    def test_delete_task(self, client, auth_headers, town_region_id):
        created = _create_task(
            client, auth_headers, town_region_id, task_name="删除测试"
        )
        resp = client.delete(
            f"/api/v1/tasks/{created['id']}", headers=auth_headers
        )
        assert resp.status_code == 200
        gone = client.get(f"/api/v1/tasks/{created['id']}", headers=auth_headers)
        assert gone.status_code == 404


class TestTaskAuthAndOwnership:
    """鉴权 + per-user ownership 隔离。"""

    def test_create_without_token_401(self, client):
        resp = client.post("/api/v1/tasks/", json={"task_name": "无token"})
        assert resp.status_code == 401

    def test_list_without_token_401(self, client):
        assert client.get("/api/v1/tasks/").status_code == 401

    def test_other_user_cannot_read_task(
        self, client, auth_headers, second_auth_headers, town_region_id
    ):
        """A 创建的任务，B 读不到（404 防枚举）。"""
        created = _create_task(
            client, auth_headers, town_region_id, task_name="A的私有任务"
        )
        resp = client.get(
            f"/api/v1/tasks/{created['id']}", headers=second_auth_headers
        )
        assert resp.status_code == 404

    def test_other_user_cannot_delete_task(
        self, client, auth_headers, second_auth_headers, town_region_id
    ):
        created = _create_task(
            client, auth_headers, town_region_id, task_name="A的待删任务"
        )
        resp = client.delete(
            f"/api/v1/tasks/{created['id']}", headers=second_auth_headers
        )
        assert resp.status_code == 404
        still = client.get(
            f"/api/v1/tasks/{created['id']}", headers=auth_headers
        )
        assert still.status_code == 200


class TestImageAPI:
    """图片上传与查询。"""

    def test_upload_image(self, client, auth_headers, town_region_id):
        task = _create_task(
            client, auth_headers, town_region_id, task_name="上传测试"
        )
        resp = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={"files": ("test.jpg", _make_jpeg(), "image/jpeg")},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["uploaded"] == 1
        assert len(body["images"]) == 1

    def test_list_task_images(self, client, auth_headers, town_region_id):
        task = _create_task(
            client, auth_headers, town_region_id, task_name="图片列表测试"
        )
        upload = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files=[
                ("files", ("a.jpg", _make_jpeg(color="blue"), "image/jpeg")),
                ("files", ("b.jpg", _make_jpeg(color="green"), "image/jpeg")),
            ],
            headers=auth_headers,
        )
        assert upload.status_code == 200, upload.text
        resp = client.get(
            f"/api/v1/tasks/{task['id']}/images", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        filenames = {i["filename"] for i in body["items"]}
        assert {"a.jpg", "b.jpg"}.issubset(filenames)
        item = next(i for i in body["items"] if i["filename"] == "a.jpg")
        assert "latitude" in item
        assert "longitude" in item
        assert "altitude" in item
        assert "capture_time" in item
        assert "created_at" in item
        assert "detection" in item

    def test_get_image_info(self, client, auth_headers, town_region_id):
        """/images/{id}/info 返回 JSON 元数据（/images/{id} 返回的是文件）。"""
        task = _create_task(
            client, auth_headers, town_region_id, task_name="图片详情测试"
        )
        upload = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={"files": ("detail.jpg", _make_jpeg(), "image/jpeg")},
            headers=auth_headers,
        )
        image_id = upload.json()["images"][0]["id"]
        resp = client.get(
            f"/api/v1/images/{image_id}/info", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "detail.jpg"

    def test_upload_rejects_non_image(
        self, client, auth_headers, town_region_id
    ):
        """P0 上传校验：非图片后缀应被拒。"""
        task = _create_task(
            client, auth_headers, town_region_id, task_name="非法上传测试"
        )
        bad = io.BytesIO(b"this is not an image")
        resp = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={"files": ("evil.txt", bad, "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_image_negative_max_width_rejected(
        self, client, auth_headers, town_region_id
    ):
        """T3 图片压缩：max_width 负值应返回 400（防非法 resize 尺寸 -> 500）。"""
        task = _create_task(
            client, auth_headers, town_region_id, task_name="压缩负值测试"
        )
        upload = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={"files": ("nw.jpg", _make_jpeg(), "image/jpeg")},
            headers=auth_headers,
        )
        image_id = upload.json()["images"][0]["id"]
        for path in (
            f"/api/v1/images/{image_id}?max_width=-1",
            f"/api/v1/images/{image_id}/annotated?max_width=-5",
        ):
            assert client.get(path, headers=auth_headers).status_code == 400

    def test_image_default_and_original_both_ok(
        self, client, auth_headers, town_region_id
    ):
        """T3：默认（压缩）与 max_width=0（原图）都应正常返回图片。"""
        task = _create_task(
            client, auth_headers, town_region_id, task_name="压缩取图测试"
        )
        upload = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={"files": ("c.jpg", _make_jpeg(size=(2400, 1600)), "image/jpeg")},
            headers=auth_headers,
        )
        image_id = upload.json()["images"][0]["id"]
        r1 = client.get(f"/api/v1/images/{image_id}", headers=auth_headers)
        assert r1.status_code == 200
        assert r1.headers["content-type"].startswith("image/")
        r2 = client.get(
            f"/api/v1/images/{image_id}?max_width=0", headers=auth_headers
        )
        assert r2.status_code == 200
        assert r2.headers["content-type"].startswith("image/")

    def test_annotated_default_uses_cached_preview(
        self, client, auth_headers, town_region_id
    ):
        """默认标注图应缓存 1920 预览图，后续请求直接复用缓存文件。"""
        task = _create_task(
            client, auth_headers, town_region_id, task_name="标注缓存测试"
        )
        upload = client.post(
            f"/api/v1/tasks/{task['id']}/images",
            files={
                "files": (
                    "annotated.jpg",
                    _make_jpeg(size=(2400, 1600)),
                    "image/jpeg",
                )
            },
            headers=auth_headers,
        )
        image_id = upload.json()["images"][0]["id"]
        cache_path = f"./thumbnails/annotated_{image_id}_1920.jpg"
        try:
            os.remove(cache_path)
        except FileNotFoundError:
            pass

        first = client.get(
            f"/api/v1/images/{image_id}/annotated", headers=auth_headers
        )
        assert first.status_code == 200
        assert first.headers["content-type"].startswith("image/")
        assert os.path.exists(cache_path)

        cached_bytes = b"cached annotated preview"
        with open(cache_path, "wb") as f:
            f.write(cached_bytes)

        second = client.get(
            f"/api/v1/images/{image_id}/annotated", headers=auth_headers
        )
        assert second.status_code == 200
        assert second.content == cached_bytes

        original = client.get(
            f"/api/v1/images/{image_id}/annotated?max_width=0",
            headers=auth_headers,
        )
        assert original.status_code == 200
        assert original.content != cached_bytes

    def test_image_without_token_401(self, client):
        assert client.get("/api/v1/images/some-id/info").status_code == 401


class TestNestsAPI:
    """虫巢查询 / 结果 / 统计。"""

    def test_get_task_nests_empty(self, client, auth_headers, town_region_id):
        task = _create_task(
            client, auth_headers, town_region_id, task_name="虫巢空列表"
        )
        resp = client.get(
            f"/api/v1/tasks/{task['id']}/nests", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_get_nest_detail_not_found(self, client, auth_headers):
        import uuid

        resp = client.get(
            f"/api/v1/nests/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_get_task_results_empty(
        self, client, auth_headers, town_region_id
    ):
        task = _create_task(
            client, auth_headers, town_region_id, task_name="空结果"
        )
        resp = client.get(
            f"/api/v1/tasks/{task['id']}/results", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] == task["id"]

    def test_get_task_statistics_empty(
        self, client, auth_headers, town_region_id
    ):
        task = _create_task(
            client, auth_headers, town_region_id, task_name="空统计"
        )
        resp = client.get(
            f"/api/v1/tasks/{task['id']}/statistics", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["task_id"] == task["id"]

    def test_nests_without_token_401(self, client):
        assert client.get("/api/v1/tasks/some-id/nests").status_code == 401


class TestHealthAPI:
    """健康检查 / 根路径 —— 不需要鉴权。"""

    def test_root_open(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_health_open(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
