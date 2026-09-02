# -*- coding: utf-8 -*-
"""CLI 统一入口：分派子命令（子模块 run(args) 直接消费共享参数对象）。

子命令：
  init-anchor   生成锚点目录模板
  stroke-check  笔画分离质量验证（Phase 1）
  run-all       300 字批量预打分（Phase 3）
"""
from __future__ import annotations

import argparse
from pathlib import Path


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 预打分 CLI")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-anchor", help="生成锚点目录模板")
    p_init.add_argument("--char", type=str, default="刀", help="字名（默认 刀）")
    p_init.add_argument("--count", type=int, default=None, help="锚点档位数 3/6/9（默认取 config）")
    p_init.add_argument("--anchor-dir", type=Path, default=None, help="锚点根目录（默认取 config）")

    p_stroke = sub.add_parser("stroke-check", help="笔画分离质量验证（颜色数 vs 实际笔画数）")
    p_stroke.add_argument("--char", type=str, default="刀", help="验证的字（默认 刀）")
    p_stroke.add_argument("--expected-strokes", type=int, default=2, help="该字预期笔画数（默认 2）")
    p_stroke.add_argument("--limit", type=int, default=0, help="抽样样本数，0=全部（默认 0）")
    p_stroke.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    p_stroke.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")

    p_feat = sub.add_parser("feature-check", help="特征提取验证（输出特征表 CSV + 分布统计）")
    p_feat.add_argument("--char", type=str, default="刀", help="处理的字（默认 刀）")
    p_feat.add_argument("--limit", type=int, default=0, help="抽样样本数，0=全部（默认 0）")
    p_feat.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    p_feat.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    p_feat.add_argument("--features-dir", type=Path, default=None, help="特征输出目录（默认取 config）")

    p_run = sub.add_parser("run-all", help="批量预打分（单字或全量）")
    p_run.add_argument("--char", type=str, default=None, help="只处理单字（默认处理清单全部）")
    p_run.add_argument("--chars-file", type=Path, default=None, help="字符清单文件（默认自动扫描源目录）")
    p_run.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    p_run.add_argument("--save-features", action="store_true", default=False, help="保存评分中间值（特征+偏差+刻度）到 data/features/{char}_score_details.json")
    p_run.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    p_run.add_argument("--anchors-dir", type=Path, default=None, help="锚点根目录（默认取 config）")

    p_apply = sub.add_parser("apply-scores", help="从 scores json 写回 Excel（独立入口）")
    p_apply.add_argument("--char", type=str, default="上", help="字名（默认 上）")
    p_apply.add_argument("--scores-file", type=Path, default=None, help="评分 json 路径（默认 data/scores/{char}_scores.json）")
    p_apply.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    p_apply.add_argument("--output-dir", type=Path, default=None, help="输出目录（默认取 config）")
    return parser.parse_args()


def main() -> None:
    args = get_args()
    if args.command == "init-anchor":
        from init_anchor import run

        run(args)
    elif args.command == "stroke-check":
        from features.stroke_check import run

        run(args)
    elif args.command == "feature-check":
        from features.feature_check import run

        run(args)
    elif args.command == "run-all":
        from pipeline.run_all import run

        run(args)
    elif args.command == "apply-scores":
        from apply_scores import run

        run(args)
    else:
        raise SystemExit(f"未知命令: {args.command}")


if __name__ == "__main__":
    main()
