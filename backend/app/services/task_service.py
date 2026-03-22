from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from uuid import UUID

from app.models import InspectionTask


class TaskService:
    """任务服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        task_name: str,
        area_name: Optional[str] = None,
        operator: Optional[str] = None,
    ) -> InspectionTask:
        """创建巡检任务"""
        task = InspectionTask(
            task_name=task_name,
            area_name=area_name,
            operator=operator,
            status="uploading",
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id) -> Optional[InspectionTask]:
        """获取任务详情"""
        # 处理 UUID 或字符串类型的 task_id
        task_id_str = str(task_id)
        result = await self.db.execute(
            select(InspectionTask).where(InspectionTask.id == task_id_str)
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self, skip: int = 0, limit: int = 20, status: Optional[str] = None
    ) -> List[InspectionTask]:
        """查询任务列表"""
        query = select(InspectionTask).order_by(desc(InspectionTask.created_at))

        if status:
            query = query.where(InspectionTask.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_task_status(
        self, task_id: UUID, status: str, processed_images: Optional[int] = None
    ) -> bool:
        """更新任务状态"""
        task = await self.get_task(task_id)
        if not task:
            return False

        task.status = status
        if processed_images is not None:
            task.processed_images = processed_images

        await self.db.commit()
        return True

    async def delete_task(self, task_id: UUID) -> bool:
        """删除任务"""
        task = await self.get_task(task_id)
        if not task:
            return False

        await self.db.delete(task)
        await self.db.commit()
        return True

    async def increment_image_count(self, task_id) -> bool:
        """增加图片计数"""
        task = await self.get_task(task_id)
        if not task:
            return False

        task.total_images = task.total_images + 1
        await self.db.commit()
        return True

    async def increment_processed_images(self, task_id) -> bool:
        """增加已处理图片计数"""
        task = await self.get_task(task_id)
        if not task:
            return False

        task.processed_images = task.processed_images + 1
        await self.db.commit()
        return True
