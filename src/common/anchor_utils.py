# -*- coding: utf-8 -*-
"""锚点公共操作：模板创建、anchor.json 生成/解析/校验。

锚点目录规范：data/anchors/{字}/{perfect,level_*,worst}.png + anchor.json。
anchor.json 使用有序列表结构（3/6/9 个锚点均可），兼容旧版三键 dict 结构。
"""
from __future__ import annotations

import json
from pathlib import Path

from common.io_utils import ensure_dir, load_json_safe
from common.image_utils import load_image, stroke_count

ANCHOR_KEYS = ("perfect", "fair", "worst")
DEFAULT_LEVELS = {"3": [1.0, 0.425, 0.125], "6": [1.0, 0.75, 0.55, 0.425, 0.25, 0.125], "9": [1.0, 0.85, 0.7, 0.55, 0.425, 0.3, 0.2, 0.125, 0.05]}


def _pick_levels(anchor_count: int, score_levels: dict | None, score_ratio: dict | None) -> list[float]:
    """确定锚点档位比例列表：显式 score_ratio（旧调用）优先，其次 score_levels[count]，最后默认 3 档。"""
    if score_ratio:
        return [score_ratio.get(k, 1.0 if k == "perfect" else (0.425 if k == "fair" else 0.125)) for k in ANCHOR_KEYS]
    levels = (score_levels or {}).get(str(anchor_count)) or DEFAULT_LEVELS.get(str(anchor_count))
    return list(levels) if levels else [1.0, 0.425, 0.125]


def _default_file(i: int, n: int) -> str:
    """锚点默认文件名：首=perfect.png、末=worst.png、3 档中间=fair.png、其余=level_{i}.png。"""
    if i == 0:
        return "perfect.png"
    if i == n - 1:
        return "worst.png"
    if n == 3:
        return "fair.png"
    return f"level_{i}.png"


def default_anchor_config(char: str, anchor_count: int = 3, score_levels: dict | None = None, score_ratio: dict | None = None) -> dict:
    """生成默认 anchor.json（有序列表结构，version=2）。anchor_count 决定档位数。"""
    levels = _pick_levels(anchor_count, score_levels, score_ratio)
    n = len(levels)
    anchors = []
    for i, ratio in enumerate(levels):
        label = "perfect" if i == 0 else ("worst" if i == n - 1 else ("fair" if ratio == 0.425 else ""))
        anchors.append({"file": _default_file(i, n), "score_ratio": ratio, "label": label})
    return {"char": char, "version": "2", "anchors": anchors, "dimension_overrides": {}}


def create_anchor_template(anchor_dir: str | Path, char: str, anchor_count: int = 3, score_levels: dict | None = None, score_ratio: dict | None = None) -> Path:
    """创建锚点目录模板：目录 + 默认 anchor.json（N 个锚点条目）。"""
    target = Path(anchor_dir) / char
    ensure_dir(target)
    config_path = target / "anchor.json"
    if not config_path.exists():
        config_path.write_text(
            json.dumps(default_anchor_config(char, anchor_count, score_levels, score_ratio), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return target


def load_anchor_config(anchor_dir: str | Path, char: str) -> dict | None:
    """读取并规范化 anchor.json；兼容旧版三键 dict 结构（自动转有序列表）；缺失/非法返回 None。"""
    config = load_json_safe(Path(anchor_dir) / char / "anchor.json")
    if not isinstance(config, dict) or config.get("char") != char:
        return None
    anchors_raw = config.get("anchors")
    if isinstance(anchors_raw, dict):
        anchors = [dict(anchors_raw[k], label=k) for k in ANCHOR_KEYS if k in anchors_raw]
    elif isinstance(anchors_raw, list):
        anchors = [dict(a) for a in anchors_raw]
    else:
        return None
    if len(anchors) < 2 or not all(a.get("file") and "score_ratio" in a for a in anchors):
        return None
    return {**config, "anchors": anchors}


def validate_anchor_dir(anchor_dir: str | Path, char: str) -> list[str]:
    """校验锚点目录：返回问题列表（空列表 = 通过）。

    检查项：目录存在、每个锚点条目对应 PNG 存在且可读、每张图非空白（颜色数 >= 2）。
    无 anchor.json 时退化为检查 perfect/fair/worst 三张图。
    """
    problems: list[str] = []
    target = Path(anchor_dir) / char
    if not target.is_dir():
        return [f"锚点目录不存在: {target}"]
    config = load_anchor_config(anchor_dir, char)
    entries = config["anchors"] if config else [{"file": f"{k}.png"} for k in ANCHOR_KEYS]
    for entry in entries:
        name = entry["file"]
        png = target / name
        if not png.exists():
            problems.append(f"缺少 {name}")
            continue
        try:
            img = load_image(png)
        except Exception as exc:
            problems.append(f"{name} 无法读取: {exc}")
            continue
        if stroke_count(img) < 2:
            problems.append(f"{name} 疑似空白或颜色数不足（{stroke_count(img)} 色）")
    return problems
