from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image  # for size extraction

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import ultralytics.utils.loss as _ultralytics_loss  # type: ignore
    from ultralytics import YOLO  # type: ignore
except Exception as e:  # pragma: no cover
    logger.error(f"YOLO导入失败: {e}")
    YOLO = None  # type: ignore
    _ultralytics_loss = None  # type: ignore


def _install_legacy_ultralytics_compat() -> None:
    """Install shims required to unpickle older YOLO checkpoints.

    Some demo-era weights reference ultralytics.utils.loss.DFLoss. The
    currently pinned ultralytics==8.0.200 no longer exposes that class, but the
    loaded model does not need the training loss object for inference.
    """
    if _ultralytics_loss is None or hasattr(_ultralytics_loss, "DFLoss"):
        return

    class DFLoss:  # pragma: no cover - exercised through checkpoint loading
        pass

    _ultralytics_loss.DFLoss = DFLoss

# ---------------------------------------------------------------------------
# Module-level NMS helpers (no YOLO dependency)
# ---------------------------------------------------------------------------

def _iou(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """IoU for two detections with x1/y1/x2/y2 pixel-coord keys."""
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = (a["x2"] - a["x1"]) * (a["y2"] - a["y1"])
    area_b = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(
    detections: List[Dict[str, Any]], iou_threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """Greedy NMS on dicts with x1/y1/x2/y2/conf keys."""
    detections = sorted(detections, key=lambda d: d["conf"], reverse=True)
    keep: List[Dict[str, Any]] = []
    while detections:
        best = detections.pop(0)
        keep.append(best)
        detections = [d for d in detections if _iou(best, d) < iou_threshold]
    return keep


def _filter_pixel_dets(
    detections: List[Dict[str, Any]],
    width: int,
    height: int,
    min_area_ratio: float,
    min_side_ratio: float,
    max_detections: Optional[int],
) -> List[Dict[str, Any]]:
    """Filter obvious low-value candidate boxes before persisting/displaying.

    The legacy demo model needs a low confidence threshold for recall, so this
    second-stage geometric filter removes tiny leaf-texture hits and caps noisy
    single-image outputs while preserving the highest confidence candidates.
    """
    image_area = max(1, width * height)
    min_side_px = min(width, height) * max(0.0, min_side_ratio)
    out: List[Dict[str, Any]] = []
    for det in detections:
        box_w = max(0.0, det["x2"] - det["x1"])
        box_h = max(0.0, det["y2"] - det["y1"])
        area_ratio = (box_w * box_h) / image_area
        if area_ratio < min_area_ratio:
            continue
        if min(box_w, box_h) < min_side_px:
            continue
        out.append(det)

    out = sorted(out, key=lambda d: d["conf"], reverse=True)
    if max_detections and max_detections > 0:
        out = out[:max_detections]
    return out


class NestDetector:
    """基于 YOLOv8 的虫巢检测器"""

    def __init__(
        self, model_path: Optional[str] = None, conf_threshold: Optional[float] = None
    ):
        settings = get_settings()

        self.model_path: Optional[str] = model_path or getattr(
            settings, "NEST_DETECTION_MODEL_PATH", "./models/nest_det.pt"
        )
        self.conf_threshold: float = (
            conf_threshold
            if conf_threshold is not None
            else getattr(settings, "CONFIDENCE_THRESHOLD", 0.5)
        )
        self.min_bbox_area_ratio: float = getattr(
            settings, "NEST_MIN_BBOX_AREA_RATIO", 0.0002
        )
        self.min_bbox_side_ratio: float = getattr(
            settings, "NEST_MIN_BBOX_SIDE_RATIO", 0.01
        )
        self.max_candidates_per_image: int = getattr(
            settings, "NEST_MAX_CANDIDATES_PER_IMAGE", 30
        )

        self._model: Optional[Any] = None
        self._model_loaded: bool = False

        self._resolved_model_path = self._resolve_model_path(self.model_path)

    @staticmethod
    def _resolve_model_path(model_path: Optional[str]) -> Optional[str]:
        if not model_path:
            return None
        p = Path(model_path)
        if p.is_absolute():
            return str(p)
        backend_root = Path(__file__).resolve().parents[2]
        abs_path = (backend_root / model_path).resolve()
        return str(abs_path)

    def _load_model(self):
        """在首次需要推理时加载模型，若模型不可用则保持 None"""
        if self._model_loaded:
            return

        self._model_loaded = True
        logger.info(f"正在加载虫巢检测模型: {self._resolved_model_path}")

        if not self._resolved_model_path:
            logger.error("模型路径为空")
            self._model = None
            return

        if not os.path.exists(self._resolved_model_path):
            logger.error(f"模型文件不存在: {self._resolved_model_path}")
            self._model = None
            return

        if YOLO is None:
            logger.error("Ultralytics YOLO 未安装")
            self._model = None
            return

        try:
            _install_legacy_ultralytics_compat()
            self._model = YOLO(self._resolved_model_path)
            logger.info(f"模型加载成功: {self._resolved_model_path}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._model = None

    # ------------------------------------------------------------------
    # Shared parsing helpers
    # ------------------------------------------------------------------

    def _parse_yolo_results(
        self, results, offset_x: int, offset_y: int
    ) -> List[Dict[str, Any]]:
        """Parse YOLO result list into pixel-coord dicts shifted by (offset_x, offset_y)."""
        out: List[Dict[str, Any]] = []
        if not isinstance(results, list):
            return out
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            box_len = len(boxes) if hasattr(boxes, "__len__") else 0
            if box_len == 0:
                continue
            try:
                xyxy_list = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy() if hasattr(boxes, "conf") else None
            except Exception as e:
                logger.error(f"解析boxes失败: {e}")
                continue
            for idx in range(len(xyxy_list)):
                x1, y1, x2, y2 = xyxy_list[idx].tolist()
                conf = float(confs[idx]) if confs is not None else 0.5
                out.append({
                    "x1": x1 + offset_x,
                    "y1": y1 + offset_y,
                    "x2": x2 + offset_x,
                    "y2": y2 + offset_y,
                    "conf": conf,
                })
        return out

    @staticmethod
    def _pixel_dets_to_normalized(
        pixel_dets: List[Dict[str, Any]], width: int, height: int
    ) -> List[Dict[str, Any]]:
        """Convert pixel-coord detection dicts to normalized output format."""
        out: List[Dict[str, Any]] = []
        for det in pixel_dets:
            x1, y1, x2, y2, conf = (
                det["x1"], det["y1"], det["x2"], det["y2"], det["conf"]
            )
            nx1, ny1 = x1 / width, y1 / height
            nx2, ny2 = x2 / width, y2 / height
            cx = ((x1 + x2) / 2.0) / width
            cy = ((y1 + y2) / 2.0) / height
            bw = (x2 - x1) / width
            bh = (y2 - y1) / height
            if conf > 0.8:
                severity = "severe"
            elif conf > 0.6:
                severity = "medium"
            else:
                severity = "light"
            out.append({
                "bbox": [nx1, ny1, nx2, ny2],
                "confidence": conf,
                "severity": severity,
                "bbox_center": [cx, cy],
                "bbox_width": bw,
                "bbox_height": bh,
            })
        return out

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, image_path: str) -> List[Dict[str, Any]]:
        """对给定图片进行虫巢检测，大图自动切片以避免 YOLO 缩放漏检小目标。"""
        self._load_model()
        if self._model is None:
            return []

        try:
            with Image.open(image_path) as img:
                img_rgb = img.convert("RGB")
                width, height = img_rgb.size
        except Exception:
            return []

        # For images larger than 640 px on either dimension, use sliced inference
        # so YOLO never has to downscale and miss small targets.
        if max(width, height) > 640:
            logger.info(
                f"图片尺寸 {width}x{height} > 640，启用切片推理: {image_path}"
            )
            return self._detect_sliced(img_rgb, width, height)

        return self._detect_full(image_path, width, height)

    # ------------------------------------------------------------------
    # Internal inference paths
    # ------------------------------------------------------------------

    def _detect_full(
        self, image_path: str, width: int, height: int
    ) -> List[Dict[str, Any]]:
        """Run YOLO on the full image (used only when image fits in 640×640)."""
        try:
            logger.info(f"全图推理: {image_path}")
            results = self._model.predict(
                source=image_path, conf=self.conf_threshold, verbose=False
            )
            pixel_dets = self._parse_yolo_results(results, offset_x=0, offset_y=0)
            pixel_dets = _filter_pixel_dets(
                pixel_dets,
                width,
                height,
                self.min_bbox_area_ratio,
                self.min_bbox_side_ratio,
                self.max_candidates_per_image,
            )
            detections = self._pixel_dets_to_normalized(pixel_dets, width, height)
            logger.info(f"全图推理完成，检测到 {len(detections)} 个目标")
            return detections
        except Exception:
            return []

    def _detect_sliced(
        self, img: Image.Image, width: int, height: int
    ) -> List[Dict[str, Any]]:
        """White-balance → slice → per-tile YOLO → NMS → full-image normalized coords."""
        from app.utils.image_utils import slice_image, white_balance_correction

        wb_img = white_balance_correction(img)
        slices = slice_image(wb_img, slice_size=640, overlap=0.2)
        logger.info(f"切片数量: {len(slices)}")

        all_pixel_dets: List[Dict[str, Any]] = []
        for sl in slices:
            tile_arr = sl["slice"]
            ox, oy = int(sl["x"]), int(sl["y"])
            try:
                results = self._model.predict(
                    source=tile_arr, conf=self.conf_threshold, verbose=False
                )
            except Exception as e:
                logger.error(f"切片推理失败 offset=({ox},{oy}): {e}")
                continue
            all_pixel_dets.extend(
                self._parse_yolo_results(results, offset_x=ox, offset_y=oy)
            )

        logger.info(f"切片推理原始检测数: {len(all_pixel_dets)}")
        merged = _nms(all_pixel_dets, iou_threshold=0.5)
        logger.info(f"NMS 后检测数: {len(merged)}")
        merged = _filter_pixel_dets(
            merged,
            width,
            height,
            self.min_bbox_area_ratio,
            self.min_bbox_side_ratio,
            self.max_candidates_per_image,
        )
        logger.info(f"几何过滤后检测数: {len(merged)}")
        return self._pixel_dets_to_normalized(merged, width, height)


__all__ = ["NestDetector"]
