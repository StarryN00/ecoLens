"""
测试工具函数
"""

import pytest
import math
from app.utils.geo_utils import pixel_to_gps, calculate_gsd, bbox_center_to_pixel
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


class TestPixelToGpsPrecision:
    """精确数学验证：pixel_to_gps 坐标偏移方向和量级"""

    # 共用参数
    ALT = 100.0        # 米
    FL = 24.0          # mm
    SW = 13.2          # mm
    W, H = 4000, 3000  # pixels
    LAT, LON = 30.0, 120.0

    def _call(self, px, py):
        return pixel_to_gps(px, py, self.W, self.H, self.LAT, self.LON,
                             self.ALT, self.FL, self.SW)

    def test_center_returns_photo_coords(self):
        lat, lon = self._call(0.5, 0.5)
        assert lat == pytest.approx(self.LAT, abs=1e-9)
        assert lon == pytest.approx(self.LON, abs=1e-9)

    def test_left_pixel_west_of_center(self):
        _, lon_left = self._call(0.0, 0.5)
        _, lon_center = self._call(0.5, 0.5)
        assert lon_left < lon_center

    def test_right_pixel_east_of_center(self):
        _, lon_right = self._call(1.0, 0.5)
        _, lon_center = self._call(0.5, 0.5)
        assert lon_right > lon_center

    def test_top_pixel_north_of_center(self):
        # image y=0 is top → in real world that's further north
        # (dy_meters negative → delta_lat negative → lat increases)
        lat_top, _ = self._call(0.5, 0.0)
        lat_center, _ = self._call(0.5, 0.5)
        assert lat_top > lat_center

    def test_bottom_pixel_south_of_center(self):
        lat_bot, _ = self._call(0.5, 1.0)
        lat_center, _ = self._call(0.5, 0.5)
        assert lat_bot < lat_center

    def test_gsd_determines_offset_magnitude(self):
        # GSD = (100 * 13.2) / (24 * 4000) = 0.01375 m/px
        expected_gsd = (self.ALT * self.SW) / (self.FL * self.W)
        # half-width offset in x: 2000 px * gsd = 27.5 m
        expected_dx_m = 0.5 * self.W * expected_gsd
        # delta_lon in degrees: dx_m / (111320 * cos(lat))
        expected_dlon = expected_dx_m / (111320 * math.cos(math.radians(self.LAT)))
        _, lon_right = self._call(1.0, 0.5)
        assert lon_right - self.LON == pytest.approx(expected_dlon, rel=1e-6)

    def test_higher_altitude_larger_footprint(self):
        # Use left-edge pixel so the x-offset (longitude) is nonzero
        _, lon_low = pixel_to_gps(0.0, 0.5, self.W, self.H, self.LAT, self.LON,
                                   50.0, self.FL, self.SW)
        _, lon_high = pixel_to_gps(0.0, 0.5, self.W, self.H, self.LAT, self.LON,
                                    200.0, self.FL, self.SW)
        # bigger footprint → corner longitude is farther from center
        assert abs(lon_high - self.LON) > abs(lon_low - self.LON)

    def test_bbox_center_to_pixel_passthrough(self):
        px, py = bbox_center_to_pixel(0.3, 0.7)
        assert px == 0.3
        assert py == 0.7


