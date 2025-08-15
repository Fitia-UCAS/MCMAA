# %% utils/paths.py
import os
import sys


def resource_path(*parts: str) -> str:
    """
    统一获取资源文件路径：
    - 打包后（PyInstaller --onefile）：使用 sys._MEIPASS 作为资源根目录
    - 开发环境：使用项目根目录（即本文件所在的 utils 目录的上一级）
    用法：
        resource_path("mcmaa.png")
        resource_path("utils", "template", "CUMCM.template")
    """
    # PyInstaller 在运行时会把打包的资源解压到临时目录 _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # 本文件位于 .../utils/paths.py -> 项目根目录是它的上一级
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base, *parts)
