# %% view/common_widget.py

# 内置库
import sys
from tkinter import *
import tkinter.filedialog as filedialog
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk

# 第三方库
import ttkbootstrap as ttk


class TextWidget(ttk.Frame):
    def __init__(self, master, **kwargs):
        # 初始化文本小组件，继承自 ttk.Frame
        super().__init__(master, **kwargs)
        # 创建可滚动的文本框，启用撤销功能
        self.textbox = ScrolledText(self, undo=True)
        self.textbox.place(relx=0, rely=0, relwidth=1, relheight=1)
        # 设置文本框为可编辑状态
        self.textbox.config(state="normal")
        # 绑定快捷键
        self.textbox.bind("<Control-z>", lambda event: self.textbox.edit_undo())  # Ctrl+Z 撤销
        self.textbox.bind("<Control-Shift-s>", lambda event: self.save_as())  # Ctrl+Shift+S 另存为
        self.textbox.bind("<Control-a>", self.select_all)  # Ctrl+A 全选

    def append(self, s):
        # 清空文本框并追加新内容
        self.textbox.delete(1.0, "end")
        self.textbox.insert("end", s)

    def clear(self):
        # 清空文本框内容
        self.textbox.delete(1.0, "end")

    def get_content(self):
        # 获取文本框内容，排除末尾换行符
        return self.textbox.get(1.0, "end-1c")

    def save_as(self):
        """另存为功能"""
        # 打开文件保存对话框
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            title="另存为",
        )
        if file_path:
            # 保存文本框内容到文件
            content = self.get_content()
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
            # 在信息面板显示保存成功的消息
            self.master.info_text_append(f"成功: 内容已另存为 {file_path}")

    def select_all(self, event):
        """全选文本"""
        # 选中文本框所有内容
        self.textbox.tag_add("sel", "1.0", "end")
        return "break"  # 阻止默认事件处理
