# -*- coding: utf-8 -*-
"""特征提取验证（Phase 2）：对某字全量分割图提取六维特征，输出特征表 CSV 与分布统计。

用法：python src/main.py feature-check --char 刀
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from common.excel_utils import first_sheet, load_workbook, extract_images_by_row
from common.io_utils import ensure_dir, source_workbook_path
from config import load_config, resolve_path
from features.features import extract_features


def get_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="特征提取验证")
    parser.add_argument("--char", type=str, default="刀", help="处理的字（默认 刀）")
    parser.add_argument("--limit", type=int, default=0, help="抽样样本数，0=全部（默认 0）")
    parser.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    parser.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    parser.add_argument("--features-dir", type=Path, default=None, help="特征输出目录（默认取 config）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    source_dir = args.source_dir or resolve_path(cfg, "source_dir")
    features_dir = args.features_dir or resolve_path(cfg, "features_dir")
    ensure_dir(features_dir)

    workbook = source_workbook_path(source_dir, args.char, cfg["paths"].get("input_suffix", "_all_data_new"))
    if not workbook.exists():
        raise SystemExit(f"源工作簿不存在: {workbook}")

    wb = load_workbook(workbook, data_only=False)
    ws = first_sheet(wb)
    images = extract_images_by_row(ws, cols=(3,))
    rows = sorted(images)
    if args.limit > 0:
        rows = rows[: args.limit]

    csv_path = features_dir / f"{args.char}_features.csv"
    fieldnames = [
        "row", "n_strokes", "center_offset", "margin_asym",
        "bbox_area_ratio", "aspect_dev", "density_entropy", "void_ratio",
        "quad_tl", "quad_tr", "quad_bl", "quad_br",
        "stroke_len_mean", "stroke_width_mean", "stroke_curvature_mean",
    ]
    stats: dict[str, list[float]] = {k: [] for k in fieldnames[2:]}
    anomalies: list[tuple[int, str]] = []

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            feats = extract_features(images[row][3], n_colors=args.n_colors)
            layout = feats["layout"]
            per = feats["per_stroke"]
            len_mean = float(np.mean([s["length"] for s in per])) if per else 0.0
            width_mean = float(np.mean([s["width_mean"] for s in per])) if per else 0.0
            curv_mean = float(np.mean([s["curvature_proxy"] for s in per])) if per else 0.0
            rec = {
                "row": row,
                "n_strokes": feats["n_strokes"],
                "center_offset": f"{layout['center_offset']:.4f}",
                "margin_asym": f"{layout['margin_asym']:.4f}",
                "bbox_area_ratio": f"{layout['bbox_area_ratio']:.4f}",
                "aspect_dev": f"{layout['aspect_dev']:.4f}",
                "density_entropy": f"{layout['density_entropy']:.4f}",
                "void_ratio": f"{layout['void_ratio']:.4f}",
                "quad_tl": f"{layout['quad'][0]:.4f}",
                "quad_tr": f"{layout['quad'][1]:.4f}",
                "quad_bl": f"{layout['quad'][2]:.4f}",
                "quad_br": f"{layout['quad'][3]:.4f}",
                "stroke_len_mean": f"{len_mean:.2f}",
                "stroke_width_mean": f"{width_mean:.2f}",
                "stroke_curvature_mean": f"{curv_mean:.4f}",
            }
            writer.writerow(rec)
            for k in stats:
                stats[k].append(float(rec[k]))
            if feats["n_strokes"] != 2:
                anomalies.append((row, f"笔画数={feats['n_strokes']}"))

    total = len(rows)
    print(f"字={args.char} 特征表已保存: {csv_path}（样本数={total}）\n")
    print("=== 特征分布（均值 ± 标准差 / 范围）===")
    labels = {
        "center_offset": "位置中心偏移(0~1, 越小越居中)",
        "margin_asym": "边距不对称(0~, 越小越均衡)",
        "bbox_area_ratio": "占格面积比(外接框/画布)",
        "aspect_dev": "宽高比偏差",
        "density_entropy": "密度熵(分布散度)",
        "void_ratio": "字内空白比",
        "stroke_len_mean": "笔画长度均值",
        "stroke_width_mean": "笔画宽度均值",
        "stroke_curvature_mean": "笔画曲率代理(0=直)",
    }
    for k, label in labels.items():
        arr = np.array(stats[k])
        if arr.size == 0:
            continue
        print(f"  {k:22s} {arr.mean():8.3f} ± {arr.std():7.3f}   [{arr.min():.3f}, {arr.max():.3f}]  {label}")

    if anomalies:
        print(f"\n笔画数异常 {len(anomalies)} 个: {anomalies[:10]}")
    else:
        print("\n笔画数全部正常（= 2）")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
