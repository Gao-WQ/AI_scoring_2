# -*- coding: utf-8 -*-
"""图像公共操作：加载、颜色量化、逐笔分离、骨架化、端点/交叉点提取。

统一约定：图像以 RGB numpy 数组（H,W,3, uint8）表示；二值掩膜为 (H,W) bool/uint8。
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize


def load_image(path: str) -> np.ndarray:
    """从文件加载图像为 RGB ndarray。"""
    return np.asarray(Image.open(path).convert("RGB"))


def image_from_bytes(data: bytes) -> np.ndarray:
    """从字节流加载图像为 RGB ndarray（用于 openpyxl 嵌入图）。"""
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))


def resize_keep_ratio(image: np.ndarray, target: int) -> np.ndarray:
    """等比缩放到最长边为 target（保持纵横比）。"""
    h, w = image.shape[:2]
    scale = target / max(h, w)
    if scale >= 1.0:
        return image
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def quantize_colors(image: np.ndarray, n_colors: int = 8) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """颜色量化：KMeans 聚类主色，返回 (标签图, 主色列表[RGB])。

    用于把笔画主色与抗锯齿过渡色归并，输出标签图每像素为 0..k-1 的主色索引。
    """
    pixels = image.reshape(-1, 3).astype(np.float32)
    _, labels, centers = cv2.kmeans(
        pixels, n_colors, None,
        criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0),
        attempts=3, flags=cv2.KMEANS_PP_CENTERS,
    )
    label_map = labels.reshape(image.shape[:2]).astype(np.uint8)
    colors = [tuple(int(c) for c in center) for center in centers]
    return label_map, colors


def separate_by_color(image: np.ndarray, n_colors: int = 8) -> dict[int, np.ndarray]:
    """按颜色分离笔画：返回 {主色索引: 该色像素掩膜(H,W,bool)}。

    背景（白色）像素占比最大的主色视为背景并剔除。
    """
    label_map, colors = quantize_colors(image, n_colors=n_colors)
    total = label_map.size
    counts = {k: int(np.sum(label_map == k)) for k in range(n_colors)}
    bg_index = max(counts, key=counts.get)
    strokes = {k: (label_map == k) for k in range(n_colors) if k != bg_index and counts[k] > 0}
    return strokes


def stroke_count(image: np.ndarray, n_colors: int = 8) -> int:
    """笔画数：按颜色分离后的非背景主色数（笔画数异常的快速检测）。"""
    return len(separate_by_color(image, n_colors=n_colors))


def to_binary(mask: np.ndarray) -> np.ndarray:
    """掩膜转二值 uint8（前景 255 / 背景 0），供骨架化使用。"""
    return (np.asarray(mask) > 0).astype(np.uint8) * 255


def skeleton_of(mask: np.ndarray) -> np.ndarray:
    """骨架化：输入前景掩膜(H,W,bool)，输出骨架掩膜(H,W,bool)。"""
    return skeletonize(np.asarray(mask) > 0)


def endpoints_of(skeleton: np.ndarray) -> list[tuple[int, int]]:
    """骨架端点：8 邻域中前景邻居数为 1 的像素坐标 (y, x)。"""
    skel = np.asarray(skeleton) > 0
    pad = np.pad(skel, 1, mode="constant")
    endpoints = []
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
    for y in range(1, pad.shape[0] - 1):
        for x in range(1, pad.shape[1] - 1):
            if pad[y, x]:
                window = pad[y - 1:y + 2, x - 1:x + 2] * kernel
                if window.sum() == 1:
                    endpoints.append((y - 1, x - 1))
    return endpoints


def intersections_of(skeleton: np.ndarray) -> list[tuple[int, int]]:
    """骨架交叉点：8 邻域中前景邻居数 >= 3 的像素坐标 (y, x)。"""
    skel = np.asarray(skeleton) > 0
    pad = np.pad(skel, 1, mode="constant")
    crossings = []
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
    for y in range(1, pad.shape[0] - 1):
        for x in range(1, pad.shape[1] - 1):
            if pad[y, x]:
                window = pad[y - 1:y + 2, x - 1:x + 2] * kernel
                if window.sum() >= 3:
                    crossings.append((y - 1, x - 1))
    return crossings
