"""
Celery worker 推理任务。

Worker 内部全部用同步 SQLAlchemy session（SyncSessionLocal），
不再 asyncio.run 出新 event loop / 重建 asyncpg 连接池。FastAPI
路由层仍是 async，互不影响（见 #8）。

为了避免把 AsyncSession 风格的 service 强行同步化，这里在 worker
里直接用 ORM 写少量 DB 操作，service 层保持不动。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from celery import shared_task  # noqa: F401  (保留导出兼容)
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SyncSessionLocal
from app.models import (
    Image,
    ImageDetection,
    InspectionTask,
    RawNestDetection,
)
from app.services.nest_detector import NestDetector
from app.services.tree_classifier import TreeClassifier
from app.utils.geo_utils import pixel_to_gps

logger = logging.getLogger(__name__)


# ---- 模型懒加载（commit #5 会换成 worker_process_init 预热）---------------
# 这里先保持每次 new 一份的旧行为，下一个 commit 切到全局缓存。
def _get_nest_detector() -> NestDetector:
    return NestDetector()


def _get_tree_classifier() -> TreeClassifier:
    return TreeClassifier()


# ---- 内部工具：把 detections 反算 GPS（不再走 GeoService 的 async 版） ----
def _attach_gps_to_detections(
    detections: List[Dict[str, Any]], image: Image
) -> List[Dict[str, Any]]:
    """同步版坐标反算。GeoService.convert_detection_to_gps 是 async，
    Worker 里直接用底层 pixel_to_gps 完成同样的逻辑，避免再绕回 async。
    """
    if not detections or not image.has_gps:
        return detections

    out: List[Dict[str, Any]] = []
    for det in detections:
        bbox_center = det.get("bbox_center", [0.5, 0.5])
        lat, lon = pixel_to_gps(
            pixel_x=bbox_center[0],
            pixel_y=bbox_center[1],
            image_width=image.image_width or 4000,
            image_height=image.image_height or 3000,
            photo_lat=image.latitude,
            photo_lon=image.longitude,
            altitude=image.altitude or 50,
            focal_length=image.focal_length or 24,
            sensor_width=image.sensor_width or 13.2,
        )
        new_det = dict(det)
        new_det["geo_latitude"] = lat
        new_det["geo_longitude"] = lon
        out.append(new_det)
    return out


def _get_max_severity(detections: List[Dict[str, Any]]) -> Optional[str]:
    """获取最高严重程度"""
    if not detections:
        return None
    severity_order = {"light": 1, "medium": 2, "severe": 3}
    max_sev = max(
        detections, key=lambda d: severity_order.get(d.get("severity", "light"), 0)
    )
    return max_sev.get("severity", "light")


# ---------------------------------------------------------------------------
# 同步纯函数核心 - 单图处理
# ---------------------------------------------------------------------------
def process_image_sync(task_id: str, image_id: str) -> Dict[str, Any]:
    """对单张图片执行完整推理流程（同步）。

    流程:
    1. 加载图片元数据
    2. 虫巢检测 (YOLO)
    3. 树种识别 (DeepLabV3+，记录用)
    4. GPS 坐标反算
    5. 写入 raw_nest_detections / image_detections
    6. 更新 task.processed_images
    """
    start_time = time.time()
    logger.info(f"开始处理图片: task_id={task_id}, image_id={image_id}")

    with SyncSessionLocal() as db:
        try:
            image = db.execute(
                select(Image).where(Image.id == image_id)
            ).scalar_one_or_none()
            if image is None:
                logger.error(f"图片不存在: image_id={image_id}")
                return {"status": "skipped", "reason": "image_not_found"}

            nest_detector = _get_nest_detector()
            detections = nest_detector.detect(image.storage_path)
            logger.info(
                f"虫巢检测结果: image_id={image_id}, detections={len(detections)}"
            )

            tree_classifier = _get_tree_classifier()
            has_camphor, camphor_ratio, _seg_mask = tree_classifier.classify(
                image.storage_path
            )
            logger.info(
                f"树种识别结果: image_id={image_id}, has_camphor={has_camphor}, "
                f"ratio={camphor_ratio:.2%}"
            )

            if detections and image.has_gps:
                detections = _attach_gps_to_detections(detections, image)

            for det in detections:
                db.add(
                    RawNestDetection(
                        image_id=image_id,
                        task_id=task_id,
                        bbox_x_center=det["bbox_center"][0],
                        bbox_y_center=det["bbox_center"][1],
                        bbox_width=det["bbox_width"],
                        bbox_height=det["bbox_height"],
                        geo_latitude=det.get("geo_latitude"),
                        geo_longitude=det.get("geo_longitude"),
                        confidence=det["confidence"],
                        severity=det["severity"],
                    )
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            db.add(
                ImageDetection(
                    image_id=image_id,
                    task_id=task_id,
                    has_camphor_tree=has_camphor,
                    has_nest=len(detections) > 0,
                    nest_count=len(detections),
                    max_severity=_get_max_severity(detections),
                    inference_time_ms=elapsed_ms,
                    model_version="v1.0",
                )
            )

            # 用 UPDATE 增量改 processed_images，避免读后写产生的覆盖丢失
            task = db.execute(
                select(InspectionTask).where(InspectionTask.id == task_id)
            ).scalar_one_or_none()
            if task is not None:
                task.processed_images = (task.processed_images or 0) + 1

            db.commit()

            # 兼容老链路：仍在最后一张完成时触发去重（commit #3 改成 chord）
            _check_and_trigger_deduplication(task_id)

            return {
                "status": "success",
                "task_id": task_id,
                "image_id": image_id,
                "inference_time_ms": elapsed_ms,
            }
        except Exception:
            db.rollback()
            raise


def _check_and_trigger_deduplication(task_id: str) -> None:
    """旧链路：所有图片处理完后触发去重。commit #3 会移除该函数。"""
    with SyncSessionLocal() as db:
        task = db.execute(
            select(InspectionTask).where(InspectionTask.id == task_id)
        ).scalar_one_or_none()
        if task is None:
            return
        if task.total_images and task.processed_images >= task.total_images:
            logger.info(f"任务 {task_id} 所有图片处理完成，触发去重")
            process_task_deduplication.delay(task_id)


