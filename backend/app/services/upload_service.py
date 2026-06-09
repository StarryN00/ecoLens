import asyncio
import logging
import os
import re
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from PIL import Image as PILImage
from PIL.ExifTags import GPSTAGS, TAGS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Image
from app.services.camera_sensors import resolve_sensor_width
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


# 上传校验常量
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
MAX_BATCH_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_FILES_PER_BATCH = 200
MAX_FILENAME_LENGTH = 200
CHUNK_SIZE = 1024 * 1024  # 1 MB


def _sanitize_filename(filename: str) -> str:
    """剔除路径分隔符和危险字符，限制长度"""
    base = os.path.basename(filename or "")
    safe = re.sub(r"[^\w.\-]", "_", base)
    if not safe:
        safe = "file"
    if len(safe) > MAX_FILENAME_LENGTH:
        # 保留扩展名，截断主名
        root, ext = os.path.splitext(safe)
        ext = ext[:16]
        root = root[: MAX_FILENAME_LENGTH - len(ext)]
        safe = root + ext
    return safe


class UploadService:
    """上传服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        settings = get_settings()
        self.UPLOAD_DIR = settings.UPLOAD_DIR
        self.THUMBNAIL_DIR = settings.THUMBNAIL_DIR
        # 确保目录存在
        Path(self.UPLOAD_DIR).mkdir(exist_ok=True, parents=True)
        Path(self.THUMBNAIL_DIR).mkdir(exist_ok=True, parents=True)

    async def upload_images(self, task_id: UUID, files: List) -> List[dict]:
        """批量上传图片，含类型/大小/真实性校验。

        所有 Image 行先 add 进 session，**仅在最后一次性 commit**，并通过
        UPDATE 把 total_images 一次性增加（不是循环 +1）。这样：

          * Celery 端读到 total_images 时一定能看到全部入库的 image
            （否则上传 + commit + Celery 拿到 task 的窗口里 total_images
            还停留在中间值，会被 processed_images >= total_images 误判
            为 "都处理完了"，提前触发去重；见 #6）
          * 整个批次是 1 个事务，部分失败时不会留下幽灵半成品

        返回 dict 中的 `id` 是写入 DB 后的真实 PK 字符串，调用方应该把
        这批 id 显式传给 trigger_task_processing，避免 worker 再去
        SELECT Image 表撞上未来插入的并发批次。
        """
        if len(files) > MAX_FILES_PER_BATCH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"单次上传图片数不能超过 {MAX_FILES_PER_BATCH} 张",
            )

        results = []
        batch_size_total = 0

        for file in files:
            # 1) 扩展名校验
            safe_filename = _sanitize_filename(file.filename or "")
            ext = os.path.splitext(safe_filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的文件类型: {ext or '<empty>'}",
                )

            # 2) MIME 校验
            content_type = (file.content_type or "").lower()
            if content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的 MIME 类型: {content_type or '<empty>'}",
                )

            image_id = uuid4()
            file_path = f"{self.UPLOAD_DIR}/{image_id}_{safe_filename}"

            # 3) 分块写入 + 边写边校验大小
            written = 0
            # FastAPI 的 UploadFile.read 是协程；测试里也可能传入同步对象
            read_is_async = asyncio.iscoroutinefunction(getattr(file, "read", None))
            try:
                with open(file_path, "wb") as out:
                    while True:
                        if read_is_async:
                            chunk = await file.read(CHUNK_SIZE)
                        else:
                            chunk = file.file.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > MAX_FILE_SIZE:
                            out.close()
                            self._cleanup(file_path)
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail=f"单个文件大小超过 {MAX_FILE_SIZE // (1024 * 1024)}MB 限制",
                            )
                        batch_size_total += len(chunk)
                        if batch_size_total > MAX_BATCH_SIZE:
                            out.close()
                            self._cleanup(file_path)
                            raise HTTPException(
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail=f"批次总大小超过 {MAX_BATCH_SIZE // (1024 * 1024 * 1024)}GB 限制",
                            )
                        out.write(chunk)
            except HTTPException:
                raise
            except Exception as exc:
                self._cleanup(file_path)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"写入文件失败: {exc}",
                )

            # 4) 真实性二次校验：PIL 能否打开 & verify
            if not self._verify_real_image(file_path):
                self._cleanup(file_path)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效图片：文件内容不是合法的 JPEG/PNG",
                )

            # 解析 EXIF
            exif_data = self._parse_exif(file_path)

            # 生成缩略图
            thumbnail_path = f"{self.THUMBNAIL_DIR}/{image_id}.jpg"
            self._create_thumbnail(file_path, thumbnail_path)

            # 数据库记录
            image = Image(
                id=str(image_id),
                task_id=str(task_id),
                filename=safe_filename,
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
                    "filename": safe_filename,
                    "has_gps": image.has_gps,
                    "latitude": image.latitude,
                    "longitude": image.longitude,
                }
            )

        # 一次性更新 total_images，再 commit。不要在循环里每张图都 +1 +
        # commit —— 那样 trigger_task_processing 中间被 enqueue 看到的就
        # 是个不一致的中间态（见 #6）。
        if results:
            task = await TaskService(self.db).get_task(task_id)
            if task is not None:
                task.total_images = (task.total_images or 0) + len(results)
                task.status = "processing"

        await self.db.commit()
        return results

    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    @staticmethod
    def _verify_real_image(path: str) -> bool:
        try:
            with PILImage.open(path) as img:
                img.verify()
            return True
        except Exception:
            return False

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

            xmp_altitude = self._parse_xmp_altitude(img)
            if xmp_altitude is not None:
                data["altitude"] = xmp_altitude

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

                if data["altitude"] is None and "GPSAltitude" in gps_info:
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
                except (ValueError, TypeError):
                    pass

            # 传感器宽度：先用 FocalPlaneXResolution 真实换算，失败回退
            # 到 Make/Model 机型表，都不命中则保持 None（GPS 反算会跳过这
            # 张图）。**绝对不能**硬编 fallback 数值——错误的 sensor_width
            # 会被下游 pixel_to_gps 当成真值用，污染虫巢坐标。
            sensor_width, _source = resolve_sensor_width(exif_data, data["width"])
            data["sensor_width"] = sensor_width

        except Exception as e:
            logger.warning("解析EXIF失败: %s", e)

        return data

    def _parse_xmp_altitude(self, img: PILImage.Image) -> Optional[float]:
        try:
            xmp_data = img.info.get("xmp") or img.info.get("xml")
            if not xmp_data:
                return None

            xmp_str = (
                xmp_data.decode("utf-8", errors="ignore")
                if isinstance(xmp_data, bytes)
                else str(xmp_data)
            )

            match = re.search(r"RelativeAltitude[^>]*>([\d.+-]+)", xmp_str)
            if match:
                return float(match.group(1))

            match = re.search(r'RelativeAltitude=["\']([\d.+-]+)["\']', xmp_str)
            if match:
                return float(match.group(1))

        except Exception as e:
            logger.warning("解析 XMP 高度失败: %s", e)

        return None

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
            logger.warning("生成缩略图失败: %s", e)
