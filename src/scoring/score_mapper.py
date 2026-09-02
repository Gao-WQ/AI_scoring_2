# -*- coding: utf-8 -*-
"""锚点刻度插值映射：把样本各维「与满分锚点的偏差距离」映射为六维分。

刻度：满分锚点偏差 d=0 → 维度满分 Max；较差锚点偏差 d_fair → Max×fair_ratio；
      最差锚点偏差 d_worst → Max×worst_ratio。分段线性插值，越界截断。
退化保护：d_fair / d_worst 异常时降级为两点插值；结果按 step 取整（默认 0.5）。
"""
from __future__ import annotations

import numpy as np

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


def map_scores_batch(
    sample_feats_list: list[dict],
    anchor_feats: dict,
    dims_cfg: dict,
    ratios: dict | None = None,
    step: float = 0.5,
    min_score: float = 1.0,
    calibration: dict | None = None,
    return_details: bool = False,
) -> tuple[list[dict | None], list[int], dict | None]:
    """批量映射：样本特征列表 → 六维分列表。

    calibration（可选，默认 None=关闭）：
      {"enabled": true, "fair_percentile": 0.5, "worst_percentile": 0.9}
      当锚点刻度过严（样本偏差普遍超过最差锚点）时，把 fair/worst 刻度放宽到
      样本偏差分布的 50/90 分位（取锚点值与分位值的较大者），保证分数分布不被压死。
      锚点仍决定“完美=满分”的位置，校准只放宽中低段刻度。
    return_details=True 时返回 (分数列表, 无效索引, details)，details 含：
      每样本偏差 d（vs 满分锚点）与分数；锚点原始刻度与校准后刻度。
    返回 (分数列表[无效样本为 None], 无效样本索引列表[, details])。
    """
    ratios = ratios or DEFAULT_RATIOS
    cal = calibration or {}
    enable_cal = bool(cal.get("enabled", False))
    fair_pct = float(cal.get("fair_percentile", 0.5))
    worst_pct = float(cal.get("worst_percentile", 0.9))

    perfect = anchor_feats["perfect"]
    d_fair_anchor = {dim: feature_distance(anchor_feats["fair"], perfect, dim) for dim in DIMENSIONS}
    d_worst_anchor = {dim: feature_distance(anchor_feats["worst"], perfect, dim) for dim in DIMENSIONS}

    # 第一遍：逐样本偏差（同时定位无效样本）
    sample_ds: dict[str, list[float]] = {dim: [] for dim in DIMENSIONS}
    invalid: list[int] = []
    valid_feats: list[tuple[int, dict]] = []
    for idx, feats in enumerate(sample_feats_list):
        if feats["n_strokes"] != perfect["n_strokes"]:
            invalid.append(idx)
            continue
        valid_feats.append((idx, feats))
        for dim in DIMENSIONS:
            sample_ds[dim].append(feature_distance(feats, perfect, dim))

    # 校准：刻度取 锚点值 与 样本分位数 的较大者（防止刻度过严）
    d_fair = dict(d_fair_anchor)
    d_worst = dict(d_worst_anchor)
    if enable_cal:
        for dim in DIMENSIONS:
            ds = sample_ds[dim]
            if not ds:
                continue
            d_fair[dim] = max(d_fair[dim], float(np.percentile(ds, fair_pct * 100)))
            d_worst[dim] = max(d_worst[dim], float(np.percentile(ds, worst_pct * 100)))

    # 第二遍：映射分数
    scores_list: list[dict | None] = [None] * len(sample_feats_list)
    sample_details: list[dict] = []
    for idx, feats in valid_feats:
        scores: dict[str, float] = {}
        d_sample: dict[str, float] = {}
        for dim in DIMENSIONS:
            max_score = float(dims_cfg[dim]["max"])
            d_sample[dim] = feature_distance(feats, perfect, dim)
            scores[dim] = map_dimension(
                d_sample[dim],
                d_fair[dim],
                d_worst[dim],
                max_score,
                ratios["fair"],
                ratios["worst"],
                step=step,
                min_score=min_score,
            )
        scores_list[idx] = scores
        if return_details:
            sample_details.append({"idx": idx, "d": d_sample, "scores": scores, "feats": feats})
    if return_details:
        details = {
            "calibration": cal,
            "anchor_scale": {"fair": d_fair_anchor, "worst": d_worst_anchor},
            "calibrated_scale": {"fair": d_fair, "worst": d_worst},
            "samples": sample_details,
        }
        return scores_list, invalid, details
    return scores_list, invalid, None
