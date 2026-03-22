from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.database import get_db
from app.models import InspectionTask, Image, ImageDetection
from app.services.task_service import TaskService
from app.tasks.inference_tasks import trigger_task_processing

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    task_name: str
    area_name: Optional[str] = None
    operator: Optional[str] = None


@router.post("/")
async def create_task(
    request: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """创建巡检任务"""
    service = TaskService(db)
    task = await service.create_task(
        request.task_name, request.area_name, request.operator
    )
    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "area_name": task.area_name,
        "operator": task.operator,
        "status": task.status,
        "created_at": task.created_at,
    }


@router.get("/")
async def list_tasks(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """查询任务列表"""
    service = TaskService(db)
    tasks = await service.list_tasks(skip, limit, status)
    return {
        "items": [
            {
                "id": str(task.id),
                "task_name": task.task_name,
                "area_name": task.area_name,
                "operator": task.operator,
                "status": task.status,
                "total_images": task.total_images,
                "processed_images": task.processed_images,
                "created_at": task.created_at,
            }
            for task in tasks
        ],
        "total": len(tasks),
    }


@router.get("/{task_id}")
async def get_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """查询任务详情"""
    service = TaskService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "area_name": task.area_name,
        "operator": task.operator,
        "status": task.status,
        "total_images": task.total_images,
        "processed_images": task.processed_images,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@router.get("/{task_id}/status")
async def get_task_status(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """查询任务处理状态"""
    service = TaskService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "id": str(task.id),
        "status": task.status,
        "total_images": task.total_images,
        "processed_images": task.processed_images,
        "progress": task.processed_images / task.total_images
        if task.total_images > 0
        else 0,
    }


@router.delete("/{task_id}")
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """删除任务"""
    service = TaskService(db)
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


@router.post("/{task_id}/process")
async def process_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    """触发任务处理（图片AI检测）"""
    service = TaskService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "uploading":
        raise HTTPException(
            status_code=400, detail="任务状态不正确，只能处理上传中的任务"
        )

    if task.total_images == 0:
        raise HTTPException(status_code=400, detail="任务没有上传图片")

    # 触发Celery任务处理
    trigger_task_processing.delay(str(task_id))

    return {
        "message": "任务处理已启动",
        "task_id": str(task_id),
        "status": "processing",
        "total_images": task.total_images,
    }
