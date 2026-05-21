"""
SQLite 兼容的数据库模型
移除了 PostgreSQL 特有的 UUID 和 PostGIS Geometry 类型
用于本地快速开发和测试
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


def generate_uuid():
    """生成字符串 UUID"""
    return str(uuid.uuid4())


class User(Base):
    """系统用户表"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Region(Base):
    """行政区域表 —— 市 / 区 / 街镇 三级树形结构（T1 多级目录架构）。

    - level: 'city' | 'district' | 'town'，三级
    - parent_id: 自引用外键。city 的 parent_id 为 NULL；district 指向 city；
      town 指向 district。
    - full_path: 冗余存完整路径 "上海市/浦东新区/陆家嘴街道"，方便任务列表 /
      详情 / 报告直接展示，不必每次回溯父链。
    巡检任务挂在 level=='town' 的叶子节点上（API 层强制）。
    """

    __tablename__ = "regions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    level = Column(String(10), nullable=False)  # city / district / town
    parent_id = Column(
        String(36), ForeignKey("regions.id"), nullable=True, index=True
    )
    full_path = Column(String(500))
    created_at = Column(DateTime, default=func.now())

    # remote_side=[id] 指明自引用的"一"端是 id
    parent = relationship("Region", remote_side=[id], backref="children")


class InspectionTask(Base):
    """巡检任务表"""

    __tablename__ = "inspection_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_name = Column(String(200), nullable=False)
    area_name = Column(String(200))
    operator = Column(String(100))
    # 资源 ownership：任务必须有创建者（M2 ownership enforcement）。
    # 模型层 NOT NULL —— 对新库 init_db 直接建对；对存量库由
    # scripts/add_missing_indexes.py 把现存任务回填给第一个 admin
    # 后再 ALTER COLUMN（Postgres）/ 跳过约束（SQLite 不支持 ADD CONSTRAINT）。
    owner_id = Column(
        String(36), ForeignKey("users.id"), index=True, nullable=False
    )
    owner = relationship("User")
    plot_area_mu = Column(Float, nullable=True)
    forestry_sub_compartment = Column(String(50), nullable=True)
    # T1 多级目录：任务挂在 town 级区域上。模型层 nullable=True（存量任务
    # 没有 region 且无法回填）；"创建任务必须选完整三级" 由 API 层强制。
    region_id = Column(
        String(36), ForeignKey("regions.id"), index=True, nullable=True
    )
    region = relationship("Region")
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
    # P1 #11：外键加索引，加速 WHERE task_id=? 和 IN (image_ids) 查询
    task_id = Column(
        String(36), ForeignKey("inspection_tasks.id"), index=True
    )
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
    # P1 #11：外键加索引
    image_id = Column(String(36), ForeignKey("images.id"), index=True)
    task_id = Column(
        String(36), ForeignKey("inspection_tasks.id"), index=True
    )
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
    # P1 #11：外键加索引
    image_id = Column(String(36), ForeignKey("images.id"), index=True)
    task_id = Column(
        String(36), ForeignKey("inspection_tasks.id"), index=True
    )
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
    # P1 #11：外键加索引
    task_id = Column(
        String(36), ForeignKey("inspection_tasks.id"), index=True
    )
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
