"""T5 —— 巡检任务 Word 报告导出端点。

GET /api/v1/tasks/{task_id}/report.docx
  返回该任务的 Word 巡检报告(.docx)。ownership 由 get_owned_task 校验。

报告内容组装在这里(DB 查询),文档构建委托给 services/docx_report.py。
"""

import io
import os

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import (
    Image,
    ImageDetection,
    InspectionTask,
    RawNestDetection,
    Region,
    UniqueNest,
)
from app.services.docx_report import build_task_report_docx
from app.services.image_render import render_annotated_image

router = APIRouter(
    prefix="/api/v1",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
# 报告附录最多嵌入多少张标注影像
MAX_ANNOTATED_IMAGES = 6
# 报告内嵌图按 1280 宽压缩(报告无需全分辨率,控体积)
REPORT_IMAGE_MAX_WIDTH = 1280


@router.get("/tasks/{task_id}/report.docx")
async def export_task_report_docx(
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """导出巡检任务 Word 报告。ownership 已由 get_owned_task 校验。"""
    task_id = str(task.id)

    # —— 区域完整路径(异步 session 下 relationship 不能懒加载,显式查)——
    region_path = None
    if task.region_id:
        region = (
            await db.execute(select(Region).where(Region.id == task.region_id))
        ).scalar_one_or_none()
        if region is not None:
            region_path = region.full_path

    task_data = {
        "task_name": task.task_name,
        "region_path": region_path,
        "area_name": task.area_name,
        "operator": task.operator,
        "plot_area_mu": task.plot_area_mu,
        "forestry_sub_compartment": task.forestry_sub_compartment,
        "status": task.status,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
        "total_images": task.total_images,
        "processed_images": task.processed_images,
    }

    results = await _build_results(db, task_id)
    nests = await _build_nest_list(db, task_id)
    annotated_images = await _build_annotated_images(db, task_id)

    docx_bytes = build_task_report_docx(
        task=task_data,
        results=results,
        nests=nests,
        annotated_images=annotated_images,
    )

    filename = f"report_{task_id}.docx"
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _build_results(db: AsyncSession, task_id: str) -> dict:
    """复刻 /tasks/{id}/results 的统计结构。"""
    detections = (
        await db.execute(
            select(ImageDetection).where(ImageDetection.task_id == task_id)
        )
    ).scalars().all()
    nest_stats = (
        await db.execute(
            select(
                func.count(UniqueNest.id).label("total"),
                func.count()
                .filter(UniqueNest.severity == "severe")
                .label("severe"),
                func.count()
                .filter(UniqueNest.severity == "medium")
                .label("medium"),
                func.count()
                .filter(UniqueNest.severity == "light")
                .label("light"),
            ).where(UniqueNest.task_id == task_id)
        )
    ).one()
    return {
        "image_stats": {
            "total_processed": len(detections),
            "with_camphor_tree": sum(
                1 for d in detections if d.has_camphor_tree
            ),
            "with_nests": sum(1 for d in detections if d.has_nest),
            "total_nest_detections": sum(d.nest_count for d in detections),
        },
        "nest_stats": {
            "total_unique": nest_stats.total or 0,
            "severe": nest_stats.severe or 0,
            "medium": nest_stats.medium or 0,
            "light": nest_stats.light or 0,
        },
    }


async def _build_nest_list(db: AsyncSession, task_id: str) -> list[dict]:
    """查询去重后虫巢清单。"""
    rows = (
        await db.execute(
            select(UniqueNest)
            .where(UniqueNest.task_id == task_id)
            .order_by(UniqueNest.nest_code)
        )
    ).scalars().all()
    return [
        {
            "nest_code": n.nest_code,
            "longitude": n.longitude,
            "latitude": n.latitude,
            "severity": n.severity,
            "confidence": n.confidence,
            "detection_count": n.detection_count,
        }
        for n in rows
    ]


async def _build_annotated_images(
    db: AsyncSession, task_id: str
) -> list[tuple[bytes, str]]:
    """挑选含虫巢的图片(按虫巢数降序),渲染标注图供报告附录使用。"""
    top = (
        await db.execute(
            select(ImageDetection)
            .where(
                ImageDetection.task_id == task_id,
                ImageDetection.has_nest.is_(True),
            )
            .order_by(ImageDetection.nest_count.desc())
            .limit(MAX_ANNOTATED_IMAGES)
        )
    ).scalars().all()

    annotated: list[tuple[bytes, str]] = []
    for det in top:
        image = (
            await db.execute(select(Image).where(Image.id == det.image_id))
        ).scalar_one_or_none()
        if image is None or not image.storage_path:
            continue
        if not os.path.exists(image.storage_path):
            continue
        raw = (
            await db.execute(
                select(RawNestDetection).where(
                    RawNestDetection.image_id == det.image_id
                )
            )
        ).scalars().all()
        try:
            jpeg = render_annotated_image(
                image.storage_path, raw, max_width=REPORT_IMAGE_MAX_WIDTH
            )
        except Exception:  # noqa: BLE001 — 单张图渲染失败不拖垮整份报告
            continue
        annotated.append((jpeg, _image_caption(image)))
    return annotated


def _image_caption(image: Image) -> str:
    """标注图图注:文件名 +(可选)GPS 坐标。"""
    caption = image.filename or "未命名影像"
    if (
        image.has_gps
        and image.latitude is not None
        and image.longitude is not None
    ):
        caption += f"　({image.latitude:.6f}, {image.longitude:.6f})"
    return caption
