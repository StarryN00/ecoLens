"""
测试工具函数
"""

import pytest
import math
from app.utils.geo_utils import pixel_to_gps, calculate_gsd
from app.utils.dedup_utils import deduplicate_nests, generate_nest_code


class TestGeoUtils:
    """测试GPS工具函数"""

    def test_pixel_to_gps(self):
        """测试像素坐标转GPS"""
        # 测试数据
        pixel_x, pixel_y = 0.5, 0.5  # 图片中心
        image_width, image_height = 4000, 3000
        photo_lat, photo_lon = 30.2567, 120.1234
        altitude = 100  # 100米高度
        focal_length = 24  # 24mm焦距
        sensor_width = 13.2  # 传感器宽度

        lat, lon = pixel_to_gps(
            pixel_x,
            pixel_y,
            image_width,
            image_height,
            photo_lat,
            photo_lon,
            altitude,
            focal_length,
            sensor_width,
        )

        # 中心点应该接近拍摄点
        assert abs(lat - photo_lat) < 0.0001
        assert abs(lon - photo_lon) < 0.0001

    def test_calculate_gsd(self):
        """测试地面分辨率计算"""
        gsd = calculate_gsd(
            altitude=100, focal_length=24, sensor_width=13.2, image_width=4000
        )

        # GSD应该为正数
        assert gsd > 0
        # 100米高度,24mm焦距,GSD应该在合理范围
        assert 0.01 < gsd < 1  # 约0.01375米/像素


class TestDedupUtils:
    """测试去重工具函数"""

    def test_deduplicate_nests_basic(self):
        """测试基本去重功能"""
        detections = [
            {
                "lat": 30.2567,
                "lon": 120.1234,
                "confidence": 0.9,
                "severity": "medium",
                "image_id": "img1",
            },
            {
                "lat": 30.25671,  # 距离很近(约1米)
                "lon": 120.12341,
                "confidence": 0.85,
                "severity": "medium",
                "image_id": "img2",
            },
            {
                "lat": 30.26,  # 距离较远(约500米)
                "lon": 120.13,
                "confidence": 0.8,
                "severity": "light",
                "image_id": "img3",
            },
        ]

        result = deduplicate_nests(detections, eps_meters=3.0)

        # 应该合并为2个(前两个很近合并,第三个独立)
        assert len(result) == 2

        # 检查第一个簇(合并前两个)
        first_cluster = result[0]
        assert first_cluster["detection_count"] == 2
        assert first_cluster["confidence"] == 0.9  # 取最大值

    def test_deduplicate_nests_empty(self):
        """测试空列表"""
        result = deduplicate_nests([])
        assert result == []

    def test_deduplicate_nests_single(self):
        """测试单条数据"""
        detections = [
            {
                "lat": 30.2567,
                "lon": 120.1234,
                "confidence": 0.9,
                "severity": "medium",
                "image_id": "img1",
            }
        ]

        result = deduplicate_nests(detections)
        assert len(result) == 1
        assert result[0]["detection_count"] == 1

    def test_generate_nest_code(self):
        """测试虫巢编号生成"""
        code = generate_nest_code("task-123", 1)

        # 格式: NEST-YYYYMMDD-001
        assert code.startswith("NEST-")
        assert len(code) == 17  # NEST-YYYYMMDD-XXX
        assert code.endswith("-001")

    def test_severity_priority(self):
        """测试严重程度优先级"""
        detections = [
            {
                "lat": 30.2567,
                "lon": 120.1234,
                "confidence": 0.8,
                "severity": "light",
                "image_id": "img1",
            },
            {
                "lat": 30.256701,
                "lon": 120.123401,
                "confidence": 0.85,
                "severity": "severe",  # 严重
                "image_id": "img2",
            },
            {
                "lat": 30.256702,
                "lon": 120.123402,
                "confidence": 0.82,
                "severity": "medium",
                "image_id": "img3",
            },
        ]

        result = deduplicate_nests(detections)

        # 应该取最严重的级别
        assert result[0]["severity"] == "severe"
