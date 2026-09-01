# -*- coding: utf-8 -*-
"""锚点公共操作：模板创建、anchor.json 生成/解析/校验。

锚点目录规范：data/anchors/{字}/{perfect,fair,worst}.png + anchor.json。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from common.io_utils import ensure_dir, load_json_safe
from common.image_utils import load_image, stroke_count

ANCHOR_KEYS = ("perfect", "fair", "worst")


def default_anchor_config(char: str, score_ratio: dict[str, float] | None = None) -> dict:
    """生成默认 anchor.json 结构。score_ratio 缺省用 perfect=1.0 / fair=0.425 / worst=0.125。"""
    ratio = score_ratio or {"perfect": 1.0, "fair": 0.425, "worst": 0.125}
    return {
        "char": char,
        "version": "1",
        "anchors": {key: {"file": f"{key}.png", "score_ratio": ratio[key]} for key in ANCHOR_KEYS},
        "dimension_overrides": {},
    }


def create_anchor_template(anchor_dir: str | Path, char: str, score_ratio: dict[str, float] | None = None) -> Path:
    """创建锚点目录模板：目录 + 三张占位说明 txt + 默认 anchor.json。"""
    target = Path(anchor_dir) / char
    ensure_dir(target)
    # for key in ANCHOR_KEYS:
    #     placeholder = target / f"{key}.png.请替换为{char}字的{key}分割图.txt"
    #     placeholder.write_text(
    #         f"请把 {char} 字的「{key}」分割图命名为 {key}.png 放入本目录。\n"
    #         "要求：PNG、RGB、无背景、每笔一色。\n"
    #         "放置完成后删除本说明文件。",
    #         encoding="utf-8",
    #     )
    config_path = target / "anchor.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(default_anchor_config(char, score_ratio), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return target


def load_anchor_config(anchor_dir: str | Path, char: str) -> dict | None:
    """读取并校验 anchor.json；缺失或非法返回 None。"""
    config = load_json_safe(Path(anchor_dir) / char / "anchor.json")
    if not isinstance(config, dict) or config.get("char") != char:
        return None
    if not all(key in config.get("anchors", {}) for key in ANCHOR_KEYS):
        return None
    return config


def validate_anchor_dir(anchor_dir: str | Path, char: str) -> list[str]:
    """校验锚点目录：返回问题列表（空列表 = 通过）。

    检查项：目录存在、三张 PNG 存在且可读、每张图非空白（颜色数 >= 2）。
    """
    problems: list[str] = []
    target = Path(anchor_dir) / char
    if not target.is_dir():
        return [f"锚点目录不存在: {target}"]
    for key in ANCHOR_KEYS:
        png = target / f"{key}.png"
        if not png.exists():
            problems.append(f"缺少 {key}.png")
            continue
        try:
            img = load_image(png)
        except Exception as exc:
            problems.append(f"{key}.png 无法读取: {exc}")
            continue
        if stroke_count(img) < 2:
            problems.append(f"{key}.png 疑似空白或颜色数不足（{stroke_count(img)} 色）")
    return problems
