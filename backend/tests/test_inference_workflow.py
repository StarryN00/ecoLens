"""P1 #6/#7/#8/#9 重构相关测试。

覆盖：
  * _to_sync_url 转换正确性（sqlite / postgresql / 已经 sync 的）
  * Celery chord 编排：trigger_processing_sync 是否用 chord(group(...))
    + process_task_deduplication.s(task_id) 起的（M1：从 .si 改为 .s，
    把 header 结果列表传给 callback）
  * worker_process_init 信号上是否挂了预热回调
  * 端到端冒烟（SQLite）：process_image_sync 在模型返回空 detections 时
    不写 raw_nest_detections，写入 image_detections，processed_images +1
  * M1：callback 看到 header results 含 failed 项时把 task 标记为 failed
"""

import os
import uuid

# 必填 env 必须在 import app 之前
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./test_inference_workflow.sqlite"
)
os.environ.setdefault("CELERY_BROKER_URL", "sqla+sqlite:///./test_celerydb.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

import pytest  # noqa: E402
from PIL import Image as PILImage  # noqa: E402

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core.database import (  # noqa: E402
    Base,
    SyncSessionLocal,
    _to_sync_url,
    sync_engine,
)
from app.models import (  # noqa: E402
    Image,
    ImageDetection,
    InspectionTask,
    RawNestDetection,
    User,
)


def _ensure_owner(db) -> str:
    """确保 sync DB 里有一个 admin 用户，返回其 id。

    M2 ownership 加固后，InspectionTask.owner_id 是 NOT NULL；这些
    测试 fixture 用 sync engine 直接 insert，不走 API，因此需要在
    插入 task 之前先准备一个用户行。"""
    user = db.query(User).filter_by(username="_test_owner").one_or_none()
    if user is None:
        user = User(
            username="_test_owner",
            hashed_password="x",
            is_active=True,
            is_admin=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id


# ---------------------------------------------------------------------------
# #8: URL converter
# ---------------------------------------------------------------------------
class TestSyncUrlConverter:
    def test_sqlite_aiosqlite_to_sync(self):
        assert (
            _to_sync_url("sqlite+aiosqlite:///./nestdb.sqlite")
            == "sqlite:///./nestdb.sqlite"
        )

    def test_sqlite_already_sync(self):
        assert _to_sync_url("sqlite:///./already.sqlite") == "sqlite:///./already.sqlite"

    def test_postgresql_asyncpg_to_psycopg2(self):
        assert (
            _to_sync_url("postgresql+asyncpg://u:p@h:5432/db")
            == "postgresql+psycopg2://u:p@h:5432/db"
        )

    def test_postgresql_bare_to_psycopg2(self):
        # 默认 sync 驱动也强制写成 psycopg2，避免在 sync_engine 上隐式走
        # 别的驱动；asyncpg 不能跑 sync。
        assert (
            _to_sync_url("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
        )

    def test_unknown_dialect_passthrough(self):
        # 未识别的方言保持原样，让 SQLAlchemy 自行报错
        assert _to_sync_url("mysql+aiomysql://u:p@h/db") == "mysql+aiomysql://u:p@h/db"

    def test_empty_string(self):
        assert _to_sync_url("") == ""


# ---------------------------------------------------------------------------
# #7: Celery chord 编排
# ---------------------------------------------------------------------------
class TestChordOrchestration:
    def test_trigger_uses_chord_with_s_callback(self, tmp_path, monkeypatch):
        """trigger_processing_sync 应该用 chord(group(...))(callback.s(task_id))
        启动一组 process_image_task。

        M1 之后改用 .s(task_id) 而非 .si(task_id)，目的是把 header
        的返回值列表透传给 callback，让 callback 能感知失败。
        """
        # 准备：往 sync DB 里插一个 task + 3 张图
        Base.metadata.create_all(sync_engine)
        task_id = str(uuid.uuid4())
        image_ids = [str(uuid.uuid4()) for _ in range(3)]
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="t",
                    total_images=3,
                    owner_id=owner_id,
                )
            )
            for img_id in image_ids:
                db.add(
                    Image(
                        id=img_id,
                        task_id=task_id,
                        filename="x.jpg",
                        storage_path="/dev/null",
                    )
                )
            db.commit()

        from app.tasks import inference_tasks as it

        captured = {}

        # 注意：fake_s 既会被绑到 process_image_task.s（header），
        # 也会被绑到 process_task_deduplication.s（callback）。
        # 通过 captured 标记区分。
        def fake_image_s(self_or_task_id, *args):
            captured.setdefault("header_s_calls", []).append(
                (self_or_task_id, args)
            )
            return ("HEADER_S", self_or_task_id, args)

        def fake_callback_s(task_id):
            captured["callback_s"] = task_id
            return ("CALLBACK_S", task_id)

        def fake_chord(header):
            captured["chord_header"] = list(header)

            def _apply(callback):
                captured["chord_callback"] = callback

            return _apply

        # group 透传 header iter
        monkeypatch.setattr(it.process_image_task, "s", fake_image_s)
        monkeypatch.setattr(it.process_task_deduplication, "s", fake_callback_s)
        monkeypatch.setattr(it, "chord", fake_chord)
        monkeypatch.setattr(it, "group", lambda gen: list(gen))

        result = it.trigger_processing_sync(task_id, image_ids=image_ids)

        assert result["status"] == "triggered"
        assert result["images"] == 3

        # 3 张图 -> 3 个 process_image_task.s 调用
        assert len(captured["header_s_calls"]) == 3
        for (passed_task, passed_args), expected_img in zip(
            captured["header_s_calls"], image_ids, strict=True
        ):
            assert passed_task == task_id
            assert passed_args == (expected_img,)

        # callback 现在用 .s(task_id)
        assert captured["callback_s"] == task_id
        assert captured["chord_callback"] == ("CALLBACK_S", task_id)

        # chord header 由 fake_chord 接收并被 fake_group 物化为 list
        assert len(captured["chord_header"]) == 3

    def test_trigger_with_no_images_falls_back_to_direct_dedup(self, monkeypatch):
        """没有任何图片时不应该起 chord，应该直接 delay 去重收尾。"""
        Base.metadata.create_all(sync_engine)
        task_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="t",
                    total_images=0,
                    owner_id=owner_id,
                )
            )
            db.commit()

        from app.tasks import inference_tasks as it

        captured = {}

        class _FakeAsync:
            def delay(self, tid):
                captured["delay"] = tid

        monkeypatch.setattr(it, "process_task_deduplication", _FakeAsync())
        # chord 不应被调用
        monkeypatch.setattr(
            it, "chord", lambda *a, **kw: pytest.fail("chord should not be called")
        )

        result = it.trigger_processing_sync(task_id, image_ids=[])
        assert result["images"] == 0
        assert captured["delay"] == task_id


