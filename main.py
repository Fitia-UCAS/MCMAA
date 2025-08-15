# %% main.py

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
 __  __   ____   ____    _       _       _     
|  \/  | / ___| / ___|  / \   __| |_   _| |__  
| |\/| | \___ \ \___ \ / _ \ / _` | | | | '_ \ 
| |  | |  ___) | ___) / ___ \ (_| | |_| | | | |
|_|  |_| |____/ |____/_/   \_\__,_|\__,_|_| |_|

     M C M   A i d   A s s i s t a n t
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
        label = ttk.Label(
            frame, text=ASCII_MCMAA, font=("Consolas", 12), justify="left"  # Windows常见；若不存在会自动回退
        )
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
        self.workbench.place(relx=0, rely=0, relwidth=1, relheight=1)


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
                root.iconphoto(True, ttk.PhotoImage(file=os.path.join(py_path, "mcmaa.png")))
            else:
                root.iconbitmap(os.path.join(py_path, "mcmaa.ico"))
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
                # 保险起见，若还在则先销毁
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
