import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from app.main import app
from app.core.database import Base, get_db
from app.core.config import get_settings

# 测试数据库
TEST_DATABASE_URL = "postgresql+asyncpg://nestuser:nestpass@localhost:5432/nestdb_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
async def setup_database():
    """设置测试数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class TestTaskAPI:
    """任务API测试"""

    def test_create_task(self):
        """测试创建任务"""
        response = client.post(
            "/api/v1/tasks/",
            data={
                "task_name": "测试任务",
                "area_name": "测试公园",
                "operator": "测试员",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "测试任务"
        assert "id" in data
        return data["id"]

    def test_get_task(self):
        """测试获取任务详情"""
        # 先创建任务
        create_response = client.post(
            "/api/v1/tasks/", data={"task_name": "查询测试任务"}
        )
        task_id = create_response.json()["id"]

        # 查询任务
        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_name"] == "查询测试任务"

    def test_list_tasks(self):
        """测试获取任务列表"""
        # 创建多个任务
        for i in range(3):
            client.post("/api/v1/tasks/", data={"task_name": f"任务{i}"})

        response = client.get("/api/v1/tasks/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 3

    def test_get_task_status(self):
        """测试获取任务状态"""
        create_response = client.post(
            "/api/v1/tasks/", data={"task_name": "状态测试任务"}
        )
        task_id = create_response.json()["id"]

        response = client.get(f"/api/v1/tasks/{task_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "uploading"
        assert "progress" in data

    def test_delete_task(self):
        """测试删除任务"""
        create_response = client.post(
            "/api/v1/tasks/", data={"task_name": "删除测试任务"}
        )
        task_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200

        # 确认已删除
        get_response = client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.status_code == 404


class TestImageAPI:
    """图片API测试"""

    def test_upload_images(self):
        """测试上传图片"""
        # 先创建任务
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "上传测试任务"}
        )
        task_id = task_response.json()["id"]

        # 准备测试图片数据(模拟)
        import io
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (100, 100), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        # 上传图片
        response = client.post(
            f"/api/v1/tasks/{task_id}/images",
            files={"files": ("test.jpg", img_bytes, "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["uploaded"] == 1
        assert len(data["images"]) == 1

    def test_list_task_images(self):
        """测试获取任务图片列表"""
        # 创建任务并上传图片
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "列表测试任务"}
        )
        task_id = task_response.json()["id"]

        response = client.get(f"/api/v1/tasks/{task_id}/images")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_image_detail(self):
        """测试获取图片详情"""
        # 创建任务并上传图片
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "图片详情测试任务"}
        )
        task_id = task_response.json()["id"]

        import io
        from PIL import Image as PILImage

        img = PILImage.new("RGB", (100, 100), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        upload_response = client.post(
            f"/api/v1/tasks/{task_id}/images",
            files={"files": ("test.jpg", img_bytes, "image/jpeg")},
        )

        image_id = upload_response.json()["images"][0]["id"]

        response = client.get(f"/api/v1/images/{image_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.jpg"
        assert data["task_id"] == task_id


class TestNestsAPI:
    """虫巢API测试"""

    def test_get_task_nests_empty(self):
        """测试获取空虫巢列表"""
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "虫巢测试任务"}
        )
        task_id = task_response.json()["id"]

        response = client.get(f"/api/v1/tasks/{task_id}/nests")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_nest_detail_not_found(self):
        """测试获取不存在的虫巢"""
        response = client.get(f"/api/v1/nests/{uuid4()}")
        assert response.status_code == 404

    def test_get_task_results_empty(self):
        """测试获取空结果"""
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "结果测试任务"}
        )
        task_id = task_response.json()["id"]

        response = client.get(f"/api/v1/tasks/{task_id}/results")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["image_stats"]["total_processed"] == 0
        assert data["nest_stats"]["total_unique"] == 0

    def test_get_task_statistics_empty(self):
        """测试获取空统计"""
        task_response = client.post(
            "/api/v1/tasks/", data={"task_name": "统计测试任务"}
        )
        task_id = task_response.json()["id"]

        response = client.get(f"/api/v1/tasks/{task_id}/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["image_statistics"]["total"] == 0
        assert data["detection_statistics"]["processed_images"] == 0


class TestHealthAPI:
    """健康检查API测试"""

    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "running"

    def test_health_check(self):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
