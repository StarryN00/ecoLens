"""单元测试 resolve_sensor_width。

覆盖三条路径：
 1) FocalPlaneXResolution 真实换算（合理 / 超界回退 / unit 缺失）
 2) Make+Model 机型表（DJI 系列代号、大小写、空格）
 3) 完全未知 -> (None, "unknown")
"""

import pytest

from app.services.camera_sensors import (
    KNOWN_CAMERA_SENSORS,
    SENSOR_WIDTH_MAX_MM,
    SENSOR_WIDTH_MIN_MM,
    resolve_sensor_width,
)

# ---------- focal_plane 路径 ----------

def test_focal_plane_out_of_range_high_inch_fallbacks():
    """4000 / 2400 * 25.4 ≈ 42.3 mm（在区间内？不，刚好 < 50）。
    我们用更极端的 2400 让它确实超界，但 42.3 实际 < 50，所以这里
    用 1000 / 25.4 配合得到 ~101 mm，应被判无效 -> 走 make_model；
    此处又没给 make/model，所以最终 unknown。
    """
    exif = {
        "FocalPlaneXResolution": 1000.0,
        "FocalPlaneResolutionUnit": 2,  # inch
        # image_width = 4000 px -> 4000/1000*25.4 = 101.6 mm 超出 50
    }
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert width is None
    assert source == "unknown"


def test_focal_plane_out_of_range_huge_fallbacks():
    """4000/400*25.4 = 254 mm 明显无效 -> 回退；无 make/model -> unknown"""
    exif = {"FocalPlaneXResolution": 400.0, "FocalPlaneResolutionUnit": 2}
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert width is None
    assert source == "unknown"


def test_focal_plane_out_of_range_300_fallbacks():
    """4000/300*25.4 ≈ 338 mm，无效 -> unknown"""
    exif = {"FocalPlaneXResolution": 300.0, "FocalPlaneResolutionUnit": 2}
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert width is None
    assert source == "unknown"


def test_focal_plane_valid_mm_unit_hits_first_tier():
    """unit=4 (mm)，image_width=2400 / FPXR=181.82 ≈ 13.2 mm 命中第一级"""
    # 2400 / 181.818... = 13.2
    exif = {"FocalPlaneXResolution": 2400.0 / 13.2, "FocalPlaneResolutionUnit": 4}
    width, source = resolve_sensor_width(exif, image_width=2400)
    assert width == pytest.approx(13.2, rel=1e-3)
    assert source == "focal_plane"


def test_focal_plane_unit_missing_skips_to_makemodel():
    """unit 缺失但有可识别 model -> 走 make_model"""
    exif = {
        "FocalPlaneXResolution": 9999.0,
        # 无 FocalPlaneResolutionUnit
        "Make": "DJI",
        "Model": "FC6310",
    }
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert width == pytest.approx(13.2)
    assert source == "make_model"


def test_focal_plane_zero_value_skips():
    """FPXR=0 是非法，跳过到下一级"""
    exif = {
        "FocalPlaneXResolution": 0.0,
        "FocalPlaneResolutionUnit": 2,
        "Make": "DJI",
        "Model": "FC6310",
    }
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert source == "make_model"
    assert width == pytest.approx(13.2)


# ---------- make_model 路径 ----------

def test_dji_phantom_4_pro_fc6310():
    exif = {"Make": "DJI", "Model": "FC6310"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(13.2)
    assert source == "make_model"


def test_dji_mavic_3_pro_l2d20c():
    exif = {"Make": "DJI", "Model": "L2D-20c"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(17.3)
    assert source == "make_model"


def test_dji_mavic_3_full_name_match():
    """Model 字段直接写 'Mavic 3 Pro' 也得命中 17.3"""
    exif = {"Make": "DJI", "Model": "Mavic 3 Pro"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(17.3)
    assert source == "make_model"


def test_dji_mini_3_fc7203():
    exif = {"Make": "DJI", "Model": "FC7203"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(6.17)
    assert source == "make_model"


def test_dji_mavic_air_2_fc3170():
    exif = {"Make": "DJI", "Model": "FC3170"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(6.4)
    assert source == "make_model"


def test_autel_evo_ii_pro():
    exif = {"Make": "Autel Robotics", "Model": "EVO II Pro"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(13.2)
    assert source == "make_model"


def test_mixed_case_with_whitespace_and_null():
    """实际 EXIF 里 Make/Model 经常有前后空格、混合大小写、尾部 \\x00"""
    exif = {"Make": "  DJI \x00", "Model": "  FC6310 \x00"}
    width, source = resolve_sensor_width(exif, image_width=None)
    assert width == pytest.approx(13.2)
    assert source == "make_model"


# ---------- unknown 路径 ----------

def test_completely_unknown_camera_returns_none():
    exif = {"Make": "Acme", "Model": "X1"}
    width, source = resolve_sensor_width(exif, image_width=4000)
    assert width is None
    assert source == "unknown"


def test_empty_exif_returns_unknown():
    width, source = resolve_sensor_width({}, image_width=None)
    assert width is None
    assert source == "unknown"


def test_unknown_does_not_fall_back_to_hardcoded_132():
    """守门测试：哪怕 image_width 给了，无 make/model 也不能返回 13.2"""
    width, source = resolve_sensor_width({"Make": "Foo", "Model": "Bar"}, image_width=4000)
    assert width is None
    assert source == "unknown"


# ---------- 表完整性自检 ----------

def test_known_sensors_widths_within_physical_range():
    """所有表里的 sensor_width 都应在合理物理区间内"""
    for _make_kw, _model_kws, width, friendly in KNOWN_CAMERA_SENSORS:
        assert SENSOR_WIDTH_MIN_MM <= width <= SENSOR_WIDTH_MAX_MM, (
            f"{friendly} width {width} out of physical range"
        )
