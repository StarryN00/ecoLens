"""路由层公共依赖：资源 ownership 校验。

M2：所有按 task_id / image_id 读写的接口必须验证"这个资源属于
current_user"。原本只有 `Depends(get_current_user)`，普通用户能
看 / 改 / 上传别人的任务。

防资源枚举攻击：不存在 和 无权访问 都返回 **404 + 同一 detail**，
不要泄露存在性。
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Image, InspectionTask, User


def _is_owner_or_admin(user: User, owner_id: Optional[str]) -> bool:
    if user.is_admin:
        return True
    if owner_id is None:
        # 旧库迁移前留下来的 NULL —— 当作非 owner 处理，admin 例外
        return False
    return owner_id == user.id


async def get_owned_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InspectionTask:
    """按 task_id 取任务并校验 ownership。

    路径参数同时支持 UUID 对象和字符串；统一转成 str 后比对（model 里
    id 是 String(36)）。

    返回：InspectionTask 实例
    抛出：HTTP 404 "任务不存在" —— 不存在 与 无权 共用同一 status/detail，
         防止枚举他人 task_id。
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在"
    )

    task_id_str = str(task_id)
    result = await db.execute(
        select(InspectionTask).where(InspectionTask.id == task_id_str)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise not_found

    if not _is_owner_or_admin(current_user, task.owner_id):
        # 故意复用 not_found：404 + 同样 detail，避免暴露存在性
        raise not_found

    return task


async def get_owned_image(
    image_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Image:
    """按 image_id 取图片，并校验所属 task 的 ownership。

    Image 不存自己的 owner_id —— 它通过 task_id 间接归属（省一层冗余）。
    实现：先 SELECT image，再 SELECT image.task_id 对应的 task，校验
    task.owner_id。两次 query 用同一个 session，事务上下文一致。

    返回：Image 实例
    抛出：HTTP 404 "图片不存在" —— 同样的反枚举语义。
    """
    not_found = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在"
    )

    img_result = await db.execute(select(Image).where(Image.id == image_id))
    img = img_result.scalar_one_or_none()
    if img is None:
        raise not_found

    if img.task_id is None:
        # 数据异常：图片没绑到任何 task。admin 仍可访问，普通用户拒绝
        if not current_user.is_admin:
            raise not_found
        return img

    task_result = await db.execute(
        select(InspectionTask).where(InspectionTask.id == img.task_id)
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        # task 行被删但 image 留下 —— 同样拒绝（admin 例外）
        if not current_user.is_admin:
            raise not_found
        return img

    if not _is_owner_or_admin(current_user, task.owner_id):
        raise not_found

    return img
