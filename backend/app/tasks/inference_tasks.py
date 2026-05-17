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

from celery import chord, group, shared_task  # noqa: F401  (保留导出兼容)
from celery.exceptions import MaxRetriesExceededError
from celery.signals import worker_process_init
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


# ---- 模型预热 / 进程级缓存（见 #9）---------------------------------------
# 每个 Celery worker 进程在启动时 fork 一次 _warmup_models()，把模型加载
# 到进程级单例里；之后所有 task 复用，避免每张图都 new YOLO/Torch 模型。
#
# 注意：pytest 不会触发 worker_process_init，所以下面的 _get_xxx() 还保留
# lazy fallback——首次调用就地实例化，并写回全局，后续测试也共享一份。
# 模型类自身的 _load_model lazy 行为保持不动，是双重防御。
_nest_detector: Optional[NestDetector] = None
_tree_classifier: Optional[TreeClassifier] = None


@worker_process_init.connect
def _warmup_models(**_kwargs) -> None:  # pragma: no cover - worker-only
    """Celery worker 子进程启动时一次性加载模型。"""
    global _nest_detector, _tree_classifier
    logger.info("worker_process_init: 预热推理模型")
    try:
        _nest_detector = NestDetector()
    except Exception as exc:
        logger.exception(f"NestDetector 预热失败: {exc}")
        _nest_detector = None
    try:
        _tree_classifier = TreeClassifier()
    except Exception as exc:
        logger.exception(f"TreeClassifier 预热失败: {exc}")
        _tree_classifier = None


def _get_nest_detector() -> NestDetector:
    """获取进程级 NestDetector；pytest / 任何未走 worker_process_init 的
    场景下做 lazy 实例化（仅一次），保证测试也能跑。"""
    global _nest_detector
    if _nest_detector is None:
        _nest_detector = NestDetector()
    return _nest_detector


def _get_tree_classifier() -> TreeClassifier:
    """同 _get_nest_detector，进程级 TreeClassifier + lazy fallback。"""
    global _tree_classifier
    if _tree_classifier is None:
        _tree_classifier = TreeClassifier()
    return _tree_classifier


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

            # 去重不在这里触发：由 chord(header)(callback) 显式编排
            # （header = group(process_image_task...)，callback =
            #  process_task_deduplication.si(task_id)）。见 trigger_processing_sync。
            return {
                "status": "success",
                "task_id": task_id,
                "image_id": image_id,
                "inference_time_ms": elapsed_ms,
            }
        except Exception:
            db.rollback()
            raise


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
def trigger_processing_sync(
    task_id: str, image_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """触发整批图片的推理。

    1. 把任务状态置为 processing、processed_images 清零
    2. 用 Celery chord 显式编排：所有 process_image_task 完成后
       自动调度 process_task_deduplication，避免之前"每张图都查 task
       + 5 分钟兜底"的双路径竞态（见 #7）。
    3. 如果 image_ids 没显式传，就从 DB 查（向后兼容旧调用方）

    image_ids 可以由调用方显式传入（推荐，见 #6：API 层 commit 后立刻
    把入库的 image_id 列表传过来，避免 worker 再读一次 DB 撞上事务窗口）。
    """
    with SyncSessionLocal() as db:
        try:
            if image_ids is None:
                images = (
                    db.execute(select(Image).where(Image.task_id == task_id))
                    .scalars()
                    .all()
                )
                resolved_ids: List[str] = [str(img.id) for img in images]
            else:
                resolved_ids = [str(i) for i in image_ids]

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

    if not resolved_ids:
        # 没有任何图片可处理：直接走一次去重收尾（也会把 task.status 置成 completed）
        logger.info(f"任务 {task_id} 没有图片，直接触发去重收尾")
        process_task_deduplication.delay(task_id)
        return {"status": "triggered", "task_id": task_id, "images": 0}

    # chord(header)(callback)：header 全部成功后才执行 callback；
    # 失败由 process_task_deduplication 内部统一处理（见 #7）。
    # process_task_deduplication.si(task_id)：immutable signature，
    # 不会把 header 的返回值塞进 args。
    header = group(
        process_image_task.s(task_id, image_id) for image_id in resolved_ids
    )
    callback = process_task_deduplication.si(task_id)
    chord(header)(callback)

    logger.info(f"已发起 chord: task_id={task_id}, header_size={len(resolved_ids)}")
    return {"status": "triggered", "task_id": task_id, "images": len(resolved_ids)}


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
    """任务级去重（Celery 入口）。

    被 chord(header)(callback) 调用。如果 header 里任一 process_image_task
    最终失败，Celery 仍会把 callback 投递过来（取决于 broker 行为），
    更重要的是去重本身可能出错。两种情况都把 task.status 改成 failed
    并把原因写到一个 InspectionTask 上能记录的字段——当前模型没有专门
    的 error 字段，所以只能写日志 + 状态码，让 API 层看到 failed 时拉日志。
    """
    logger.info(f"开始任务去重: task_id={task_id}")
    try:
        return deduplicate_task_sync(task_id)
    except Exception as exc:
        logger.exception(f"去重失败，task_id={task_id}, error={exc}")
        _mark_task_failed(task_id, reason=str(exc))
        # 不再 raise：chord callback 自己挂掉没有意义，状态已经写到 DB
        return {"status": "failed", "task_id": task_id, "error": str(exc)}


def _mark_task_failed(task_id: str, reason: str) -> None:
    """把任务状态改为 failed。reason 只走日志（当前模型无 error 字段）。"""
    try:
        with SyncSessionLocal() as db:
            task = db.execute(
                select(InspectionTask).where(InspectionTask.id == task_id)
            ).scalar_one_or_none()
            if task is not None:
                task.status = "failed"
                db.commit()
            logger.error(f"任务 {task_id} 标记为 failed，reason={reason}")
    except Exception as inner:
        # 写状态都失败了，只能记日志，不再传播
        logger.exception(
            f"标记任务 failed 时再次失败 task_id={task_id}, inner={inner}"
        )


@celery_app.task
def trigger_task_processing(task_id: str, image_ids: Optional[List[str]] = None):
    """触发任务处理（Celery 入口，由上传接口调用）。

    image_ids 由 API 层在 upload commit 之后显式传入（见 #6），避免
    worker 自己再去 SELECT 一次撞 race。如果调用方没传（旧代码/回放），
    走 DB fallback。
    """
    logger.info(
        f"触发任务处理: task_id={task_id}, "
        f"image_ids_passed={None if image_ids is None else len(image_ids)}"
    )
    return trigger_processing_sync(task_id, image_ids=image_ids)
