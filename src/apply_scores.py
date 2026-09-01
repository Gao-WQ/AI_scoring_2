# -*- coding: utf-8 -*-
"""单字写回入口：从 scores json 把六维分写回源工作簿，另存为已评分版本。

独立入口：老师可修改 data/scores/{char}_scores.json 后重新写回；
single_char.py 内部也调用本模块的 write_back 完成写回步骤。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.excel_utils import (
    first_sheet,
    formulas_snapshot,
    load_workbook,
    set_full_recalc,
    verify_workbook,
    write_scores,
)
from common.io_utils import ensure_dir
from config import load_config, resolve_path


def get_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 scores json 写回 Excel")
    parser.add_argument("--char", type=str, default="上", help="字名（默认 上）")
    parser.add_argument("--scores-file", type=Path, default=None, help="评分 json 路径（默认 data/scores/{char}_scores.json）")
    parser.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    parser.add_argument("--output-dir", type=Path, default=None, help="输出目录（默认取 config）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def write_back(char: str, cfg: dict, scores_path: Path) -> dict:
    """把 scores json 写回 {char}_all_data_new.xlsx，另存为已评分版本。"""
    source_dir = resolve_path(cfg, "source_dir")
    output_dir = resolve_path(cfg, "output_dir")
    ensure_dir(output_dir)
    dims_cfg = cfg["dimensions"]
    step = cfg["scoring"]["step"]

    workbook = source_dir / f"{char}_all_data_new.xlsx"
    if not workbook.exists():
        raise SystemExit(f"源工作簿不存在: {workbook}")

    records = {int(rec["row"]): rec for rec in json.loads(scores_path.read_text(encoding="utf-8"))}

    wb = load_workbook(workbook, data_only=False)
    ws = first_sheet(wb)
    expected_images = len(ws._images)
    formulas_before = formulas_snapshot(ws)
    write_scores(ws, records)
    verify_workbook(
        ws, records, formulas_before, expected_images,
        maxes={k: v["max"] for k, v in dims_cfg.items()}, step=step,
    )
    set_full_recalc(wb)
    output_path = output_dir / f"{char}{cfg['batch']['output_suffix']}"
    wb.save(output_path)
    return {
        "char": char,
        "rows": len(records),
        "images": expected_images,
        "output_path": str(output_path),
    }


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    scores_dir = resolve_path(cfg, "scores_dir")
    scores_path = args.scores_file or (scores_dir / f"{args.char}_scores.json")
    if not scores_path.exists():
        raise SystemExit(f"评分文件不存在: {scores_path}")
    result = write_back(args.char, cfg, scores_path)
    print(f"已写回: {result['output_path']}（{result['rows']} 行，图片 {result['images']} 张）")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
