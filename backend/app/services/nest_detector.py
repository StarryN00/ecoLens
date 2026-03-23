from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO  # type: ignore
except Exception as e:  # pragma: no cover
    logger.error(f"YOLO导入失败: {e}")
    YOLO = None  # type: ignore

from PIL import Image  # for size extraction


class NestDetector:
    """基于 YOLOv8 的虫巢检测器"""

    def __init__(
        self, model_path: Optional[str] = None, conf_threshold: Optional[float] = None
    ):
        """
        初始化检测器

        :param model_path: 模型权重路径，相对路径将相对于后端根目录解析
        :param conf_threshold: 置信度阈值，默认使用配置中的 CONFIDENCE_THRESHOLD
        """
        settings = get_settings()

        # 模型路径来自参数或配置
        self.model_path: Optional[str] = model_path or getattr(
            settings, "NEST_DETECTION_MODEL_PATH", "./models/nest_det.pt"
        )
        self.conf_threshold: float = (
            conf_threshold
            if conf_threshold is not None
            else getattr(settings, "CONFIDENCE_THRESHOLD", 0.5)
        )

        self._model: Optional[Any] = None
        self._model_loaded: bool = False

        # 计算模型的绝对路径，优先使用传入的绝对路径，其次将相对路径解析为 backend/models 目录下的路径
        self._resolved_model_path = self._resolve_model_path(self.model_path)

    @staticmethod
    def _resolve_model_path(model_path: Optional[str]) -> Optional[str]:
        if not model_path:
            return None
        p = Path(model_path)
        if p.is_absolute():
            return str(p)
        # 基于当前文件位置向上回溯到 backend/ 目录再拼接模型路径
        # nest_detector.py 在 backend/app/services/，parents[2] = backend/
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
            # 使用 YOLOv8 加载模型
            self._model = YOLO(self._resolved_model_path)
            logger.info(f"模型加载成功: {self._resolved_model_path}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            self._model = None

    def detect(self, image_path: str) -> List[Dict[str, Any]]:
        """
        对给定图片进行虫巢检测

        :param image_path: 待检测图片路径
        :return: 符合指定格式的检测结果列表
        """
        self._load_model()

        if self._model is None:
            # 模型不可用，返回空列表
            return []

        # 打开图片以获取尺寸
        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            # 无法打开图片，返回空
            return []

        try:
            # 运行推理
            logger.info(f"开始检测图片: {image_path}")
            results = self._model.predict(
                source=image_path, conf=self.conf_threshold, verbose=False
            )
            logger.info(
                f"检测完成，原始结果数量: {len(results) if isinstance(results, list) else 1}"
            )

            # Ultralytics v8 的结果结构因版本略有不同，做尽量兼容的解析
            detections: List[Dict[str, Any]] = []

            # results 可能是一个列表（多图/多模型返回），遍历处理
            if isinstance(results, list):
                for r in results:
                    boxes = getattr(r, "boxes", None)
                    logger.info(f" boxes对象: {boxes}")
                    if boxes is None:
                        logger.info(f" boxes为None，跳过")
                        continue
                    # 检查boxes是否有数据
                    box_len = len(boxes) if hasattr(boxes, "__len__") else 0
                    logger.info(f" boxes数量: {box_len}")
                    if box_len == 0:
                        continue
                    # boxes.xyxy 是一个 tensor( N, 4 )
                    try:
                        xyxy_list = boxes.xyxy.cpu().numpy()
                        confs = (
                            boxes.conf.cpu().numpy() if hasattr(boxes, "conf") else None
                        )
                        logger.info(
                            f" xyxy_list形状: {xyxy_list.shape}, confs: {confs}"
                        )
                    except Exception as e:
                        logger.error(f" 解析boxes失败: {e}")
                        continue

                    for idx in range(len(xyxy_list)):
                        x1, y1, x2, y2 = xyxy_list[idx].tolist()
                        conf = (
                            float(confs[idx])
                            if confs is not None
                            else float(getattr(boxes, "conf", [0.0])[idx])
                        )

                        # 归一化
                        nx1, ny1, nx2, ny2 = (
                            float(x1) / width,
                            float(y1) / height,
                            float(x2) / width,
                            float(y2) / height,
                        )

                        # 计算中心、宽高（相对值）
                        cx = ((x1 + x2) / 2.0) / width
                        cy = ((y1 + y2) / 2.0) / height
                        bw = (x2 - x1) / width
                        bh = (y2 - y1) / height

                        # 严重程度
                        if conf > 0.8:
                            severity = "severe"
                        elif conf > 0.6:
                            severity = "medium"
                        else:
                            severity = "light"

                        detections.append(
                            {
                                "bbox": [nx1, ny1, nx2, ny2],
                                "confidence": float(conf),
                                "severity": severity,
                                "bbox_center": [float(cx), float(cy)],
                                "bbox_width": float(bw),
                                "bbox_height": float(bh),
                            }
                        )
            return detections
        except Exception:
            # 推理过程异常，返回空列表
            return []


__all__ = ["NestDetector"]
