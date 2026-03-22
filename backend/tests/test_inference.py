import pytest
import numpy as np
from PIL import Image
import io
import tempfile
import os

from app.services.nest_detector import NestDetector
from app.services.tree_classifier import TreeClassifier
from app.services.geo_service import GeoService
from app.services.dedup_service import DedupService
from app.utils.image_utils import (
    white_balance_correction,
    slice_image,
    preprocess_image,
    save_slices,
)
from app.utils.geo_utils import pixel_to_gps, calculate_gsd
from app.utils.dedup_utils import deduplicate_nests, generate_nest_code


class TestImageUtils:
    """图像处理工具测试"""

    def test_white_balance_correction(self):
        """测试白平衡校正"""
        # 创建测试图像
        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)

        result = white_balance_correction(img_array)

        assert result.shape == img_array.shape
        assert result.dtype == np.uint8

    def test_slice_image(self):
        """测试图像切片"""
        img_array = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        slices = slice_image(img_array, slice_size=640, overlap=0.2)

        assert len(slices) >= 1
        assert "slice" in slices[0]
        assert "x" in slices[0]
        assert "y" in slices[0]
        assert "width" in slices[0]
        assert "height" in slices[0]

    def test_preprocess_image(self, tmp_path):
        """测试图像预处理"""
        # 创建临时图片
        img = Image.new("RGB", (1000, 1000), color="red")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        slices = preprocess_image(str(img_path))

        assert len(slices) > 0
        for s in slices:
            assert "original_name" in s
            assert s["original_name"] == "test"

    def test_save_slices(self, tmp_path):
        """测试保存切片"""
        slices = [
            {
                "slice": np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8),
                "x": 0,
                "y": 0,
                "original_name": "test",
            }
        ]

        output_dir = tmp_path / "slices"
        saved_paths = save_slices(slices, str(output_dir))

        assert len(saved_paths) == 1
        assert os.path.exists(saved_paths[0])


class TestGeoUtils:
    """GPS工具测试"""

    def test_calculate_gsd(self):
        """测试地面分辨率计算"""
        gsd = calculate_gsd(
            altitude=100,  # 100米高度
            focal_length=24,  # 24mm焦距
            sensor_width=13.2,  # 传感器宽度
            image_width=4000,  # 4000像素
        )

        assert gsd > 0
        # GSD ≈ 0.01375 米/像素 (约1.4cm/像素)
        assert 0.01 < gsd < 0.02

    def test_pixel_to_gps(self):
        """测试像素转GPS"""
        lat, lon = pixel_to_gps(
            pixel_x=0.5,
            pixel_y=0.5,
            image_width=4000,
            image_height=3000,
            photo_lat=30.25,
            photo_lon=120.15,
            altitude=100,
            focal_length=24,
            sensor_width=13.2,
        )

        # 中心点应该接近拍摄点
        assert abs(lat - 30.25) < 0.001
        assert abs(lon - 120.15) < 0.001


class TestDedupUtils:
    """去重工具测试"""

    def test_deduplicate_nests(self):
        """测试DBSCAN去重"""
        detections = [
            {
                "lat": 30.25,
                "lon": 120.15,
                "confidence": 0.9,
                "severity": "severe",
                "image_id": "img1",
            },
            {
                "lat": 30.25001,
                "lon": 120.15001,
                "confidence": 0.8,
                "severity": "medium",
                "image_id": "img2",
            },
            {
                "lat": 30.26,
                "lon": 120.16,
                "confidence": 0.7,
                "severity": "light",
                "image_id": "img3",
            },
        ]

        result = deduplicate_nests(detections, eps_meters=3.0)

        # 前两个点距离很近(约1.5米)，应该被聚类为一个
        assert len(result) <= 2

        # 检查结果字段
        if result:
            assert "latitude" in result[0]
            assert "longitude" in result[0]
            assert "confidence" in result[0]
            assert "severity" in result[0]
            assert "source_images" in result[0]
            assert "detection_count" in result[0]

    def test_generate_nest_code(self):
        """测试虫巢编号生成"""
        code = generate_nest_code("task123", 1)

        assert code.startswith("NEST-")
        assert code.endswith("-001")


class TestNestDetector:
    """虫巢检测器测试"""

    def test_init_without_model(self):
        """测试无模型时的初始化"""
        detector = NestDetector(model_path="/nonexistent/path.pt")

        # 应该能够初始化，但模型为None
        assert detector._model is None

    def test_detect_without_model(self, tmp_path):
        """测试无模型时的检测"""
        detector = NestDetector(model_path="/nonexistent/path.pt")

        # 创建临时图片
        img = Image.new("RGB", (640, 480), color="blue")
        img_path = tmp_path / "test.jpg"
        img.save(img_path)

        result = detector.detect(str(img_path))

        # 无模型时应返回空列表
        assert result == []


class TestTreeClassifier:
    """树种分类器测试"""

    def test_init_without_model(self):
        """测试无模型时的初始化"""
        classifier = TreeClassifier()

        # 应该能够初始化
        assert hasattr(classifier, "classify")

    def test_classify_without_model(self, tmp_path):
        """测试无模型时的分类"""
        classifier = TreeClassifier()
        classifier.model_ready = False  # 强制模拟模式

        # 创建临时图片
        img = Image.new("RGB", (512, 512), color="green")
        img_path = tmp_path / "tree.jpg"
        img.save(img_path)

        has_camphor, ratio, mask = classifier.classify(str(img_path))

        # 模拟模式下应返回False和0.0
        assert has_camphor is False
        assert ratio == 0.0
        assert mask.shape[0] > 0 and mask.shape[1] > 0


class TestServicesIntegration:
    """服务集成测试"""

    @pytest.mark.asyncio
    async def test_geo_service_mock(self):
        """测试GPS服务（模拟）"""
        # 这里需要模拟数据库会话
        # 实际测试需要在有数据库的环境下运行
        pass

    @pytest.mark.asyncio
    async def test_dedup_service_mock(self):
        """测试去重服务（模拟）"""
        # 这里需要模拟数据库会话
        # 实际测试需要在有数据库的环境下运行
        pass
