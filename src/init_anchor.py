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
    parser.add_argument("--char", type=str, default="刀", help="字名（目录名，须与 anchor.json 的 char 一致）")
    parser.add_argument("--anchor-dir", type=Path, default=None, help="锚点根目录（默认取 config.json）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    anchor_dir = args.anchor_dir or resolve_path(cfg, "anchors_dir")
    ensure_dir(anchor_dir)

    target = create_anchor_template(anchor_dir, args.char)
    print(f"已创建锚点模板: {target}")
    print("请放置三张分割图后删除占位说明文件：perfect.png / fair.png / worst.png")

    problems = validate_anchor_dir(anchor_dir, args.char)
    if problems:
        print("当前校验（尚未放置图片时的预期提示）:")
        for p in problems:
            print(f"  - {p}")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
