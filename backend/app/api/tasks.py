from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_task
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import InspectionTask, Region, User
from app.services.task_service import TaskService
from app.tasks.inference_tasks import trigger_task_processing

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


class TaskCreateRequest(BaseModel):
    task_name: str
    # T1 多级目录：region_id 无默认值 => pydantic 视为必填，缺失直接 422。
    # 这是"创建任务必须选完整三级区域"的第一道强制；第二道是 create_task
    # 里校验它确实指向一个 town 级区域。
    region_id: str
    area_name: Optional[str] = None
    operator: Optional[str] = None
    plot_area_mu: Optional[float] = None
    forestry_sub_compartment: Optional[str] = None


async def _region_path(db: AsyncSession, region_id: Optional[str]) -> Optional[str]:
    """查单个区域的 full_path。"""
    if not region_id:
        return None
    res = await db.execute(
        select(Region.full_path).where(Region.id == region_id)
    )
    return res.scalar_one_or_none()


async def _region_paths(db: AsyncSession, region_ids) -> dict:
    """批量查 {region_id: full_path}，避免任务列表 N+1。"""
    ids = list({r for r in region_ids if r})
    if not ids:
        return {}
    res = await db.execute(
        select(Region.id, Region.full_path).where(Region.id.in_(ids))
    )
    return {rid: fp for rid, fp in res.all()}


def _task_dict(task: InspectionTask, region_path: Optional[str] = None) -> dict:
    return {
        "id": str(task.id),
        "task_name": task.task_name,
        "area_name": task.area_name,
        "operator": task.operator,
        "plot_area_mu": task.plot_area_mu,
        "forestry_sub_compartment": task.forestry_sub_compartment,
        "region_id": task.region_id,
        "region_path": region_path,
        "status": task.status,
        "total_images": task.total_images,
        "processed_images": task.processed_images,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@router.post("/")
async def create_task(
    request: TaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建巡检任务。owner_id 自动写入当前用户 id。

    region_id 必须指向一个 **town（街镇）级** 区域——这强制用户在前端
    选完整的 市→区→街镇 三级，任务不能挂在市/区级。
    """
    res = await db.execute(
        select(Region).where(Region.id == request.region_id)
    )
    region = res.scalar_one_or_none()
    if region is None:
        raise HTTPException(
            status_code=400, detail="region_id 指向的区域不存在"
        )
    if region.level != "town":
        raise HTTPException(
            status_code=400,
            detail="必须选择完整的 市/区/街镇，任务只能归属到街镇(town)级区域",
        )

    service = TaskService(db)
    task = await service.create_task(
        request.task_name,
        request.area_name,
        request.operator,
        owner_id=current_user.id,
        plot_area_mu=request.plot_area_mu,
        forestry_sub_compartment=request.forestry_sub_compartment,
        region_id=request.region_id,
    )
    result = _task_dict(task, region_path=region.full_path)
    # 创建接口历史上不返回这两个字段，保持兼容裁掉
    result.pop("completed_at", None)
    return result


@router.get("/")
async def list_tasks(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    region_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询任务列表。

    - 普通用户只能看自己创建的任务；admin 看全部
    - region_id 过滤在数据库层 WHERE 完成（见 TaskService.list_tasks），
      不是前端对当前页结果再筛
    """
    service = TaskService(db)
    owner_filter = None if current_user.is_admin else current_user.id
    tasks = await service.list_tasks(
        skip, limit, status, owner_id=owner_filter, region_id=region_id
    )
    paths = await _region_paths(db, [t.region_id for t in tasks])
    return {
        "items": [
            _task_dict(task, region_path=paths.get(task.region_id))
            for task in tasks
        ],
        "total": len(tasks),
    }


@router.get("/{task_id}")
async def get_task(
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """查询任务详情。ownership 由 get_owned_task 依赖校验。"""
    region_path = await _region_path(db, task.region_id)
    return _task_dict(task, region_path=region_path)


@router.get("/{task_id}/status")
async def get_task_status(task: InspectionTask = Depends(get_owned_task)):
    """查询任务处理状态（前端轮询用，精简返回）。"""
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
