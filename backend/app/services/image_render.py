"""标注图渲染 —— 在无人机原图上画虫巢检测框。

当前仅供 ``/api/v1/images/{id}/annotated`` 端点生成前端预览图。
Word 巡检报告只导出数据和统计表,不再嵌入标注图片。

本模块是**同步纯 CPU 函数**:调用方负责异步查 DB 把检测框取出来后传入。
"""

from __future__ import annotations

import io

from PIL import Image as PILImage
from PIL import ImageDraw

# 与 T4「虫巢标注框红色加粗」一致:统一红框、线宽 5。
BOX_COLOR = "red"
BOX_WIDTH = 5
# 与 T3 图片压缩一致:JPEG quality 82。
JPEG_QUALITY = 82


def render_annotated_image(storage_path, detections, max_width=1920) -> bytes:
    """在原图上画检测框,按 max_width 压缩,返回 JPEG 字节。

    参数:
      storage_path: 原图文件路径(调用方需先确认文件存在)。
      detections: 检测框对象列表,每个对象需有属性 ——
        bbox_x_center / bbox_y_center / bbox_width / bbox_height(0~1 归一化),
        confidence(float)。
      max_width: >0 时,宽度超过该值则等比缩放到该宽度;<=0 时不缩放
        (返回全分辨率标注图)。

    检测框始终在**原图分辨率**上绘制以保证坐标精度,绘制完成后再缩放。
    """
    image = PILImage.open(storage_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size

    for det in detections:
        # 归一化坐标 -> 像素坐标
        cx = det.bbox_x_center * width
        cy = det.bbox_y_center * height
        bw = det.bbox_width * width
        bh = det.bbox_height * height

        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2

        draw.rectangle([x1, y1, x2, y2], outline=BOX_COLOR, width=BOX_WIDTH)
        # confidence 在模型层可空,缺失时按 0 处理(防 None 格式化崩溃)
        conf = det.confidence if det.confidence is not None else 0.0
        draw.text((x1, y1 - 20), f"{conf:.2%}", fill=BOX_COLOR)

    # 画框完成后按 max_width 统一缩放
    if max_width > 0 and image.width > max_width:
        ratio = max_width / image.width
        image = image.resize(
            (max_width, max(1, int(image.height * ratio))), PILImage.LANCZOS
        )

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()