# ---------------------------------------------------------------------------
# M1: chord callback 透传 header 失败 → 任务状态置 failed
# ---------------------------------------------------------------------------
class TestCallbackHandlesHeaderFailures:
    """process_task_deduplication 现在接收 header 结果列表。
    任何一项是 {"status": "failed", ...} 就把 task 标 failed，
    不再卡在 'processing'。"""

    def test_callback_marks_task_failed_when_any_image_failed(self):
        from app.tasks import inference_tasks as it

        Base.metadata.create_all(sync_engine)
        task_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="m1-failed",
                    total_images=2,
                    processed_images=2,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.commit()

        results = [
            {"status": "failed", "task_id": task_id, "image_id": "x", "error": "boom"},
            {"status": "success", "task_id": task_id, "image_id": "y"},
        ]

        out = it.process_task_deduplication(results, task_id)
        assert out["status"] == "failed"
        assert out["failed_count"] == 1
        assert out["total"] == 2

        with SyncSessionLocal() as db:
            task = db.query(InspectionTask).filter_by(id=task_id).one()
        assert task.status == "failed"

    def test_callback_runs_dedup_when_all_success(self, monkeypatch):
        """所有 header 都成功时，callback 应该走正常去重路径。"""
        from app.tasks import inference_tasks as it

        Base.metadata.create_all(sync_engine)
        task_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="m1-success",
                    total_images=1,
                    processed_images=1,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.commit()

        # 用 stub 替掉真正的去重，避免依赖空 raw_nest_detections 的行为
        called = {}

        def fake_dedup(tid):
            called["task_id"] = tid
            return {"status": "success", "task_id": tid, "unique_nests": 0}

        monkeypatch.setattr(it, "deduplicate_task_sync", fake_dedup)

        results = [{"status": "success", "task_id": task_id, "image_id": "a"}]
        out = it.process_task_deduplication(results, task_id)
        assert out["status"] == "success"
        assert called["task_id"] == task_id

    def test_callback_backwards_compat_with_delay_no_images(self, monkeypatch):
        """trigger_processing_sync 在没有任何图片时 .delay(task_id) 直接
        触发去重收尾——此时 Celery 把 task_id 作为第一个位置参数传入，
        即 results=task_id, task_id=None。callback 必须兼容。"""
        from app.tasks import inference_tasks as it

        Base.metadata.create_all(sync_engine)
        task_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="m1-no-images",
                    total_images=0,
                    processed_images=0,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.commit()

        called = {}

        def fake_dedup(tid):
            called["task_id"] = tid
            return {"status": "success", "task_id": tid, "unique_nests": 0}

        monkeypatch.setattr(it, "deduplicate_task_sync", fake_dedup)

        # 模拟 .delay(task_id) 直接调用，Celery 把它当成
        # process_task_deduplication(task_id) -> results=task_id, task_id=None
        out = it.process_task_deduplication(task_id)
        assert out["status"] == "success"
        assert called["task_id"] == task_id


