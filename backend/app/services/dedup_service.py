from typing import List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.utils.dedup_utils import deduplicate_nests, generate_nest_code
from app.models import RawNestDetection, UniqueNest


class DedupService:
    """虫巢去重服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def deduplicate_task_nests(
        self, task_id: UUID, eps_meters: float = 3.0
    ) -> List[Dict]:
        """
        对任务的所有原始检测结果进行去重

        Args:
            task_id: 任务ID
            eps_meters: DBSCAN聚类半径（米）

        Returns:
            去重后的虫巢列表
        """
        # 1. 获取该任务的所有原始检测结果
        result = await self.db.execute(
            select(RawNestDetection).where(RawNestDetection.task_id == task_id)
        )
        raw_detections = result.scalars().all()

        if not raw_detections:
            return []

        # 2. 转换为去重工具需要的格式
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

        # 3. 调用DBSCAN去重
        unique_nests_data = deduplicate_nests(
            detections=detections_for_dedup, eps_meters=eps_meters, min_samples=1
        )

        # 4. 生成虫巢编号
        for i, nest in enumerate(unique_nests_data):
            nest["nest_code"] = generate_nest_code(str(task_id), i + 1)
            nest["task_id"] = task_id

        return unique_nests_data

    async def save_unique_nests(self, task_id: UUID, unique_nests: List[Dict]) -> int:
        """
        保存去重后的虫巢到数据库

        Args:
            task_id: 任务ID
            unique_nests: 去重后的虫巢列表

        Returns:
            保存的虫巢数量
        """
        # 1. 清空该任务的旧去重结果
        await self.db.execute(delete(UniqueNest).where(UniqueNest.task_id == task_id))

        # 2. 保存新的去重结果
        count = 0
        for nest_data in unique_nests:
            unique_nest = UniqueNest(
                task_id=task_id,
                nest_code=nest_data["nest_code"],
                latitude=nest_data["latitude"],
                longitude=nest_data["longitude"],
                severity=nest_data["severity"],
                confidence=nest_data["confidence"],
                detection_count=nest_data["detection_count"],
                source_images=nest_data["source_images"],
            )
            self.db.add(unique_nest)
            count += 1

        await self.db.commit()
        return count
