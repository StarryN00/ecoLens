from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.services.upload_service import UploadService
from app.models import ImageDetection
from app.tasks.inference_tasks import trigger_task_processing

router = APIRouter(prefix="/api/v1", tags=["images"])


@router.post("/tasks/{task_id}/images")
async def upload_images(
    task_id: str,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """批量上传图片（上传完成后自动触发AI处理）"""
    service = UploadService(db)
    results = await service.upload_images(task_id, files)

    # 自动触发AI处理任务
    if results:
        trigger_task_processing.delay(task_id)

    return {
        "task_id": task_id,
        "uploaded": len(results),
        "images": [
            {
                "id": str(img["id"]),
                "filename": img["filename"],
                "has_gps": img["has_gps"],
                "latitude": img["latitude"],
                "longitude": img["longitude"],
            }
            for img in results
        ],
    }


@router.get("/tasks/{task_id}/images")
async def list_task_images(
    task_id: str, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """查询任务图片列表（包含检测结果）"""
    service = UploadService(db)
    # 使用字符串ID查询
    images = await service.list_images(task_id, skip, limit)

    # 获取所有图片的检测结果
    image_ids = [str(img.id) for img in images]
    detection_result = await db.execute(
        select(ImageDetection).where(ImageDetection.image_id.in_(image_ids))
    )
    detections = detection_result.scalars().all()

    # 构建检测结果字典
    detection_map = {}
    for det in detections:
        detection_map[str(det.image_id)] = {
            "has_camphor_tree": det.has_camphor_tree,
            "has_nest": det.has_nest,
            "nest_count": det.nest_count,
            "max_severity": det.max_severity,
        }

    return {
        "items": [
            {
                "id": str(img.id),
                "filename": img.filename,
                "has_gps": img.has_gps,
                "latitude": img.latitude,
                "longitude": img.longitude,
                "altitude": img.altitude,
                "capture_time": img.capture_time,
                "detection": detection_map.get(str(img.id)),
            }
            for img in images
        ]
    }


@router.get("/images/{image_id}")
async def get_image_file(image_id: str, db: AsyncSession = Depends(get_db)):
    """获取图片文件（原图）"""
    from fastapi.responses import FileResponse
    import os

    service = UploadService(db)
    img = await service.get_image(image_id)

    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")

    if os.path.exists(img.storage_path):
        return FileResponse(img.storage_path, filename=img.filename)

    raise HTTPException(status_code=404, detail="图片文件不存在")


@router.get("/images/{image_id}/info")
async def get_image_info(image_id: str, db: AsyncSession = Depends(get_db)):
    """查询单张图片详情"""
    service = UploadService(db)
    img = await service.get_image(image_id)

    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")

    return {
        "id": str(img.id),
        "task_id": str(img.task_id),
        "filename": img.filename,
        "storage_path": img.storage_path,
        "has_gps": img.has_gps,
        "latitude": img.latitude,
        "longitude": img.longitude,
        "altitude": img.altitude,
        "focal_length": img.focal_length,
        "sensor_width": img.sensor_width,
        "image_width": img.image_width,
        "image_height": img.image_height,
        "capture_time": img.capture_time,
    }


@router.get("/images/{image_id}/thumbnail")
async def get_image_thumbnail(image_id: str, db: AsyncSession = Depends(get_db)):
    """获取图片缩略图（不存在则返回原图）"""
    from fastapi.responses import FileResponse
    import os

    service = UploadService(db)
    img = await service.get_image(image_id)

    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")

    thumbnail_path = f"./thumbnails/{image_id}.jpg"
    if os.path.exists(thumbnail_path):
        return FileResponse(thumbnail_path, filename=f"thumb_{img.filename}")

    # 缩略图不存在，返回原图
    if os.path.exists(img.storage_path):
        return FileResponse(img.storage_path, filename=img.filename)

    raise HTTPException(status_code=404, detail="图片文件不存在")


@router.get("/images/{image_id}/annotated")
async def get_image_annotated(image_id: str, db: AsyncSession = Depends(get_db)):
    """获取带检测框标注的图片"""
    from fastapi.responses import StreamingResponse
    from app.models import RawNestDetection
    from PIL import Image, ImageDraw
    import io
    import os

    # 获取图片信息
    service = UploadService(db)
    img = await service.get_image(image_id)

    if not img:
        raise HTTPException(status_code=404, detail="图片不存在")

    if not os.path.exists(img.storage_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    # 获取检测框数据
    result = await db.execute(
        select(RawNestDetection).where(RawNestDetection.image_id == image_id)
    )
    detections = result.scalars().all()

    # 打开原图
    image = Image.open(img.storage_path)
    draw = ImageDraw.Draw(image)
    width, height = image.size

    # 绘制检测框
    for det in detections:
        # 计算像素坐标（归一化坐标转像素坐标）
        cx = det.bbox_x_center * width
        cy = det.bbox_y_center * height
        bw = det.bbox_width * width
        bh = det.bbox_height * height

        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2

        # 根据严重程度选择颜色
        color_map = {"severe": "red", "medium": "orange", "light": "green"}
        color = color_map.get(det.severity, "blue")

        # 绘制矩形框
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # 绘制置信度文字
        conf_text = f"{det.confidence:.2%}"
        draw.text((x1, y1 - 20), conf_text, fill=color)

    # 保存到内存
    img_io = io.BytesIO()
    image.save(img_io, format="JPEG", quality=90)
    img_io.seek(0)

    return StreamingResponse(img_io, media_type="image/jpeg")
