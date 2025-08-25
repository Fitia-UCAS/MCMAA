# %% utils/py-contents.py
# -*- coding: utf-8 -*-

"""
只获取 .py 文件内容并写入指定文件
"""

# 内置库
import sys
import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# 要排除的文件夹
IGNORE_FOLDERS = [".git", "__pycache__", "ai-aid-mcmaa", ".venv", "env", "venv"]

# 要排除的文件
IGNORE_FILES = [
    "contents.py",
    "contents.txt",
    "__init__.py",
]


def generate_directory_structure(startpath, indent="", IGNORE_FOLDERS=None):
    """
    生成目录结构的字符串表示（只展示 .py 文件）
    """
    structure = ""
    path = Path(startpath)

    if not any(path.iterdir()):
        structure += f"{indent}|-- (空目录)\n"
    else:
        for item in path.iterdir():
            if item.is_dir():
                if IGNORE_FOLDERS and item.name in IGNORE_FOLDERS:
                    continue
                structure += f"{indent}|-- 文件夹: {item.name}\n"
                structure += generate_directory_structure(item, indent + "|   ", IGNORE_FOLDERS)
            else:
                if item.suffix == ".py" and item.name not in IGNORE_FILES:
                    structure += f"{indent}|-- 文件: {item.name}\n"
    return structure


def clean_content(content):
    """
    清理文本内容：原样返回
    """
    return content


def write_py_contents_to_file(scan_directory, output_directory, output_file_name, IGNORE_FOLDERS=None):
    """
    仅写入 .py 文件的内容
    """
    current_dir = Path(scan_directory)

    if not current_dir.is_dir():
        print(f"错误: {scan_directory} 不存在或不是目录.")
        return

    # 输出目录
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = output_dir / output_file_name

    with open(output_file_path, "w", encoding="utf-8") as output_file:
        # 写目录结构
        directory_structure = generate_directory_structure(current_dir, IGNORE_FOLDERS=IGNORE_FOLDERS)
        output_file.write("目录结构 (仅 .py 文件):\n")
        output_file.write(directory_structure)
        output_file.write("\n\n")

        # 遍历目录，只处理 .py 文件
        for root, dirs, files in os.walk(current_dir):
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]
            py_files = [f for f in files if f.endswith(".py") and f not in IGNORE_FILES]

            for file in py_files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except (UnicodeDecodeError, IsADirectoryError):
                    try:
                        with open(file_path, "r", encoding="latin1") as f:
                            content = f.read()
                    except Exception:
                        continue

                cleaned_content = clean_content(content)

                marker = "=" * 80
                output_file.write(f"{marker}\n")
                output_file.write(f"{file_path} 的内容:\n")
                output_file.write(f"{marker}\n")
                output_file.write(cleaned_content)
                output_file.write("\n\n")


def choose_directory(title="选择目录"):
    """选择扫描目录"""
    root = tk.Tk()
    root.withdraw()
    selected_directory = filedialog.askdirectory(title=title)
    return selected_directory


if __name__ == "__main__":
    scan_directory = choose_directory("选择要扫描的目录")
    if not scan_directory:
        print("未选择目录，程序退出。")
        sys.exit(0)

    output_directory = "./tools/"
    output_file_name = "py-contents.txt"

    write_py_contents_to_file(scan_directory, output_directory, output_file_name, IGNORE_FOLDERS)
