# -*- coding: utf-8 -*-
"""笔画分离质量验证（Phase 1）：读取某字工作簿的全部分割图，统计颜色分离出的笔画数，
与预期笔画数对比，输出分布报告与异常样本名单。

用法：python src/main.py stroke-check --char 刀 --expected-strokes 2
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from common.excel_utils import first_sheet, load_workbook, extract_images_by_row
from config import load_config, resolve_path
from features.stroke_separate import check_stroke_count


def get_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="笔画分离质量验证")
    parser.add_argument("--char", type=str, default="刀", help="验证的字（默认 刀）")
    parser.add_argument("--expected-strokes", type=int, default=2, help="该字预期笔画数（默认 2）")
    parser.add_argument("--limit", type=int, default=0, help="抽样样本数，0=全部（默认 0）")
    parser.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    parser.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    source_dir = args.source_dir or resolve_path(cfg, "source_dir")
    workbook = source_dir / f"{args.char}_all_data_new.xlsx"
    if not workbook.exists():
        raise SystemExit(f"源工作簿不存在: {workbook}")

    wb = load_workbook(workbook, data_only=False)
    ws = first_sheet(wb)
    images = extract_images_by_row(ws, cols=(3,))
    rows = sorted(images)
    if args.limit > 0:
        rows = rows[: args.limit]
    print(f"字={args.char} 预期笔画数={args.expected_strokes} 分割图样本数={len(rows)}")

    counts: Counter[int] = Counter()
    abnormal: list[tuple[int, int, str]] = []
    for row in rows:
        ok, actual, problems = check_stroke_count(images[row][3], args.expected_strokes, n_colors=args.n_colors)
        counts[actual] += 1
        if not ok:
            abnormal.append((row, actual, problems[0]))

    total = len(rows)
    print("\n=== 笔画数分布（颜色分离结果）===")
    for actual in sorted(counts):
        n = counts[actual]
        print(f"  {actual} 画: {n:4d}  ({n / total * 100:.1f}%)")
    ok_count = counts.get(args.expected_strokes, 0)
    print(f"\n一致性: {ok_count}/{total} = {ok_count / total * 100:.1f}%")

    if abnormal:
        print(f"\n=== 异常样本 {len(abnormal)} 个（建议老师复核或检查分割图）===")
        for row, actual, desc in abnormal[:30]:
            print(f"  row {row}: {desc}")
        if len(abnormal) > 30:
            print(f"  ... 其余 {len(abnormal) - 30} 个见日志")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
