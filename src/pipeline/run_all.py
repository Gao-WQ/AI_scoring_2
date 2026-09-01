# -*- coding: utf-8 -*-
"""批量主入口：遍历字符清单，逐字调用 single_char.run_char，输出汇总 summary.csv。

用法：python src/main.py run-all [--char 上] [--chars-file data/chars.txt]
缺锚点的字跳过并记入汇总，不中断整批；补好锚点后可单字重跑。
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from common.io_utils import ensure_dir, resolve_char_list
from config import load_config, resolve_path
from pipeline.single_char import run_char


def get_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量预打分")
    parser.add_argument("--char", type=str, default=None, help="只处理单字（默认处理清单全部）")
    parser.add_argument("--chars-file", type=Path, default=None, help="字符清单文件（默认自动扫描源目录）")
    parser.add_argument("--n-colors", type=int, default=8, help="颜色量化聚类数（默认 8）")
    parser.add_argument("--source-dir", type=Path, default=None, help="源工作簿目录（默认取 config）")
    parser.add_argument("--anchors-dir", type=Path, default=None, help="锚点根目录（默认取 config）")
    parser.add_argument("--config", type=Path, default=None, help="config.json 路径（默认 src/config.json）")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    source_dir = args.source_dir or resolve_path(cfg, "source_dir")
    output_dir = resolve_path(cfg, "output_dir")
    ensure_dir(output_dir)

    chars = resolve_char_list(source_dir, args.chars_file)
    if args.char:
        chars = [args.char]
    print(f"待处理字（{len(chars)} 个）: {chars}")

    results = [run_char(char, cfg, args) for char in chars]
    summary_path = output_dir / "summary.csv"
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["char", "status", "total", "scored", "anomaly_count", "total_min", "total_max", "total_mean", "problems"])
        for r in results:
            writer.writerow(
                [
                    r["char"], r["status"], r.get("total", 0), r.get("scored", 0),
                    r.get("anomaly_count", 0), r.get("total_min", 0), r.get("total_max", 0),
                    r.get("total_mean", 0.0), "; ".join(r.get("problems", [])),
                ]
            )
    print(f"\n汇总已保存: {summary_path}\n")

    for r in results:
        if r["status"] == "ok":
            print(
                f"[OK] {r['char']}: 样本 {r['total']} / 已评分 {r['scored']} / 异常 {r['anomaly_count']} "
                f"| 总分 {r['total_min']}-{r['total_max']} 均值 {r['total_mean']}"
            )
            for a in r["anomalies"][:5]:
                print(f"      异常 row {a['row']}: {a['reason']}")
        else:
            print(f"[SKIP] {r['char']}: {'; '.join(r.get('problems', []))}")


def main(argv: list[str] | None = None) -> None:
    run(get_args(argv))


if __name__ == "__main__":
    main()
