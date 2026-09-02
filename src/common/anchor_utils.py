# -*- coding: utf-8 -*-
"""锚点公共操作：模板创建、anchorN.json 生成/解析/校验。

锚点目录规范（不兼容旧版）：
  data/anchors/{字}/ 下为共享图池 1.png ~ 9.png（1=最佳 perfect，9=最差 worst，5=fair），
  anchor{count}.json 为该档位的锚点描述（count ∈ {3,5,9}，三套可并存）。

档位 → 图序号映射（固定）：
  3 档 → [1, 5, 9]；5 档 → [1, 3, 5, 7, 9]；9 档 → [1, 2, ..., 9]
  每档 ratio 独立，来自 config.json → anchor_defaults.score_levels（互不派生，可自行调整）。

anchor{count}.json 结构（version 2 有序列表）：
  {"char": 字, "version": "2", "anchors": [{"file": "N.png", "score_ratio": r, "label": ...}, ...],
   "dimension_overrides": {}}
  label 约定：首条 perfect、末条 worst、中档 fair（i == n//2），其余空。
"""
from __future__ import annotations

import json
from pathlib import Path

from common.io_utils import ensure_dir, load_json_safe
from common.image_utils import load_image, stroke_count

# 档位 → 使用的图序号（1~9 图池）
ANCHOR_SETS: dict[int, list[int]] = {3: [1, 5, 9], 5: [1, 3, 5, 7, 9], 9: list(range(1, 10))}
# ratio 兜底表（config.json → anchor_defaults.score_levels 优先，此表仅防缺键）
DEFAULT_LEVELS = {
    "3": [1.0, 0.425, 0.125],
    "5": [1.0, 0.78, 0.55, 0.32, 0.1],
    "9": [1.0, 0.85, 0.7, 0.55, 0.425, 0.3, 0.2, 0.125, 0.05],
}


def anchor_set(anchor_count: int) -> list[int]:
    """返回档位对应的图序号列表；非法档位抛 ValueError。"""
    if anchor_count not in ANCHOR_SETS:
        raise ValueError(f"不支持的锚点档位数: {anchor_count}（仅支持 {sorted(ANCHOR_SETS)}）")
    return list(ANCHOR_SETS[anchor_count])


def _pick_levels(anchor_count: int, score_levels: dict | None) -> list[float]:
    """确定该档位 ratio 列表：config 的 score_levels[count] 优先，缺失用内置兜底表。"""
    levels = (score_levels or {}).get(str(anchor_count)) or DEFAULT_LEVELS.get(str(anchor_count))
    if not levels or len(levels) != anchor_count:
        raise ValueError(f"档位 {anchor_count} 的 ratio 表缺失或长度不符（需 {anchor_count} 个值）")
    return list(levels)


def _label_of(i: int, n: int) -> str:
    """label 约定：首 perfect、末 worst、中档 fair（3/5/9 均为奇数，中档唯一）。"""
    if i == 0:
        return "perfect"
    if i == n - 1:
        return "worst"
    if i == n // 2:
        return "fair"
    return ""


def default_anchor_config(char: str, anchor_count: int = 3, score_levels: dict | None = None) -> dict:
    """生成默认 anchor{count}.json 内容（有序列表，version 2）。anchor_count 决定档位数。"""
    nums = anchor_set(anchor_count)
    levels = _pick_levels(anchor_count, score_levels)
    anchors = [
        {"file": f"{num}.png", "score_ratio": ratio, "label": _label_of(i, anchor_count)}
        for i, (num, ratio) in enumerate(zip(nums, levels))
    ]
    return {"char": char, "version": "2", "anchors": anchors, "dimension_overrides": {}}


def anchor_config_path(anchor_dir: str | Path, char: str, anchor_count: int) -> Path:
    """返回档位配置文件路径 data/anchors/{char}/anchor{count}.json。"""
    return Path(anchor_dir) / char / f"anchor{anchor_count}.json"


def create_anchor_template(anchor_dir: str | Path, char: str, anchor_count: int = 3, score_levels: dict | None = None) -> Path:
    """创建锚点目录模板：目录 + 默认 anchor{count}.json（N 个锚点条目）。"""
    target = Path(anchor_dir) / char
    ensure_dir(target)
    config_path = anchor_config_path(anchor_dir, char, anchor_count)
    if not config_path.exists():
        config_path.write_text(
            json.dumps(default_anchor_config(char, anchor_count, score_levels), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return target


def load_anchor_config(anchor_dir: str | Path, char: str, anchor_count: int = 3) -> dict | None:
    """读取并校验 anchor{count}.json（无旧版兼容）。

    校验：文件存在、char 匹配、anchors 为有序列表、条数 == anchor_count、每条含 file 与 score_ratio。
    任一不满足返回 None。
    """
    config = load_json_safe(anchor_config_path(anchor_dir, char, anchor_count))
    if not isinstance(config, dict) or config.get("char") != char:
        return None
    anchors_raw = config.get("anchors")
    if not isinstance(anchors_raw, list) or len(anchors_raw) != anchor_count:
        return None
    anchors = [dict(a) for a in anchors_raw]
    if not all(a.get("file") and "score_ratio" in a for a in anchors):
        return None
    return {**config, "anchors": anchors}


def validate_anchor_dir(anchor_dir: str | Path, char: str, anchor_count: int = 3) -> list[str]:
    """校验锚点目录（针对指定档位）：返回问题列表（空列表 = 通过）。

    检查项：目录存在、anchor{count}.json 存在且合法、每条目对应 PNG 存在且可读、
    每张图非空白（颜色数 >= 2）。不检查其它档位/其它 json。
    """
    problems: list[str] = []
    target = Path(anchor_dir) / char
    if not target.is_dir():
        return [f"锚点目录不存在: {target}"]

    if anchor_count not in ANCHOR_SETS:
        return [f"不支持的锚点档位数: {anchor_count}（仅支持 {sorted(ANCHOR_SETS)}）"]

    config = load_anchor_config(anchor_dir, char, anchor_count)
    if config is None:
        cfg_path = anchor_config_path(anchor_dir, char, anchor_count)
        if not cfg_path.exists():
            problems.append(f"缺少 {cfg_path.name}（{anchor_count} 档配置），请先运行 init-anchor 生成模板")
        else:
            problems.append(f"{cfg_path.name} 不合法：char 不匹配 / 不是有序列表 / 条数≠{anchor_count} / 条目缺 file 或 score_ratio")
        return problems

    for entry in config["anchors"]:
        name = entry["file"]
        png = target / name
        if not png.exists():
            problems.append(f"缺少 {name}（{anchor_count} 档条目）")
            continue
        try:
            img = load_image(png)
        except Exception as exc:
            problems.append(f"{name} 无法读取: {exc}")
            continue
        if stroke_count(img) < 2:
            problems.append(f"{name} 疑似空白或颜色数不足（{stroke_count(img)} 色）")
    return problems