# ---------------------------------------------------------------------------
# #9: worker_process_init 信号声明
# ---------------------------------------------------------------------------
class TestWorkerProcessInitSignal:
    def test_warmup_is_registered(self):
        """_warmup_models 必须挂在 worker_process_init 上。"""
        from celery.signals import worker_process_init

        # 触发模块导入以保证 @worker_process_init.connect 跑过
        from app.tasks.inference_tasks import _warmup_models  # noqa: F401

        # celery 的 Signal.receivers 是 [((rid, sid), weakref|callable), ...]
        resolved = []
        for _key, ref in worker_process_init.receivers:
            target = ref() if callable(ref) else ref
            if target is not None:
                resolved.append(target)
        assert _warmup_models in resolved, (
            f"_warmup_models 未注册到 worker_process_init，"
            f"当前 receivers={resolved}"
        )

    def test_lazy_fallback_when_globals_none(self, monkeypatch):
        """pytest 不会触发 worker_process_init，_get_xxx 在全局是 None 时
        必须就地实例化。"""
        from app.tasks import inference_tasks as it

        monkeypatch.setattr(it, "_nest_detector", None)
        monkeypatch.setattr(it, "_tree_classifier", None)

        d = it._get_nest_detector()
        c = it._get_tree_classifier()
        assert d is not None
        assert c is not None


