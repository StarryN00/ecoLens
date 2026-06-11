from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_image, get_owned_task
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Image, ImageDetection, InspectionTask
from app.services.upload_service import UploadService

router = APIRouter(
    prefix="/api/v1",
    tags=["images"],
    dependencies=[Depends(get_current_user)],
)


def _annotated_cache_path(image_id: str, max_width: int) -> Path:
    settings = get_settings()
    return Path(settings.THUMBNAIL_DIR) / f"annotated_{image_id}_{max_width}.jpg"


def _is_annotated_cache_fresh(cache_path: Path, img: Image, detections) -> bool:
    if not cache_path.exists():
        return False

    cache_mtime = cache_path.stat().st_mtime
    try:
        if cache_mtime < Path(img.storage_path).stat().st_mtime:
            return False
    except FileNotFoundError:
        # If the original is gone but a cached preview exists, serving it is
        # still cheaper and more useful than failing the list thumbnail.
        return True

    for det in detections:
        if det.created_at and cache_mtime < det.created_at.timestamp():
            return False
    return True


def _write_annotated_cache(cache_path: Path, jpeg_bytes: bytes) -> None:
    cache_path.parent.mkdir(exist_ok=True, parents=True)
    tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")
    tmp_path.write_bytes(jpeg_bytes)
    tmp_path.replace(cache_path)


@router.post("/tasks/{task_id}/images")
async def upload_images(
    files: List[UploadFile] = File(...),
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """批量上传图片（上传完成后自动触发AI处理）。

    ownership：通过 get_owned_task 校验，无权访问的非 owner 看到 404
    "任务不存在"，与不存在共用同一响应（防资源枚举）。
    """
    if task.status == "processing" or (
        task.status == "uploading" and (task.total_images or 0) > 0
    ):
        raise HTTPException(
            status_code=409,
            detail="任务正在处理图片，请等待当前处理完成后再追加上传",
        )

    service = UploadService(db)
    results = await service.upload_images(str(task.id), files)

    # commit 已经发生在 upload_images 内部；把入库后的真实 image_id 列表
    # 显式传给 trigger_task_processing，worker 端不再 SELECT Image 表
    # （避免上传/触发之间的事务窗口里看到旧 total_images）。见 #6。
    if results:
        from app.tasks.inference_tasks import trigger_task_processing

        image_ids = [str(img["id"]) for img in results]
        trigger_task_processing.delay(str(task.id), image_ids)

    return {
        "task_id": str(task.id),
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
    skip: int = 0,
    limit: int = 50,
    task: InspectionTask = Depends(get_owned_task),
    db: AsyncSession = Depends(get_db),
):
    """查询任务图片列表（包含检测结果）。ownership 已校验。"""
    service = UploadService(db)
    # 使用字符串ID查询
    images = await service.list_images(str(task.id), skip, limit)

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
                "created_at": img.created_at,
                "detection": detection_map.get(str(img.id)),
            }
            for img in images
        ]
    }


@router.get("/images/{image_id}")
async def get_image_file(
    img: Image = Depends(get_owned_image),
    max_width: int = 1920,
):
    """获取图片。ownership 通过 get_owned_image 校验。

    T3 图片压缩：**默认**返回宽度上限 1920px 的压缩版（JPEG quality≈82），
    无人机原图常达 10-20MB，压缩后通常 200-800KB，前端加载快一个数量级。
    - `max_width=0`：返回未压缩原图（"查看原图"用）
    - `max_width>0`：宽度超过该值才缩放，否则直接发原文件省一次重编码
    - `max_width<0`：拒绝（400），防止 resize 计算出非法尺寸导致 500

    用 inline 而非 attachment：浏览器 / antd Image / blob URL 流程都把它
    当成图片直接渲染。
    """
    import io
    import os

    from fastapi.responses import FileResponse, StreamingResponse
    from PIL import Image as PILImage

    if max_width < 0:
        raise HTTPException(status_code=400, detail="max_width 不能为负数")

    if not os.path.exists(img.storage_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    def _original():
        return FileResponse(
            img.storage_path,
            filename=img.filename,
            content_disposition_type="inline",
        )

    # 显式要原图
    if max_width == 0:
        return _original()

    pil = PILImage.open(img.storage_path)
    # 原图本就不超过上限 → 直接发原文件，避免无谓重编码
    if pil.width <= max_width:
        return _original()

    # 等比缩放到 max_width 宽 + JPEG 压缩
    ratio = max_width / pil.width
    pil = pil.convert("RGB").resize(
        (max_width, max(1, int(pil.height * ratio))), PILImage.LANCZOS
    )
    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=82, optimize=True)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


@router.get("/images/{image_id}/info")
async def get_image_info(img: Image = Depends(get_owned_image)):
    """查询单张图片详情。ownership 已校验。"""
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
async def get_image_thumbnail(img: Image = Depends(get_owned_image)):
    """获取图片缩略图（不存在则返回原图）。ownership 已校验。"""
    import os

    from fastapi.responses import FileResponse

    thumbnail_path = f"./thumbnails/{img.id}.jpg"
    if os.path.exists(thumbnail_path):
        return FileResponse(
            thumbnail_path,
            filename=f"thumb_{img.filename}",
            content_disposition_type="inline",
        )

    # 缩略图不存在，返回原图
    if os.path.exists(img.storage_path):
        return FileResponse(
            img.storage_path,
            filename=img.filename,
            content_disposition_type="inline",
        )

    raise HTTPException(status_code=404, detail="图片文件不存在")


@router.get("/images/{image_id}/annotated")
async def get_image_annotated(
    img: Image = Depends(get_owned_image),
    db: AsyncSession = Depends(get_db),
    max_width: int = 1920,
):
    """获取带检测框标注的图片。ownership 已校验。

    T3 图片压缩：检测框始终在**原图分辨率**上绘制以保证坐标精度，绘制
    完成后再按 max_width 统一缩放。
    - `max_width=0`：标注后的全分辨率图
    - `max_width>0`（默认 1920）：标注后缩放到该宽度上限
    - `max_width<0`：拒绝（400）
    """
    import io
    import os

    from fastapi.responses import FileResponse, StreamingResponse

    from app.models import RawNestDetection
    from app.services.image_render import render_annotated_image

    if max_width < 0:
        raise HTTPException(status_code=400, detail="max_width 不能为负数")

    # 获取检测框数据
    result = await db.execute(
        select(RawNestDetection).where(RawNestDetection.image_id == str(img.id))
    )
    detections = result.scalars().all()

    cache_path = None
    if max_width > 0:
        cache_path = _annotated_cache_path(str(img.id), max_width)
        if _is_annotated_cache_fresh(cache_path, img, detections):
            return FileResponse(
                cache_path,
                filename=f"annotated_{img.filename}",
                content_disposition_type="inline",
                media_type="image/jpeg",
            )

    if not os.path.exists(img.storage_path):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    # 渲染逻辑统一在 image_render.render_annotated_image
    jpeg_bytes = render_annotated_image(
        img.storage_path, detections, max_width=max_width
    )
    if cache_path is not None:
        _write_annotated_cache(cache_path, jpeg_bytes)
    return StreamingResponse(io.BytesIO(jpeg_bytes), media_type="image/jpeg")
