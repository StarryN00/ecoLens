import numpy as np
from sklearn.cluster import DBSCAN
from typing import List, Dict


def deduplicate_nests(
    detections: List[Dict], eps_meters: float = 3.0, min_samples: int = 1
) -> List[Dict]:
    """
    基于地理坐标的虫巢去重

    参数:
        detections: [{lat, lon, confidence, severity, image_id}, ...]
        eps_meters: 聚类半径（米）
        min_samples: 最小样本数

    返回:
        去重后的虫巢列表
    """
    if not detections:
        return []

    # 提取坐标
    coords = np.array([[d["lat"], d["lon"]] for d in detections])
    coords_rad = np.radians(coords)

    # eps 转为弧度: eps_meters / 地球半径
    eps_rad = eps_meters / 6371000

    # DBSCAN聚类
    clustering = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine").fit(
        coords_rad
    )

    # 按簇聚合
    unique_nests = []
    for cluster_id in set(clustering.labels_):
        mask = clustering.labels_ == cluster_id
        cluster_dets = [d for d, m in zip(detections, mask) if m]

        # 严重程度排序
        severity_order = {"light": 1, "medium": 2, "severe": 3}

        unique_nests.append(
            {
                "latitude": float(np.mean([d["lat"] for d in cluster_dets])),
                "longitude": float(np.mean([d["lon"] for d in cluster_dets])),
                "confidence": max(d["confidence"] for d in cluster_dets),
                "severity": max(
                    [d["severity"] for d in cluster_dets],
                    key=lambda s: severity_order.get(s, 0),
                ),
                "source_images": list(set(d["image_id"] for d in cluster_dets)),
                "detection_count": len(cluster_dets),
            }
        )

    return unique_nests


def generate_nest_code(task_id: str, index: int) -> str:
    """
    生成虫巢编号

    格式: NEST-YYYYMMDD-XXX
    """
    from datetime import datetime

    date_str = datetime.now().strftime("%Y%m%d")
    return f"NEST-{date_str}-{index:03d}"
