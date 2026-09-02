# -*- coding: utf-8 -*-
"""锚点目录模板工具：生成 data/anchors/{字}/ 骨架 + 默认 anchor.json + 占位说明。

用法（经 main.py 分派）：python src/main.py init-anchor --char 刀
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common.anchor_utils import create_anchor_template, validate_anchor_dir
from common.io_utils import ensure_dir
from config import load_config, resolve_path


def get_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成锚点目录模板")
    parser.add_argument("--char", type=str, default="刀", help="字名（目录名，须与 anchorN.json 的 char 一致）")
    parser.add_argument("--count", type=int, default=None, help="锚点档位数 3/5/9（默认取 config.anchor_defaults.anchor_count）")
    parser.add_argument("--anchor-dir", type=Path, default=None, help="锚点根目录（默认取 config.json）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    anchor_dir = args.anchor_dir or resolve_path(cfg, "anchors_dir")
    ensure_dir(anchor_dir)

    anchor_count = args.count or cfg.get("anchor_defaults", {}).get("anchor_count", 3)
    if anchor_count not in (3, 5, 9):
        raise SystemExit(f"锚点档位数 {anchor_count} 不在支持范围内（仅 3/5/9），请检查 --count 或 config.anchor_defaults.anchor_count")
    score_levels = cfg.get("anchor_defaults", {}).get("score_levels")
    target = create_anchor_template(anchor_dir, args.char, anchor_count=anchor_count, score_levels=score_levels)
    print(f"已创建锚点模板（{anchor_count} 档）: {target}")
    print(f"请放置分割图后重跑校验：图池 1.png=最佳(perfect)、9.png=最差(worst)、5.png=中等(fair)；")
    print(f"本档使用的图序号见 anchor{anchor_count}.json 的 file 字段，ratio 可按需修改")
    print("（同一目录可再对 3/5/9 分别生成 anchor3/5/9.json，跑分时用 --anchor-count 选择）")

    problems = validate_anchor_dir(anchor_dir, args.char, anchor_count)
    if problems:
        print("当前校验（尚未放置图片时的预期提示）:")
        for p in problems:
            print(f"  - {p}")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
