# %% utils/aid_loader.py
# -*- coding: utf-8 -*-

from pathlib import Path
from .paths import resource_path

# 允许的后缀（按你的需要增减）
_ALLOWED_SUFFIX = {".txt", ".md", ".tex"}  # 需要就加，或只留 .txt


def list_aid_files():
    """
    返回 [(显示名, 绝对路径), ...]，递归 utils/ai-aid-mcmaa
    显示名用相对目录，适合放到下拉框
    """
    base = Path(resource_path("utils", "ai-aid-mcmaa"))

    if not base.exists():
        return []

    files = []
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in _ALLOWED_SUFFIX:
            rel = p.relative_to(base).as_posix()
            files.append((rel, str(p)))

    # 按相对路径排序：带数字前缀的会自然排序
    files.sort(key=lambda t: t[0].lower())
    return files