# ---------------------------------------------------------------------------
# 端到端冒烟：process_image_sync 不依赖真实模型 / Redis
# ---------------------------------------------------------------------------
class TestProcessImageSyncSmoke:
    @pytest.fixture(autouse=True)
    def _prepare_db(self):
        Base.metadata.create_all(sync_engine)
        yield
        # 不 drop_all，多个测试模块共用一个 sqlite 文件

    def test_empty_detections_only_writes_image_detection(self, tmp_path, monkeypatch):
        # 准备一张 1x1 像素 jpg
        img_path = tmp_path / "tiny.jpg"
        PILImage.new("RGB", (1, 1), color="white").save(img_path, "JPEG")

        task_id = str(uuid.uuid4())
        image_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="smoke",
                    total_images=1,
                    processed_images=0,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.add(
                Image(
                    id=image_id,
                    task_id=task_id,
                    filename="tiny.jpg",
                    storage_path=str(img_path),
                    has_gps=False,
                )
            )
            db.commit()

        from app.tasks import inference_tasks as it

        class _StubDetector:
            def detect(self, _path):
                return []

        class _StubClassifier:
            def classify(self, _path):
                import numpy as np

                return False, 0.0, np.zeros((1, 1), dtype="uint8")

        # 全局缓存替换成 stub，避免触发真实模型加载
        monkeypatch.setattr(it, "_nest_detector", _StubDetector())
        monkeypatch.setattr(it, "_tree_classifier", _StubClassifier())

        result = it.process_image_sync(task_id, image_id)
        assert result["status"] == "success"

        with SyncSessionLocal() as db:
            raws = db.query(RawNestDetection).filter_by(image_id=image_id).all()
            dets = db.query(ImageDetection).filter_by(image_id=image_id).all()
            task = (
                db.query(InspectionTask).filter_by(id=task_id).one()
            )

        # 没 detection -> 不写 raw_nest_detections
        assert raws == []
        # 写一行 image_detections，has_nest=False
        assert len(dets) == 1
        assert dets[0].has_nest is False
        assert dets[0].nest_count == 0
        assert dets[0].model_version == "v1.0"
        # processed_images +1
        assert task.processed_images == 1


