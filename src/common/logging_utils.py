# -*- coding: utf-8 -*-
"""日志公共操作：统一初始化 logger（控制台 + 运行日志文件）。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from common.io_utils import ensure_dir


def setup_logger(log_dir: str | Path, name: str = "ai_scoring", level: int = logging.INFO) -> logging.Logger:
    """初始化 logger：同时输出到控制台与 logs 目录下的运行日志文件。

    返回可复用的 logger；重复调用对同一 name 不重复添加 handler。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    log_dir = ensure_dir(log_dir)
    file_handler = logging.FileHandler(log_dir / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
