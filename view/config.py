# %% view/config.py
# -*- coding: utf-8 -*-

# 内置库
import os


# 全局配置
DATA_CONFIG = {
    "app": None,
    "window": None,
    "screen": None,
    "py_path": os.path.dirname(os.path.abspath(__file__)),
}

SCREEN_CONFIG = {"borderwidth": 5, "relief": "raised"}
MAIN_FRAME_CONFIG = {"borderwidth": 5, "relief": "sunken"}
RAISED_SUBFRAME_CONFIG = {"borderwidth": 2, "relief": "raised"}
FLAT_SUBFRAME_CONFIG = {"borderwidth": 2}
ENTRY_LABEL_CONFIG = {"padding": 2}
