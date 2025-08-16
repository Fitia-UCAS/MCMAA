# %% utils/contents.py
# -*- coding: utf-8 -*-

# 内置库
import sys
import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# 定义需要忽略的文件扩展名
IGNORE_EXTENSIONS = [
    ".pyc",
    ".idx",
    ".pack",
    ".rev",
    ".sample",
    ".jpg",
    ".xmind",
    ".pdf",
    ".docx",
    ".zip",
    ".jpg",
    ".icns",
    ".ico",
    ".gif",
    ".agx",
    ".jpeg",
    ".synctex.gz",
    ".aux",
    ".log",
    ".wav",
    ".mp3",
    ".aac",
    ".xlsx",
    ".blg",
    ".out",
    ".toc",
    ".bbl",
    ".csv",
    ".ttf",
    ".md",
    ".m",
    ".cpp",
    ".ico",
    ".png",
    ".template",
    ".pkg",
    ".pyz",
    ".exe",
    ".html",
    # ".cls",
    # ".tex",
    # ".txt",
]

# 定义需要忽略的文件
IGNORE_FILES = [
    ".ignore",
    ".gitignore",
    ".gitattributes",
    "contents.py",
    "contents.txt",
    "grok.txt",
    "warn-main.txt",
    "info.tex",
    "main.tex",
    "cumcmthesis.cls",
    "references.bib",
]

# 排除的文件夹列表
IGNORE_FOLDERS = [".git", "__pycache__", "ai-aid-mcmaa"]


def generate_directory_structure(startpath, indent="", IGNORE_FOLDERS=None):
    """
    生成目录结构的字符串表示
    :param startpath: 要扫描的起始目录路径
    :param indent: 缩进字符，用于显示目录层级
    :param IGNORE_FOLDERS: 要排除的文件夹列表
    :return: 目录结构字符串
    """
    structure = ""
    path = Path(startpath)

    if not any(path.iterdir()):  # 如果目录为空
        structure += f"{indent}|-- (空目录)\n"
    else:
        for item in path.iterdir():
            if item.is_dir():
                # 如果该文件夹在排除列表中，则跳过
                if IGNORE_FOLDERS and item.name in IGNORE_FOLDERS:
                    continue
                structure += f"{indent}|-- 文件夹: {item.name}\n"
                # 递归生成子目录结构
                structure += generate_directory_structure(item, indent + "|   ", IGNORE_FOLDERS)
            else:
                structure += f"{indent}|-- 文件: {item.name}\n"
    return structure


def clean_content(content):
    """
    清理文本内容：原样返回内容，不进行任何修改
    :param content: 要处理的文本内容
    :return: 原样返回内容
    """
    return content


def write_directory_contents_to_file(scan_directory, output_directory, output_file_name, IGNORE_FOLDERS=None):
    """
    将目录内容和文件内容写入到指定的输出文件
    :param scan_directory: 要扫描的目录路径
    :param output_directory: 输出文件夹路径
    :param output_file_name: 输出文件名
    :param IGNORE_FOLDERS: 要排除的文件夹列表
    """
    # 获取当前脚本所在的目录
    current_dir = Path(scan_directory)

    # 验证扫描目录是否存在
    if not current_dir.is_dir():
        print(f"错误: 指定的扫描目录 {scan_directory} 不存在或不是目录.")
        return

    # 确保输出目录存在
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构建输出文件路径
    output_file_path = output_dir / output_file_name

    with open(output_file_path, "w", encoding="utf-8") as output_file:
        # 写入目录结构
        directory_structure = generate_directory_structure(current_dir, IGNORE_FOLDERS=IGNORE_FOLDERS)
        output_file.write("目录结构:\n")
        output_file.write(directory_structure)
        output_file.write("\n\n")

        # 遍历当前目录
        for root, dirs, files in os.walk(current_dir):
            # 排除特定的文件夹
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS]
            dirs[:] = [d for d in dirs if d != ".git"]  # 额外忽略 .git 文件夹

            # 过滤掉忽略的文件
            files = [f for f in files if not (any(f.endswith(ext) for ext in IGNORE_EXTENSIONS) or f in IGNORE_FILES)]

            # 处理文件内容
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    # 尝试以 UTF-8 编码读取文件
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except (UnicodeDecodeError, IsADirectoryError):
                    try:
                        # 如果 UTF-8 失败，尝试以 latin1 编码读取
                        with open(file_path, "r", encoding="latin1") as f:
                            content = f.read()
                    except (UnicodeDecodeError, IsADirectoryError):
                        continue

                # 清理内容（当前为原样返回）
                cleaned_content = clean_content(content)

                # 写入文件内容并添加分隔线
                marker = "=" * 80
                output_file.write(f"{marker}\n")
                output_file.write(f"{file_path} 的内容:\n")
                output_file.write(f"{marker}\n")
                output_file.write(cleaned_content)
                output_file.write("\n\n")


def choose_directory(title="选择目录"):
    """
    打开一个目录选择对话框，允许用户选择目录
    :param title: 对话框的标题
    :return: 用户选择的目录路径
    """
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    selected_directory = filedialog.askdirectory(title=title)
    return selected_directory


if __name__ == "__main__":
    # 选择要扫描的目录
    scan_directory = choose_directory("选择要扫描的目录")
    if not scan_directory:
        print("未选择目录，程序退出。")
        sys.exit(0)

    # 设置输出路径和文件名
    output_directory = "./mcmaa_tk/utils/"
    output_file_name = "contents.txt"

    # 将目录内容写入文件
    write_directory_contents_to_file(scan_directory, output_directory, output_file_name, IGNORE_FOLDERS)
