# %% view/screens/screen_workbench.py

from tkinter import *
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import os
import re
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from ..config import DATA_CONFIG, SCREEN_CONFIG, MAIN_FRAME_CONFIG
from model.latex_extractor import LatexExtractor
from model.text_replacer import find_marker_pairs, replace_contents


class Screen_Workbench(ttk.Frame):
    """
    一体化工作台（极简版）
    - 左侧：导航（大纲/问题）
    - 右侧：Notebook（编辑 / 预览 / 替换）
    - 文件快捷键：Ctrl+O 打开；Ctrl+S 保存
    """

    MODE_NAME = "一体化工作台"

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 状态
        self.current_file = None
        self.extractor = None
        self.marker_pairs = []
        self.replacements = {}
        self.selected_pair_display = StringVar(value="选择标记对")

        # ===== 主左右分割 =====
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧：仅导航（大纲/问题）
        left_frame = ttk.Frame(main_paned, **MAIN_FRAME_CONFIG)
        main_paned.add(left_frame, weight=30)
        self.left_tabs = ttk.Notebook(left_frame)
        self.left_tabs.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 大纲
        self.outline_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.outline_tab, text="大纲")
        self.outline_tree = ttk.Treeview(self.outline_tab, show="tree")
        self.outline_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.outline_tree.bind("<<TreeviewSelect>>", self.on_outline_select)

        # 问题
        self.problem_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.problem_tab, text="问题")
        self.problem_tree = ttk.Treeview(self.problem_tab, show="tree")
        self.problem_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.problem_tree.bind("<<TreeviewSelect>>", self.on_problem_select)

        # 右侧：Notebook（编辑/预览/替换）
        right_frame = ttk.Frame(main_paned, **MAIN_FRAME_CONFIG)
        main_paned.add(right_frame, weight=70)
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 编辑
        self.tab_edit = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_edit, text="编辑")
        self.editor = ScrolledText(self.tab_edit, wrap="none", undo=True)
        self.editor.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.editor.bind("<Control-a>", lambda e: self._select_all(self.editor))
        self.editor.bind("<Control-s>", lambda e: (self.save_current_text(), "break"))
        self.editor.bind("<Control-o>", lambda e: (self.select_file(), "break"))

        # 预览
        self.tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview, text="预览")
        self.preview = ScrolledText(self.tab_preview, wrap="word", state="disabled")
        self.preview.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 替换（把“输入替换内容”搬到这里）
        self.tab_replace = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_replace, text="替换")
        # 顶部：标记对选择
        topbar = ttk.Frame(self.tab_replace)
        topbar.place(relx=0, rely=0, relwidth=1, height=40)
        ttk.Label(topbar, text="标记对：").place(relx=0.0, rely=0, relwidth=0.12, relheight=1)
        self.pair_menu = ttk.OptionMenu(topbar, self.selected_pair_display, "选择标记对")
        self.pair_menu.place(relx=0.12, rely=0, relwidth=0.88, relheight=1)
        self.selected_pair_display.trace_add("write", self.on_pair_select)

        # 中部：输入框
        self.replace_input = ScrolledText(self.tab_replace, wrap="word")
        self.replace_input.place(relx=0, rely=0.07, relwidth=1, relheight=0.83)
        self.replace_input.bind("<Control-a>", self._select_all)
        self.replace_input.bind("<Control-s>", lambda e: (self.apply_replace(), "break"))

        # 底部：应用按钮
        btn = ttk.Button(self.tab_replace, text="应用替换到编辑器", command=self.apply_replace)
        btn.place(relx=0, rely=0.92, relwidth=1, relheight=0.07)

        # 进入“替换”页时自动扫描标记对
        self.notebook.bind("<<NotebookTabChanged>>", self._maybe_refresh_pairs)

    # --------- 工具函数 ---------
    def _select_all(self, widget):
        widget.tag_add("sel", "1.0", "end")
        return "break"

    def _get_editor_text(self):
        return self.editor.get(1.0, "end-1c")

    def set_preview(self, text):
        self.notebook.select(self.tab_preview)
        self.preview.config(state="normal")
        self.preview.delete(1.0, "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    # --------- 文件 I/O（快捷键驱动） ---------
    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 LaTeX 文件",
            filetypes=[("LaTeX files", "*.tex"), ("LaTeX Template files", "*.template"), ("All files", "*.*")],
        )
        if not file_path:
            return
        self.current_file = file_path
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
            self.editor.delete(1.0, "end")
            self.editor.insert("end", text)
            self.set_preview(f"文件已加载: {file_path}")
            self.build_extractor()
            self._refresh_marker_pairs()  # 初始也扫描一次
            self.notebook.select(self.tab_edit)
        except Exception as e:
            self.set_preview(f"错误: {e}")

    def save_current_text(self):
        if not self.current_file:
            return
        try:
            text = self._get_editor_text()
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.build_extractor()  # 保存后重建导航
        except Exception as e:
            self.set_preview(f"保存失败: {e}")

    # --------- 解析 / 导航 ---------
    def build_extractor(self):
        try:
            if not self.current_file:
                self.set_preview("提示: 尚未打开文件")
                return
            self.extractor = LatexExtractor(self.current_file, max_level=3)
            self._build_outline_tree()
            self._build_problem_tree()
        except Exception as e:
            self.set_preview(f"解析失败: {e}")

    def _build_outline_tree(self):
        self.outline_tree.delete(*self.outline_tree.get_children())
        if not self.extractor:
            return
        stack = [("", 0)]
        for section_type, title, level, line_num in self.extractor.sections:
            while stack and level <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0] if stack else ""
            node = self.outline_tree.insert(parent, "end", text=title, values=(line_num, level))
            stack.append((node, level))

    def _build_problem_tree(self):
        self.problem_tree.delete(*self.problem_tree.get_children())
        if not self.extractor:
            return
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

    # --------- 导航事件 ---------
    def on_outline_select(self, _event):
        if not self.extractor:
            return
        item = self.outline_tree.focus()
        vals = self.outline_tree.item(item, "values")
        if not vals:
            return
        line_num, section_level = map(int, vals)
        content = self.extractor.extract_content(line_num, section_level)
        self.set_preview("\n".join(content))

    def on_problem_select(self, _event):
        if not self.extractor:
            return
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        if len(vals) == 1:  # 点击“问题X”
            k = vals[0]
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
        else:
            k, part = vals
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

    # --------- 替换功能 ---------
    def _maybe_refresh_pairs(self, _evt=None):
        # 只有切到“替换”页时刷新
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
            if tab_text == "替换":
                self._refresh_marker_pairs()
        except Exception:
            pass

    def _refresh_marker_pairs(self):
        text = self._get_editor_text()
        self.marker_pairs = find_marker_pairs(text)
        display = ["选择标记对"]
        for pair in self.marker_pairs:
            match = re.search(r"<-----(.*?)----->", pair["marker_type"])
            disp = match.group(1).strip() if match else pair["marker_type"]
            display.append(disp)
        self.pair_menu.set_menu(*display)
        self.selected_pair_display.set("选择标记对")

    def on_pair_select(self, *_):
        sel = self.selected_pair_display.get()
        if sel == "选择标记对":
            self.replace_input.delete(1.0, "end")
            return
        for pair in self.marker_pairs:
            match = re.search(r"<-----(.*?)----->", pair["marker_type"])
            disp = match.group(1).strip() if match else pair["marker_type"]
            if disp == sel:
                self.replace_input.delete(1.0, "end")
                idx = pair["index"]
                self.replace_input.insert("end", self.replacements.get(idx, pair["content"]))
                break

    def apply_replace(self):
        sel = self.selected_pair_display.get()
        if sel == "选择标记对":
            return
        # 找索引
        idx = None
        for pair in self.marker_pairs:
            match = re.search(r"<-----(.*?)----->", pair["marker_type"])
            disp = match.group(1).strip() if match else pair["marker_type"]
            if disp == sel:
                idx = pair["index"]
                break
        if idx is None:
            return

        try:
            new_content = self.replace_input.get(1.0, "end-1c")
            self.replacements[idx] = new_content
            base_text = self._get_editor_text()
            new_text = replace_contents(base_text, self.replacements)
            self.editor.delete(1.0, "end")
            self.editor.insert("end", new_text)
            # 替换后再次扫描，保持索引准确
            self._refresh_marker_pairs()
        except Exception as e:
            messagebox.showerror("错误", f"替换失败: {str(e)}")
