# %% main.py

# 内置库
import os
import sys
import logging  # 导入 logging 模块
from tkinter import *

# 第三方库
import ttkbootstrap as ttk

from view.config import (
    DATA_CONFIG,
    SCREEN_CONFIG,
)
from view.screens.screen1_mcmaa import Screen1_MCMAA
from view.screens.screen2_latex_extractor import Screen2_LaTeX_Extractor
from view.screens.screen3_text_replacer import Screen3_Text_Replacer
from utils.clear_pycache import clear_pycache

# 配置 logging
logging.basicConfig(
    filename="app.log",  # 日志文件保存为 app.log
    filemode="w",  # 每次运行时重写文件
    level=logging.INFO,  # 设置日志级别为 INFO
    format="%(asctime)s - %(levelname)s - %(message)s",  # 日志格式：时间 - 级别 - 消息
    encoding="utf-8",  # 支持中文
)


# 四个主界面
class Screen(ttk.Frame):
    def __init__(self):
        super().__init__(DATA_CONFIG["window"], **SCREEN_CONFIG)
        DATA_CONFIG["screen"] = self
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 创建所有子界面并存储在字典中
        self.frames = {
            "MCM论文辅助": Screen1_MCMAA(self),
            "LaTeX提取器": Screen2_LaTeX_Extractor(self),
            "Text替换器": Screen3_Text_Replacer(self),
        }

        # 设置默认界面为“MCM论文辅助”
        self.current_frame = self.frames["MCM论文辅助"]
        self.current_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        logging.info("初始化显示: MCM论文辅助")

        # 隐藏其他界面
        for frame_name, frame in self.frames.items():
            if frame != self.current_frame:
                frame.place_forget()
                logging.info(f"隐藏界面: {frame_name}")

        # 设置默认模式
        DATA_CONFIG["mode"].set("MCM论文辅助")

    def change_mode(self, *args):
        new_mode = DATA_CONFIG["mode"].get()
        logging.info(f"切换到模式: {new_mode}")

        # 隐藏当前界面
        self.current_frame.place_forget()
        logging.info(f"隐藏: {self.current_frame.__class__.__name__}")

        # 显示新界面
        self.current_frame = self.frames[new_mode]
        self.current_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        logging.info(f"显示: {self.current_frame.__class__.__name__}")

        DATA_CONFIG["screen"] = self.current_frame


class App:
    """应用主体"""

    def __init__(self, py_path=os.path.dirname(os.path.abspath(__file__))):
        DATA_CONFIG["app"] = self
        DATA_CONFIG["py_path"] = py_path
        DATA_CONFIG["window"] = ttk.Window(
            themename="sandstone",
            title="数学建模论文写作辅助软件 MCM Aid Assistant v1.0.0",
        )

        DATA_CONFIG["mode"] = StringVar()

        try:
            if sys.platform.startswith("darwin"):
                DATA_CONFIG["window"].iconphoto(
                    True, PhotoImage(file=os.path.join(py_path, "mcmaa.png"))
                )
            else:
                DATA_CONFIG["window"].iconbitmap(os.path.join(py_path, "mcmaa.ico"))
        except Exception as e:
            logging.info(f"图标加载失败: {e}")
        min_height = 960
        min_width = int(min_height * 4 / 3)
        DATA_CONFIG["window"].minsize(min_width, min_height)
        DATA_CONFIG["window"].geometry(f"{min_width}x{min_height}")
        screen_height = DATA_CONFIG["window"].winfo_screenheight()
        screen_width = DATA_CONFIG["window"].winfo_screenwidth()
        default_height = int(screen_height * 0.75)
        default_width = int(screen_height * 0.75 * 4 / 3)
        if screen_height < min_height or screen_width < min_width:
            DATA_CONFIG["window"].minsize(screen_width, screen_height)
            default_height = screen_height
            default_width = screen_width
            DATA_CONFIG["window"].geometry(f"{default_width}x{default_height}")
        elif screen_height * 0.75 > min_height and screen_height * 0.75 * 4 / 3 > min_width:
            default_height = int(screen_height * 0.75)
            default_width = int(screen_height * 0.75 * 4 / 3)
            DATA_CONFIG["window"].geometry(f"{default_width}x{default_height}")
        DATA_CONFIG["window"].geometry("+0+0")
        DATA_CONFIG["screen"] = Screen()
        DATA_CONFIG["window"].mainloop()


if __name__ == "__main__":
    App()
    # 获取当前脚本所在的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    clear_pycache(script_dir)
