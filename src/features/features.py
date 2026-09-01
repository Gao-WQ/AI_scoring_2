# -*- coding: utf-8 -*-
"""六维特征提取（业务层）：从分割图提取六维代理量，并提供每维「与满分锚点的偏差距离」。

特征分两类：
  - 绝对特征（layout）：位置/占格/结构分布/留白熵，直接以画布为参考系计算
  - 笔画级特征（per_stroke）：逐笔几何（方向/长度/宽度/曲率），供「笔画规范/衔接位置」逐笔比对

feature_distance(a, b, dim) 定义每维偏差：0 = 与满分锚点完全一致，值越大越差。
笔画数不匹配时返回 1e9（极大偏差），由上层按「笔画数异常」处理。
"""
from __future__ import annotations

import math

import numpy as np

from features.skeleton import analyze_stroke, stroke_vector
from features.stroke_separate import separate_strokes

PIX = np.pi / 2.0  # 方向角范围 0(横)~pi/2(竖)


def extract_features(image: np.ndarray, n_colors: int = 8, min_area: int = 8) -> dict:
    """提取单样本六维特征。返回 {n_strokes, per_stroke, layout}。"""
    strokes = separate_strokes(image, n_colors=n_colors, min_area=min_area)
    per_stroke = [analyze_stroke(s["mask"]) for s in strokes]
    layout = _layout_features(image, strokes)
    return {"n_strokes": len(strokes), "per_stroke": per_stroke, "layout": layout}


def _layout_features(image: np.ndarray, strokes: list[dict]) -> dict:
    """画布参考系下的绝对特征：外接框/位置/占格/四宫格/密度熵/空白。"""
    h, w = image.shape[:2]
    glyph = np.zeros((h, w), dtype=bool)
    for s in strokes:
        glyph |= s["mask"]
    ys, xs = np.nonzero(glyph)

    if len(ys) == 0:
        return {
            "bbox_area_ratio": 0.0, "aspect_dev": 1.0, "center_offset": 1.0,
            "margin_asym": 1.0, "quad": np.zeros(4), "density_entropy": 0.0,
            "void_ratio": 0.0,
        }

    top, bottom = ys.min(), ys.max()
    left, right = xs.min(), xs.max()
    bbox_h, bbox_w = bottom - top + 1, right - left + 1
    canvas_area = float(h * w)
    bbox_area = float(bbox_h * bbox_w)

    center_y = (top + bottom) / 2.0
    center_x = (left + right) / 2.0
    canvas_cy, canvas_cx = (h - 1) / 2.0, (w - 1) / 2.0
    center_offset = math.hypot((center_y - canvas_cy) / h, (center_x - canvas_cx) / w)

    margins = np.array([top, h - 1 - bottom, left, w - 1 - right], dtype=float)
    margin_asym = float(margins.std() / max(margins.mean(), 1.0))

    area_ratio = bbox_area / canvas_area
    aspect = bbox_w / bbox_h if bbox_h > 0 else 0.0
    canvas_aspect = w / h
    aspect_dev = abs(aspect - canvas_aspect) / max(canvas_aspect, 1e-6)

    # 四宫格墨迹占比（左右/上下划分）
    mid_y, mid_x = (top + bottom) / 2.0, (left + right) / 2.0
    quad = np.array(
        [
            glyph[top : int(mid_y) + 1, left : int(mid_x) + 1].sum(),
            glyph[top : int(mid_y) + 1, int(mid_x) : right + 1].sum(),
            glyph[int(mid_y) : bottom + 1, left : int(mid_x) + 1].sum(),
            glyph[int(mid_y) : bottom + 1, int(mid_x) : right + 1].sum(),
        ],
        dtype=float,
    )
    quad_total = quad.sum()
    quad = quad / quad_total if quad_total > 0 else np.zeros(4)

    # 密度熵：8×8 分块墨迹占比的熵
    density_entropy = _block_entropy(glyph)

    # 空白：外接框内字形外空白占比（字内空洞 proxy）
    glyph_total = float(glyph.sum())
    bbox_pixels = bbox_h * bbox_w
    void_ratio = float(max(0.0, bbox_pixels - glyph_total) / max(bbox_pixels, 1))

    return {
        "bbox_area_ratio": area_ratio,
        "aspect_dev": aspect_dev,
        "center_offset": center_offset,
        "margin_asym": margin_asym,
        "quad": quad,
        "density_entropy": density_entropy,
        "void_ratio": void_ratio,
    }


