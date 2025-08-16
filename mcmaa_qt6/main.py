# %% main.py
# -*- coding: utf-8 -*-

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QMenu,
    QTextEdit,
    QDialog,
    QVBoxLayout,
)

from view.screens.screen_workbench import Screen_Workbench
from utils.paths import resource_path

# ---------- 日志 ----------
logger = logging.getLogger()
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler("app.log", mode="a", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_handler.setFormatter(_formatter)
logger.handlers = [_handler]


class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("应用日志 app.log")
        self.resize(900, 600)
        lay = QVBoxLayout(self)
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        lay.addWidget(self.text)

    def load_log(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.text.setPlainText(f.read())
        except Exception as e:
            self.text.setPlainText(f"(无法读取日志: {e})")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数学建模论文写作辅助软件 MCM Aid Assistant v1.1.0")

        # 图标
        try:
            ico_path = resource_path("mcmaa.ico")
            if os.path.exists(ico_path):
                self.setWindowIcon(QIcon(ico_path))
        except Exception:
            pass

        # 中央工作台（你已改为 Qt 小部件）
        self.workbench = Screen_Workbench(self)
        self.setCentralWidget(self.workbench)

        # 初始窗口尺寸
        self.resize(1280, 960)
        self.move(0, 0)

        # 菜单栏
        self._build_menubar()

    # ---------- 菜单 ----------
    def _build_menubar(self):
        menubar = self.menuBar()

        # File
        m_file = menubar.addMenu("File")

        act_open = QAction("Open\tCtrl+O", self)
        act_open.triggered.connect(self.workbench.select_file)
        m_file.addAction(act_open)

        act_save = QAction("Save\tCtrl+S", self)
        act_save.triggered.connect(self.workbench.save_current_text)
        m_file.addAction(act_save)

        act_reload = QAction("Reload", self)
        act_reload.triggered.connect(self.workbench.reload_from_disk)
        m_file.addAction(act_reload)

        m_file.addSeparator()

        self.quick_menu = QMenu("Quick Open", self)
        # aboutToShow 时动态刷新
        self.quick_menu.aboutToShow.connect(self._refresh_quick_open)
        m_file.addMenu(self.quick_menu)

        # View
        m_view = menubar.addMenu("View")
        # 先保留开关占位，当前逻辑在 set_preview 中总是切到预览页
        self.sync_preview = True
        act_sync = QAction("Sync Preview", self, checkable=True, checked=True)

        def _toggle_sync(_):
            self.sync_preview = act_sync.isChecked()
            # 目前仅保存偏好，必要时你可在 Screen_Workbench.set_preview 里读取

        act_sync.triggered.connect(_toggle_sync)
        m_view.addAction(act_sync)

        # Help
        m_help = menubar.addMenu("Help")

        act_log = QAction("View Log", self)
        act_log.triggered.connect(self._show_log_window)
        m_help.addAction(act_log)

        m_help.addSeparator()

        act_about = QAction("About", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _refresh_quick_open(self):
        self.quick_menu.clear()
        paths = self.workbench.get_recent_files()
        if not paths:
            dummy = QAction("(Empty)", self)
            dummy.setEnabled(False)
            self.quick_menu.addAction(dummy)
            return
        for p in paths:
            act = QAction(p, self)
            act.triggered.connect(lambda _=False, _p=p: self.workbench.quick_open(_p))
            self.quick_menu.addAction(act)

    def _show_log_window(self):
        dlg = LogDialog(self)
        dlg.load_log(os.path.join(os.getcwd(), "app.log"))
        dlg.exec()

    def _about(self):
        QMessageBox.information(
            self,
            "About",
            "MCM Aid Assistant v1.1.0\n\n"
            "极简写作工作台：左侧大纲/问题树，右侧编辑/预览/标记替换。\n"
            "快捷键：Ctrl+O 打开，Ctrl+S 保存，Ctrl+F 查找，Ctrl+H 替换。\n"
            "File → Quick Open 提供最近文件。",
        )


def main():
    # 统一 Qt 应用入口
    app = QApplication(sys.argv)

    # （可选）简单 splash：这里用计时器延后展示主窗，想用图片可换 QSplashScreen
    win = MainWindow()
    win.hide()

    def _show():
        win.show()
        win.raise_()
        win.activateWindow()

    QTimer.singleShot(200, _show)  # 轻微延迟避免首次绘制撕裂

    sys.exit(app.exec())


if __name__ == "__main__":
    # 兜底：把未捕获异常写到日志，再弹框
    def _excepthook(exc_type, exc, tb):
        logging.exception("Uncaught exception", exc_info=(exc_type, exc, tb))
        try:
            QMessageBox.critical(None, "错误", f"发生未处理异常：{exc_type.__name__}: {exc}")
        except Exception:
            pass

    sys.excepthook = _excepthook

    main()
