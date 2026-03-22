import os
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from typing import Tuple

# 尝试从项目配置中导入常量
try:
    from app.core.config import get_settings

    settings = get_settings()
    TREE_CLASSIFICATION_MODEL_PATH = getattr(
        settings, "TREE_CLASSIFICATION_MODEL_PATH", "./models/tree_seg.pt"
    )
    TREE_DETECTION_THRESHOLD = getattr(settings, "TREE_DETECTION_THRESHOLD", 0.05)
    CAMPHOR_TREE_CLASS_ID = getattr(settings, "CAMPHOR_TREE_CLASS_ID", 1)
except Exception:
    # 回退默认值，确保模块可独立导入测试
    TREE_CLASSIFICATION_MODEL_PATH = "./models/tree_seg.pt"
    TREE_DETECTION_THRESHOLD = 0.05
    CAMPHOR_TREE_CLASS_ID = 1


class TreeClassifier:
    """
    DeepLabV3+-style tree segmentation classifier with a simple decision rule.

    classify(image_path) -> (has_camphor_tree: bool, camphor_ratio: float, segmentation_mask: np.ndarray)
    - has_camphor_tree: 是否检测到香樟树
    - camphor_ratio: 图像中香樟树分割区域占比 (0-1)
    - segmentation_mask: 分割掩码 (numpy.ndarray, 0/1 或 类别ID掩码，取决于模型输出)
    """

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.model_ready = False
        self._load_model()

        # 统一的输入变换（尽量不依赖于具体模型训练细节，兼容性友好）
        self.transform = transforms.Compose(
            [
                transforms.Resize((512, 512)),
                transforms.ToTensor(),
            ]
        )

    def _load_model(self):
        path = TREE_CLASSIFICATION_MODEL_PATH
        if not path:
            self.model_ready = False
            self.model = None
            return

        if not os.path.isabs(path):
            # 相对路径转绝对路径，基于当前工作目录
            path = os.path.abspath(path)

        if not os.path.exists(path):
            self.model_ready = False
            self.model = None
            return

        try:
            # 尝试加载为 TorchScript
            self.model = torch.jit.load(path)
            self.model.to(self.device)
            self.model.eval()
            self.model_ready = True
            return
        except Exception:
            pass

        try:
            # 尝试加载 state dict / 传统模型
            self.model = torch.load(path, map_location=self.device)
            self.model.eval()
            self.model_ready = True
            return
        except Exception:
            self.model_ready = False
            self.model = None

    def classify(self, image_path: str) -> Tuple[bool, float, np.ndarray]:
        """
        执行推理，并返回三元组：
        (has_camphor_tree: bool, camphor_ratio: float, segmentation_mask: np.ndarray)

        模式：
        - 模型可用时，返回实际推理的结果
        - 模型不可用/加载失败时，进入模拟模式，返回全零掩码和 0.0 的比例
        """
        # 读取图像尺寸，作为分割掩码的尺寸基准
        try:
            image = Image.open(image_path).convert("RGB")
            width, height = image.size
        except Exception:
            # 图像无法打开，返回默认的模拟结果
            height, width = 224, 224
            image = None

        if not self.model_ready or image is None:
            # 模拟模式：不依赖模型
            segmentation_mask = np.zeros((height, width), dtype=np.uint8)
            camphor_ratio = 0.0
            has_camphor_tree = False
            return bool(has_camphor_tree), float(camphor_ratio), segmentation_mask

        # 模型推理路径
        try:
            # 对输入进行预处理
            input_tensor = self.transform(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                output = self.model(input_tensor)

            segmentation_mask = None
            if isinstance(output, torch.Tensor):
                # 常见输出形状处理：
                # - (1, C, H, W) -> 取 argmax
                # - (1, H, W) 或 (C, H, W) -> 解释为单通道或多通道
                if output.dim() == 4:
                    seg = output[0].argmax(dim=0)
                    segmentation_mask = seg.cpu().numpy().astype(np.uint8)
                elif output.dim() == 3:
                    if output.shape[0] == 1:
                        seg = (output[0] > 0.5).cpu().numpy().astype(np.uint8)
                        segmentation_mask = seg
                    else:
                        seg = output.argmax(dim=0)
                        segmentation_mask = seg.cpu().numpy().astype(np.uint8)
                else:
                    segmentation_mask = (output > 0.5).cpu().numpy().astype(np.uint8)

            if segmentation_mask is None:
                segmentation_mask = np.zeros((height, width), dtype=np.uint8)

            camphor_pixels = int((segmentation_mask > 0).sum())
            total_pixels = segmentation_mask.size
            camphor_ratio = camphor_pixels / total_pixels if total_pixels > 0 else 0.0
            has_camphor_tree = camphor_ratio >= TREE_DETECTION_THRESHOLD
            return bool(has_camphor_tree), float(camphor_ratio), segmentation_mask
        except Exception:
            # 推理异常，回退到模拟模式的输出以确保健壮
            segmentation_mask = np.zeros((height, width), dtype=np.uint8)
            return False, 0.0, segmentation_mask


__all__ = ["TreeClassifier"]
