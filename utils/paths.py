# utils/paths.py
# -*- coding: utf-8 -*-
import sys
from pathlib import Path


def resource_path(*parts: str) -> str:
    """
    - 打包后：以 _MEIPASS 为根
    - 开发期：以项目根目录为根（utils 的上一级）
    - 可传多段路径：resource_path("utils", "ai-aid-mcmaa", "1.txt")
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[1]
    return str(base.joinpath(*parts))
