from __future__ import annotations

import os
from typing import Any, Dict, List, Union

import numpy as np
from PIL import Image


def white_balance_correction(
    image: Union[Image.Image, np.ndarray],
) -> Union[Image.Image, np.ndarray]:
    """
    使用简单的灰度世界算法对图像进行白平衡矫正。

    参数:
        image: PIL.Image.Image 或 numpy.ndarray，RGB 或 RGBA 图像

    返回:
        与输入同类型的校正后图像（若输入为 PIL.Image，则返回 Image；若输入为 ndarray，则返回 ndarray）
    """
    # 将输入统一转换为 numpy 数组以便处理
    if isinstance(image, Image.Image):
        in_pil = True
        img = np.asarray(image)
    elif isinstance(image, np.ndarray):
        in_pil = False
        img = image.copy()
    else:
        raise TypeError("image must be a PIL.Image or numpy.ndarray")

    if img.ndim == 2:
        # 灰度图，不进行处理
        corrected = img
    else:
        # 处理彩色通道（支持 3 通道或 4 通道，4 通道保留透明度）
        if img.shape[2] >= 3:
            rgb = img[..., :3].astype(np.float32)
            # 灰度世界：计算三个通道的均值，取全局平均作为目标亮度
            channel_means = rgb.mean(axis=(0, 1))  # shape (3,)
            avg_mean = float(np.mean(channel_means))
            if avg_mean <= 0:
                avg_mean = 1.0
            # 对前三通道应用缩放因子
            scales = avg_mean / (channel_means + 1e-6)  # shape (3,)
            corrected_rgb = rgb * scales.reshape((1, 1, 3))
            corrected_rgb = np.clip(corrected_rgb, 0, 255).astype(np.uint8)

            if img.shape[2] == 4:
                # 保留 alpha 通道
                alpha = img[..., 3:4]
                corrected = np.concatenate([corrected_rgb, alpha], axis=2)
            else:
                corrected = corrected_rgb
        else:
            corrected = img  # 其他情况原样返回

    if in_pil:
        return Image.fromarray(corrected)
    else:
        return corrected


def slice_image(
    image: Union[Image.Image, np.ndarray],
    slice_size: int = 640,
    overlap: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    将图像切分成大小为 slice_size x slice_size 的小块，带有指定的重叠。

    参数:
        image: PIL.Image.Image 或 numpy.ndarray，RGB 图像
        slice_size: 小块边长，默认 640
        overlap: 重叠比例，0 <= overlap < 1，默认为 0.2（20%）

    返回:
        切片信息列表：[{"slice": tile_array, "x": x, "y": y, "width": w, "height": h}, ...]
    """
    if not (0.0 <= overlap < 1.0):
        raise ValueError("overlap must be in [0, 1)")

    if isinstance(image, Image.Image):
        arr = np.asarray(image)
    elif isinstance(image, np.ndarray):
        arr = image
    else:
        raise TypeError("image must be a PIL.Image or numpy.ndarray")

    h, w = arr.shape[:2]
    stride = int(slice_size * (1 - overlap))
    if stride <= 0:
        stride = 1

    slices: List[Dict[str, Any]] = []
    y = 0
    while y < h:
        if y + slice_size > h:
            y0 = max(h - slice_size, 0)
        else:
            y0 = y
        end_y = min(y0 + slice_size, h)

        x = 0
        while x < w:
            if x + slice_size > w:
                x0 = max(w - slice_size, 0)
            else:
                x0 = x
            end_x = min(x0 + slice_size, w)

            tile = arr[y0:end_y, x0:end_x].copy()
            slices.append(
                {
                    "slice": tile,
                    "x": int(x0),
                    "y": int(y0),
                    "width": int(end_x - x0),
                    "height": int(end_y - y0),
                }
            )
            x += stride
        y += stride

    return slices


def preprocess_image(image_path: str) -> List[Dict[str, Any]]:
    """
    读取图片，应用白平衡，然后进行切片处理。

    返回每个切片的字典，包含 slice、x、y、width、height、original_name 等字段。

    参数:
        image_path: 图片文件路径

    返回:
        切片信息列表，每个元素是一个 dict
    """
    img = Image.open(image_path).convert("RGB")
    wb_img = white_balance_correction(img)
    slices = slice_image(wb_img, slice_size=640, overlap=0.2)

    base_name = os.path.basename(image_path)
    original_name = os.path.splitext(base_name)[0]

    for s in slices:
        s["original_name"] = original_name

    return slices


def save_slices(slices: List[Dict[str, Any]], output_dir: str) -> List[str]:
    """
    将切片保存到输出目录。

    命名格式: {original_name}_slice_{x}_{y}.jpg

    返回:
        保存的文件路径列表
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_paths: List[str] = []

    for s in slices:
        tile = s.get("slice")
        if isinstance(tile, np.ndarray):
            pil = Image.fromarray(tile)
        elif isinstance(tile, Image.Image):
            pil = tile
        else:
            continue

        orig = s.get("original_name", "slice")
        x = s.get("x", 0)
        y = s.get("y", 0)
        filename = f"{orig}_slice_{x}_{y}.jpg"
        path = os.path.join(output_dir, filename)
        pil.save(path)
        saved_paths.append(path)

    return saved_paths


__all__ = [
    "white_balance_correction",
    "slice_image",
    "preprocess_image",
    "save_slices",
]
