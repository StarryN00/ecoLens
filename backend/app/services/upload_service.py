import os
import shutil
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4
from PIL import Image as PILImage
from PIL.ExifTags import TAGS, GPSTAGS

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Image
from app.services.task_service import TaskService


class UploadService:
    """上传服务"""

    UPLOAD_DIR = "/home/ubuntu/ecoLens/uploads"
    THUMBNAIL_DIR = "/home/ubuntu/ecoLens/thumbnails"

    def __init__(self, db: AsyncSession):
        self.db = db
        # 确保目录存在
        Path(self.UPLOAD_DIR).mkdir(exist_ok=True)
        Path(self.THUMBNAIL_DIR).mkdir(exist_ok=True)

    async def upload_images(self, task_id: UUID, files: List) -> List[dict]:
        """批量上传图片"""
        results = []
        task_service = TaskService(self.db)

        for file in files:
            # 生成唯一ID
            image_id = uuid4()

            # 保存原始文件
            file_path = f"{self.UPLOAD_DIR}/{image_id}_{file.filename}"
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            # 解析EXIF
            exif_data = self._parse_exif(file_path)

            # 生成缩略图
            thumbnail_path = f"{self.THUMBNAIL_DIR}/{image_id}.jpg"
            self._create_thumbnail(file_path, thumbnail_path)

            # 创建数据库记录
            image = Image(
                id=str(image_id),
                task_id=str(task_id),
                filename=file.filename,
                storage_path=file_path,
                latitude=exif_data.get("latitude"),
                longitude=exif_data.get("longitude"),
                altitude=exif_data.get("altitude"),
                focal_length=exif_data.get("focal_length"),
                sensor_width=exif_data.get("sensor_width"),
                capture_time=exif_data.get("capture_time"),
                image_width=exif_data.get("width"),
                image_height=exif_data.get("height"),
                has_gps=exif_data.get("has_gps", False),
            )

            self.db.add(image)
            results.append(
                {
                    "id": image_id,
                    "filename": file.filename,
                    "has_gps": image.has_gps,
                    "latitude": image.latitude,
                    "longitude": image.longitude,
                }
            )

            # 更新任务图片计数
            await task_service.increment_image_count(task_id)

        await self.db.commit()
        return results

    async def list_images(self, task_id, skip: int = 0, limit: int = 50) -> List[Image]:
        """查询图片列表"""
        result = await self.db.execute(
            select(Image).where(Image.task_id == str(task_id)).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def get_image(self, image_id: UUID) -> Optional[Image]:
        """获取单张图片"""
        result = await self.db.execute(select(Image).where(Image.id == image_id))
        return result.scalar_one_or_none()

    def _parse_exif(self, image_path: str) -> dict:
        """解析EXIF元数据"""
        data = {
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "focal_length": None,
            "sensor_width": None,
            "capture_time": None,
            "width": None,
            "height": None,
            "has_gps": False,
        }

        try:
            img = PILImage.open(image_path)
            data["width"] = img.width
            data["height"] = img.height

            exif = img._getexif()
            if not exif:
                return data

            exif_data = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_data[tag] = value

            # 提取GPS信息
            if "GPSInfo" in exif_data:
                gps_info = {}
                for key in exif_data["GPSInfo"].keys():
                    decode = GPSTAGS.get(key, key)
                    gps_info[decode] = exif_data["GPSInfo"][key]

                # 解析经纬度
                if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
                    lat = self._convert_dms(gps_info["GPSLatitude"])
                    if gps_info["GPSLatitudeRef"] == "S":
                        lat = -lat
                    data["latitude"] = lat
                    data["has_gps"] = True

                if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
                    lon = self._convert_dms(gps_info["GPSLongitude"])
                    if gps_info["GPSLongitudeRef"] == "W":
                        lon = -lon
                    data["longitude"] = lon
                    data["has_gps"] = True

                # 高度
                if "GPSAltitude" in gps_info:
                    data["altitude"] = float(gps_info["GPSAltitude"])

            # 焦距
            if "FocalLength" in exif_data:
                data["focal_length"] = float(exif_data["FocalLength"])

            # 拍摄时间
            if "DateTimeOriginal" in exif_data:
                from datetime import datetime

                try:
                    data["capture_time"] = datetime.strptime(
                        exif_data["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S"
                    )
                except:
                    pass

            # 传感器宽度(估算,常见值)
            if "FocalPlaneXResolution" in exif_data:
                # 这里简化处理,实际需要更复杂的计算
                data["sensor_width"] = 13.2  # 默认常见值

        except Exception as e:
            print(f"解析EXIF失败: {e}")

        return data

    def _convert_dms(self, dms) -> float:
        """转换度分秒为十进制度"""
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        return degrees + minutes / 60 + seconds / 3600

    def _create_thumbnail(self, image_path: str, thumbnail_path: str, size=(300, 300)):
        """生成缩略图"""
        try:
            with PILImage.open(image_path) as img:
                img.thumbnail(size)
                img.save(thumbnail_path, "JPEG", quality=85)
        except Exception as e:
            print(f"生成缩略图失败: {e}")
