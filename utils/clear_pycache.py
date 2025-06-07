# %% utils/clear_pycache.py

import os
import shutil


def clear_pycache(root_dir="."):
    for dirpath, dirnames, _ in os.walk(root_dir):
        for dirname in dirnames:
            # 如果是 __pycache__ 文件夹，删除它
            if dirname == "__pycache__":
                dir_to_delete = os.path.join(dirpath, dirname)
                # print(f"Deleting: {dir_to_delete}")
                shutil.rmtree(dir_to_delete)
