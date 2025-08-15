# %% view/screens/screen_workbench.py

from tkinter import *
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import os
import re
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import pathlib, appdirs

from ..config import DATA_CONFIG, SCREEN_CONFIG, MAIN_FRAME_CONFIG
from model.latex_extractor import LatexExtractor
from model.text_replacer import find_marker_pairs, replace_contents
from utils.paths import resource_path


RECENT_FILE_MAX = 5
RECENT_FILE_STORE = "recent_files.txt"


class Screen_Workbench(ttk.Frame):
    """
    一体化工作台（极简版）
    - 左侧：导航（大纲/问题/代码）
    - 右侧：Notebook（编辑 / 预览 / 替换）
    - 文件快捷键：Ctrl+O 打开；Ctrl+S 保存（替换页为“应用替换”）
    - Ctrl+F 全文搜索；Ctrl+H 全文替换
    """

    MODE_NAME = "一体化工作台"

    # ---------- 最近文件：读写 ----------
    @staticmethod
    def _recent_store_path():
        """
        将最近文件记录存放到用户数据目录，跨平台更稳：
        Windows:  C:\\Users\\<User>\\AppData\\Local\\mcm\\mcmaa\\recent_files.txt
        macOS:    ~/Library/Application Support/mcmaa/recent_files.txt
        Linux:    ~/.local/share/mcmaa/recent_files.txt
        """
        app_dir = appdirs.user_data_dir(appname="mcmaa", appauthor="mcm")
        pathlib.Path(app_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(app_dir, RECENT_FILE_STORE)

    @staticmethod
    def _load_recent():
        path = Screen_Workbench._recent_store_path()
        items = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    p = line.strip()
                    if p and os.path.exists(p):
                        items.append(p)
        except Exception:
            pass
        return items[:RECENT_FILE_MAX]

    @staticmethod
    def _save_recent(items):
        path = Screen_Workbench._recent_store_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                for p in items[:RECENT_FILE_MAX]:
                    f.write(p + "\n")
        except Exception:
            pass

    def _add_recent(self, p):
        if not p:
            return
        if p in self.recent_files:
            self.recent_files.remove(p)
        self.recent_files.insert(0, p)
        self.recent_files = self.recent_files[:RECENT_FILE_MAX]
        self._save_recent(self.recent_files)

    # ---------- 对外给菜单用的 API ----------
    def get_recent_files(self):
        """给主菜单调用，获取最近文件列表（最新在前）"""
        return list(self.recent_files)

    def quick_open(self, p):
        """给主菜单的 Quick Open 点击使用"""
        if not p or not os.path.exists(p):
            messagebox.showwarning("提示", "文件不存在，已从最近列表移除。")
            try:
                self.recent_files.remove(p)
                self._save_recent(self.recent_files)
            except Exception:
                pass
            return
        self._open_path(p)

    # =====================================================

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 状态
        self.current_file = None
        self.extractor = None
        self.marker_pairs = []
        self.replacements = {}
        self.selected_pair_display = StringVar(value="")  # Combobox 使用空初值更自然
        self.recent_files = self._load_recent()

        # ===== 主左右分割 =====
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧：导航（大纲/问题/代码）
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
        # 双击大纲项：跳转到编辑器对应行并闪烁高亮
        self.outline_tree.bind("<Double-1>", self._goto_outline_line)

        # 问题（含右键菜单）
        self.problem_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.problem_tab, text="问题")
        self.problem_tree = ttk.Treeview(self.problem_tab, show="tree")
        self.problem_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.problem_tree.bind("<<TreeviewSelect>>", self.on_problem_select)
        self._init_problem_context_menu()

        # 代码（新的 Treeview，专门放 codeblock）
        self.code_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.code_tab, text="代码")
        self.code_tree = ttk.Treeview(self.code_tab, show="tree")
        self.code_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.code_tree.bind("<<TreeviewSelect>>", self.on_code_select)

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
        # 快捷键（Win/Linux: Ctrl，macOS: Command）
        self.editor.bind("<Control-a>", lambda e: self._select_all(self.editor))
        self.editor.bind("<Control-s>", lambda e: (self.save_current_text(), "break"))
        self.editor.bind("<Control-o>", lambda e: (self.select_file(), "break"))
        self.editor.bind("<Control-f>", lambda e: (self._open_find_dialog(), "break"))
        self.editor.bind("<Control-h>", lambda e: (self._open_replace_dialog(), "break"))
        self.editor.bind("<Command-a>", lambda e: self._select_all(self.editor))
        self.editor.bind("<Command-s>", lambda e: (self.save_current_text(), "break"))
        self.editor.bind("<Command-o>", lambda e: (self.select_file(), "break"))
        self.editor.bind("<Command-f>", lambda e: (self._open_find_dialog(), "break"))
        self.editor.bind("<Command-h>", lambda e: (self._open_replace_dialog(), "break"))

        # 预览
        self.tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview, text="预览")
        self.preview = ScrolledText(self.tab_preview, wrap="word", state="disabled")
        self.preview.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 替换页
        self.tab_replace = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_replace, text="替换")

        # 顶部工具栏：标记对下拉 + 主按钮（用 pack 占据横向）
        topbar = ttk.Frame(self.tab_replace, padding=(8, 6))
        topbar.pack(side="top", fill="x")

        ttk.Label(topbar, text="标记对：").pack(side="left")
        self.pair_combo = ttk.Combobox(topbar, textvariable=self.selected_pair_display, state="readonly", width=40)
        self.pair_combo.pack(side="left", padx=(6, 8), fill="x", expand=True)
        self.pair_combo.bind("<<ComboboxSelected>>", lambda e: self.on_pair_select())

        apply_btn = ttk.Button(topbar, text="应用替换（Ctrl+S）", bootstyle="primary", command=self.apply_replace)
        apply_btn.pack(side="right")

        # 中部：输入框 —— 占满剩余全部空间（解决底部留白）
        self.replace_input = ScrolledText(self.tab_replace, wrap="word")
        self.replace_input.pack(side="top", fill="both", expand=True)
        self.replace_input.bind("<Control-a>", self._select_all)
        self.replace_input.bind("<Command-a>", self._select_all)

        # 全局 Ctrl/⌘+S：替换页=应用替换；其它页=保存
        self.bind_all("<Control-s>", self._on_global_save_or_apply)
        self.bind_all("<Command-s>", self._on_global_save_or_apply)

        # 进入“替换”页时自动扫描标记对
        self.notebook.bind("<<NotebookTabChanged>>", self._maybe_refresh_pairs)

        # ===== 辅助页：展示 utils/ai-aid-mcmaa 下的 .txt，并可一键插入到编辑器 =====
        self.tab_aid = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_aid, text="辅助")

        # 顶部工具栏：文件下拉 + 主按钮
        aid_top = ttk.Frame(self.tab_aid, padding=(8, 6))
        aid_top.pack(side="top", fill="x")

        ttk.Label(aid_top, text="辅助文件：").pack(side="left")
        self.aid_selected = ttk.StringVar(value="")
        self.aid_combo = ttk.Combobox(aid_top, textvariable=self.aid_selected, state="readonly", width=46)
        self.aid_combo.pack(side="left", padx=(6, 8), fill="x", expand=True)
        self.aid_combo.bind("<<ComboboxSelected>>", lambda e: self._on_aid_select())

        aid_apply_btn = ttk.Button(
            aid_top, text="插入到编辑器（Ctrl+S）", bootstyle="secondary", command=self.apply_aid_to_editor
        )
        aid_apply_btn.pack(side="right")

        # 中部文本：显示所选 txt 的内容（可编辑，便于临时调整；如需只读把 state 设为 disabled）
        self.aid_view = ScrolledText(self.tab_aid, wrap="word")
        self.aid_view.pack(side="top", fill="both", expand=True)
        self.aid_view.bind("<Control-a>", self._select_all)
        self.aid_view.bind("<Command-a>", self._select_all)

        # 进入“辅助”页时刷新文件列表
        def _maybe_refresh_aid(_evt=None):
            try:
                if self.notebook.tab(self.notebook.select(), "text") == "辅助":
                    self._refresh_aid_files()
            except Exception:
                pass

        self.notebook.bind("<<NotebookTabChanged>>", _maybe_refresh_aid)

        # 首次构建时也加载一次
        self._refresh_aid_files()

    # ---------- 辅助页：文件列表/读取/插入 ----------
    def _aid_dir_path(self):
        """
        返回 utils/ai-aid-mcmaa 目录（支持打包后运行）
        """
        return resource_path("utils", "ai-aid-mcmaa")

    def _refresh_aid_files(self):
        """
        刷新下拉列表，枚举目录下的 .txt 文件
        """
        aid_dir = self._aid_dir_path()
        files = []
        try:
            if os.path.isdir(aid_dir):
                for name in os.listdir(aid_dir):
                    if name.lower().endswith(".txt"):
                        files.append(name)
        except Exception:
            files = []

        files.sort()
        self.aid_combo["values"] = files
        # 若没有选中或当前选中的文件已不存在，默认选中第一项
        if not files:
            self.aid_selected.set("")
            self.aid_view.delete(1.0, "end")
        else:
            cur = self.aid_selected.get()
            if cur not in files:
                self.aid_selected.set(files[0])
            self._on_aid_select()

    def _on_aid_select(self):
        """
        读取被选中的 txt 内容到中部文本框
        """
        fname = self.aid_selected.get().strip()
        if not fname:
            self.aid_view.delete(1.0, "end")
            return
        fpath = os.path.join(self._aid_dir_path(), fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                txt = f.read()
        except Exception as e:
            txt = f"(读取失败：{e})"
        self.aid_view.delete(1.0, "end")
        self.aid_view.insert("end", txt)

    def apply_aid_to_editor(self):
        """
        将辅助区当前内容插入编辑器：
        - 若编辑器有选区：替换选区
        - 否则：在光标处插入
        最后把焦点切回编辑器，便于继续编辑。
        """
        content = self.aid_view.get(1.0, "end-1c")
        self.notebook.select(self.tab_edit)
        self.editor.focus_set()
        try:
            try:
                # 如果有选区则替换
                sel_start = self.editor.index("sel.first")
                sel_end = self.editor.index("sel.last")
                self.editor.delete(sel_start, sel_end)
                self.editor.insert(sel_start, content)
                self.editor.mark_set(INSERT, f"{sel_start}+{len(content)}c")
            except Exception:
                # 没有选区，在光标处插入
                self.editor.insert(INSERT, content)
                self.editor.mark_set(INSERT, f"insert+{len(content)}c")
        except Exception as e:
            messagebox.showerror("错误", f"插入失败：{e}")

    # ---------------- 工具函数 ----------------
    def _select_all(self, target=None):
        """
        支持两种调用方式：
        1) 作为事件回调：_select_all(event) —— 从 event.widget 取出控件
        2) 直接传控件：_select_all(widget)
        """
        widget = None
        if hasattr(target, "widget"):  # 事件对象
            widget = target.widget
        elif target is not None:  # 直接传入控件
            widget = target
        else:
            return "break"

        try:
            widget.tag_add("sel", "1.0", "end")
        except Exception:
            pass
        return "break"

    def _get_editor_text(self):
        return self.editor.get(1.0, "end-1c")

    def set_preview(self, text):
        self.notebook.select(self.tab_preview)
        self.preview.config(state="normal")
        self.preview.delete(1.0, "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    # 全局保存/应用的统一入口

    def _on_global_save_or_apply(self, _event=None):
        """全局快捷键：替换页 Ctrl/⌘+S 应用替换；辅助页插入文本；其它页保存文件"""
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
        except Exception:
            tab_text = ""
        if tab_text == "替换":
            self.apply_replace()
        elif tab_text == "辅助":
            self.apply_aid_to_editor()
        else:
            self.save_current_text()
        return "break"

    # ---------------- 文件 I/O（快捷键驱动） ----------------
    def reload_from_disk(self):
        """从磁盘重载，不改动文件内容"""
        if not self.current_file:
            return
        try:
            with open(self.current_file, "r", encoding="utf-8") as f:
                text = f.read()
            self.editor.delete(1.0, "end")
            self.editor.insert("end", text)
            self.build_extractor()
            self._refresh_marker_pairs()
        except Exception as e:
            self.set_preview(f"重载失败: {e}")

    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 LaTeX 文件",
            filetypes=[("LaTeX files", "*.tex"), ("LaTeX Template files", "*.template"), ("All files", "*.*")],
        )
        if not file_path:
            return
        self._open_path(file_path)

    def _open_path(self, file_path):
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
            self._add_recent(file_path)  # 维护最近文件
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
            self._add_recent(self.current_file)
        except Exception as e:
            self.set_preview(f"保存失败: {e}")

    # ---------------- 解析 / 导航 ----------------
    def build_extractor(self):
        try:
            if not self.current_file:
                self.set_preview("提示: 尚未打开文件")
                return
            self.extractor = LatexExtractor(self.current_file, max_level=3)
            self._build_outline_tree()
            self._build_problem_tree()
            self._build_code_tree()
        except Exception as e:
            self.set_preview(f"解析失败: {e}")

    def _build_outline_tree(self):
        self.outline_tree.delete(*self.outline_tree.get_children())
        if not self.extractor:
            return
        stack = [("", 0)]
        for section_type, title, level, line_num in self.extractor.sections:
            # 关键点：把 codeblock 从“大纲”里剔除
            if section_type == "codeblock":
                continue
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

    def _build_code_tree(self):
        """新的代码树，只列出 codeblock，顺序按在文中的出现顺序"""
        self.code_tree.delete(*self.code_tree.get_children())
        if not self.extractor:
            return
        for cb in self.extractor.codeblocks:
            # values: (start_line, level) 与大纲统一
            self.code_tree.insert("", "end", text=cb["title"], values=(cb["start"], 4))

    # ---------------- 问题树：右键菜单 ----------------
    def _init_problem_context_menu(self):
        self.problem_menu = ttk.Menu(self.problem_tree, tearoff=False)
        self.problem_menu.add_command(label="复制该问题：摘要+重述+分析+建模", command=self._copy_problem_merged)
        self.problem_menu.add_separator()
        self.problem_menu.add_command(label="只复制 摘要片段", command=lambda: self._copy_problem_part("abstract"))
        self.problem_menu.add_command(label="只复制 问题重述", command=lambda: self._copy_problem_part("restate"))
        self.problem_menu.add_command(label="只复制 问题分析", command=lambda: self._copy_problem_part("analysis"))
        self.problem_menu.add_command(label="只复制 模型与求解", command=lambda: self._copy_problem_part("modeling"))
        # 绑定右键
        self.problem_tree.bind("<Button-3>", self._popup_problem_menu)

    def _popup_problem_menu(self, event):
        try:
            iid = self.problem_tree.identify_row(event.y)
            if iid:
                self.problem_tree.selection_set(iid)
                self.problem_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.problem_menu.grab_release()

    def _copy_to_clipboard(self, s):
        try:
            top = self.winfo_toplevel()
            top.clipboard_clear()
            top.clipboard_append(s)
            top.update_idletasks()
        except Exception:
            pass

    def _copy_problem_merged(self):
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        k = vals[0] if len(vals) >= 1 else None
        if not k or not self.extractor:
            return
        parts = self.extractor.extract_problem_parts(k)
        abstract = self.extractor.extract_abstract_parts(k)
        merged = []
        if abstract:
            merged += abstract + [""]
        if "Restatement" in parts:
            merged += parts["Restatement"] + [""]
        if "Analysis" in parts:
            merged += parts["Analysis"] + [""]
        if "Modeling" in parts:
            merged += parts["Modeling"] + [""]
        text = "\n".join(merged).strip()
        if text:
            self._copy_to_clipboard(text)

    def _copy_problem_part(self, part):
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        k = vals[0]
        if not self.extractor:
            return
        content = []
        if part == "abstract":
            content = self.extractor.extract_abstract_parts(k)
        else:
            p = self.extractor.extract_problem_parts(k)
            mapping = {
                "restate": "Restatement",
                "analysis": "Analysis",
                "modeling": "Modeling",
            }
            content = p.get(mapping.get(part, ""), [])
        text = "\n".join(content).strip()
        if text:
            self._copy_to_clipboard(text)

    # ---------------- 导航事件 ----------------
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

    def _goto_outline_line(self, _event=None):
        """双击大纲项，编辑器跳转到对应行，并临时高亮"""
        item = self.outline_tree.focus()
        vals = self.outline_tree.item(item, "values")
        if not vals:
            return
        line_num = int(vals[0]) + 1  # Tk 文本行号从 1 开始
        self.notebook.select(self.tab_edit)
        idx = f"{line_num}.0"
        self.editor.see(idx)
        self.editor.mark_set("insert", idx)
        # 闪烁高亮
        self.editor.tag_configure("goto_flash", background="#a5d6a7")
        self.editor.tag_add("goto_flash", idx, f"{line_num}.end")
        self.editor.after(2000, lambda: self.editor.tag_delete("goto_flash"))

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

    def on_code_select(self, _event):
        """选中代码树中的项，右侧预览显示该 codeblock 内容"""
        if not self.extractor:
            return
        item = self.code_tree.focus()
        vals = self.code_tree.item(item, "values")
        if not vals:
            return
        line_num, level = map(int, vals)
        content = self.extractor.extract_content(line_num, level)
        self.set_preview("\n".join(content))

    # ---------------- 替换功能（仅服务标记对） ----------------
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
        display = []
        for pair in self.marker_pairs:
            match = re.search(r"<-----(.*?)----->", pair["marker_type"])
            disp = match.group(1).strip() if match else pair["marker_type"]
            display.append(disp)
        # 适配 Combobox：设置候选项，并默认选中首项（若存在）
        if hasattr(self, "pair_combo"):
            self.pair_combo["values"] = display
            if display:
                self.selected_pair_display.set(display[0])
                self.on_pair_select()
            else:
                self.selected_pair_display.set("")
                self.replace_input.delete(1.0, "end")

    def on_pair_select(self, *_):
        sel = self.selected_pair_display.get().strip()
        self.replace_input.delete(1.0, "end")
        if not sel:
            return
        for pair in self.marker_pairs:
            match = re.search(r"<-----(.*?)----->", pair["marker_type"])
            disp = match.group(1).strip() if match else pair["marker_type"]
            if disp == sel:
                idx = pair["index"]
                self.replace_input.insert("end", self.replacements.get(idx, pair["content"]))
                break

    def apply_replace(self):
        sel = self.selected_pair_display.get().strip()
        if not sel:
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

    # ---------------- 编辑器：全文搜索 / 替换 ----------------
    def _clear_search_tags(self):
        self.editor.tag_delete("search_hit")
        # 重新创建高亮 tag
        self.editor.tag_configure("search_hit", background="#ffd54f")

    def _do_find_all(self, needle):
        self._clear_search_tags()
        if not needle:
            return 0
        idx = "1.0"
        count = 0
        while True:
            idx = self.editor.search(needle, idx, nocase=False, stopindex=END)
            if not idx:
                break
            lastidx = f"{idx}+{len(needle)}c"
            self.editor.tag_add("search_hit", idx, lastidx)
            idx = lastidx
            count += 1
        if count:
            self.editor.see("search_hit.first")
        return count

    def _open_find_dialog(self):
        top = Toplevel(self)
        top.title("查找 (Ctrl+F)")
        top.transient(self.winfo_toplevel())
        top.resizable(False, False)

        ttk.Label(top, text="查找内容:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        var_find = StringVar()
        entry = ttk.Entry(top, textvariable=var_find, width=40)
        entry.grid(row=0, column=1, padx=8, pady=8)
        entry.focus_set()

        msg = ttk.Label(top, text="", bootstyle="secondary")
        msg.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")

        def do_find():
            n = self._do_find_all(var_find.get())
            msg.config(text=f"匹配 {n} 处")

        ttk.Button(top, text="查找全部并高亮", command=do_find).grid(row=0, column=2, padx=8, pady=8)

        def on_close():
            top.destroy()

        top.bind("<Return>", lambda e: do_find())
        top.protocol("WM_DELETE_WINDOW", on_close)

    def _open_replace_dialog(self):
        top = Toplevel(self)
        top.title("替换 (Ctrl+H)")
        top.transient(self.winfo_toplevel())
        top.resizable(False, False)

        var_find = StringVar()
        var_repl = StringVar()

        ttk.Label(top, text="查找:").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        e_find = ttk.Entry(top, textvariable=var_find, width=42)
        e_find.grid(row=0, column=1, padx=8, pady=8)
        e_find.focus_set()

        ttk.Label(top, text="替换为:").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        e_repl = ttk.Entry(top, textvariable=var_repl, width=42)
        e_repl.grid(row=1, column=1, padx=8, pady=8)

        msg = ttk.Label(top, text="", bootstyle="secondary")
        msg.grid(row=2, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="w")

        def replace_next():
            needle = var_find.get()
            if not needle:
                return
            # 从光标后开始查
            idx = self.editor.index(INSERT)
            pos = self.editor.search(needle, idx, nocase=False, stopindex=END)
            if not pos:
                # 从头再找一次
                pos = self.editor.search(needle, "1.0", nocase=False, stopindex=END)
                if not pos:
                    msg.config(text="未找到")
                    return
            last = f"{pos}+{len(needle)}c"
            self.editor.delete(pos, last)
            self.editor.insert(pos, var_repl.get())
            self.editor.mark_set(INSERT, f"{pos}+{len(var_repl.get())}c")
            msg.config(text="已替换 1 处")

        def replace_all():
            needle = var_find.get()
            repl = var_repl.get()
            if not needle:
                return
            text = self._get_editor_text()
            count = text.count(needle)
            if count == 0:
                msg.config(text="未找到")
                return
            text = text.replace(needle, repl)
            self.editor.delete(1.0, END)
            self.editor.insert(END, text)
            msg.config(text=f"已替换 {count} 处")

        ttk.Button(top, text="替换下一个", command=replace_next).grid(row=0, column=2, padx=8, pady=8)
        ttk.Button(top, text="全部替换", command=replace_all).grid(row=1, column=2, padx=8, pady=8)

        top.bind("<Return>", lambda e: replace_next())
        top.protocol("WM_DELETE_WINDOW", top.destroy)
