"""T5 —— 巡检任务 Word 报告导出端点。

GET /api/v1/tasks/{task_id}/report.docx
  返回该任务的 Word 巡检报告(.docx)。ownership 由 get_owned_task 校验。

报告内容组装在这里(DB 查询),文档构建委托给 services/docx_report.py。
"""

import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import (
    ImageDetection,
    InspectionTask,
    Region,
    UniqueNest,
)
from app.services.docx_report import build_task_report_docx

router = APIRouter(
    prefix="/api/v1",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


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

    docx_bytes = build_task_report_docx(
        task=task_data,
        results=results,
        nests=nests,
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
    total_candidate_detections = sum(d.nest_count for d in detections)
    return {
        "image_stats": {
            "total_processed": len(detections),
            "with_camphor_tree": sum(
                1 for d in detections if d.has_camphor_tree
            ),
            "with_nests": sum(1 for d in detections if d.has_nest),
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
