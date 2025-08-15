# %% view/screens/screen4_atom_editor.py

from tkinter import *
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import os
import tkinter.filedialog as filedialog

from ..config import (
    DATA_CONFIG,
    SCREEN_CONFIG,
    MAIN_FRAME_CONFIG,
    FLAT_SUBFRAME_CONFIG,
)
from model.latex_extractor import LatexExtractor


class Screen4_AtomLike_Editor(ttk.Frame):
    """
    写作编辑器（与屏幕2/3同风格）：
    左侧：按钮区 + 信息区
    右侧：Notebook(编辑/预览)；左侧再带一个 Notebook(大纲/问题) 便于导航
    """

    MODE_NAME = "写作编辑器"

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        # 和 1/2/3 一致：使用 place + PanedWindow
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 状态
        self.current_file = None
        self.extractor = None

        # ===== 主左右分割 =====
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧再垂直分割（按钮区 + 信息区）
        self.left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(self.left_paned, weight=30)

        # 右侧容器
        right_frame = ttk.Frame(main_paned, **MAIN_FRAME_CONFIG)
        main_paned.add(right_frame, weight=70)

        # 右侧再垂直分割（上内容，下状态/空白扩展）
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # ===== 左侧：按钮区 =====
        self.button_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.button_frame, weight=1)

        # 按钮区内容（同风格的竖排按钮）
        bh = 50  # 每个控件高度
        self.button_frame.config(height=bh * 6)

        row0 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        row0.place(relx=0, rely=0.00, relwidth=1, height=bh)
        self.button_mode = ttk.OptionMenu(row0, DATA_CONFIG["mode"], "", command=self.master.change_mode)
        self.button_mode.set_menu(self.MODE_NAME, *DATA_CONFIG["modes"])
        self.button_mode.place(relx=0, rely=0, relwidth=1, relheight=1)

        row1 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        row1.place(relx=0, rely=0.17, relwidth=1, height=bh)
        self.btn_open = ttk.Button(row1, text="打开 .tex / .template", command=self.select_file)
        self.btn_open.place(relx=0, rely=0, relwidth=1, relheight=1)

        row2 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        row2.place(relx=0, rely=0.34, relwidth=1, height=bh)
        self.btn_save = ttk.Button(row2, text="保存编辑内容到文件", command=self.save_current_text)
        self.btn_save.place(relx=0, rely=0, relwidth=1, relheight=1)

        row3 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        row3.place(relx=0, rely=0.51, relwidth=1, height=bh)
        self.btn_refresh = ttk.Button(row3, text="重新解析", command=self.refresh_all)
        self.btn_refresh.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧：导航 Notebook（大纲/问题）
        row4 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        row4.place(relx=0, rely=0.68, relwidth=1, relheight=bh)
        ttk.Label(row4, text="导航").place(relx=0, rely=0, relwidth=1, relheight=1)

        self.nav_holder = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.nav_holder, weight=2)

        self.left_tabs = ttk.Notebook(self.nav_holder)
        self.left_tabs.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.outline_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.outline_tab, text="大纲")
        self.outline_tree = ttk.Treeview(self.outline_tab, show="tree")
        self.outline_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.outline_tree.bind("<<TreeviewSelect>>", self.on_outline_select)

        self.problem_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.problem_tab, text="问题")
        self.problem_tree = ttk.Treeview(self.problem_tab, show="tree")
        self.problem_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.problem_tree.bind("<<TreeviewSelect>>", self.on_problem_select)

        # ===== 左侧：信息区 =====
        self.info_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.info_frame, weight=1)

        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)

        # ===== 右侧：Notebook(编辑/预览) =====
        self.notebook = ttk.Notebook(self.right_paned)
        self.right_paned.add(self.notebook, weight=7)

        self.tab_edit = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_edit, text="编辑")

        self.tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview, text="预览")

        # 编辑器
        self.editor = ScrolledText(self.tab_edit, wrap="none", undo=True)
        self.editor.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.editor.bind("<Control-a>", lambda e: self._select_all(self.editor))
        self.editor.bind("<Control-s>", lambda e: (self.save_current_text(), "break"))

        # 预览
        self.preview = ScrolledText(self.tab_preview, wrap="word", state="disabled")
        self.preview.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 底部状态（右侧再加一个空白区撑开结构，保持与 2/3 一致）
        self.status_holder = ttk.Frame(self.right_paned, **MAIN_FRAME_CONFIG)
        self.right_paned.add(self.status_holder, weight=1)
        self.status = ttk.Label(self.status_holder, text="就绪", anchor="w")
        self.status.place(relx=0, rely=0, relwidth=1)

    # ============== 工具函数 ==============
    def info_text_append(self, text):
        self.info_text.config(state="normal")
        self.info_text.insert("end", text + "\n")
        self.info_text.config(state="disabled")
        self.info_text.see("end")

    def set_preview(self, text):
        self.notebook.select(self.tab_preview)
        self.preview.config(state="normal")
        self.preview.delete(1.0, "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    def _select_all(self, widget):
        widget.tag_add("sel", "1.0", "end")
        return "break"

    # ============== 文件 I/O ==============
    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 LaTeX 文件",
            filetypes=[
                ("LaTeX files", "*.tex"),
                ("LaTeX Template files", "*.template"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        self.current_file = file_path
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.editor.delete(1.0, "end")
            self.editor.insert("end", text)
            self.set_preview("文件已加载: " + file_path)
            self.build_extractor()
            self.notebook.select(self.tab_edit)
        except Exception as e:
            self.set_preview(f"错误: {e}")

    def save_current_text(self):
        if not self.current_file:
            self.info_text_append("提示: 尚未打开文件")
            return
        try:
            text = self.editor.get(1.0, "end-1c")
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.info_text_append("已保存: " + self.current_file)
            self.build_extractor()
        except Exception as e:
            self.set_preview(f"保存失败: {e}")

    # ============== 解析 & 构建树 ==============
    def build_extractor(self):
        try:
            self.extractor = LatexExtractor(self.current_file, max_level=3)
            self.refresh_all()
            self.status.config(text=f"已解析: {os.path.basename(self.current_file)}")
        except Exception as e:
            self.set_preview(f"解析失败: {e}")

    def refresh_all(self):
        if not self.extractor:
            self.set_preview("提示: 尚未解析文件")
            return
        self._build_outline_tree()
        self._build_problem_tree()
        self.info_text_append("导航已刷新")

    def _build_outline_tree(self):
        self.outline_tree.delete(*self.outline_tree.get_children())
        stack = [("", 0)]
        for section_type, title, level, line_num in self.extractor.sections:
            while stack and level <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0] if stack else ""
            node = self.outline_tree.insert(parent, "end", text=title, values=(line_num, level))
            stack.append((node, level))

    def _build_problem_tree(self):
        self.problem_tree.delete(*self.problem_tree.get_children())
        try:
            keywords = self.extractor.get_unique_keywords()
        except Exception:
            keywords = []
        for k in keywords:
            pnode = self.problem_tree.insert("", "end", text=f"问题{k}", values=(k,))
            self.problem_tree.insert(pnode, "end", text="摘要片段", values=(k, "abstract"))
            self.problem_tree.insert(pnode, "end", text="问题重述", values=(k, "restate"))
            self.problem_tree.insert(pnode, "end", text="问题分析", values=(k, "analysis"))
            self.problem_tree.insert(pnode, "end", text="模型与求解", values=(k, "modeling"))

    # ============== 事件：树选择 ==============
    def on_outline_select(self, _event):
        if not self.extractor:
            return
        item = self.outline_tree.focus()
        if not item:
            return
        vals = self.outline_tree.item(item, "values")
        if not vals:
            return
        line_num = int(vals[0])
        section_level = int(vals[1])
        content = self.extractor.extract_content(line_num, section_level)
        self.set_preview("\n".join(content))

    def on_problem_select(self, _event):
        if not self.extractor:
            return
        item = self.problem_tree.focus()
        if not item:
            return
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        if len(vals) == 1:
            self._show_problem_all(vals[0])
        else:
            k, part = vals
            self._show_problem_part(k, part)

    def _show_problem_all(self, k):
        parts = self.extractor.extract_problem_parts(k)
        abstract = self.extractor.extract_abstract_parts(k)
        merged = []
        if abstract:
            merged += ["% ===== 摘要片段 ====="] + abstract + [""]
        if "Restatement" in parts:
            merged += ["% ===== 问题重述 ====="] + parts["Restatement"] + [""]
        if "Analysis" in parts:
            merged += ["% ===== 问题分析 ====="] + parts["Analysis"] + [""]
        if "Modeling" in parts:
            merged += ["% ===== 模型与求解 ====="] + parts["Modeling"] + [""]
        self.set_preview("\n".join(merged) if merged else "未找到对应内容")

    def _show_problem_part(self, k, part):
        parts = self.extractor.extract_problem_parts(k)
        if part == "abstract":
            content = self.extractor.extract_abstract_parts(k)
        elif part == "restate":
            content = parts.get("Restatement", [])
        elif part == "analysis":
            content = parts.get("Analysis", [])
        elif part == "modeling":
            content = parts.get("Modeling", [])
        else:
            content = []
        self.set_preview("\n".join(content) if content else "未找到对应内容")
