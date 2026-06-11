from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _is_owner_or_admin, get_owned_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import (
    Image,
    ImageDetection,
    InspectionTask,
    UniqueNest,
    User,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["nests"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/tasks/{task_id}/nests")
async def get_task_nests(
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """获取任务的去重后虫巢列表。ownership 已校验。"""
    query = select(UniqueNest).where(UniqueNest.task_id == str(task.id))

    if severity:
        query = query.where(UniqueNest.severity == severity)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    nests = result.scalars().all()

    return {
        "items": [
            {
                "id": str(nest.id),
                "nest_code": nest.nest_code,
                "latitude": nest.latitude,
                "longitude": nest.longitude,
                "severity": nest.severity,
                "confidence": nest.confidence,
                "detection_count": nest.detection_count,
                "source_images": nest.source_images,
                "created_at": nest.created_at,
            }
            for nest in nests
        ],
        "total": len(nests),
    }


@router.get("/nests/{nest_id}")
async def get_nest_detail(
    nest_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个虫巢详情（包含来源图片）。

    ownership：unique_nests 没有 owner_id，靠 task_id 间接归属。
    用 JOIN 一次性查 nest+task.owner_id，省一次 round-trip。
    不存在 / 无权 都返回 404 + "虫巢不存在"。
    """
    not_found = HTTPException(status_code=404, detail="虫巢不存在")

    result = await db.execute(
        select(UniqueNest, InspectionTask.owner_id)
        .join(
            InspectionTask,
            InspectionTask.id == UniqueNest.task_id,
            isouter=True,
        )
        .where(UniqueNest.id == str(nest_id))
    )
    row = result.one_or_none()
    if row is None:
        raise not_found

    nest, owner_id = row
    if not _is_owner_or_admin(current_user, owner_id):
        raise not_found

    # 获取来源图片详情
    source_images_details = []
    if nest.source_images:
        img_result = await db.execute(
            select(Image).where(Image.id.in_(nest.source_images))
        )
        images = img_result.scalars().all()
        source_images_details = [
            {"id": str(img.id), "filename": img.filename} for img in images
        ]

    return {
        "id": str(nest.id),
        "nest_code": nest.nest_code,
        "latitude": nest.latitude,
        "longitude": nest.longitude,
        "severity": nest.severity,
        "confidence": nest.confidence,
        "detection_count": nest.detection_count,
        "source_images": source_images_details,
        "created_at": nest.created_at,
    }


@router.get("/tasks/{task_id}/results")
async def get_task_results(
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """获取任务检测结果概览。ownership 已校验。"""
    # 查询图片检测统计
    detection_result = await db.execute(
        select(ImageDetection).where(ImageDetection.task_id == str(task.id))
    )
    detections = detection_result.scalars().all()

    # 统计有香樟树和虫巢的图片数
    camphor_count = sum(1 for d in detections if d.has_camphor_tree)
    nest_count = sum(1 for d in detections if d.has_nest)
    total_candidate_detections = sum(d.nest_count for d in detections)

    # 查询去重后的虫巢统计
    nests_result = await db.execute(
        select(
            func.count(UniqueNest.id).label("total"),
            func.count().filter(UniqueNest.severity == "severe").label("severe"),
            func.count().filter(UniqueNest.severity == "medium").label("medium"),
            func.count().filter(UniqueNest.severity == "light").label("light"),
        ).where(UniqueNest.task_id == str(task.id))
    )
    nest_stats = nests_result.one()

    return {
        "task_id": str(task.id),
        "image_stats": {
            "total_processed": len(detections),
            "with_camphor_tree": camphor_count,
            "with_nests": nest_count,
            "total_candidate_detections": total_candidate_detections,
            "total_nest_detections": total_candidate_detections,
        },
        "nest_stats": {
            "total_unique": nest_stats.total or 0,
            "severe": nest_stats.severe or 0,
            "medium": nest_stats.medium or 0,
            "light": nest_stats.light or 0,
        },
    }


@router.get("/tasks/{task_id}/statistics")
async def get_task_statistics(
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """获取任务详细统计数据。ownership 已校验。"""
    task_id_str = str(task.id)
    # 查询图片统计
    img_result = await db.execute(
        select(func.count(Image.id)).where(Image.task_id == task_id_str)
    )
    total_images = img_result.scalar() or 0

    # 查询GPS统计
    gps_result = await db.execute(
        select(func.count(Image.id)).where(
            Image.task_id == task_id_str, Image.has_gps.is_(True)
        )
    )
    gps_images = gps_result.scalar() or 0

    # 查询检测结果统计
    det_result = await db.execute(
        select(ImageDetection).where(ImageDetection.task_id == task_id_str)
    )
    detections = det_result.scalars().all()

    return {
        "task_id": task_id_str,
        "image_statistics": {
            "total": total_images,
            "with_gps": gps_images,
            "without_gps": total_images - gps_images,
        },
        "detection_statistics": {
            "processed_images": len(detections),
            "camphor_tree_images": sum(1 for d in detections if d.has_camphor_tree),
            "nest_images": sum(1 for d in detections if d.has_nest),
            "avg_inference_time_ms": sum(d.inference_time_ms or 0 for d in detections)
            / len(detections)
            if detections
            else 0,
        },
    }
