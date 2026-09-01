# -*- coding: utf-8 -*-
"""逐笔骨架分析（业务层）：对单笔掩膜做骨架化并提取笔画级几何量。

复用 common/image_utils 的骨架化/端点/交叉点原语；本模块负责组装笔画几何特征，
供 features.py 的「笔画规范」维度逐笔比对使用。

笔画几何量：
  - length           骨架像素数（笔画长度代理）
  - width_mean/std   中轴距离变换 ×2（笔画粗细均值/方差）
  - direction_hist   相邻骨架点方向直方图（8 bins，归一化）
  - main_direction   直方图峰值 bin 对应的角度（弧度，0~π）
  - curvature_proxy  方向分散度 = 1 - 峰值占比（越直越接近 0）
  - endpoints/intersections  端点/交叉点坐标
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from skimage.morphology import medial_axis

from common.image_utils import endpoints_of, intersections_of, skeleton_of

N_BINS = 8
NEIGHBOR_DIST = 1.5  # 相邻骨架点判定距离（像素）


def analyze_stroke(mask: np.ndarray) -> dict:
    """分析单笔掩膜，返回笔画几何特征字典。"""
    binary = np.asarray(mask) > 0
    skeleton = skeleton_of(binary)
    pts = np.argwhere(skeleton)

    if len(pts) == 0:
        return {
            "length": 0,
            "width_mean": 0.0,
            "width_std": 0.0,
            "direction_hist": np.zeros(N_BINS, dtype=float),
            "main_direction": 0.0,
            "curvature_proxy": 0.0,
            "endpoints": [],
            "intersections": [],
        }

    # 宽度：中轴距离变换
    _, distance = medial_axis(binary, return_distance=True)
    widths = distance[skeleton] * 2.0

    # 方向直方图：相邻骨架点连线角度（用 cKDTree 找近邻）
    tree = cKDTree(pts)
    angles: list[float] = []
    for i, (y, x) in enumerate(pts):
        neighbors = tree.query_ball_point([y, x], NEIGHBOR_DIST)
        for j in neighbors:
            if j <= i:
                continue
            ny, nx = pts[j]
            dy, dx = ny - y, nx - x
            if dy == 0 and dx == 0:
                continue
            angles.append(np.arctan2(abs(dy), abs(dx)))  # 0(横) ~ pi/2(竖)
    hist, _ = np.histogram(angles or [0.0], bins=N_BINS, range=(0.0, np.pi / 2))
    hist = hist.astype(float)
    total = hist.sum()
    if total > 0:
        hist /= total
    peak_bin = int(np.argmax(hist))

    return {
        "length": int(len(pts)),
        "width_mean": float(widths.mean()),
        "width_std": float(widths.std()),
        "direction_hist": hist,
        "main_direction": float((peak_bin + 0.5) * (np.pi / 2) / N_BINS),
        "curvature_proxy": float(1.0 - hist[peak_bin]),
        "endpoints": endpoints_of(skeleton),
        "intersections": intersections_of(skeleton),
    }


def stroke_vector(stroke: dict) -> np.ndarray:
    """笔画几何 → 定长向量（供逐笔距离计算）：[方向, 长度, 宽度均值, 宽度方差, 曲率, 端点数]。"""
    return np.array(
        [
            stroke["main_direction"],
            stroke["length"],
            stroke["width_mean"],
            stroke["width_std"],
            stroke["curvature_proxy"],
            len(stroke["endpoints"]),
        ],
        dtype=float,
    )
