# -*- coding: utf-8 -*-
"""单字处理流水线：锚点加载 → 样本特征 → 锚点刻度插值 → scores json → 写回 Excel。

流程（对单个字）：
  1. 校验并加载锚点（data/anchors/{char}/），三张锚点图提取特征
  2. 读源工作簿（{source_dir}/{char}{input_suffix}.xlsx），提取 C 列分割图
  3. 逐样本提取特征并做三锚点插值映射，得到六维分
  4. 保存 scores json（data/scores/{char}_scores.json）
  5. 写回 Excel（D:I + L 清空 + 公式保留 + 校验）到 data/output/{char}{input_suffix}{output_suffix}.xlsx
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
from common.io_utils import ensure_dir, output_workbook_path, progress_bar, save_json, source_workbook_path
from config import load_config, resolve_path
from features.features import extract_features
from scoring.score_mapper import map_scores_batch

import numpy as np

STANDARD_SIZE = 256
ANCHOR_KEYS = ("perfect", "fair", "worst")

FEATURE_HEADERS = [
    "char_id", "笔画数",
    "中心偏移", "边距不对称", "占格面积比", "宽高比偏差", "密度熵", "字内空白比",
    "四宫格-左上", "四宫格-右上", "四宫格-左下", "四宫格-右下",
    "笔画长度均值", "笔画宽度均值", "笔画曲率均值",
    "偏差-笔画", "偏差-结构", "偏差-位置", "偏差-占格", "偏差-衔接", "偏差-留白",
    "笔画规范分", "结构规范分", "位置规范分", "占格大小分", "笔画衔接分", "留白空间分",
    "总分",
]


def add_feature_sheet(ws2, details: dict, rows: list[int]) -> None:
    """在输出工作簿新增"ai特征值"sheet：中文列名、第一列 char_id、无图片、按样本顺序一行一条。

    内容 = 特征（layout + 笔画统计）+ 每维偏差 d + 六维分，即评分全过程中间值。
    """
    wb = ws2.parent
    if "ai特征值" in wb.sheetnames:
        del wb["ai特征值"]
    sheet = wb.create_sheet("ai特征值")
    sheet.append(FEATURE_HEADERS)
    for sample in details["samples"]:
        row = rows[sample["idx"]]
        feats = sample["feats"]
        layout = feats["layout"]
        per = feats["per_stroke"]
        quad = layout["quad"]
        n = len(per)
        sheet.append(
            [
                ws2.cell(row, 1).value,  # char_id（源工作簿 A 列）
                feats["n_strokes"],
                round(layout["center_offset"], 4), round(layout["margin_asym"], 4),
                round(layout["bbox_area_ratio"], 4), round(layout["aspect_dev"], 4),
                round(layout["density_entropy"], 4), round(layout["void_ratio"], 4),
                round(quad[0], 4), round(quad[1], 4), round(quad[2], 4), round(quad[3], 4),
                round(np.mean([s["length"] for s in per]), 2) if n else 0,
                round(np.mean([s["width_mean"] for s in per]), 4) if n else 0,
                round(np.mean([s["curvature_proxy"] for s in per]), 4) if n else 0,
                *[round(sample["d"][dim], 4) for dim in ("D", "E", "F", "G", "H", "I")],
                *[round(sample["scores"][dim], 2) for dim in ("D", "E", "F", "G", "H", "I")],
                round(sum(sample["scores"][dim] for dim in ("D", "E", "F", "G", "H", "I")), 2),
            ]
        )


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
    source_dir = args.source_dir or resolve_path(cfg, "source_dir")
    scores_dir = resolve_path(cfg, "scores_dir")
    output_dir = resolve_path(cfg, "output_dir")
    ensure_dir(scores_dir)
    ensure_dir(output_dir)

    problems = validate_anchor_dir(anchors_dir, char)
    if problems:
        return {"char": char, "status": "no_anchor", "problems": problems}

    input_suffix = cfg["paths"].get("input_suffix", "_all_data_new")
    workbook = source_workbook_path(source_dir, char, input_suffix)
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

    scores_path = scores_dir / f"{char}_scores.json"
    print(f"[处理] 字={char} | 待打分样本量={len(rows)} | 打分表保存: {scores_path}")

    records: dict[int, dict] = {}
    feats_list: list[dict] = []
    total_rows = len(rows)
    for i, row in enumerate(rows, 1):
        feats_list.append(extract_features(resize_keep_ratio(images[row][3], STANDARD_SIZE), n_colors=args.n_colors))
        if total_rows > 50:
            progress_bar(i, total_rows, prefix=f"{char} 打分进度")

    scores_list, _, details = map_scores_batch(
        feats_list,
        anchor_feats,
        dims_cfg,
        ratios=ratios,
        step=step,
        min_score=min_score,
        calibration=cfg.get("calibration"),
        return_details=getattr(args, "save_features", False),
    )
    anomalies: list[dict] = []
    for idx, scores in enumerate(scores_list):
        row = rows[idx]
        if scores is None:
            anomalies.append({"row": row, "reason": f"笔画数={feats_list[idx]['n_strokes']}（锚点={anchor_feats['perfect']['n_strokes']}）"})
            continue
        records[row] = {"row": row, **{dim: round(scores[dim], 2) for dim in dims_cfg}}

    # 保存 scores json
    save_json(scores_path, list(records.values()))

    # 写回 Excel（可选：新增 ai特征值 sheet）
    wb2 = load_workbook(workbook, data_only=False)
    ws2 = first_sheet(wb2)
    expected_images = len(ws2._images)
    formulas_before = formulas_snapshot(ws2)
    write_scores(ws2, records)
    verify_workbook(ws2, records, formulas_before, expected_images, maxes={k: v["max"] for k, v in dims_cfg.items()}, step=step)
    if details is not None:
        add_feature_sheet(ws2, details, rows)
    set_full_recalc(wb2)
    output_path = output_workbook_path(output_dir, char, input_suffix, cfg["batch"]["output_suffix"])
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
