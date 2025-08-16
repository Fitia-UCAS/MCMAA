# %% view/screens/screen_workbench.py
# -*- coding: utf-8 -*-

"""
Screen_Workbench — 一体化工作台（View）
=====================================
职责（MVC：View）
- 只负责 UI 构建、事件绑定、以及把用户操作转交给 Controller；
- 文本解析/文件 I/O/业务逻辑统一委托给 WorkbenchController；
- 代码按“Tab 功能”进行分组：编辑/预览、替换、辅助、Agent、导航树。

快捷键
- Ctrl+O 打开；Ctrl+S 保存（在“替换”页时为“应用替换”，在“辅助”页为“插入到编辑器”）；
- Ctrl+F 查找；Ctrl+H 替换。
"""
from __future__ import annotations

import re
import time
from tkinter import *
from tkinter.scrolledtext import ScrolledText
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import ttkbootstrap as ttk

from ..config import SCREEN_CONFIG, MAIN_FRAME_CONFIG
from controller.workbench_controller import WorkbenchController


class Screen_Workbench(ttk.Frame):
    """统一工作台视图。

    左：导航（大纲/问题/代码）
    右：Notebook（编辑/预览｜替换｜辅助｜Agent）
    """

    MODE_NAME = "一体化工作台"

    # ---------------------------------------------------------------------
    # 生命周期
    # ---------------------------------------------------------------------
    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Controller & 轻量状态
        self.ctrl = WorkbenchController()
        self.selected_pair_display = StringVar(value="")  # 替换页下拉

        # 主布局：左右分割
        self._build_layout()
        self._build_left_nav()
        self._build_right_tabs()

        # 绑定“切页时刷新”的钩子
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Agent 回调 -> 回 UI 线程
        self.ctrl.set_agent_handlers(
            on_status=lambda s: self.after(0, lambda: self._agent_set_status(s)),
            on_message=lambda m: self.after(0, lambda: self._agent_log(f"< {m}\n")),
            on_error=lambda e: self.after(0, lambda: messagebox.showerror("Agent 错误", e)),
        )

        # 初次刷新
        self._refresh_aid_files()

        # 全局 Ctrl/⌘+S：替换页=应用替换；辅助页=插入；其它页=保存
        self.bind_all("<Control-s>", self._on_global_save_or_apply)
        self.bind_all("<Command-s>", self._on_global_save_or_apply)

    # ---------------------------------------------------------------------
    # 对外给菜单用的 API（主窗口菜单调用）
    # ---------------------------------------------------------------------
    def get_recent_files(self):
        """返回最近文件列表（最新在前）。"""
        return list(self.ctrl.recent_files)

    def quick_open(self, path: str):
        """Quick Open 菜单项点击：委托 Controller，View 负责 UI 更新与文案。"""
        ok, _msg, text = self.ctrl.quick_open(path)
        if not ok:
            messagebox.showwarning("提示", "文件不存在，已从最近列表移除。")
            return
        self._editor_set_text(text)
        self.set_preview(f"文件已加载: {path}")
        self._refresh_marker_pairs()
        self._rebuild_all_trees()
        self.notebook.select(self.tab_edit)

    # ---------------------------------------------------------------------
    # 布局与 UI 构建
    # ---------------------------------------------------------------------

    def _build_layout(self):
        self.main_paned = ttk.PanedWindow(self, orient="horizontal")
        self.main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 左侧：导航容器
        self.left_frame = ttk.Frame(self.main_paned, **MAIN_FRAME_CONFIG)
        self.main_paned.add(self.left_frame, weight=30)

        # 右侧：Notebook 容器
        self.right_frame = ttk.Frame(self.main_paned, **MAIN_FRAME_CONFIG)
        self.main_paned.add(self.right_frame, weight=70)

        # 初始化时给个合理的分割（sash 索引从 0 开始，避免无效索引）
        try:
            self.main_paned.sashpos(1, 260)
        except Exception:
            pass

    def _build_left_nav(self):
        self.left_tabs = ttk.Notebook(self.left_frame)
        self.left_tabs.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 大纲
        self.outline_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.outline_tab, text="大纲")
        self.outline_tree = ttk.Treeview(self.outline_tab, show="tree")
        self.outline_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.outline_tree.bind("<<TreeviewSelect>>", self.on_outline_select)
        self.outline_tree.bind("<Double-1>", self._goto_outline_line)

        # 问题（含右键菜单）
        self.problem_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.problem_tab, text="问题")
        self.problem_tree = ttk.Treeview(self.problem_tab, show="tree")
        self.problem_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.problem_tree.bind("<<TreeviewSelect>>", self.on_problem_select)
        self._init_problem_context_menu()

        # 代码（专门放 codeblock）
        self.code_tab = ttk.Frame(self.left_tabs)
        self.left_tabs.add(self.code_tab, text="代码")
        self.code_tree = ttk.Treeview(self.code_tab, show="tree")
        self.code_tree.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.code_tree.bind("<<TreeviewSelect>>", self.on_code_select)

    def _build_right_tabs(self):
        self.notebook = ttk.Notebook(self.right_frame)
        self.notebook.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_tab_edit_preview()
        self._build_tab_replace()
        self._build_tab_aid()
        self._build_tab_agent()

    # --------------------------- Edit / Preview ---------------------------
    def _build_tab_edit_preview(self):
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

    # ------------------------------- 替换页 -------------------------------

    def _build_tab_replace(self):
        self.tab_replace = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_replace, text="替换")

        topbar = ttk.Frame(self.tab_replace, padding=(8, 6))
        topbar.pack(side="top", fill="x")

        ttk.Label(topbar, text="标记对：").pack(side="left")
        self.pair_combo = ttk.Combobox(topbar, textvariable=self.selected_pair_display, state="readonly", width=40)
        self.pair_combo.pack(side="left", padx=(6, 8), fill="x", expand=True)
        self.pair_combo.bind("<<ComboboxSelected>>", lambda e: self.on_pair_select())

        # 保留“仅应用所选” + “应用所有块”
        ttk.Button(topbar, text="应用所有块（Ctrl+S）", bootstyle="primary", command=self.apply_replace_all).pack(
            side="right"
        )
        ttk.Button(topbar, text="仅应用所选", command=self.apply_replace).pack(side="right", padx=(0, 8))

        # 右侧分屏区域
        self.replace_paned = ttk.PanedWindow(self.tab_replace, orient="horizontal")
        self.replace_paned.pack(side="top", fill="both", expand=True)

        # 保存“分屏块”的引用：(label, text_widget)
        self.replace_blocks = []

        # 初始给一个空块
        self._rebuild_replace_blocks([])

    # -------------------------------- 辅助页 --------------------------------
    def _build_tab_aid(self):
        self.tab_aid = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_aid, text="辅助")

        aid_top = ttk.Frame(self.tab_aid, padding=(8, 6))
        aid_top.pack(side="top", fill="x")

        ttk.Label(aid_top, text="辅助文件：").pack(side="left")
        self.aid_selected = ttk.StringVar(value="")
        self.aid_combo = ttk.Combobox(aid_top, textvariable=self.aid_selected, state="readonly", width=46)
        self.aid_combo.pack(side="left", padx=(6, 8), fill="x", expand=True)
        self.aid_combo.bind("<<ComboboxSelected>>", lambda e: self._on_aid_select())

        ttk.Button(
            aid_top, text="插入到编辑器（Ctrl+S）", bootstyle="secondary", command=self.apply_aid_to_editor
        ).pack(side="right")

        self.aid_view = ScrolledText(self.tab_aid, wrap="word")
        self.aid_view.pack(side="top", fill="both", expand=True)
        self.aid_view.bind("<Control-a>", self._select_all)
        self.aid_view.bind("<Command-a>", self._select_all)

    # -------------------------------- Agent 页 --------------------------------
    def _build_tab_agent(self):
        self.tab_agent = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_agent, text="Agent")

        # 顶部连接区
        agent_top = ttk.Frame(self.tab_agent, padding=(8, 6))
        agent_top.pack(side="top", fill="x")

        ttk.Label(agent_top, text="URL:").pack(side="left")
        self.agent_url = ttk.StringVar(value="ws://127.0.0.1:8000/ws")
        ttk.Entry(agent_top, textvariable=self.agent_url, width=34).pack(side="left", padx=(4, 12))

        ttk.Label(agent_top, text="Token:").pack(side="left")
        self.agent_token = ttk.StringVar(value="")
        ttk.Entry(agent_top, textvariable=self.agent_token, width=22, show="•").pack(side="left", padx=(4, 12))

        ttk.Label(agent_top, text="Proxy:").pack(side="left")
        self.agent_proxy = ttk.StringVar(value="")
        ttk.Entry(agent_top, textvariable=self.agent_proxy, width=18).pack(side="left", padx=(4, 12))

        ttk.Button(agent_top, text="连接", bootstyle="success", command=self._agent_connect).pack(side="left", padx=4)
        ttk.Button(agent_top, text="断开", command=self._agent_close).pack(side="left", padx=4)

        # 中部消息/输入区
        mid = ttk.Frame(self.tab_agent, padding=(8, 6))
        mid.pack(side="top", fill="both", expand=True)

        # 左：消息控制
        left = ttk.Frame(mid)
        left.pack(side="left", fill="y")
        ttk.Button(left, text="Ping", command=self._agent_ping).pack(side="top", fill="x", pady=(0, 6))
        ttk.Button(left, text="发送请求 infer", bootstyle="primary", command=self._agent_infer).pack(
            side="top", fill="x"
        )

        # 右：日志/状态
        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="状态:").pack(anchor="w")
        self.agent_status_var = ttk.StringVar(value="disconnected")
        ttk.Label(right, textvariable=self.agent_status_var, bootstyle="secondary").pack(anchor="w", pady=(0, 6))
        ttk.Label(right, text="消息:").pack(anchor="w")
        self.agent_console = ScrolledText(right, wrap="word", state="disabled", height=14)
        self.agent_console.pack(fill="both", expand=True)

    # ---------------------------------------------------------------------
    # Tab 变更钩子
    # ---------------------------------------------------------------------
    def _on_tab_changed(self, _evt=None):
        try:
            tab_text = self.notebook.tab(self.notebook.select(), "text")
        except Exception:
            return
        if tab_text == "替换":
            self._refresh_marker_pairs()
        elif tab_text == "辅助":
            self._refresh_aid_files()

    # ---------------------------------------------------------------------
    # 文件 I/O（菜单/快捷键驱动）
    # ---------------------------------------------------------------------
    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 LaTeX 文件",
            filetypes=[("LaTeX files", "*.tex"), ("LaTeX Template files", "*.template"), ("All files", "*.*")],
        )
        if file_path:
            self._open_path(file_path)

    def _open_path(self, file_path: str):
        try:
            data = self.ctrl.open_path(file_path)
            self._editor_set_text(data.get("text", ""))
            self.set_preview(f"文件已加载: {file_path}")
            self._refresh_marker_pairs()
            self._rebuild_all_trees()
            self.notebook.select(self.tab_edit)
        except Exception as e:
            self.set_preview(f"错误: {e}")

    def reload_from_disk(self):
        """从磁盘重载（不改动文件内容）。"""
        data = self.ctrl.reload_from_disk()
        text = data.get("text", "")
        if not text:
            return
        self._editor_set_text(text)
        self._refresh_marker_pairs()
        self._rebuild_all_trees()
        self.set_preview("已从磁盘重载。")

    def save_current_text(self):
        ok, msg = self.ctrl.save_text(self._get_editor_text())
        if not ok:
            self.set_preview(f"保存失败：{msg or '未知错误'}")
            return
        self._rebuild_all_trees()
        self.set_preview("保存成功。")

    # ---------------------------------------------------------------------
    # 导航树：构建与事件
    # ---------------------------------------------------------------------
    def _rebuild_all_trees(self):
        self._build_outline_tree()
        self._build_problem_tree()
        self._build_code_tree()

    def _build_outline_tree(self):
        self.outline_tree.delete(*self.outline_tree.get_children())
        if not self.ctrl.extractor:
            return
        nodes = self.ctrl.make_outline_nodes(self.ctrl.extractor)
        stack = [("", 0)]  # [(tk_node_id, level)]
        for n in nodes:
            title, level, line_num = n["title"], n["level"], n["line_num"]
            while stack and level <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0] if stack else ""
            node_id = self.outline_tree.insert(parent, "end", text=title, values=(line_num, level))
            stack.append((node_id, level))

    def _build_problem_tree(self):
        self.problem_tree.delete(*self.problem_tree.get_children())
        if not self.ctrl.extractor:
            return
        items = self.ctrl.make_problem_tree(self.ctrl.extractor)
        for item in items:
            pnode = self.problem_tree.insert("", "end", text=item["text"], values=item["values"])
            for child in item.get("children", []):
                self.problem_tree.insert(pnode, "end", text=child["text"], values=child["values"])

    def _build_code_tree(self):
        self.code_tree.delete(*self.code_tree.get_children())
        if not self.ctrl.extractor:
            return
        nodes = self.ctrl.make_code_nodes(self.ctrl.extractor)
        for n in nodes:
            self.code_tree.insert("", "end", text=n["text"], values=n["values"])

    # ---- 导航事件 ----
    def on_outline_select(self, _event):
        if not self.ctrl.extractor:
            return
        item = self.outline_tree.focus()
        vals = self.outline_tree.item(item, "values")
        if not vals:
            return
        line_num, section_level = map(int, vals)
        text = self.ctrl.render_outline_preview(self.ctrl.extractor, line_num, section_level)
        self.set_preview(text)

    def _goto_outline_line(self, _event=None):
        """双击大纲项：编辑器跳转到对应行，并临时高亮。"""
        item = self.outline_tree.focus()
        vals = self.outline_tree.item(item, "values")
        if not vals:
            return
        line_num = int(vals[0]) + 1  # Tk 文本行号从 1 开始
        self.notebook.select(self.tab_edit)
        idx = f"{line_num}.0"
        self.editor.see(idx)
        self.editor.mark_set("insert", idx)
        self.editor.tag_configure("goto_flash", background="#a5d6a7")
        self.editor.tag_add("goto_flash", idx, f"{line_num}.end")
        self.editor.after(2000, lambda: self.editor.tag_delete("goto_flash"))

    def on_problem_select(self, _event):
        if not self.ctrl.extractor:
            return
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        if len(vals) == 1:  # 点击“问题X” -> 合并预览（View 侧加分隔标题，仅展示）
            k = vals[0]
            text = self._compose_problem_preview_with_headings(k)
        else:
            k, part = vals
            body = self.ctrl.build_problem_part_text(self.ctrl.extractor, k, part)
            title_map = {
                "abstract": "摘要片段",
                "restate": "问题重述",
                "analysis": "问题分析",
                "modeling": "模型与求解",
            }
            header = f"% ===== {title_map.get(part, part)} =====\n" if body else ""
            text = f"{header}{body}".strip()
        self.set_preview(text)

    def _compose_problem_preview_with_headings(self, k: str) -> str:
        """合并预览（View 侧添加分节标题，避免污染业务层）。"""
        pieces = [
            ("摘要片段", self.ctrl.build_problem_part_text(self.ctrl.extractor, k, "abstract")),
            ("问题重述", self.ctrl.build_problem_part_text(self.ctrl.extractor, k, "restate")),
            ("问题分析", self.ctrl.build_problem_part_text(self.ctrl.extractor, k, "analysis")),
            ("模型与求解", self.ctrl.build_problem_part_text(self.ctrl.extractor, k, "modeling")),
        ]
        out = []
        for title, body in pieces:
            if body:
                out.append(f"% ===== {title} =====")
                out.append(body)
                out.append("")
        return "\n".join(out).strip()

    def on_code_select(self, _event):
        if not self.ctrl.extractor:
            return
        item = self.code_tree.focus()
        vals = self.code_tree.item(item, "values")
        if not vals:
            return
        line_num, level = map(int, vals)
        text = self.ctrl.render_code_preview(self.ctrl.extractor, line_num, level)
        self.set_preview(text)

    # ---- 问题树：右键菜单 ----
    def _init_problem_context_menu(self):
        self.problem_menu = ttk.Menu(self.problem_tree, tearoff=False)
        self.problem_menu.add_command(label="复制该问题：摘要+重述+分析+建模", command=self._copy_problem_merged)
        self.problem_menu.add_separator()
        self.problem_menu.add_command(label="只复制 摘要片段", command=lambda: self._copy_problem_part("abstract"))
        self.problem_menu.add_command(label="只复制 问题重述", command=lambda: self._copy_problem_part("restate"))
        self.problem_menu.add_command(label="只复制 问题分析", command=lambda: self._copy_problem_part("analysis"))
        self.problem_menu.add_command(label="只复制 模型与求解", command=lambda: self._copy_problem_part("modeling"))
        self.problem_tree.bind("<Button-3>", self._popup_problem_menu)

    def _popup_problem_menu(self, event):
        try:
            iid = self.problem_tree.identify_row(event.y)
            if iid:
                self.problem_tree.selection_set(iid)
                self.problem_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.problem_menu.grab_release()

    def _copy_problem_merged(self):
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        k = vals[0] if len(vals) >= 1 else None
        if not k:
            return
        text = self.ctrl.build_problem_merged_text(self.ctrl.extractor, k)
        if text:
            self._copy_to_clipboard(text)

    def _copy_problem_part(self, part: str):
        item = self.problem_tree.focus()
        vals = self.problem_tree.item(item, "values")
        if not vals:
            return
        k = vals[0]
        text = self.ctrl.build_problem_part_text(self.ctrl.extractor, k, part)
        if text:
            self._copy_to_clipboard(text)

    # ---------------------------------------------------------------------
    # 替换功能（标记对）
    # ---------------------------------------------------------------------

    def _refresh_marker_pairs(self):
        """
        扫描标记对并刷新下拉 + 右侧分屏（严格以“当前编辑器文本”为准，不叠加历史）。
        """
        current = self._get_editor_text()

        # 同步 Controller 的当前文本（不落盘）
        self.ctrl.update_current_text_only(current)
        display = self.ctrl.update_marker_pairs_from_text(current)

        # View 侧解析（用于右侧分栏）
        pairs = self._parse_marker_pairs(current)  # [{'label':..., 'content':...}, ...]

        # 下拉框刷新
        labels = [p["label"] for p in pairs] or display
        if hasattr(self, "pair_combo"):
            self.pair_combo["values"] = labels
            if labels:
                self.selected_pair_display.set(labels[0])
            else:
                self.selected_pair_display.set("")

        # 分栏按“当前标签个数”重建（不递增）
        self._rebuild_replace_blocks(pairs)

        # 若选择了项，联动定位
        if labels:
            self.on_pair_select()

    def _parse_marker_pairs(self, text: str):
        """
        解析形如
            <-----标签----->
            ...内容...
            <-----标签----->
        的成对标记，返回 [{'label': str, 'content': str}, ...]
        """
        pat = re.compile(r"^\s*<-----([^-\n]+)----->\s*$", re.M)
        pairs = []
        opened = {}

        for m in pat.finditer(text):
            label = m.group(1).strip()
            if label in opened:  # 关闭并成对
                start = opened.pop(label).end()
                end = m.start()
                content = text[start:end]
                pairs.append({"label": label, "content": content})
            else:
                opened[label] = m
        return pairs

    def _rebuild_replace_blocks(self, pairs):
        """
        根据解析到的标记对数量，重建右侧分屏块。
        每块：标题（label）+ 可编辑 ScrolledText（预填原内容）。
        先彻底清理旧 Pane，避免历史递增。
        """
        # 彻底清空旧 pane
        for w in list(self.replace_paned.winfo_children()):
            try:
                self.replace_paned.forget(w)
            except Exception:
                pass
            try:
                w.destroy()
            except Exception:
                pass
        self.replace_blocks = []

        if not pairs:
            # 没有标记就给一个空块，防止页面空白
            frame = ttk.Frame(self.replace_paned, padding=(6, 4))
            self.replace_paned.add(frame, weight=1)
            ttk.Label(frame, text="（未发现标记对）", bootstyle="secondary").pack(anchor="w")
            txt = ScrolledText(frame, wrap="word")
            txt.pack(fill="both", expand=True)
            self.replace_blocks.append(("未发现标记对", txt))
            return

        # 有 N 个标记对 -> N 个分屏块
        for p in pairs:
            frame = ttk.Frame(self.replace_paned, padding=(6, 4))
            self.replace_paned.add(frame, weight=1)
            ttk.Label(frame, text=p["label"]).pack(anchor="w")
            txt = ScrolledText(frame, wrap="word")
            txt.pack(fill="both", expand=True)
            txt.insert("1.0", p["content"].strip())
            self.replace_blocks.append((p["label"], txt))

    def on_pair_select(self, *_):
        """
        下拉选择某个标记时，把焦点定位到对应的分屏编辑框；
        若该标记对应块存在，则选中其全部内容，方便直接粘贴覆盖。
        """
        sel = (self.selected_pair_display.get() or "").strip()
        if not sel:
            return

        # 找到对应的分屏块（txt 是 ScrolledText）
        txt = self._find_block_by_label(sel)
        if not txt:
            return

        try:
            txt.focus_set()
            txt.tag_add("sel", "1.0", "end")  # 选中整块，便于直接粘贴
            txt.see("1.0")
        except Exception:
            pass

    def _find_block_by_label(self, label: str):
        """
        在 self.replace_blocks 中按标签名查找对应的文本控件。
        self.replace_blocks 的元素结构为 (label, text_widget)。
        """
        for lab, txt in getattr(self, "replace_blocks", []):
            if lab == label:
                return txt
        return None

    def apply_replace(self):
        """
        仅应用“下拉选中的那个标记”的替换：读取对应分屏块中的内容，写回整篇到编辑器。
        """
        sel = (self.selected_pair_display.get() or "").strip()
        if not sel:
            return
        try:
            txt = self._find_block_by_label(sel)
            if not txt:
                return
            new_content = txt.get("1.0", "end-1c")
            base_text = self._get_editor_text()
            new_text = self.ctrl.apply_replace_for_display(base_text, sel, new_content)
            self._editor_set_text(new_text)
            self._refresh_marker_pairs()
        except Exception as e:
            messagebox.showerror("错误", f"替换失败: {str(e)}")

    def apply_replace_all(self):
        """
        读取右侧每一块的文本，按‘标签’依次替换回整篇。
        逐块调用 Controller.apply_replace_for_display，避免自己拼正则。
        """
        base_text = self._get_editor_text()
        new_text = base_text
        for label, txt in self.replace_blocks:
            content = txt.get("1.0", "end-1c")
            new_text = self.ctrl.apply_replace_for_display(new_text, label, content)

        self._editor_set_text(new_text)
        self._refresh_marker_pairs()

    # ---------------------------------------------------------------------
    # 辅助页：文件列表/读取/插入
    # ---------------------------------------------------------------------
    def _aid_dir_path(self):
        return self.ctrl.aid_dir()

    def _refresh_aid_files(self):
        files = self.ctrl.list_aid_txt()
        self.aid_combo["values"] = files
        if not files:
            self.aid_selected.set("")
            self.aid_view.delete(1.0, "end")
        else:
            cur = self.aid_selected.get()
            if cur not in files:
                self.aid_selected.set(files[0])
            self._on_aid_select()

    def _on_aid_select(self):
        fname = self.aid_selected.get().strip()
        self.aid_view.delete(1.0, "end")
        if not fname:
            return
        try:
            txt = self.ctrl.read_aid_txt(fname)
        except Exception as e:
            txt = f"(读取失败：{e})"
        self.aid_view.insert("end", txt)

    def apply_aid_to_editor(self):
        """
        将辅助区当前内容“覆盖写入”编辑器（不再插入/叠加）；
        然后按新文本重新**扫描标签并重建分栏**，保证不递增。
        """
        content = self.aid_view.get(1.0, "end-1c")

        # 1) 覆盖写入编辑器 & 焦点
        self.notebook.select(self.tab_edit)
        self._editor_set_text(content)
        self.editor.focus_set()
        self.editor.mark_set(INSERT, "1.0")

        # 2) 同步到 Controller（不落盘），重建解析/树/分栏
        self.ctrl.update_current_text_only(content)
        self._refresh_marker_pairs()
        self._rebuild_all_trees()

        # 3) 直接切到“替换”页，便于马上编辑各块
        self.notebook.select(self.tab_replace)

    # ---------------------------------------------------------------------
    # Agent 集成：回调/动作
    # ---------------------------------------------------------------------
    def _agent_set_status(self, s: str):
        self.agent_status_var.set(str(s))

    def _agent_log(self, text: str):
        self.agent_console.config(state="normal")
        self.agent_console.insert("end", text)
        self.agent_console.see("end")
        self.agent_console.config(state="disabled")

    def _agent_connect(self):
        url = self.agent_url.get().strip()
        token = self.agent_token.get().strip() or None
        proxy = self.agent_proxy.get().strip() or None
        try:
            self.ctrl.agent_connect(
                url=url, token=token, proxy=proxy, ping_interval=20.0, insecure_skip_tls_verify=True
            )
            self._agent_log(f"> CONNECT {url}\n")
        except Exception as e:
            messagebox.showerror("连接失败", str(e))

    def _agent_close(self):
        try:
            self.ctrl.agent_close()
            self._agent_log("> CLOSE\n")
        except Exception as e:
            messagebox.showerror("断开失败", str(e))

    def _agent_ping(self):
        try:
            self.ctrl.agent_send_json({"type": "ping", "ts": time.time()})
            self._agent_log("> ping\n")
        except Exception as e:
            messagebox.showerror("发送失败", str(e))

    def _agent_infer(self):
        """示例：同步请求-响应。"""
        try:
            resp = self.ctrl.agent_request({"type": "infer", "payload": {"text": "hello mcmaa"}}, timeout=15.0)
            self._agent_log(f"> infer hello mcmaa\n< {resp}\n")
        except Exception as e:
            messagebox.showerror("请求失败", str(e))

    # ---------------------------------------------------------------------
    # 编辑器：全文搜索 / 替换对话框
    # ---------------------------------------------------------------------
    def _clear_search_tags(self):
        self.editor.tag_delete("search_hit")
        self.editor.tag_configure("search_hit", background="#ffd54f")

    def _do_find_all(self, needle: str) -> int:
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
        ttk.Entry(top, textvariable=var_find, width=40).grid(row=0, column=1, padx=8, pady=8)
        msg = ttk.Label(top, text="", bootstyle="secondary")
        msg.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="w")

        def do_find():
            n = self._do_find_all(var_find.get())
            msg.config(text=f"匹配 {n} 处")

        ttk.Button(top, text="查找全部并高亮", command=do_find).grid(row=0, column=2, padx=8, pady=8)
        top.bind("<Return>", lambda e: do_find())
        top.protocol("WM_DELETE_WINDOW", top.destroy)

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
            idx = self.editor.index(INSERT)
            pos = self.editor.search(needle, idx, nocase=False, stopindex=END)
            if not pos:
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
            self._editor_set_text(text)
            msg.config(text=f"已替换 {count} 处")

        ttk.Button(top, text="替换下一个", command=replace_next).grid(row=0, column=2, padx=8, pady=8)
        ttk.Button(top, text="全部替换", command=replace_all).grid(row=1, column=2, padx=8, pady=8)
        top.bind("<Return>", lambda e: replace_next())
        top.protocol("WM_DELETE_WINDOW", top.destroy)

    # ---------------------------------------------------------------------
    # 工具与杂项
    # ---------------------------------------------------------------------
    def _on_global_save_or_apply(self, _event=None):
        """统一 Ctrl/⌘+S 行为：替换页=应用替换；辅助页=插入；其余=保存。"""
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

    def set_preview(self, text: str):
        self.notebook.select(self.tab_preview)
        self.preview.config(state="normal")
        self.preview.delete(1.0, "end")
        self.preview.insert("end", text)
        self.preview.config(state="disabled")

    def _get_editor_text(self) -> str:
        return self.editor.get(1.0, "end-1c")

    def _editor_set_text(self, s: str) -> None:
        self.editor.delete(1.0, "end")
        self.editor.insert("end", s)

    def _select_all(self, target=None):
        """支持两种调用：作为事件 (_select_all(event)) 或直接传控件 (_select_all(widget))。"""
        widget = None
        if hasattr(target, "widget"):
            widget = target.widget
        elif target is not None:
            widget = target
        else:
            return "break"
        try:
            widget.tag_add("sel", "1.0", "end")
        except Exception:
            pass
        return "break"

    def _copy_to_clipboard(self, s: str):
        try:
            top = self.winfo_toplevel()
            top.clipboard_clear()
            top.clipboard_append(s)
            top.update_idletasks()
        except Exception:
            pass
