# %% view/screens/screen_workbench.py
# -*- coding: utf-8 -*-

"""
Qt6 (PySide6) 版 View：一体化工作台
- 左侧：导航（大纲/问题/代码）
- 右侧：Tab（编辑 / 预览 / 替换 / 辅助）
- 与原 Tk 版保持同名 API：get_recent_files / quick_open / reload_from_disk / select_file / save_current_text 等
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QSplitter,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QPlainTextEdit,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QMenu,
    QComboBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QDialog,
    QLineEdit,
    QFormLayout,
)

from controller.workbench_controller import WorkbenchController


class Screen_Workbench(QWidget):
    """
    一体化工作台（MVC：View，Qt6）
    - 业务逻辑均委托给 WorkbenchController
    """

    MODE_NAME = "一体化工作台"

    # ---------- 对外给“主窗/菜单”用的 API ----------
    def get_recent_files(self):
        """给主菜单调用，获取最近文件列表（最新在前）"""
        return list(self.ctrl.recent_files)

    def quick_open(self, p: str):
        """给主菜单的 Quick Open 点击使用（委托 Controller，文案由 View 负责）"""
        ok, _msg, text = self.ctrl.quick_open(p)
        if not ok:
            QMessageBox.warning(self, "提示", "文件不存在，已从最近列表移除。")
            return
        self.editor.setPlainText(text)
        self.set_preview(f"文件已加载: {p}")
        self._refresh_marker_pairs()
        self._rebuild_all_trees()
        self.tabs.setCurrentWidget(self.tab_edit)

    # =====================================================

    def __init__(self, parent=None):
        super().__init__(parent)

        # Controller & 轻量状态
        self.ctrl = WorkbenchController()
        self.selected_pair_display = ""  # 当前选中的“标记对”显示名

        # ===== 主左右分割 =====
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.splitter)

        # 左侧：导航（大纲/问题/代码）
        self.left_tabs = QTabWidget()
        self.splitter.addWidget(self.left_tabs)

        # 大纲
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.left_tabs.addTab(self.outline_tree, "大纲")
        self.outline_tree.itemSelectionChanged.connect(self.on_outline_select)
        self.outline_tree.itemDoubleClicked.connect(self._goto_outline_line)

        # 问题（含右键菜单）
        self.problem_tree = QTreeWidget()
        self.problem_tree.setHeaderHidden(True)
        self.left_tabs.addTab(self.problem_tree, "问题")
        self.problem_tree.itemSelectionChanged.connect(self.on_problem_select)
        self._init_problem_context_menu()

        # 代码（专门放 codeblock）
        self.code_tree = QTreeWidget()
        self.code_tree.setHeaderHidden(True)
        self.left_tabs.addTab(self.code_tree, "代码")
        self.code_tree.itemSelectionChanged.connect(self.on_code_select)

        # 右侧：Notebook（编辑/预览/替换/辅助）
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.splitter.addWidget(right)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # 编辑
        self.tab_edit = QWidget()
        v = QVBoxLayout(self.tab_edit)
        self.editor = QPlainTextEdit()
        v.addWidget(self.editor)
        self.tabs.addTab(self.tab_edit, "编辑")

        # 预览
        self.tab_preview = QWidget()
        v2 = QVBoxLayout(self.tab_preview)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        v2.addWidget(self.preview)
        self.tabs.addTab(self.tab_preview, "预览")

        # 替换
        self.tab_replace = QWidget()
        rlay = QVBoxLayout(self.tab_replace)
        topbar = QHBoxLayout()
        topbar.addWidget(QLabel("标记对："))
        self.pair_combo = QComboBox()
        topbar.addWidget(self.pair_combo, 1)
        self.btn_apply_replace = QPushButton("应用替换（Ctrl+S）")
        topbar.addWidget(self.btn_apply_replace)
        rlay.addLayout(topbar)
        self.replace_input = QTextEdit()
        rlay.addWidget(self.replace_input, 1)
        self.tabs.addTab(self.tab_replace, "替换")

        # 辅助
        self.tab_aid = QWidget()
        alay = QVBoxLayout(self.tab_aid)
        atop = QHBoxLayout()
        atop.addWidget(QLabel("辅助文件："))
        self.aid_combo = QComboBox()
        atop.addWidget(self.aid_combo, 1)
        self.btn_aid_apply = QPushButton("插入到编辑器（Ctrl+S）")
        atop.addWidget(self.btn_aid_apply)
        alay.addLayout(atop)
        self.aid_view = QTextEdit()
        alay.addWidget(self.aid_view, 1)
        self.tabs.addTab(self.tab_aid, "辅助")

        # 分割比例
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 7)

        # ---------- 快捷键（与 Tk 版等价） ----------
        self._install_shortcuts()

        # ---------- 信号绑定 ----------
        self.pair_combo.currentIndexChanged.connect(self.on_pair_select)
        self.btn_apply_replace.clicked.connect(self.apply_replace)
        self.btn_aid_apply.clicked.connect(self.apply_aid_to_editor)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.aid_combo.currentIndexChanged.connect(self._on_aid_select)

        # 初始
        self._refresh_aid_files()

    # ---------- 快捷键 ----------
    def _install_shortcuts(self):
        # Ctrl/⌘+A：编辑器全选
        act_sel_all = QAction(self)
        act_sel_all.setShortcut(QKeySequence("Ctrl+A"))
        act_sel_all.triggered.connect(lambda: self._select_all(self.editor))
        self.addAction(act_sel_all)

        # Ctrl/⌘+S：全局保存/应用
        act_save = QAction(self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._on_global_save_or_apply)
        self.addAction(act_save)

        # Ctrl/⌘+O：打开
        act_open = QAction(self)
        act_open.setShortcut(QKeySequence("Ctrl+O"))
        act_open.triggered.connect(self.select_file)
        self.addAction(act_open)

        # Ctrl/⌘+F：查找；Ctrl/⌘+H：替换
        act_find = QAction(self)
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self._open_find_dialog)
        self.addAction(act_find)

        act_repl = QAction(self)
        act_repl.setShortcut(QKeySequence("Ctrl+H"))
        act_repl.triggered.connect(self._open_replace_dialog)
        self.addAction(act_repl)

    # ---------------- 工具函数 ----------------
    def _select_all(self, target=None):
        """全选：兼容事件/直接调用"""
        w = target if isinstance(target, (QPlainTextEdit, QTextEdit)) else self.editor
        w.selectAll()

    def _get_editor_text(self) -> str:
        return self.editor.toPlainText()

    def set_preview(self, text: str):
        self.tabs.setCurrentWidget(self.tab_preview)
        self.preview.setPlainText(text or "")

    # 全局保存/应用的统一入口
    def _on_global_save_or_apply(self):
        """替换页 Ctrl/⌘+S 应用替换；辅助页插入；其它页保存文件"""
        tab_text = self.tabs.tabText(self.tabs.currentIndex())
        if tab_text == "替换":
            self.apply_replace()
        elif tab_text == "辅助":
            self.apply_aid_to_editor()
        else:
            self.save_current_text()

    # ---------------- 文件 I/O（快捷键驱动） ----------------
    def reload_from_disk(self):
        """从磁盘重载，不改动文件内容"""
        data = self.ctrl.reload_from_disk()
        text = data.get("text", "")
        if not text:
            return
        self.editor.setPlainText(text)
        self._refresh_marker_pairs()
        self._rebuild_all_trees()
        self.set_preview("已从磁盘重载。")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择 LaTeX 文件", "", "LaTeX files (*.tex);;LaTeX Template (*.template);;All files (*)"
        )
        if not file_path:
            return
        self._open_path(file_path)

    def _open_path(self, file_path: str):
        try:
            data = self.ctrl.open_path(file_path)
            text = data.get("text", "")
            self.editor.setPlainText(text)
            self.set_preview(f"文件已加载: {file_path}")
            self._refresh_marker_pairs()
            self._rebuild_all_trees()
            self.tabs.setCurrentWidget(self.tab_edit)
        except Exception as e:
            self.set_preview(f"错误: {e}")

    def save_current_text(self):
        ok, msg = self.ctrl.save_text(self._get_editor_text())
        if not ok:
            self.set_preview(f"保存失败：{msg or '未知错误'}")
            return
        self._rebuild_all_trees()
        self.set_preview("保存成功。")

    # ---------------- 解析 / 导航 ----------------
    def _rebuild_all_trees(self):
        self._build_outline_tree()
        self._build_problem_tree()
        self._build_code_tree()

    def _build_outline_tree(self):
        self.outline_tree.clear()
        if not self.ctrl.extractor:
            return
        nodes = self.ctrl.make_outline_nodes(self.ctrl.extractor)
        # 用堆栈构建层级
        stack = [(None, 0)]
        for n in nodes:
            title, level, line_num = n["title"], n["level"], n["line_num"]
            while stack and level <= stack[-1][1]:
                stack.pop()
            parent = stack[-1][0]
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.UserRole, (line_num, level))
            if parent is None:
                self.outline_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            stack.append((item, level))
        self.outline_tree.expandAll()

    def _build_problem_tree(self):
        self.problem_tree.clear()
        if not self.ctrl.extractor:
            return
        items = self.ctrl.make_problem_tree(self.ctrl.extractor)
        for item in items:
            pnode = QTreeWidgetItem([item["text"]])
            pnode.setData(0, Qt.UserRole, tuple(item["values"]))
            self.problem_tree.addTopLevelItem(pnode)
            for child in item.get("children", []):
                c = QTreeWidgetItem([child["text"]])
                c.setData(0, Qt.UserRole, tuple(child["values"]))
                pnode.addChild(c)
        self.problem_tree.expandAll()

    def _build_code_tree(self):
        self.code_tree.clear()
        if not self.ctrl.extractor:
            return
        nodes = self.ctrl.make_code_nodes(self.ctrl.extractor)
        for n in nodes:
            it = QTreeWidgetItem([n["text"]])
            it.setData(0, Qt.UserRole, tuple(n["values"]))
            self.code_tree.addTopLevelItem(it)
        self.code_tree.expandAll()

    # ---------------- 问题树：右键菜单 ----------------
    def _init_problem_context_menu(self):
        self.problem_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.problem_tree.customContextMenuRequested.connect(self._popup_problem_menu)

    def _popup_problem_menu(self, pos):
        item = self.problem_tree.itemAt(pos)
        if not item:
            return
        self.problem_tree.setCurrentItem(item)
        menu = QMenu(self)
        act_all = menu.addAction("复制该问题：摘要+重述+分析+建模")
        menu.addSeparator()
        act_a = menu.addAction("只复制 摘要片段")
        act_r = menu.addAction("只复制 问题重述")
        act_an = menu.addAction("只复制 问题分析")
        act_m = menu.addAction("只复制 模型与求解")

        act = menu.exec(self.problem_tree.mapToGlobal(pos))
        if not act:
            return
        if act == act_all:
            self._copy_problem_merged()
        elif act == act_a:
            self._copy_problem_part("abstract")
        elif act == act_r:
            self._copy_problem_part("restate")
        elif act == act_an:
            self._copy_problem_part("analysis")
        elif act == act_m:
            self._copy_problem_part("modeling")

    def _copy_to_clipboard(self, s: str):
        if not s:
            return
        cb = self.clipboard() if hasattr(self, "clipboard") else None
        # QWidget 没有 clipboard()；用 QApplication
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(s)

    def _copy_problem_merged(self):
        item = self.problem_tree.currentItem()
        if not item:
            return
        vals = item.data(0, Qt.UserRole)
        if not vals:
            return
        k = vals[0] if len(vals) >= 1 else None
        if not k:
            return
        text = self.ctrl.build_problem_merged_text(self.ctrl.extractor, k)
        if text:
            self._copy_to_clipboard(text)

    def _copy_problem_part(self, part: str):
        item = self.problem_tree.currentItem()
        if not item:
            return
        vals = item.data(0, Qt.UserRole)
        if not vals:
            return
        k = vals[0]
        text = self.ctrl.build_problem_part_text(self.ctrl.extractor, k, part)
        if text:
            self._copy_to_clipboard(text)

    # ---------------- 导航事件 ----------------
    def on_outline_select(self):
        if not self.ctrl.extractor:
            return
        items = self.outline_tree.selectedItems()
        if not items:
            return
        vals = items[0].data(0, Qt.UserRole)
        if not vals:
            return
        line_num, section_level = vals
        text = self.ctrl.render_outline_preview(self.ctrl.extractor, line_num, section_level)
        # render_outline_preview 已返回字符串（你的实现返回 "\n".join(lines)）
        self.set_preview(text)

    def _goto_outline_line(self):
        """双击大纲项，编辑器跳转到对应行，并临时高亮"""
        items = self.outline_tree.selectedItems()
        if not items:
            return
        vals = items[0].data(0, Qt.UserRole)
        if not vals:
            return
        line_num = int(vals[0]) + 1  # 文本行号从 1 开始
        self.tabs.setCurrentWidget(self.tab_edit)
        doc = self.editor.document()
        # 逐行定位
        block = doc.findBlockByLineNumber(max(0, line_num - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        # 临时高亮：选中整行后 2s 清除
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        QTimer.singleShot(2000, lambda: self.editor.moveCursor(QTextCursor.End))  # 取消选择

    def on_problem_select(self):
        if not self.ctrl.extractor:
            return
        items = self.problem_tree.selectedItems()
        if not items:
            return
        vals = items[0].data(0, Qt.UserRole)
        if not vals:
            return
        if len(vals) == 1:  # 点击“问题X” -> 合并并加分隔标题（展示层）
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
        """在 View 侧为合并预览加上分节标题与分隔（纯展示）"""
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

    def on_code_select(self):
        if not self.ctrl.extractor:
            return
        items = self.code_tree.selectedItems()
        if not items:
            return
        vals = items[0].data(0, Qt.UserRole)
        if not vals:
            return
        line_num, level = vals
        text = self.ctrl.render_code_preview(self.ctrl.extractor, line_num, level)
        self.set_preview(text if isinstance(text, str) else "\n".join(text))

    # ---------------- 替换功能（仅服务标记对） ----------------
    def _on_tab_changed(self, _idx: int):
        tab_text = self.tabs.tabText(self.tabs.currentIndex())
        if tab_text == "替换":
            self._refresh_marker_pairs()
        if tab_text == "辅助":
            self._refresh_aid_files()

    def _refresh_marker_pairs(self):
        """
        View 只负责：
        - 将当前编辑器文本同步给 Controller（保持业务状态在 Controller）
        - 请求 Controller 扫描并返回可显示的标记对列表
        - 刷新下拉与文本框
        """
        current = self._get_editor_text()
        self.ctrl.update_current_text_only(current)
        display = self.ctrl.update_marker_pairs_from_text(current)
        self.pair_combo.blockSignals(True)
        self.pair_combo.clear()
        self.pair_combo.addItems(display)
        self.pair_combo.blockSignals(False)
        if display:
            self.pair_combo.setCurrentIndex(0)
            self.on_pair_select()
        else:
            self.selected_pair_display = ""
            self.replace_input.clear()

    def on_pair_select(self):
        sel = (self.pair_combo.currentText() or "").strip()
        self.selected_pair_display = sel
        self.replace_input.clear()
        if not sel:
            return
        content = self.ctrl.get_pair_content_by_display(sel)
        self.replace_input.setPlainText(content)

    def apply_replace(self):
        """
        View 只负责读入 UI 值并将结果写回编辑器；
        具体替换业务由 Controller 完成。
        """
        sel = (self.selected_pair_display or "").strip()
        if not sel:
            return
        try:
            new_content = self.replace_input.toPlainText()
            base_text = self._get_editor_text()
            new_text = self.ctrl.apply_replace_for_display(base_text, sel, new_content)
            self.editor.setPlainText(new_text)
            self._refresh_marker_pairs()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"替换失败: {str(e)}")

    # ---------------- 编辑器：全文搜索 / 替换 ----------------
    def _do_find_all(self, needle: str) -> int:
        """高亮全部匹配（简易实现：定位到第一个匹配并选中；Qt 原生无多范围高亮，这里返回计数）"""
        if not needle:
            return 0
        text = self._get_editor_text()
        count = text.count(needle)
        if count:
            # 定位到第一个
            cursor = self.editor.textCursor()
            doc = self.editor.document()
            found = doc.find(needle, 0)
            if found.isNull():
                return count
            self.editor.setTextCursor(found)
            self.editor.centerCursor()
        return count

    def _open_find_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("查找 (Ctrl+F)")
        form = QFormLayout(dlg)
        e_find = QLineEdit()
        msg = QLabel("")
        form.addRow("查找内容:", e_find)
        form.addRow(msg)
        btns = QHBoxLayout()
        b_find = QPushButton("查找全部并高亮")
        btns.addWidget(b_find)
        form.addRow(btns)

        def do_find():
            n = self._do_find_all(e_find.text())
            msg.setText(f"匹配 {n} 处")

        b_find.clicked.connect(do_find)
        e_find.returnPressed.connect(do_find)
        dlg.setModal(True)
        dlg.resize(420, 110)
        dlg.show()

    def _open_replace_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("替换 (Ctrl+H)")
        form = QFormLayout(dlg)
        e_find = QLineEdit()
        e_repl = QLineEdit()
        msg = QLabel("")
        form.addRow("查找:", e_find)
        form.addRow("替换为:", e_repl)
        row = QHBoxLayout()
        b_next = QPushButton("替换下一个")
        b_all = QPushButton("全部替换")
        row.addWidget(b_next)
        row.addWidget(b_all)
        form.addRow(row)
        form.addRow(msg)

        def replace_next():
            needle = e_find.text()
            if not needle:
                return
            doc = self.editor.document()
            cur = self.editor.textCursor()
            # 从当前位置向后找
            found = doc.find(needle, cur)
            if found.isNull():
                # 从头再找
                found = doc.find(needle, 0)
                if found.isNull():
                    msg.setText("未找到")
                    return
            self.editor.setTextCursor(found)
            self.editor.insertPlainText(e_repl.text())
            msg.setText("已替换 1 处")

        def replace_all():
            needle = e_find.text()
            repl = e_repl.text()
            if not needle:
                return
            text = self._get_editor_text()
            count = text.count(needle)
            if count == 0:
                msg.setText("未找到")
                return
            text = text.replace(needle, repl)
            self.editor.setPlainText(text)
            msg.setText(f"已替换 {count} 处")

        b_next.clicked.connect(replace_next)
        b_all.clicked.connect(replace_all)
        e_find.returnPressed.connect(replace_next)
        dlg.setModal(True)
        dlg.resize(460, 150)
        dlg.show()

    # ---------- 辅助页：文件列表/读取/插入 ----------
    def _aid_dir_path(self):
        return self.ctrl.aid_dir()

    def _refresh_aid_files(self):
        files = self.ctrl.list_aid_txt()
        self.aid_combo.blockSignals(True)
        self.aid_combo.clear()
        self.aid_combo.addItems(files)
        self.aid_combo.blockSignals(False)
        if files:
            self._on_aid_select()
        else:
            self.aid_view.clear()

    def _on_aid_select(self):
        fname = (self.aid_combo.currentText() or "").strip()
        self.aid_view.clear()
        if not fname:
            return
        try:
            txt = self.ctrl.read_aid_txt(fname)
        except Exception as e:
            txt = f"(读取失败：{e})"
        self.aid_view.setPlainText(txt)

    def apply_aid_to_editor(self):
        """
        将辅助区当前内容插入编辑器：
        - 若编辑器有选区：替换选区
        - 否则：在光标处插入
        """
        content = self.aid_view.toPlainText()
        self.tabs.setCurrentWidget(self.tab_edit)
        self.editor.setFocus()
        cursor = self.editor.textCursor()
        cursor.insertText(content)
        self.editor.setTextCursor(cursor)
