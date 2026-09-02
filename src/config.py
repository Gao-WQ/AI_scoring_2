# -*- coding: utf-8 -*-
"""全局配置加载。路径、维度上限、默认刻度等全部集中在此，业务代码不硬编码路径与魔法数字。

约定：所有参数通过 get_args() 传入（每个参数带 default），本模块只负责从 config.json 读取并解析路径。
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config(config_path: str | Path | None = None) -> dict:
    """读取 config.json，返回配置字典。"""
    path = Path(config_path) if config_path else CONFIG_PATH
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(cfg: dict, key: str) -> Path:
    """把配置中的相对路径解析为绝对路径（基于 project_root）。"""
    rel = cfg["paths"][key]
    p = Path(rel)
    if p.is_absolute():
        return p
    return Path(cfg["paths"]["project_root"]) / p


def resolve_all_paths(cfg: dict | None = None) -> dict[str, Path]:
    """解析全部路径为绝对路径，供各模块一次性获取（跳过非路径键如 input_suffix）。"""
    cfg = cfg or load_config()
    skip = {"input_suffix"}
    return {key: resolve_path(cfg, key) for key in cfg["paths"] if key not in skip}
