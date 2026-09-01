# -*- coding: utf-8 -*-
"""锚点刻度插值映射：把样本各维「与满分锚点的偏差距离」映射为六维分。

刻度：满分锚点偏差 d=0 → 维度满分 Max；较差锚点偏差 d_fair → Max×fair_ratio；
      最差锚点偏差 d_worst → Max×worst_ratio。分段线性插值，越界截断。
退化保护：d_fair / d_worst 异常时降级为两点插值；结果按 step 取整（默认 0.5）。
"""
from __future__ import annotations

from features.features import feature_distance

DIMENSIONS = ("D", "E", "F", "G", "H", "I")
DEFAULT_RATIOS = {"perfect": 1.0, "fair": 0.425, "worst": 0.125}


def _clamp_step(value: float, max_score: float, step: float, min_score: float) -> float:
    """按 step 取整并夹到 [min_score, max_score]。"""
    rounded = round(value / step) * step
    return min(max_score, max(min_score, rounded))


def map_dimension(
    d_sample: float,
    d_fair: float,
    d_worst: float,
    max_score: float,
    fair_ratio: float,
    worst_ratio: float,
    step: float = 0.5,
    min_score: float = 1.0,
) -> float:
    """单个维度的三锚点插值。d 为与满分锚点的偏差（0=完美）。"""
    mid = max_score * fair_ratio
    low = max_score * worst_ratio

    # 退化：较差/最差锚点偏差异常时降级为两点插值
    if d_fair <= 0 or d_worst <= d_fair:
        upper = max(d_fair, d_worst, 1e-9)
        if d_sample <= 0:
            score = max_score
        elif d_sample >= upper:
            score = low
        else:
            score = max_score - (d_sample / upper) * (max_score - low)
        return _clamp_step(score, max_score, step, min_score)

    if d_sample <= 0:
        return max_score
    if d_sample <= d_fair:
        ratio = d_sample / d_fair
        score = max_score - ratio * (max_score - mid)
    elif d_sample <= d_worst:
        ratio = (d_sample - d_fair) / (d_worst - d_fair)
        score = mid - ratio * (mid - low)
    else:
        score = low
    return _clamp_step(score, max_score, step, min_score)


def map_scores(
    sample_feats: dict,
    anchor_feats: dict,
    dims_cfg: dict,
    ratios: dict | None = None,
    step: float = 0.5,
    min_score: float = 1.0,
) -> dict[str, float] | None:
    """样本特征 → 六维分。anchor_feats = {perfect/fair/worst: 特征字典}。

    样本与满分锚点笔画数不一致时返回 None（由上层标记无效，不参与打分）。
    """
    ratios = ratios or DEFAULT_RATIOS
    perfect = anchor_feats["perfect"]
    if sample_feats["n_strokes"] != perfect["n_strokes"]:
        return None

    d_fair = {dim: feature_distance(anchor_feats["fair"], perfect, dim) for dim in DIMENSIONS}
    d_worst = {dim: feature_distance(anchor_feats["worst"], perfect, dim) for dim in DIMENSIONS}

    scores: dict[str, float] = {}
    for dim in DIMENSIONS:
        max_score = float(dims_cfg[dim]["max"])
        d_sample = feature_distance(sample_feats, perfect, dim)
        scores[dim] = map_dimension(
            d_sample,
            d_fair[dim],
            d_worst[dim],
            max_score,
            ratios["fair"],
            ratios["worst"],
            step=step,
            min_score=min_score,
        )
    return scores
