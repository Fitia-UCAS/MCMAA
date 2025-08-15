# %% view/screens/screen_workbench.py

from tkinter import *
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import os
import re
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from ..config import (
    DATA_CONFIG,
    SCREEN_CONFIG,
    MAIN_FRAME_CONFIG,
    FLAT_SUBFRAME_CONFIG,
)
from model.latex_extractor import LatexExtractor
from model.text_replacer import find_marker_pairs, replace_contents


class Screen_Workbench(ttk.Frame):
    """
    写作一体化工作台：
    - 文件：打开 / 保存 / 重新解析
    - 提取：问题编号下拉、章节下拉；预览与导出 .tex
    - 替换：扫描 <-----TAG-----> 标记对，选择并替换，应用到编辑器
    - 导航：大纲树/问题树，快速定位并在右侧“预览”展示
    - 右侧：Notebook(编辑/预览)
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
        self.keyword_var = StringVar(value="问题编号")
        self.section_var = StringVar(value="选择章节")

        # ===== 主左右分割 =====
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧垂直分割（控制区 + 导航 + 信息）
        self.left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(self.left_paned, weight=30)

        # 右侧容器（Notebook + 状态）
        right_frame = ttk.Frame(main_paned, **MAIN_FRAME_CONFIG)
        main_paned.add(right_frame, weight=70)
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # ===== 左上：控制区 =====
        self.ctrl_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.ctrl_frame, weight=3)
        self._build_controls(self.ctrl_frame)

        # ===== 左中：导航（大纲/问题） =====
        self.nav_holder = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.nav_holder, weight=3)
        self.left_tabs = ttk.Notebook(self.nav_holder)
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

        # ===== 左下：信息区 =====
        self.info_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.info_frame, weight=2)
        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)

        # ===== 右侧：Notebook(编辑/预览) =====
        self.notebook = ttk.Notebook(self.right_paned)
        self.right_paned.add(self.notebook, weight=7)

        # 编辑器
        self.tab_edit = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_edit, text="编辑")
        self.editor = ScrolledText(self.tab_edit, wrap="none", undo=True)
        self.editor.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.editor.bind("<Control-a>", lambda e: self._select_all(self.editor))
        self.editor.bind("<Control-s>", lambda e: (self.save_current_text(), "break"))

        # 预览
        self.tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_preview, text="预览")
        self.preview = ScrolledText(self.tab_preview, wrap="word", state="disabled")
        self.preview.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 右下状态栏
        self.status_holder = ttk.Frame(self.right_paned, **MAIN_FRAME_CONFIG)
        self.right_paned.add(self.status_holder, weight=1)
        self.status = ttk.Label(self.status_holder, text="就绪", anchor="w")
        self.status.place(relx=0, rely=0, relwidth=1)

    # ---------------- 工具函数 ----------------
    def info_text_append(self, text):
        self.info_text.config(state="normal")
        self.info_text.insert("end", text + "\n")
        self.info_text.config(state="disabled")
        self.info_text.see("end")

    def _select_all(self, widget):
        widget.tag_add("sel", "1.0", "end")
        return "break"

    def set_preview(self, text):
        self.notebook.select(self.tab_preview)
        self.preview.config(state="normal")
        self.preview.delete(1.0, "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    def _get_editor_text(self):
        return self.editor.get(1.0, "end-1c")

    # ---------------- 控制区布局 ----------------
    def _build_controls(self, root):
        # 采用多行扁平面板，维持统一风格
        h = 46

        # 文件操作
        row_f = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_f.place(relx=0, rely=0.00, relwidth=1, height=h)
        ttk.Button(row_f, text="打开 .tex / .template", command=self.select_file).place(
            relx=0, rely=0, relwidth=1, relheight=1
        )

        row_s = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_s.place(relx=0, rely=0.11, relwidth=1, height=h)
        ttk.Button(row_s, text="保存编辑内容到文件", command=self.save_current_text).place(
            relx=0, rely=0, relwidth=1, relheight=1
        )

        row_r = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_r.place(relx=0, rely=0.22, relwidth=1, height=h)
        ttk.Button(row_r, text="重新解析", command=self.build_extractor).place(relx=0, rely=0, relwidth=1, relheight=1)

        # 提取：问题编号 & 章节
        row_k = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_k.place(relx=0, rely=0.33, relwidth=1, height=h)
        self.button_keyword = ttk.OptionMenu(row_k, self.keyword_var, "问题编号")
        self.button_keyword.place(relx=0, rely=0, relwidth=0.72, relheight=1)
        ttk.Button(row_k, text="导出该问题为 .tex", command=self.export_problem).place(
            relx=0.73, rely=0, relwidth=0.27, relheight=1
        )
        self.keyword_var.trace_add("write", lambda *_: self.preview_problem())

        row_c = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_c.place(relx=0, rely=0.44, relwidth=1, height=h)
        self.button_section = ttk.OptionMenu(row_c, self.section_var, "选择章节")
        self.button_section.place(relx=0, rely=0, relwidth=0.72, relheight=1)
        ttk.Button(row_c, text="导出该章节为 .tex", command=self.export_section).place(
            relx=0.73, rely=0, relwidth=0.27, relheight=1
        )
        self.section_var.trace_add("write", lambda *_: self.preview_section())

        # 替换：标记对 & 应用
        row_scan = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_scan.place(relx=0, rely=0.55, relwidth=1, height=h)
        ttk.Button(row_scan, text="刷新标记列表", command=self.refresh_marker_pairs).place(
            relx=0, rely=0, relwidth=1, relheight=1
        )

        row_pair = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_pair.place(relx=0, rely=0.66, relwidth=1, height=h)
        self.pair_menu = ttk.OptionMenu(row_pair, self.selected_pair_display, "选择标记对")
        self.pair_menu.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.selected_pair_display.trace_add("write", self.on_pair_select)

        row_in = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_in.place(relx=0, rely=0.77, relwidth=1, height=120)
        ttk.Label(row_in, text="输入替换内容").place(relx=0, rely=0, relwidth=1, height=18)
        self.replace_input = ScrolledText(row_in)
        self.replace_input.place(relx=0, rely=0.16, relwidth=1, relheight=0.84)
        self.replace_input.bind("<Control-a>", self._select_all)
        self.replace_input.bind("<Control-s>", lambda e: (self.apply_replace(), "break"))

        row_do = ttk.Frame(root, **FLAT_SUBFRAME_CONFIG)
        row_do.place(relx=0, rely=0.90, relwidth=1, height=h)
        ttk.Button(row_do, text="应用替换到编辑器", command=self.apply_replace).place(
            relx=0, rely=0, relwidth=1, relheight=1
        )

    # ---------------- 文件 I/O ----------------
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
            self.refresh_marker_pairs()
            self.notebook.select(self.tab_edit)
        except Exception as e:
            self.set_preview(f"错误: {e}")

    def save_current_text(self):
        if not self.current_file:
            self.info_text_append("提示: 尚未打开文件")
            return
        try:
            text = self._get_editor_text()
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.info_text_append("已保存: " + self.current_file)
            self.build_extractor()  # 保存后重新解析
        except Exception as e:
            self.set_preview(f"保存失败: {e}")

    # ---------------- 解析 / 列表刷新 ----------------
    def build_extractor(self):
        try:
            if not self.current_file:
                self.set_preview("提示: 尚未打开文件")
                return
            self.extractor = LatexExtractor(self.current_file, max_level=3)
            self._build_outline_tree()
            self._build_problem_tree()
            self._refresh_dropdowns()
            self.status.config(text=f"已解析: {os.path.basename(self.current_file)}")
            self.info_text_append("导航已刷新")
        except Exception as e:
            self.set_preview(f"解析失败: {e}")

    def _refresh_dropdowns(self):
        # 问题编号
        try:
            keywords = self.extractor.get_unique_keywords()
        except Exception:
            keywords = []
        self.button_keyword.set_menu("问题编号", *keywords)
        self.keyword_var.set("问题编号")

        # 一级章节
        try:
            section_titles = [title for _, title, level, _ in self.extractor.sections if level == 1]
        except Exception:
            section_titles = []
        self.button_section.set_menu("选择章节", *section_titles)
        self.section_var.set("选择章节")

    def refresh_marker_pairs(self):
        text = self._get_editor_text()
        self.marker_pairs = find_marker_pairs(text)
        pair_display = ["选择标记对"]
        for pair in self.marker_pairs:
            marker_type = pair["marker_type"]
            match = re.search(r"<-----(.*?)----->", marker_type)
            display_text = match.group(1).strip() if match else marker_type
            pair_display.append(display_text)
        self.pair_menu.set_menu(*pair_display)
        self.selected_pair_display.set("选择标记对")
        if self.marker_pairs:
            self.info_text_append(f"扫描到 {len(self.marker_pairs)} 个标记对")
        else:
            self.info_text_append("未发现标记对")

    # ---------------- 导航构建 ----------------
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

    # ---------------- 导航事件 ----------------
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

    # ---------------- 提取 / 导出 ----------------
    def preview_problem(self):
        k = self.keyword_var.get()
        if k == "问题编号" or not self.extractor:
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
        self.set_preview("\n".join(merged) if merged else "未找到相关章节")

    def export_problem(self):
        k = self.keyword_var.get()
        if k == "问题编号" or not self.extractor:
            self.info_text_append("错误: 请选择一个问题编号")
            return
        parts = self.extractor.extract_problem_parts(k)
        abstract = self.extractor.extract_abstract_parts(k)
        if not parts and not abstract:
            self.info_text_append("错误: 未找到相关章节")
            return
        all_content = []
        all_content.extend(abstract or [])
        if "Restatement" in parts:
            all_content.extend(parts["Restatement"])
        if "Analysis" in parts:
            all_content.extend(parts["Analysis"])
        if "Modeling" in parts:
            all_content.extend(parts["Modeling"])
        output_file = os.path.join(os.path.dirname(self.current_file or "."), f"问题{k}.tex")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(all_content))
            self.info_text_append(f"成功: 内容已保存到 {output_file}")
        except Exception as e:
            self.info_text_append(f"错误: {str(e)}")

    def preview_section(self):
        s = self.section_var.get()
        if s == "选择章节" or not self.extractor:
            return
        content = self.extractor.extract_section(s)
        self.set_preview("\n".join(content) if content else "未找到相关章节")

    def export_section(self):
        s = self.section_var.get()
        if s == "选择章节" or not self.extractor:
            self.info_text_append("错误: 请选择一个章节")
            return
        content = self.extractor.extract_section(s)
        if not content:
            self.info_text_append("错误: 未找到相关章节")
            return
        output_file = os.path.join(os.path.dirname(self.current_file or "."), f"{s}.tex")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\\section{" + s + "}\n" + "\n".join(content))
            self.info_text_append(f"成功: 章节已保存到 {output_file}")
        except Exception as e:
            self.info_text_append(f"错误: {str(e)}")

    # ---------------- 替换功能 ----------------
    def on_pair_select(self, *_):
        sel = self.selected_pair_display.get()
        if sel == "选择标记对":
            self.replace_input.delete(1.0, "end")
            return
        # 找到对应 pair，将原内容或已替换内容填入输入框
        for pair in self.marker_pairs:
            marker_type = pair["marker_type"]
            match = re.search(r"<-----(.*?)----->", marker_type)
            disp = match.group(1).strip() if match else marker_type
            if disp == sel:
                self.replace_input.delete(1.0, "end")
                idx = pair["index"]
                if idx in self.replacements:
                    self.replace_input.insert("end", self.replacements[idx])
                else:
                    self.replace_input.insert("end", pair["content"])
                break

    def apply_replace(self):
        sel = self.selected_pair_display.get()
        if sel == "选择标记对":
            self.info_text_append("请先选择一个标记对")
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
            self.info_text_append("未找到匹配的标记对")
            return

        try:
            new_content = self.replace_input.get(1.0, "end-1c")
            self.replacements[idx] = new_content
            # 基于当前编辑器文本进行替换，并回写到编辑器
            base_text = self._get_editor_text()
            new_text = replace_contents(base_text, self.replacements)
            self.editor.delete(1.0, "end")
            self.editor.insert("end", new_text)
            self.info_text_append(f"已应用替换: {sel}")
            self.refresh_marker_pairs()  # 替换后重新扫描索引位置
        except Exception as e:
            self.info_text_append(f"替换失败: {str(e)}")
            messagebox.showerror("错误", f"替换失败: {str(e)}")
