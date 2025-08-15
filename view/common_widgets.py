# %% view/common_widget.py

# 内置库
from tkinter import *
import tkinter.filedialog as filedialog
from tkinter.scrolledtext import ScrolledText
import tkinter.messagebox as messagebox

# 第三方库
import ttkbootstrap as ttk


class TextWidget(ttk.Frame):
    def __init__(self, master, on_info=None, **kwargs):
        """
        文本小组件：
        - 带滚动条的可编辑文本框
        - 常用快捷键：撤销/全选/另存为（支持 Win/Linux 的 Ctrl 与 macOS 的 Command）
        :param master: 父容器
        :param on_info: 可选的回调函数，形如 on_info(msg: str)，用于显示提示信息
        :param kwargs: 传给 ttk.Frame 的其他参数
        """
        super().__init__(master, **kwargs)
        self.on_info = on_info

        # 创建可滚动的文本框，启用撤销功能
        self.textbox = ScrolledText(self, undo=True)
        self.textbox.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 设置文本框为可编辑状态
        self.textbox.config(state="normal")

        # 绑定快捷键（Win/Linux: Ctrl，macOS: Command）
        self.textbox.bind("<Control-z>", lambda event: self.textbox.edit_undo())  # Ctrl+Z 撤销
        self.textbox.bind("<Command-z>", lambda event: self.textbox.edit_undo())  # ⌘Z 撤销
        self.textbox.bind("<Control-Shift-s>", lambda event: self.save_as())  # Ctrl+Shift+S 另存为
        self.textbox.bind("<Command-Shift-s>", lambda event: self.save_as())  # ⌘⇧S 另存为
        self.textbox.bind("<Control-a>", self.select_all)  # Ctrl+A 全选
        self.textbox.bind("<Command-a>", self.select_all)  # ⌘A 全选

    def append(self, s):
        """清空并写入内容"""
        self.textbox.delete(1.0, "end")
        self.textbox.insert("end", s)

    def clear(self):
        """清空内容"""
        self.textbox.delete(1.0, "end")

    def get_content(self):
        """获取内容（去除末尾换行）"""
        return self.textbox.get(1.0, "end-1c")

    def save_as(self):
        """另存为功能"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            title="另存为",
        )
        if not file_path:
            return

        # 保存文本框内容到文件
        content = self.get_content()
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(content)
        except Exception as e:
            messagebox.showerror("保存失败", f"写入文件时出错：\n{e}")
            return

        # 提示成功：优先用回调，其次用消息框
        msg = f"成功：内容已另存为\n{file_path}"
        if callable(self.on_info):
            try:
                self.on_info(msg)
            except Exception:
                # 回调异常时回退到消息框
                messagebox.showinfo("成功", msg)
        else:
            messagebox.showinfo("成功", msg)

    def select_all(self, event=None):
        """全选文本"""
        self.textbox.tag_add("sel", "1.0", "end")
        return "break"  # 阻止默认事件处理
