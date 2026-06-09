"""追加上传处理的进度与并发保护测试。"""

import os
import uuid

os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-pytest-DO-NOT-USE")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./test_append_upload_processing.sqlite"
)
os.environ.setdefault("CELERY_BROKER_URL", "sqla+sqlite:///./test_celerydb.sqlite")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
)

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core.database import Base, SyncSessionLocal, sync_engine  # noqa: E402
from app.models import Image, InspectionTask, User  # noqa: E402


def _owner_id() -> str:
    Base.metadata.create_all(sync_engine)
    with SyncSessionLocal() as db:
        user = db.query(User).filter_by(username="_append_owner").one_or_none()
        if user is None:
            user = User(
                username="_append_owner",
                hashed_password="x",
                is_active=True,
                is_admin=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user.id


def test_explicit_append_batch_does_not_reset_processed_images(monkeypatch):
    """追加批次只处理新增 image_ids，不能把已处理总数清零。"""
    from app.tasks import inference_tasks as it

    task_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    owner_id = _owner_id()

    with SyncSessionLocal() as db:
        db.add(
            InspectionTask(
                id=task_id,
                task_name="append",
                status="completed",
                total_images=25,
                processed_images=20,
                owner_id=owner_id,
            )
        )
        db.add(
            Image(
                id=image_id,
                task_id=task_id,
                filename="new.jpg",
                storage_path="/dev/null",
            )
        )
        db.commit()

    monkeypatch.setattr(it.process_image_task, "s", lambda task, image: ("image", task, image))
    monkeypatch.setattr(it.process_task_deduplication, "s", lambda task: ("dedup", task))
    monkeypatch.setattr(it, "group", lambda gen: list(gen))
    monkeypatch.setattr(it, "chord", lambda header: lambda callback: None)

    result = it.trigger_processing_sync(task_id, image_ids=[image_id])

    assert result["images"] == 1
    with SyncSessionLocal() as db:
        task = db.query(InspectionTask).filter_by(id=task_id).one()
        assert task.status == "processing"
        assert task.processed_images == 20


def test_full_reprocess_without_explicit_image_ids_still_resets_progress(monkeypatch):
    """兼容旧的全量重跑入口：未传 image_ids 时仍从 0 重新计数。"""
    from app.tasks import inference_tasks as it

    task_id = str(uuid.uuid4())
    image_id = str(uuid.uuid4())
    owner_id = _owner_id()

    with SyncSessionLocal() as db:
        db.add(
            InspectionTask(
                id=task_id,
                task_name="reprocess",
                status="completed",
                total_images=1,
                processed_images=1,
                owner_id=owner_id,
            )
        )
        db.add(
            Image(
                id=image_id,
                task_id=task_id,
                filename="old.jpg",
                storage_path="/dev/null",
            )
        )
        db.commit()

    monkeypatch.setattr(it.process_image_task, "s", lambda task, image: ("image", task, image))
    monkeypatch.setattr(it.process_task_deduplication, "s", lambda task: ("dedup", task))
    monkeypatch.setattr(it, "group", lambda gen: list(gen))
    monkeypatch.setattr(it, "chord", lambda header: lambda callback: None)

    result = it.trigger_processing_sync(task_id, image_ids=None)

    assert result["images"] == 1
    with SyncSessionLocal() as db:
        task = db.query(InspectionTask).filter_by(id=task_id).one()
        assert task.status == "processing"
        assert task.processed_images == 0
