# %% main.py
# -*- coding: utf-8 -*-

# 内置库
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from tkinter import Toplevel
import tkinter.messagebox as messagebox

# 第三方库
import ttkbootstrap as ttk

from view.config import DATA_CONFIG, SCREEN_CONFIG
from view.screens.screen_workbench import Screen_Workbench
from utils.clear_pycache import clear_pycache
from utils.paths import resource_path

# ========== 日志 ==========
logger = logging.getLogger()
logger.setLevel(logging.INFO)
_handler = RotatingFileHandler("app.log", mode="a", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_handler.setFormatter(_formatter)
logger.handlers = [_handler]


# 捕获未处理异常：写日志 + 弹窗提示
def _excepthook(exc_type, exc, tb):
    logging.exception("Uncaught exception", exc_info=(exc_type, exc, tb))
    try:
        messagebox.showerror("错误", f"发生未处理异常：{exc_type.__name__}: {exc}")
    except Exception:
        pass


sys.excepthook = _excepthook


# ========== 启动画面（ASCII Splash）==========
ASCII_MCMAA = r"""
        ,'  , `.  ,----..          ,'  , `.   ,---,         ,---,        
     ,-+-,.' _ | /   /   \      ,-+-,.' _ |  '  .' \       '  .' \       
  ,-+-. ;   , |||   :     :  ,-+-. ;   , || /  ;    '.    /  ;    '.     
 ,--.'|'   |  ;|.   |  ;. / ,--.'|'   |  ;|:  :       \  :  :       \    
|   |  ,', |  ':.   ; /--` |   |  ,', |  '::  |   /\   \ :  |   /\   \   
|   | /  | |  ||;   | ;    |   | /  | |  |||  :  ' ;.   :|  :  ' ;.   :  
'   | :  | :  |,|   : |    '   | :  | :  |,|  |  ;/  \   \  |  ;/  \   \ 
;   . |  ; |--' .   | '___ ;   . |  ; |--' '  :  | \  \ ,'  :  | \  \ ,' 
|   : |  | ,    '   ; : .'||   : |  | ,    |  |  '  '--' |  |  '  '--'   
|   : '  |/     '   | '/  :|   : '  |/     |  :  :       |  :  :         
;   | |`-'      |   :    / ;   | |`-'      |  | ,'       |  | ,'         
|   ;/           \   \ .'  |   ;/          `--''         `--''           
'---'             `---`    '---'                                         
"""


class Splash(Toplevel):
    def __init__(self, master, delay_ms=1200):
        super().__init__(master)
        # 无边框置顶
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # 内容
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        # 使用等宽字体以显示 ASCII
        label = ttk.Label(frame, text=ASCII_MCMAA, font=("Consolas", 12), justify="left")
        label.pack()

        # 居中
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

        # 延时关闭
        self.after(delay_ms, self.destroy)


# ========== 主屏 ==========
class Screen(ttk.Frame):
    """唯一主界面：写作工作台"""

    def __init__(self):
        super().__init__(DATA_CONFIG["window"], **SCREEN_CONFIG)
        DATA_CONFIG["screen"] = self
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 直接加载合并后的工作台
        self.workbench = Screen_Workbench(self)
        # 给“同步预览”留一个开关（目前工作台始终同步，后续可在 set_preview 里读取此值）
        self.workbench.sync_preview = True
        self.workbench.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 菜单栏
        self._build_menubar()

    # ---------- 顶部极简菜单 ----------
    def _build_menubar(self):
        root = DATA_CONFIG["window"]
        menubar = ttk.Menu(root)

        # File
        m_file = ttk.Menu(menubar, tearoff=False)
        m_file.add_command(label="Open\tCtrl+O", command=self.workbench.select_file)
        m_file.add_command(label="Save\tCtrl+S", command=self.workbench.save_current_text)
        m_file.add_command(label="Reload", command=self.workbench.reload_from_disk)
        m_file.add_separator()

        # Quick Open 子菜单：用 postcommand 动态刷新
        self.quick_open_menu = ttk.Menu(m_file, tearoff=False, postcommand=self._refresh_quick_open)
        m_file.add_cascade(label="Quick Open", menu=self.quick_open_menu)

        menubar.add_cascade(label="File", menu=m_file)

        # View
        m_view = ttk.Menu(menubar, tearoff=False)
        self._sync_preview_var = ttk.BooleanVar(value=True)

        def _toggle_sync():
            # 目前 set_preview 会自动切换到“预览”，这里仅保存偏好，便于将来生效
            self.workbench.sync_preview = bool(self._sync_preview_var.get())

        m_view.add_checkbutton(
            label="Sync Preview", onvalue=True, offvalue=False, variable=self._sync_preview_var, command=_toggle_sync
        )
        menubar.add_cascade(label="View", menu=m_view)

        # Help
        m_help = ttk.Menu(menubar, tearoff=False)
        m_help.add_command(label="View Log", command=self._show_log_window)
        m_help.add_separator()
        m_help.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=m_help)

        root.config(menu=menubar)

    def _refresh_quick_open(self):
        # 先清空
        self.quick_open_menu.delete(0, "end")
        paths = self.workbench.get_recent_files()
        if not paths:
            self.quick_open_menu.add_command(label="(Empty)", state="disabled")
            return
        for p in paths:
            self.quick_open_menu.add_command(label=p, command=lambda _p=p: self.workbench.quick_open(_p))

    def _show_log_window(self):
        log_path = os.path.join(DATA_CONFIG.get("py_path") or ".", "app.log")
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"(无法读取日志: {e})"

        win = ttk.Toplevel(self)
        win.title("应用日志 app.log")
        win.geometry("900x600")
        txt = ttk.ScrolledText(win, wrap="word", state="normal")
        txt.pack(fill="both", expand=True)
        txt.insert("end", content)
        txt.config(state="disabled")

    def _about(self):
        messagebox.showinfo(
            "About",
            "MCM Aid Assistant v1.1.0\n\n"
            "极简写作工作台：左侧大纲/问题树，右侧编辑/预览/标记替换。\n"
            "快捷键：Ctrl+O 打开，Ctrl+S 保存，Ctrl+F 查找，Ctrl+H 替换。\n"
            "File→Quick Open 提供最近文件。",
        )


