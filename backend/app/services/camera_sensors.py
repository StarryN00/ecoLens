"""相机传感器宽度解析模块。

为什么单独成文件：upload_service 里硬编码 13.2mm 会让所有非 Phantom4 Pro
机型的 GSD（地面采样距离）算错，进而 pixel_to_gps 反算虫巢坐标也错。
这里提供两级回退：

  1) FocalPlaneXResolution + FocalPlaneResolutionUnit + image_width
     真实计算物理传感器宽度
  2) Make + Model 模糊匹配机型表（DJI/Autel 主流机型）

都不命中则返回 None — 上层会把 sensor_width 留空，GPS 反算会跳过这张图，
**严禁**写死任何 fallback 数值（一旦数值化，下游错误的 GPS 会被当成
"已知数据" 入库，污染后续聚类）。
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# FocalPlaneResolutionUnit 取值 -> 转 mm 的系数
# EXIF 规范：1 = none, 2 = inch, 3 = cm, 4 = mm, 5 = um
_UNIT_TO_MM = {
    2: 25.4,    # inch
    3: 10.0,    # cm
    4: 1.0,     # mm
    5: 0.001,   # micrometer (罕见但定义在规范里)
}

# 物理合理的传感器宽度区间（mm）。低于 2 mm 多半是手机/相机内部
# crop 因子异常，高于 50 mm 多半是 EXIF 单位被报错（实际很少有 > 中
# 画幅 44mm 的无人机相机）。算出超出区间一律视为无效，回退到机型表。
SENSOR_WIDTH_MIN_MM = 2.0
SENSOR_WIDTH_MAX_MM = 50.0


# (make_keyword, model_keywords_list, sensor_width_mm, friendly_name)
# 匹配策略：make 必须包含 make_keyword（小写），model 包含 list 中任意
# 一个关键词即命中。**顺序很重要**：把更具体的 model 关键词放在更通用
# 的前面，否则 "mini" 会先匹配上 "mini 2" 后面那一条。
KNOWN_CAMERA_SENSORS = [
    # ===== DJI 消费级 =====
    ("dji", ["phantom 4 pro v2", "phantom 4 pro", "p4p", "fc6310"], 13.2, "DJI Phantom 4 Pro"),
    ("dji", ["mavic 2 pro", "l1d-20c"], 13.2, "DJI Mavic 2 Pro"),
    # Mavic 3 系列（含 Pro / Enterprise / Multispectral）—— 4/3 CMOS
    ("dji", ["mavic 3 pro", "mavic 3 enterprise", "mavic 3m", "mavic 3", "l2d-20c", "fc4382", "fc4170"], 17.3, "DJI Mavic 3"),
    # Mavic Air 2 / 2S —— 1 英寸主摄按 13.2，但 Air 2 是 1/2 英寸 6.4
    ("dji", ["mavic air 2s", "fc3411"], 13.2, "DJI Mavic Air 2S"),
    ("dji", ["mavic air 2", "fc3170", "fc7303"], 6.4, "DJI Mavic Air 2"),
    # Mini 系列
    ("dji", ["mini 3 pro", "mini 3", "mini 2", "fc7203", "fc8482"], 6.17, "DJI Mini"),
    # ===== DJI 行业级 =====
    # M300 RTK / M350 / M30 主流载荷（H20 / P1 / L1 / L2）—— 这里以 H20T
    # 主载荷的 4/3 CMOS（17.3 mm）为基准；如果用户用了别的载荷，仍然在
    # 同一量级，比硬编 13.2 准
    ("dji", ["matrice 300", "m300", "h20"], 17.3, "DJI M300"),
    ("dji", ["matrice 350", "m350", "matrice 30", "m30"], 17.3, "DJI M350/M30"),
    # Inspire 2 X5S
    ("dji", ["inspire 2", "x5s"], 17.3, "DJI Inspire 2 X5S"),
    # ===== Autel =====
    ("autel", ["evo ii pro", "evo 2 pro"], 13.2, "Autel EVO II Pro"),
]


def _resolve_from_focal_plane(exif_data: dict, image_width: Optional[int]) -> Optional[float]:
    """从 FocalPlaneXResolution + FocalPlaneResolutionUnit 反算物理宽度。

    公式：sensor_width_mm = image_width_px / FocalPlaneXResolution_px_per_unit * unit_to_mm
    返回 None 表示数据不全/无效/超出合理区间。
    """
    if not image_width:
        return None

    fpxr_raw = exif_data.get("FocalPlaneXResolution")
    if fpxr_raw is None:
        return None

    unit = exif_data.get("FocalPlaneResolutionUnit")
    # 规范里 1 = "no absolute unit"，缺失同样无法换算 mm
    unit_to_mm = _UNIT_TO_MM.get(unit) if unit is not None else None
    if unit_to_mm is None:
        return None

    try:
        fpxr = float(fpxr_raw)
    except (TypeError, ValueError):
        return None

    if fpxr <= 0:
        return None

    sensor_width_mm = image_width / fpxr * unit_to_mm

    if not (SENSOR_WIDTH_MIN_MM <= sensor_width_mm <= SENSOR_WIDTH_MAX_MM):
        return None

    return sensor_width_mm


def _resolve_from_make_model(exif_data: dict) -> Tuple[Optional[float], Optional[str]]:
    """从 Make + Model 模糊匹配机型表。返回 (sensor_width, friendly_name)。"""
    make = (exif_data.get("Make") or "")
    model = (exif_data.get("Model") or "")

    # EXIF 字段经常带尾部 \x00 或前后空格，统一清洗
    make_lc = str(make).strip().strip("\x00").lower()
    model_lc = str(model).strip().strip("\x00").lower()

    if not make_lc and not model_lc:
        return None, None

    for make_kw, model_kws, width, friendly in KNOWN_CAMERA_SENSORS:
        if make_kw not in make_lc:
            continue
        for mkw in model_kws:
            if mkw in model_lc:
                return width, friendly

    return None, None


def resolve_sensor_width(
    exif_data: dict,
    image_width: Optional[int],
) -> Tuple[Optional[float], str]:
    """两级回退确定 sensor_width。

    返回 (sensor_width_mm | None, source)，source ∈
    {"focal_plane", "make_model", "unknown"}。
    """
    width_fp = _resolve_from_focal_plane(exif_data, image_width)
    if width_fp is not None:
        return width_fp, "focal_plane"

    width_mm, friendly = _resolve_from_make_model(exif_data)
    if width_mm is not None:
        logger.debug(
            "sensor_width resolved by make/model table: %s -> %.2f mm",
            friendly,
            width_mm,
        )
        return width_mm, "make_model"

    make = (exif_data.get("Make") or "").strip()
    model = (exif_data.get("Model") or "").strip()
    logger.warning(
        "Unknown camera: make=%r model=%r, sensor_width unset, "
        "GPS reverse projection will be skipped for this image",
        make,
        model,
    )
    return None, "unknown"