class TestDeduplicateNestsEdgeCases:
    """额外边界用例：全合并、source_images 去重、多簇计数"""

    def _det(self, lat, lon, conf=0.9, sev="medium", img="img1"):
        return {"lat": lat, "lon": lon, "confidence": conf,
                "severity": sev, "image_id": img}

    def test_all_within_eps_becomes_one_cluster(self):
        detections = [
            self._det(30.0000, 120.0000, img="a"),
            self._det(30.0000, 120.0000, img="b"),  # identical point
            self._det(30.0000, 120.0001, img="c"),  # ~9 m east, within 10 m eps
        ]
        result = deduplicate_nests(detections, eps_meters=10.0)
        assert len(result) == 1
        assert result[0]["detection_count"] == 3

    def test_source_images_deduplicated(self):
        # Same image contributes two nearby detections → only one image_id in source_images
        detections = [
            self._det(30.0, 120.0, img="img42"),
            self._det(30.0, 120.0000001, img="img42"),
        ]
        result = deduplicate_nests(detections, eps_meters=5.0)
        assert len(result) == 1
        assert result[0]["source_images"] == ["img42"]

    def test_three_distinct_clusters(self):
        detections = [
            self._det(30.0, 120.0),         # cluster A
            self._det(30.001, 120.001),      # cluster B (~140 m away)
            self._det(30.002, 120.002),      # cluster C (~280 m away)
        ]
        result = deduplicate_nests(detections, eps_meters=5.0)
        assert len(result) == 3

    def test_mean_coordinates_of_merged_cluster(self):
        detections = [
            self._det(30.0000, 120.0000, img="a"),
            self._det(30.0000, 120.0000, img="b"),
        ]
        result = deduplicate_nests(detections, eps_meters=5.0)
        assert len(result) == 1
        assert result[0]["latitude"] == pytest.approx(30.0, abs=1e-9)
        assert result[0]["longitude"] == pytest.approx(120.0, abs=1e-9)

    def test_confidence_is_max_of_cluster(self):
        detections = [
            self._det(30.0, 120.0, conf=0.6, img="a"),
            self._det(30.0, 120.0000001, conf=0.95, img="b"),
        ]
        result = deduplicate_nests(detections, eps_meters=5.0)
        assert result[0]["confidence"] == pytest.approx(0.95)


class TestEndToEndPipeline:
    """集成用例：pixel_to_gps → deduplicate_nests 全流程"""

    def test_pixel_to_gps_then_dedup_merges_same_nest(self):
        # Two images overlapping the same area both detect the same nest
        # at slightly different pixel coordinates → should merge after dedup
        common_params = dict(
            image_width=4000, image_height=3000,
            photo_lat=30.0, photo_lon=120.0,
            altitude=100.0, focal_length=24.0, sensor_width=13.2,
        )
        # Detection from image A: nest at pixel center
        lat_a, lon_a = pixel_to_gps(0.5, 0.5, **common_params)
        # Detection from image B: same nest, 1 pixel off (subgsd error)
        lat_b, lon_b = pixel_to_gps(0.5001, 0.5001, **common_params)

        detections = [
            {"lat": lat_a, "lon": lon_a, "confidence": 0.9,
             "severity": "medium", "image_id": "img_a"},
            {"lat": lat_b, "lon": lon_b, "confidence": 0.85,
             "severity": "light", "image_id": "img_b"},
        ]
        result = deduplicate_nests(detections, eps_meters=3.0)
        assert len(result) == 1, "Same nest seen from two images should merge"
        assert result[0]["detection_count"] == 2
        assert set(result[0]["source_images"]) == {"img_a", "img_b"}
        assert result[0]["severity"] == "medium"  # max severity wins

    def test_pixel_to_gps_then_dedup_keeps_distant_nests_separate(self):
        common_params = dict(
            image_width=4000, image_height=3000,
            photo_lat=30.0, photo_lon=120.0,
            altitude=100.0, focal_length=24.0, sensor_width=13.2,
        )
        # Nest at top-left corner
        lat_a, lon_a = pixel_to_gps(0.1, 0.1, **common_params)
        # Nest at bottom-right corner (many meters away)
        lat_b, lon_b = pixel_to_gps(0.9, 0.9, **common_params)

        detections = [
            {"lat": lat_a, "lon": lon_a, "confidence": 0.9,
             "severity": "severe", "image_id": "img_a"},
            {"lat": lat_b, "lon": lon_b, "confidence": 0.88,
             "severity": "light", "image_id": "img_b"},
        ]
        result = deduplicate_nests(detections, eps_meters=3.0)
        assert len(result) == 2, "Nests far apart must remain separate"