def _block_entropy(glyph: np.ndarray, blocks: int = 8) -> float:
    """分块墨迹占比的信息熵（越均匀越接近 0；分布越散越大）。"""
    h, w = glyph.shape
    hist = np.zeros(blocks * blocks, dtype=float)
    bh, bw = h / blocks, w / blocks
    for i in range(blocks):
        for j in range(blocks):
            block = glyph[int(i * bh) : int((i + 1) * bh), int(j * bw) : int((j + 1) * bw)]
            hist[i * blocks + j] = block.mean()
    total = hist.sum()
    if total <= 0:
        return 0.0
    p = hist / total
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def stroke_topology(feats: dict) -> dict:
    """笔画衔接拓扑量：总端点数、总交叉点数、悬空率。

    dangling_ratio = 端点数 / (端点数 + 2×交叉点数)，0=全部相接/闭合，1=全部悬空。
    相比单对端点距离更稳健：整图统计，不依赖“哪对端点该接”的配对先验。
    """
    endpoint_count = int(sum(len(s["endpoints"]) for s in feats["per_stroke"]))
    intersection_count = int(sum(len(s["intersections"]) for s in feats["per_stroke"]))
    denominator = endpoint_count + 2 * intersection_count
    dangling_ratio = endpoint_count / denominator if denominator > 0 else 1.0
    return {
        "endpoint_count": endpoint_count,
        "intersection_count": intersection_count,
        "dangling_ratio": dangling_ratio,
    }


def feature_distance(a: dict, b: dict, dim: str) -> float:
    """样本特征 a 与参考特征 b（满分锚点）在 dim 维度上的偏差距离。0 = 完全一致。"""
    if a["n_strokes"] != b["n_strokes"]:
        return 1e9
    if dim == "D":  # 笔画规范：逐笔几何加权偏差
        total, count = 0.0, 0
        for sa, sb in zip(a["per_stroke"], b["per_stroke"]):
            va, vb = stroke_vector(sa), stroke_vector(sb)
            d = np.array(
                [
                    abs(va[0] - vb[0]) / PIX,
                    abs(va[1] - vb[1]) / max(va[1], vb[1], 1.0),
                    abs(va[2] - vb[2]) / max(va[2], vb[2], 1e-6),
                    abs(va[3] - vb[3]) / max(va[3], vb[3], 1e-6),
                    abs(va[4] - vb[4]),
                    abs(va[5] - vb[5]) / max(va[5], vb[5], 1.0),
                ]
            )
            weights = np.array([0.3, 0.25, 0.2, 0.1, 0.1, 0.05])
            total += float(np.dot(weights, np.minimum(d, 1.0)))
            count += 1
        return total / max(count, 1)
    if dim == "E":  # 结构规范：四宫格分布 + 重心
        qa, qb = a["layout"]["quad"], b["layout"]["quad"]
        return float(np.linalg.norm(qa - qb)) + 0.5 * abs(a["layout"]["center_offset"] - b["layout"]["center_offset"])
    if dim == "F":  # 位置规范：中心偏移 + 边距不对称
        return abs(a["layout"]["center_offset"] - b["layout"]["center_offset"]) + 0.5 * abs(
            a["layout"]["margin_asym"] - b["layout"]["margin_asym"]
        )
    if dim == "G":  # 占格大小：面积比 + 宽高比
        return abs(a["layout"]["bbox_area_ratio"] - b["layout"]["bbox_area_ratio"]) + 0.5 * abs(
            a["layout"]["aspect_dev"] - b["layout"]["aspect_dev"]
        )
    if dim == "H":  # 笔画衔接位置：拓扑量（端点数/悬空率）
        ta, tb = stroke_topology(a), stroke_topology(b)
        d_endpoint = abs(ta["endpoint_count"] - tb["endpoint_count"]) / max(ta["endpoint_count"], tb["endpoint_count"], 1)
        d_dangling = abs(ta["dangling_ratio"] - tb["dangling_ratio"])
        return 0.5 * d_endpoint + 0.5 * d_dangling
    if dim == "I":  # 留白空间：密度熵 + 字内空白
        return abs(a["layout"]["density_entropy"] - b["layout"]["density_entropy"]) + 0.5 * abs(
            a["layout"]["void_ratio"] - b["layout"]["void_ratio"]
        )
    raise ValueError(f"未知维度: {dim}")
