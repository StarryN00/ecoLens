import math
from typing import Tuple


def pixel_to_gps(
    pixel_x: float,
    pixel_y: float,
    image_width: int,
    image_height: int,
    photo_lat: float,
    photo_lon: float,
    altitude: float,
    focal_length: float,
    sensor_width: float,
) -> Tuple[float, float]:
    """
    将图像上的像素坐标转换为GPS地理坐标

    参数:
        pixel_x, pixel_y: 像素坐标 (0~1 相对值)
        image_width, image_height: 图片尺寸（像素）
        photo_lat, photo_lon: 拍摄点GPS坐标
        altitude: 航拍高度（米）
        focal_length: 焦距（毫米）
        sensor_width: 传感器宽度（毫米）

    返回:
        (latitude, longitude): 虫巢地理坐标
    """
    # 地面分辨率 (米/像素)
    gsd = (altitude * sensor_width) / (focal_length * image_width)

    # 像素偏移量（相对图片中心）
    dx_pixels = (pixel_x - 0.5) * image_width
    dy_pixels = (pixel_y - 0.5) * image_height

    # 转为地面距离（米）
    dx_meters = dx_pixels * gsd
    dy_meters = dy_pixels * gsd

    # 转为经纬度偏移
    delta_lat = dy_meters / 111320
    delta_lon = dx_meters / (111320 * math.cos(math.radians(photo_lat)))

    nest_lat = photo_lat - delta_lat  # 图片y轴向下，纬度向上
    nest_lon = photo_lon + delta_lon

    return nest_lat, nest_lon


def calculate_gsd(
    altitude: float, focal_length: float, sensor_width: float, image_width: int
) -> float:
    """
    计算地面分辨率(GSD)

    参数:
        altitude: 航拍高度（米）
        focal_length: 焦距（毫米）
        sensor_width: 传感器宽度（毫米）
        image_width: 图片宽度（像素）

    返回:
        GSD（米/像素）
    """
    return (altitude * sensor_width) / (focal_length * image_width)


def bbox_center_to_pixel(
    bbox_x_center: float, bbox_y_center: float
) -> Tuple[float, float]:
    """
    将相对bbox中心坐标转为像素坐标

    参数:
        bbox_x_center: 相对x坐标 (0~1)
        bbox_y_center: 相对y坐标 (0~1)

    返回:
        (pixel_x, pixel_y): 像素坐标 (0~1)
    """
    return bbox_x_center, bbox_y_center