class App:
    """应用主体"""

    def __init__(self, py_path=os.path.dirname(os.path.abspath(__file__))):
        DATA_CONFIG["app"] = self
        DATA_CONFIG["py_path"] = py_path

        # 先创建主窗口，但先隐藏
        DATA_CONFIG["window"] = ttk.Window(
            themename="sandstone",
            title="数学建模论文写作辅助软件 MCM Aid Assistant v1.1.0",
        )
        root = DATA_CONFIG["window"]
        root.withdraw()

        # 图标
        try:
            if sys.platform.startswith("darwin"):
                root.iconphoto(True, ttk.PhotoImage(file=resource_path("mcmaa.png")))
            else:
                # Linux 用 iconphoto，更通用；Windows 可留 iconbitmap
                ico_path = resource_path("mcmaa.ico")
                if sys.platform.startswith("win"):
                    root.iconbitmap(ico_path)
                else:
                    root.iconphoto(True, ttk.PhotoImage(file=resource_path("mcmaa.png")))
        except Exception as e:
            logging.info(f"图标加载失败: {e}")

        # 尺寸
        min_height = 960
        min_width = int(min_height * 4 / 3)
        root.minsize(min_width, min_height)
        root.geometry(f"{min_width}x{min_height}")
        screen_height = root.winfo_screenheight()
        screen_width = root.winfo_screenwidth()
        default_height = int(screen_height * 0.75)
        default_width = int(screen_height * 0.75 * 4 / 3)
        if screen_height < min_height or screen_width < min_width:
            root.minsize(screen_width, screen_height)
            default_height = screen_height
            default_width = screen_width
            root.geometry(f"{default_width}x{default_height}")
        elif screen_height * 0.75 > min_height and screen_height * 0.75 * 4 / 3 > min_width:
            root.geometry(f"{default_width}x{default_height}")
        root.geometry("+0+0")

        # 显示启动 ASCII Splash
        splash = Splash(root, delay_ms=1200)

        # Splash 消失后显示主界面
        def _show_main():
            if splash.winfo_exists():
                try:
                    splash.destroy()
                except Exception:
                    pass
            root.deiconify()
            Screen()  # 创建主界面

        root.after(1250, _show_main)  # 稍微比 Splash 多 50ms，避免闪烁
        root.mainloop()


if __name__ == "__main__":
    App()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    clear_pycache(script_dir)
