from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.services.nest_detector import NestDetector
from app.services.tree_classifier import TreeClassifier
from app.services.geo_service import GeoService
from app.services.dedup_service import DedupService
from app.services.task_service import TaskService
from app.models import Image, ImageDetection, RawNestDetection
from sqlalchemy import select
from uuid import UUID
import time

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_image_task(self, task_id: str, image_id: str):
    """
    处理单张图片的完整推理流程

    流程:
    1. 加载图片和元数据
    2. 树种识别 (DeepLabV3+)
    3. 如果检测到香樟树 -> 虫巢检测 (YOLOv8)
    4. GPS坐标反算
    5. 保存结果到数据库

    Args:
        task_id: 任务ID
        image_id: 图片ID
    """
    logger.info(f"开始处理图片: task_id={task_id}, image_id={image_id}")
    start_time = time.time()

    try:
        # 使用异步数据库会话
        import asyncio

        asyncio.run(_process_image_async(self, task_id, image_id, start_time))

        elapsed_time = int((time.time() - start_time) * 1000)
        logger.info(f"图片处理完成: image_id={image_id}, 耗时={elapsed_time}ms")

        return {
            "status": "success",
            "task_id": task_id,
            "image_id": image_id,
            "inference_time_ms": elapsed_time,
        }

    except Exception as exc:
        logger.error(f"图片处理失败: image_id={image_id}, error={str(exc)}")
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"达到最大重试次数: image_id={image_id}")
            raise


async def _process_image_async(self, task_id: str, image_id: str, start_time: float):
    """异步处理图片"""
    async with AsyncSessionLocal() as db:
        try:
            # 1. 获取图片信息（使用字符串查询）
            result = await db.execute(select(Image).where(Image.id == image_id))
            image = result.scalar_one_or_none()

            if not image:
                logger.error(f"图片不存在: image_id={image_id}")
                return

            # 2. 初始化检测器（跳过了树种识别，直接检测虫巢）
            nest_detector = NestDetector()
            detections = []

            # 3. 直接进行虫巢检测（不依赖树种识别）
            logger.info(f"开始虫巢检测: image_id={image_id}")
            detections = nest_detector.detect(image.storage_path)
            logger.info(
                f"虫巢检测结果: image_id={image_id}, detections={len(detections)}"
            )

            # 4. 树种识别（用于记录，但不影响虫巢检测）
            tree_classifier = TreeClassifier()
            has_camphor, camphor_ratio, seg_mask = tree_classifier.classify(
                image.storage_path
            )
            logger.info(
                f"树种识别结果: image_id={image_id}, has_camphor={has_camphor}, ratio={camphor_ratio:.2%}"
            )

            # 5. GPS坐标反算
            if detections and image.has_gps:
                geo_service = GeoService(db)
                detections = await geo_service.convert_detection_to_gps(
                    image_id, detections
                )

            # 6. 保存原始检测结果
            for det in detections:
                raw_detection = RawNestDetection(
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
                db.add(raw_detection)

            # 7. 保存图片级检测结果
            image_detection = ImageDetection(
                image_id=image_id,
                task_id=task_id,
                has_camphor_tree=has_camphor,
                has_nest=len(detections) > 0,
                nest_count=len(detections),
                max_severity=_get_max_severity(detections),
                inference_time_ms=int((time.time() - start_time) * 1000),
                model_version="v1.0",
            )
            db.add(image_detection)

            # 8. 更新任务进度
            task_service = TaskService(db)
            await task_service.increment_processed_images(task_id)

            await db.commit()

            # 9. 检查是否所有图片都处理完成，如果是则立即触发去重
            await _check_and_trigger_deduplication(task_id)

        except Exception as e:
            await db.rollback()
            logger.error(f"处理过程异常: {e}")
            raise


async def _check_and_trigger_deduplication(task_id: str):
    """检查是否所有图片处理完成，如果是则触发去重"""
    async with AsyncSessionLocal() as db:
        try:
            # 获取任务信息
            from app.services.task_service import TaskService

            task_service = TaskService(db)
            task = await task_service.get_task(task_id)

            if not task:
                return

            # 检查是否所有图片都处理完成
            if task.processed_images >= task.total_images:
                logger.info(f"任务 {task_id} 所有图片处理完成，触发去重")
                # 立即触发去重任务
                process_task_deduplication.delay(task_id)

        except Exception as e:
            logger.error(f"检查去重触发失败: {e}")


def _get_max_severity(detections):
    """获取最高严重程度"""
    if not detections:
        return None

    severity_order = {"light": 1, "medium": 2, "severe": 3}
    max_sev = max(
        detections, key=lambda d: severity_order.get(d.get("severity", "light"), 0)
    )
    return max_sev.get("severity", "light")


@celery_app.task
def process_task_deduplication(task_id: str):
    """
    对任务进行虫巢去重

    在所有图片处理完成后执行
    """
    logger.info(f"开始任务去重: task_id={task_id}")

    import asyncio

    asyncio.run(_deduplicate_async(task_id))

    logger.info(f"任务去重完成: task_id={task_id}")
    return {"status": "success", "task_id": task_id}


async def _deduplicate_async(task_id: str):
    """异步执行去重"""
    async with AsyncSessionLocal() as db:
        try:
            dedup_service = DedupService(db)

            # 执行去重
            unique_nests = await dedup_service.deduplicate_task_nests(
                task_id, eps_meters=3.0
            )

            # 保存结果
            count = await dedup_service.save_unique_nests(task_id, unique_nests)

            # 更新任务状态为完成
            task_service = TaskService(db)
            await task_service.update_task_status(
                task_id, "completed", processed_images=None
            )

            await db.commit()
            logger.info(f"去重完成: task_id={task_id}, unique_nests={count}")

        except Exception as e:
            await db.rollback()
            logger.error(f"去重失败: {e}")
            raise


@celery_app.task
def trigger_task_processing(task_id: str):
    """
    触发任务处理

    上传完成后调用，批量处理任务中的所有图片
    """
    logger.info(f"触发任务处理: task_id={task_id}")

    import asyncio

    asyncio.run(_trigger_processing_async(task_id))

    return {"status": "triggered", "task_id": task_id}


async def _trigger_processing_async(task_id: str):
    """异步触发处理"""
    async with AsyncSessionLocal() as db:
        try:
            # 获取任务的所有图片（使用字符串查询）
            result = await db.execute(select(Image).where(Image.task_id == task_id))
            images = result.scalars().all()

            # 更新任务状态为处理中
            task_service = TaskService(db)
            await task_service.update_task_status(
                task_id, "processing", processed_images=0
            )
            await db.commit()

            # 为每张图片创建异步任务
            for image in images:
                process_image_task.delay(task_id, str(image.id))

            logger.info(f"已创建 {len(images)} 个图片处理任务")

            # 创建去重任务（在所有图片处理完成后执行）
            # 使用Celery的group和chain可以更好地处理依赖关系
            # 这里简化为在足够长的时间后执行（实际应用应使用更精确的方式）
            process_task_deduplication.apply_async(
                args=[task_id],
                countdown=300,  # 5分钟后执行去重
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"触发处理失败: {e}")
            raise
