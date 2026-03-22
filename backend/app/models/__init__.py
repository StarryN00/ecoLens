"""
SQLite 兼容的数据库模型
移除了 PostgreSQL 特有的 UUID 和 PostGIS Geometry 类型
用于本地快速开发和测试
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Boolean,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


def generate_uuid():
    """生成字符串 UUID"""
    return str(uuid.uuid4())


class InspectionTask(Base):
    """巡检任务表"""

    __tablename__ = "inspection_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_name = Column(String(200), nullable=False)
    area_name = Column(String(200))
    operator = Column(String(100))
    status = Column(
        String(20), default="uploading"
    )  # uploading/processing/completed/failed
    total_images = Column(Integer, default=0)
    processed_images = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)


class Image(Base):
    """图片元数据表"""

    __tablename__ = "images"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("inspection_tasks.id"))
    filename = Column(String(500), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    focal_length = Column(Float)
    sensor_width = Column(Float)
    capture_time = Column(DateTime)
    image_width = Column(Integer)
    image_height = Column(Integer)
    has_gps = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())


class ImageDetection(Base):
    """图片级检测结果表"""

    __tablename__ = "image_detections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    image_id = Column(String(36), ForeignKey("images.id"))
    task_id = Column(String(36), ForeignKey("inspection_tasks.id"))
    has_camphor_tree = Column(Boolean, default=False)
    has_nest = Column(Boolean, default=False)
    nest_count = Column(Integer, default=0)
    max_severity = Column(String(20))  # light/medium/severe
    inference_time_ms = Column(Integer)
    model_version = Column(String(50))
    created_at = Column(DateTime, default=func.now())


class RawNestDetection(Base):
    """虫巢原始检测表(去重前)"""

    __tablename__ = "raw_nest_detections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    image_id = Column(String(36), ForeignKey("images.id"))
    task_id = Column(String(36), ForeignKey("inspection_tasks.id"))
    # 像素坐标(相对值0~1)
    bbox_x_center = Column(Float, nullable=False)
    bbox_y_center = Column(Float, nullable=False)
    bbox_width = Column(Float, nullable=False)
    bbox_height = Column(Float, nullable=False)
    # 反算后的GPS坐标
    geo_latitude = Column(Float)
    geo_longitude = Column(Float)
    # 注：SQLite 不支持 Geometry，用普通 Float 存储
    # geo_point = Column(Geometry("POINT", srid=4326))
    # 检测属性
    confidence = Column(Float)
    severity = Column(String(20))  # light/medium/severe
    created_at = Column(DateTime, default=func.now())


class UniqueNest(Base):
    """去重后的唯一虫巢表"""

    __tablename__ = "unique_nests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("inspection_tasks.id"))
    nest_code = Column(String(50), nullable=False)  # NEST-20260307-001
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # geo_point = Column(Geometry("POINT", srid=4326))
    severity = Column(String(20), nullable=False)
    confidence = Column(Float)
    detection_count = Column(Integer, default=1)
    # source_images = Column(ARRAY(Text))  # SQLite 不支持 ARRAY，用 JSON 字符串
    source_images = Column(Text)  # JSON 格式存储
    created_at = Column(DateTime, default=func.now())