# ---------------------------------------------------------------------------
# 同步纯函数核心 - 去重
# ---------------------------------------------------------------------------
def deduplicate_task_sync(task_id: str) -> Dict[str, Any]:
    """同步执行任务去重 + 更新任务状态为 completed。

    去重核心算法仍然复用 utils 层，纯 Python；service 层是 async 的，
    所以这里直接调用 utils + ORM 重写一遍 save_unique_nests 的逻辑。
    """
    import json

    from app.models import UniqueNest
    from app.utils.dedup_utils import deduplicate_nests, generate_nest_code
    from sqlalchemy import delete

    with SyncSessionLocal() as db:
        try:
            raw_detections = (
                db.execute(
                    select(RawNestDetection).where(RawNestDetection.task_id == task_id)
                )
                .scalars()
                .all()
            )

            detections_for_dedup = [
                {
                    "lat": det.geo_latitude,
                    "lon": det.geo_longitude,
                    "confidence": det.confidence or 0.5,
                    "severity": det.severity or "light",
                    "image_id": str(det.image_id),
                }
                for det in raw_detections
                if det.geo_latitude and det.geo_longitude
            ]

            unique_nests = deduplicate_nests(
                detections=detections_for_dedup, eps_meters=3.0, min_samples=1
            )

            # 清空旧去重结果（同一任务可重跑）
            db.execute(delete(UniqueNest).where(UniqueNest.task_id == task_id))

            count = 0
            for i, nest_data in enumerate(unique_nests):
                db.add(
                    UniqueNest(
                        task_id=task_id,
                        nest_code=generate_nest_code(str(task_id), i + 1),
                        latitude=nest_data["latitude"],
                        longitude=nest_data["longitude"],
                        severity=nest_data["severity"],
                        confidence=nest_data["confidence"],
                        detection_count=nest_data["detection_count"],
                        source_images=json.dumps(nest_data["source_images"]),
                    )
                )
                count += 1

            task = db.execute(
                select(InspectionTask).where(InspectionTask.id == task_id)
            ).scalar_one_or_none()
            if task is not None:
                task.status = "completed"

            db.commit()
            logger.info(f"去重完成: task_id={task_id}, unique_nests={count}")
            return {"status": "success", "task_id": task_id, "unique_nests": count}
        except Exception:
            db.rollback()
            raise


# ---------------------------------------------------------------------------
# 同步纯函数核心 - 触发整批处理
# ---------------------------------------------------------------------------
def trigger_processing_sync(task_id: str) -> Dict[str, Any]:
    """触发整批图片的推理。

    1. 把任务状态置为 processing、processed_images 清零
    2. 把所有图片 id 一一 enqueue process_image_task
    3. 兜底 5 分钟后 enqueue 一次 process_task_deduplication（commit #3 删）
    """
    with SyncSessionLocal() as db:
        try:
            images = (
                db.execute(select(Image).where(Image.task_id == task_id))
                .scalars()
                .all()
            )
            image_ids = [str(img.id) for img in images]

            task = db.execute(
                select(InspectionTask).where(InspectionTask.id == task_id)
            ).scalar_one_or_none()
            if task is not None:
                task.status = "processing"
                task.processed_images = 0
            db.commit()
        except Exception:
            db.rollback()
            raise

    for image_id in image_ids:
        process_image_task.delay(task_id, image_id)

    logger.info(f"已创建 {len(image_ids)} 个图片处理任务")

    # 旧兜底链路，commit #3 会被 chord 替换
    process_task_deduplication.apply_async(args=[task_id], countdown=300)

    return {"status": "triggered", "task_id": task_id, "images": len(image_ids)}


# ---------------------------------------------------------------------------
# Celery 任务（薄外壳）
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_image_task(self, task_id: str, image_id: str):
    """处理单张图片（Celery 入口）"""
    try:
        return process_image_sync(task_id, image_id)
    except Exception as exc:
        logger.error(f"图片处理失败: image_id={image_id}, error={exc}")
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"达到最大重试次数: image_id={image_id}")
            raise


@celery_app.task
def process_task_deduplication(task_id: str):
    """任务级去重（Celery 入口）"""
    logger.info(f"开始任务去重: task_id={task_id}")
    return deduplicate_task_sync(task_id)


@celery_app.task
def trigger_task_processing(task_id: str):
    """触发任务处理（Celery 入口，由上传接口调用）"""
    logger.info(f"触发任务处理: task_id={task_id}")
    return trigger_processing_sync(task_id)
