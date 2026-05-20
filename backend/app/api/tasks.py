from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import InspectionTask, User
from app.services.task_service import TaskService
from app.tasks.inference_tasks import trigger_task_processing

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


class TaskCreateRequest(BaseModel):
    task_name: str
    area_name: Optional[str] = None
    operator: Optional[str] = None
    plot_area_mu: Optional[float] = None
    forestry_sub_compartment: Optional[str] = None


@router.post("/")
async def create_task(
    request: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建巡检任务。owner_id 自动写入当前用户 id。"""
    service = TaskService(db)
    task = await service.create_task(
        request.task_name,
        request.area_name,
        request.operator,
        owner_id=current_user.id,
        plot_area_mu=request.plot_area_mu,
        forestry_sub_compartment=request.forestry_sub_compartment,
    )
    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "area_name": task.area_name,
        "operator": task.operator,
        "plot_area_mu": task.plot_area_mu,
        "forestry_sub_compartment": task.forestry_sub_compartment,
        "status": task.status,
        "created_at": task.created_at,
    }


@router.get("/")
async def list_tasks(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询任务列表。

    普通用户只能看自己创建的任务；admin 看全部。
    """
    service = TaskService(db)
    owner_filter = None if current_user.is_admin else current_user.id
    tasks = await service.list_tasks(skip, limit, status, owner_id=owner_filter)
    return {
        "items": [
            {
                "id": str(task.id),
                "task_name": task.task_name,
                "area_name": task.area_name,
                "operator": task.operator,
                "plot_area_mu": task.plot_area_mu,
                "forestry_sub_compartment": task.forestry_sub_compartment,
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
async def get_task(task: InspectionTask = Depends(get_owned_task)):
    """查询任务详情。ownership 由 get_owned_task 依赖校验。"""
    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "area_name": task.area_name,
        "operator": task.operator,
        "plot_area_mu": task.plot_area_mu,
        "forestry_sub_compartment": task.forestry_sub_compartment,
        "status": task.status,
        "total_images": task.total_images,
        "processed_images": task.processed_images,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@router.get("/{task_id}/status")
async def get_task_status(task: InspectionTask = Depends(get_owned_task)):
    """查询任务处理状态。"""
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
async def delete_task(
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """删除任务。ownership 已通过依赖校验。"""
    service = TaskService(db)
    success = await service.delete_task(task.id)
    if not success:
        # 极少出现：依赖里查到的 task 在 delete 前被并发删了
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "任务已删除"}


@router.post("/{task_id}/process")
async def process_task(task: InspectionTask = Depends(get_owned_task)):
    """触发任务处理（图片AI检测）。ownership 已校验。"""
    if task.status != "uploading":
        raise HTTPException(
            status_code=400, detail="任务状态不正确，只能处理上传中的任务"
        )

    if task.total_images == 0:
        raise HTTPException(status_code=400, detail="任务没有上传图片")

    # 触发Celery任务处理
    trigger_task_processing.delay(str(task.id))

    return {
        "message": "任务处理已启动",
        "task_id": str(task.id),
        "status": "processing",
        "total_images": task.total_images,
    }
