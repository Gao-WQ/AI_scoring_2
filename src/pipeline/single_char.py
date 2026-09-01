# -*- coding: utf-8 -*-
"""单字处理流水线：锚点加载 → 样本特征 → 锚点刻度插值 → scores json → 写回 Excel。

流程（对单个字）：
  1. 校验并加载锚点（data/anchors/{char}/），三张锚点图提取特征
  2. 读源工作簿（{source_dir}/{char}_all_data_new.xlsx），提取 C 列分割图
  3. 逐样本提取特征并做三锚点插值映射，得到六维分
  4. 保存 scores json（data/scores/{char}_scores.json）
  5. 写回 Excel（D:I + L 清空 + 公式保留 + 校验）到 data/output/{char}_all_data_new_已评分.xlsx
  6. 返回统计结果（含笔画数异常名单）
"""
from __future__ import annotations

from pathlib import Path

from common.anchor_utils import load_anchor_config, validate_anchor_dir
from common.excel_utils import (
    extract_images_by_row,
    first_sheet,
    formulas_snapshot,
    load_workbook,
    set_full_recalc,
    verify_workbook,
    write_scores,
)
from common.image_utils import load_image, resize_keep_ratio
from common.io_utils import ensure_dir, save_json
from config import load_config, resolve_path
from features.features import extract_features
from scoring.score_mapper import map_scores

STANDARD_SIZE = 256
ANCHOR_KEYS = ("perfect", "fair", "worst")


def _anchor_features(anchors_dir: Path, char: str) -> dict[str, dict]:
    """加载三张锚点图并提取特征，返回 {perfect/fair/worst: feats}。"""
    feats: dict[str, dict] = {}
    for key in ANCHOR_KEYS:
        img = load_image(anchors_dir / char / f"{key}.png")
        feats[key] = extract_features(resize_keep_ratio(img, STANDARD_SIZE))
    return feats


def run_char(char: str, cfg: dict, args) -> dict:
    """处理单个字，返回统计结果 dict。缺锚点/源缺失时返回带 status 的结果。"""
    anchors_dir = resolve_path(cfg, "anchors_dir")
    source_dir = resolve_path(cfg, "source_dir")
    scores_dir = resolve_path(cfg, "scores_dir")
    output_dir = resolve_path(cfg, "output_dir")
    ensure_dir(scores_dir)
    ensure_dir(output_dir)

    problems = validate_anchor_dir(anchors_dir, char)
    if problems:
        return {"char": char, "status": "no_anchor", "problems": problems}

    workbook = source_dir / f"{char}_all_data_new.xlsx"
    if not workbook.exists():
        return {"char": char, "status": "no_source", "problems": [f"源工作簿不存在: {workbook}"]}

    anchor_cfg = load_anchor_config(anchors_dir, char)
    anchor_feats = _anchor_features(anchors_dir, char)
    dims_cfg = cfg["dimensions"]
    ratios = {key: anchor_cfg["anchors"][key]["score_ratio"] for key in ANCHOR_KEYS}
    step = cfg["scoring"]["step"]
    min_score = cfg["scoring"]["min_score"]

    wb = load_workbook(workbook, data_only=False)
    ws = first_sheet(wb)
    images = extract_images_by_row(ws, cols=(3,))
    rows = sorted(images)

    records: dict[int, dict] = {}
    anomalies: list[dict] = []
    for row in rows:
        feats = extract_features(resize_keep_ratio(images[row][3], STANDARD_SIZE), n_colors=args.n_colors)
        scores = map_scores(feats, anchor_feats, dims_cfg, ratios=ratios, step=step, min_score=min_score)
        if scores is None:
            anomalies.append({"row": row, "reason": f"笔画数={feats['n_strokes']}（锚点={anchor_feats['perfect']['n_strokes']}）"})
            continue
        records[row] = {"row": row, **{dim: round(scores[dim], 2) for dim in dims_cfg}}

    # 保存 scores json
    scores_path = scores_dir / f"{char}_scores.json"
    save_json(scores_path, list(records.values()))

    # 写回 Excel
    wb2 = load_workbook(workbook, data_only=False)
    ws2 = first_sheet(wb2)
    expected_images = len(ws2._images)
    formulas_before = formulas_snapshot(ws2)
    write_scores(ws2, records)
    verify_workbook(ws2, records, formulas_before, expected_images, maxes={k: v["max"] for k, v in dims_cfg.items()}, step=step)
    set_full_recalc(wb2)
    output_path = output_dir / f"{char}{cfg['batch']['output_suffix']}"
    wb2.save(output_path)

    totals = [sum(rec[d] for d in dims_cfg) for rec in records.values()]
    return {
        "char": char,
        "status": "ok",
        "total": len(rows),
        "scored": len(records),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies[:20],
        "total_min": min(totals) if totals else 0,
        "total_max": max(totals) if totals else 0,
        "total_mean": round(sum(totals) / len(totals), 2) if totals else 0.0,
        "scores_path": str(scores_path),
        "output_path": str(output_path),
    }
