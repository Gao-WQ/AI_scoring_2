# -*- coding: utf-8 -*-
"""笔画分离（业务层）：基于分割图颜色分离出逐笔画，并提供笔画级几何信息。

复用 common/image_utils 的颜色量化/分离/骨架化原语；本模块只做业务组装与异常判定。
"""
from __future__ import annotations

import numpy as np

from common.image_utils import (
    endpoints_of,
    intersections_of,
    quantize_colors,
    separate_by_color,
    skeleton_of,
)


def separate_strokes(image: np.ndarray, n_colors: int = 8, min_area: int = 8) -> list[dict]:
    """把分割图分离为逐笔画结构。

    返回每笔一个 dict：{index, color(RGB), mask, area, centroid(y,x), skeleton, endpoints, intersections}。
    背景（面积最大主色）自动剔除；面积小于 min_area 的色块视为噪声忽略。
    """
    strokes_map = separate_by_color(image, n_colors=n_colors)
    strokes: list[dict] = []
    for index, (color_idx, mask) in enumerate(sorted(strokes_map.items(), key=lambda kv: int(np.sum(kv[1])), reverse=True)):
        area = int(np.sum(mask))
        if area < min_area:
            continue
        ys, xs = np.nonzero(mask)
        skeleton = skeleton_of(mask)
        strokes.append(
            {
                "index": index,
                "color": color_idx,
                "area": area,
                "centroid": (float(ys.mean()), float(xs.mean())),
                "mask": mask,
                "skeleton": skeleton,
                "endpoints": endpoints_of(skeleton),
                "intersections": intersections_of(skeleton),
            }
        )
    return strokes


def check_stroke_count(image: np.ndarray, expected: int, n_colors: int = 8) -> tuple[bool, int, list[str]]:
    """笔画数校验：返回 (是否正常, 实际笔画数, 问题描述)。

    正常 = 实际颜色数与预期笔画数一致；不一致（缺笔/粘连/异常）时给出描述。
    """
    strokes = separate_strokes(image, n_colors=n_colors)
    actual = len(strokes)
    problems: list[str] = []
    if actual != expected:
        problems.append(f"笔画数异常：预期 {expected}，实际 {actual}")
    return actual == expected, actual, problems
