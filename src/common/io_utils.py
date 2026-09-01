# -*- coding: utf-8 -*-
"""通用 IO：目录管理、JSON 安全读写、字符清单与源工作簿发现。

约定：所有可复用函数只在此定义一次，业务模块 import 调用；错误统一由调用方处理或标记，不在此抛出致命异常（除参数错误）。
"""
from __future__ import annotations

import json
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，返回 Path 对象。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_json_safe(path: str | Path, default=None) -> object:
    """安全读取 JSON；文件不存在或解析失败时返回 default。"""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: str | Path, data: object, indent: int = 2) -> Path:
    """写入 JSON（UTF-8），自动创建父目录，返回路径。"""
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    return p


def read_lines(path: str | Path, default: list[str] | None = None) -> list[str]:
    """按行读取文本文件，去除空行与首尾空白；文件不存在时返回 default 或空列表。"""
    p = Path(path)
    if not p.exists():
        return list(default) if default else []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def list_source_workbooks(source_dir: str | Path) -> list[str]:
    """扫描源目录，返回全部 *_all_data_new.xlsx 对应的字名（排序去重）。"""
    names = sorted(p.stem.replace("_all_data_new", "") for p in Path(source_dir).glob("*_all_data_new.xlsx"))
    return names


def resolve_char_list(source_dir: str | Path, chars_file: str | Path | None = None) -> list[str]:
    """确定字符清单：显式 chars.txt 优先，否则自动扫描源目录全部工作簿。"""
    if chars_file:
        listed = read_lines(chars_file)
        if listed:
            return listed
    return list_source_workbooks(source_dir)
