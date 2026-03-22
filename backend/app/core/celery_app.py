from celery import Celery
from app.core.config import get_settings

settings = get_settings()

# 创建Celery应用
celery_app = Celery(
    "nest_detection",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.inference_tasks"],
)

# 配置Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    worker_prefetch_multiplier=1,  # 避免任务积压
)

__all__ = ["celery_app"]
