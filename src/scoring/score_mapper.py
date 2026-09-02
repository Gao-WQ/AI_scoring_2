# -*- coding: utf-8 -*-
"""锚点刻度插值映射：把样本各维「与满分锚点的偏差距离」映射为六维分。

多锚点分段线性插值（3/5/9 个锚点均可，由 run-all --anchor-count 指定）：
  满分锚点偏差 d=0 → 维度满分 Max；其余锚点 (d_i, ratio_i) 依序排列，
  样本偏差落在相邻两个锚点区间内即线性插值，越界截断到最差锚点档或满分。
退化保护：相邻锚点偏差相同时取后一档比例；结果按 step 取整（默认 0.5）。
anchor_feats 结构：{"anchors": [{"score_ratio":..., "label":..., "feats":...}, ...]}，
第 0 个必须是满分锚点（score_ratio=1.0）。
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
    anchors: list[tuple[float, float]],
    max_score: float,
    step: float = 0.5,
    min_score: float = 1.0,
) -> float:
    """单个维度的 N 锚点分段插值。anchors = 按偏差升序的 [(d, ratio)]，首项 (0, 1.0)。"""
    if d_sample <= 0:
        return max_score
    d_last = anchors[-1][0]
    if d_last <= 0 or d_sample >= d_last:
        return _clamp_step(max_score * anchors[-1][1], max_score, step, min_score)
    for i in range(len(anchors) - 1):
        d0, r0 = anchors[i]
        d1, r1 = anchors[i + 1]
        if d_sample <= d1:
            ratio = r0 + (r1 - r0) * (d_sample - d0) / (d1 - d0) if d1 > d0 else r1
            return _clamp_step(max_score * ratio, max_score, step, min_score)
    return _clamp_step(max_score * anchors[-1][1], max_score, step, min_score)


def _anchor_entries(anchor_feats: dict, perfect: dict) -> dict[str, list[dict]]:
    """每维原始锚点条目（未去重）：[{label, ratio, d}]，顺序与 anchors 列表一致。

    d 为相对满分锚点的偏差（满分锚点恒为 0）。校准在此阶段按标签定位，不会因去重错位。
    """
    entries: dict[str, list[dict]] = {}
    for dim in DIMENSIONS:
        lst = []
        for i, a in enumerate(anchor_feats["anchors"]):
            d = 0.0 if i == 0 else feature_distance(a["feats"], perfect, dim)
            lst.append({"label": a.get("label", ""), "ratio": a["score_ratio"], "d": d})
        entries[dim] = lst
    return entries


def _calibrate_entries(entries: dict[str, list[dict]], labels: list[str], sample_ds: dict[str, list[float]], cal: dict) -> dict[str, list[dict]]:
    """分布校准（去重前执行）：放宽 fair（50 分位）与 worst（最后一个锚点，90 分位）两处刻度，其余锚点不动。"""
    fair_idx = next((i for i, lab in enumerate(labels) if lab == "fair"), 1 if len(labels) > 1 else 0)
    worst_idx = len(labels) - 1
    fair_pct = float(cal.get("fair_percentile", 0.5))
    worst_pct = float(cal.get("worst_percentile", 0.9))
    for dim, lst in entries.items():
        ds = sample_ds[dim]
        if not ds:
            continue
        lst[fair_idx]["d"] = max(lst[fair_idx]["d"], float(np.percentile(ds, fair_pct * 100)))
        lst[worst_idx]["d"] = max(lst[worst_idx]["d"], float(np.percentile(ds, worst_pct * 100)))
    return entries


def _build_interp_points(entries: list[dict]) -> list[tuple[float, float]]:
    """从（校准后的）锚点条目构建插值点：按偏差升序，跳过不劣于前档的锚点（如 d=0 的 fair），同偏差保留比例更大者。"""
    ordered = sorted(entries, key=lambda e: e["d"])
    pts: list[tuple[float, float]] = []
    for e in ordered:
        if not pts or e["d"] > pts[-1][0]:
            pts.append((e["d"], e["ratio"]))
        elif e["d"] == pts[-1][0] and e["ratio"] > pts[-1][1]:
            pts[-1] = (e["d"], e["ratio"])
    return pts


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

    anchor_feats = {"anchors": [{"score_ratio", "label", "feats"}, ...]}，第 0 个为满分锚点。
    calibration（可选，默认 None=关闭）：
      {"enabled": true, "fair_percentile": 0.5, "worst_percentile": 0.9}
      当锚点刻度过严（样本偏差普遍超过最差锚点）时，把 fair/worst 两处刻度放宽到
      样本偏差分布的 50/90 分位（取锚点值与分位值的较大者），保证分数分布不被压死。
      锚点仍决定“完美=满分”的位置，校准只放宽中低段刻度。
    return_details=True 时 details 含：每样本偏差 d（vs 满分锚点）与分数；锚点原始刻度与校准后刻度。
    返回固定 3 元组 (分数列表[无效样本为 None], 无效样本索引列表, details)。
    """
    ratios = ratios or DEFAULT_RATIOS
    cal = calibration or {}
    enable_cal = bool(cal.get("enabled", False))

    perfect = anchor_feats["anchors"][0]["feats"]
    labels = [a.get("label", "") for a in anchor_feats["anchors"]]
    entries = _anchor_entries(anchor_feats, perfect)

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

    # 校准（去重前执行，按标签定位不会错位）：放宽 fair/worst 两处刻度
    if enable_cal:
        entries = _calibrate_entries(entries, labels, sample_ds, cal)

    # 第二遍：映射分数（每维先构建去重插值点）
    points = {dim: _build_interp_points(entries[dim]) for dim in DIMENSIONS}
    scores_list: list[dict | None] = [None] * len(sample_feats_list)
    sample_details: list[dict] = []
    for idx, feats in valid_feats:
        scores: dict[str, float] = {}
        d_sample: dict[str, float] = {}
        for dim in DIMENSIONS:
            max_score = float(dims_cfg[dim]["max"])
            d_sample[dim] = feature_distance(feats, perfect, dim)
            scores[dim] = map_dimension(d_sample[dim], points[dim], max_score, step=step, min_score=min_score)
        scores_list[idx] = scores
        if return_details:
            sample_details.append({"idx": idx, "d": d_sample, "scores": scores, "feats": feats})
    if return_details:
        details = {
            "calibration": cal,
            "scales": {
                "label": labels,
                "ratio": [a["score_ratio"] for a in anchor_feats["anchors"]],
                "anchor_d": {dim: [e["d"] for e in entries[dim]] for dim in DIMENSIONS},
                "calibrated_d": {dim: [p[0] for p in points[dim]] for dim in DIMENSIONS},
            },
            "samples": sample_details,
        }
        return scores_list, invalid, details
    return scores_list, invalid, None
