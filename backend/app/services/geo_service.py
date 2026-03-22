from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.geo_utils import pixel_to_gps, calculate_gsd
from app.models import Image
from sqlalchemy import select


class GeoService:
    """GPS坐标服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def convert_detection_to_gps(
        self, image_id: UUID, detections: List[Dict]
    ) -> List[Dict]:
        """
        将检测结果的像素坐标转换为GPS坐标

        Args:
            image_id: 图片ID
            detections: 检测结果列表，每个包含 bbox_center, bbox_width, bbox_height

        Returns:
            添加了geo_latitude, geo_longitude的检测结果
        """
        # 1. 获取图片元数据
        result = await self.db.execute(select(Image).where(Image.id == image_id))
        image = result.scalar_one_or_none()

        if not image or not image.has_gps:
            # 没有GPS信息，返回原始结果
            return detections

        # 2. 转换每个检测结果的坐标
        results_with_gps = []
        for det in detections:
            bbox_center_x = det.get("bbox_center", [0.5, 0.5])[0]
            bbox_center_y = det.get("bbox_center", [0.5, 0.5])[1]

            # 使用geo_utils转换
            lat, lon = pixel_to_gps(
                pixel_x=bbox_center_x,
                pixel_y=bbox_center_y,
                image_width=image.image_width or 4000,
                image_height=image.image_height or 3000,
                photo_lat=image.latitude,
                photo_lon=image.longitude,
                altitude=image.altitude or 50,
                focal_length=image.focal_length or 24,
                sensor_width=image.sensor_width or 13.2,
            )

            det_with_gps = det.copy()
            det_with_gps["geo_latitude"] = lat
            det_with_gps["geo_longitude"] = lon
            results_with_gps.append(det_with_gps)

        return results_with_gps

    def calculate_image_gsd(self, image: Image) -> float:
        """计算图片的地面分辨率"""
        if not image.altitude or not image.focal_length:
            return 0.01  # 默认值 1cm/像素

        return calculate_gsd(
            altitude=image.altitude,
            focal_length=image.focal_length,
            sensor_width=image.sensor_width or 13.2,
            image_width=image.image_width or 4000,
        )