# ---------------------------------------------------------------------------
# B1: _attach_gps_to_detections 在 EXIF 缺失时必须跳过 GPS 反算
# ---------------------------------------------------------------------------
class TestAttachGpsExifGuard:
    """worker 不得把 None 的 sensor_width 等字段 fallback 成硬编码常量，
    否则 #10 的"未知机型跳过 GPS 反算"设计会被绕过。"""

    def test_skips_when_sensor_width_missing(self):
        from app.tasks import inference_tasks as it

        # 模拟一张 has_gps=True 但 sensor_width=None 的图（未知机型）
        class _Img:
            id = "img-no-sensor"
            has_gps = True
            image_width = 4000
            image_height = 3000
            altitude = 50.0
            focal_length = 24.0
            sensor_width = None
            latitude = 31.0
            longitude = 121.0

        dets = [
            {
                "bbox_center": [0.5, 0.5],
                "bbox_width": 0.1,
                "bbox_height": 0.1,
                "confidence": 0.9,
                "severity": "medium",
            }
        ]
        out = it._attach_gps_to_detections(dets, _Img())
        # 必须不写 geo_latitude/geo_longitude（即缺省，None）
        assert len(out) == 1
        assert out[0].get("geo_latitude") is None
        assert out[0].get("geo_longitude") is None

    def test_full_exif_produces_geo_coords(self):
        from app.tasks import inference_tasks as it

        class _Img:
            id = "img-full-exif"
            has_gps = True
            image_width = 4000
            image_height = 3000
            altitude = 50.0
            focal_length = 24.0
            sensor_width = 13.2
            latitude = 31.0
            longitude = 121.0

        dets = [
            {
                "bbox_center": [0.6, 0.4],
                "bbox_width": 0.1,
                "bbox_height": 0.1,
                "confidence": 0.9,
                "severity": "medium",
            }
        ]
        out = it._attach_gps_to_detections(dets, _Img())
        assert len(out) == 1
        assert out[0]["geo_latitude"] is not None
        assert out[0]["geo_longitude"] is not None
        # 非 0 偏移 -> 必然不等于拍摄点本身
        assert out[0]["geo_latitude"] != 31.0 or out[0]["geo_longitude"] != 121.0

    def test_end_to_end_missing_exif_writes_null_geo(self, tmp_path, monkeypatch):
        """跑一遍完整 process_image_sync：缺 sensor_width 时
        raw_nest_detections.geo_latitude 必须为 None。"""
        from app.tasks import inference_tasks as it

        img_path = tmp_path / "no_sensor.jpg"
        PILImage.new("RGB", (1, 1), color="white").save(img_path, "JPEG")

        task_id = str(uuid.uuid4())
        image_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="exif-missing",
                    total_images=1,
                    processed_images=0,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.add(
                Image(
                    id=image_id,
                    task_id=task_id,
                    filename="no_sensor.jpg",
                    storage_path=str(img_path),
                    has_gps=True,
                    latitude=31.0,
                    longitude=121.0,
                    altitude=50.0,
                    focal_length=24.0,
                    sensor_width=None,  # 未知机型
                    image_width=4000,
                    image_height=3000,
                )
            )
            db.commit()

        class _StubDetector:
            def detect(self, _path):
                return [
                    {
                        "bbox_center": [0.5, 0.5],
                        "bbox_width": 0.1,
                        "bbox_height": 0.1,
                        "confidence": 0.9,
                        "severity": "medium",
                    }
                ]

        class _StubClassifier:
            def classify(self, _path):
                import numpy as np

                return False, 0.0, np.zeros((1, 1), dtype="uint8")

        monkeypatch.setattr(it, "_nest_detector", _StubDetector())
        monkeypatch.setattr(it, "_tree_classifier", _StubClassifier())

        result = it.process_image_sync(task_id, image_id)
        assert result["status"] == "success"

        with SyncSessionLocal() as db:
            raws = db.query(RawNestDetection).filter_by(image_id=image_id).all()

        assert len(raws) == 1
        assert raws[0].geo_latitude is None
        assert raws[0].geo_longitude is None

    def test_end_to_end_full_exif_writes_geo(self, tmp_path, monkeypatch):
        """跑一遍完整 process_image_sync：EXIF 齐全时 geo_* 必须算出非 None。"""
        from app.tasks import inference_tasks as it

        img_path = tmp_path / "full_exif.jpg"
        PILImage.new("RGB", (1, 1), color="white").save(img_path, "JPEG")

        task_id = str(uuid.uuid4())
        image_id = str(uuid.uuid4())
        with SyncSessionLocal() as db:
            owner_id = _ensure_owner(db)
            db.add(
                InspectionTask(
                    id=task_id,
                    task_name="exif-full",
                    total_images=1,
                    processed_images=0,
                    status="processing",
                    owner_id=owner_id,
                )
            )
            db.add(
                Image(
                    id=image_id,
                    task_id=task_id,
                    filename="full_exif.jpg",
                    storage_path=str(img_path),
                    has_gps=True,
                    latitude=31.0,
                    longitude=121.0,
                    altitude=50.0,
                    focal_length=24.0,
                    sensor_width=13.2,
                    image_width=4000,
                    image_height=3000,
                )
            )
            db.commit()

        class _StubDetector:
            def detect(self, _path):
                return [
                    {
                        "bbox_center": [0.6, 0.4],
                        "bbox_width": 0.1,
                        "bbox_height": 0.1,
                        "confidence": 0.9,
                        "severity": "medium",
                    }
                ]

        class _StubClassifier:
            def classify(self, _path):
                import numpy as np

                return False, 0.0, np.zeros((1, 1), dtype="uint8")

        monkeypatch.setattr(it, "_nest_detector", _StubDetector())
        monkeypatch.setattr(it, "_tree_classifier", _StubClassifier())

        result = it.process_image_sync(task_id, image_id)
        assert result["status"] == "success"

        with SyncSessionLocal() as db:
            raws = db.query(RawNestDetection).filter_by(image_id=image_id).all()

        assert len(raws) == 1
        assert raws[0].geo_latitude is not None
        assert raws[0].geo_longitude is not None
