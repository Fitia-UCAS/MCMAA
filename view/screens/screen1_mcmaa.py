# %% view/screens/screen1_mcmaa.py

from tkinter import StringVar, ttk
from ..common_widgets import TextWidget
from ..config import DATA_CONFIG, MAIN_FRAME_CONFIG, FLAT_SUBFRAME_CONFIG


class Screen1_MCMAA(ttk.Frame):

    MODE_NAME = "MCM论文辅助"

    """MCM论文辅助初始界面，仅提供使用提示和模式切换"""

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.paned_window = ttk.PanedWindow(self, orient="horizontal")
        self.paned_window.pack(fill="both", expand=True)
        self.left_frame = ttk.Frame(self.paned_window, **MAIN_FRAME_CONFIG)
        self.right_frame = ttk.Frame(self.paned_window, **MAIN_FRAME_CONFIG)
        self.paned_window.add(self.left_frame, weight=1)
        self.paned_window.add(self.right_frame, weight=3)
        self.arrangeLeft()
        self.arrangeRight()
        self.addInfoLabel()

    def arrangeLeft(self):
        """设置左侧区域，仅包含模式切换下拉菜单"""
        tmp = ttk.Frame(self.left_frame, **FLAT_SUBFRAME_CONFIG)
        tmp.pack(fill="x")
        self.button_mode = ttk.OptionMenu(tmp, DATA_CONFIG["mode"], "", command=self.master.change_mode)
        self.button_mode.set_menu(self.MODE_NAME, *DATA_CONFIG["modes"])
        self.button_mode.pack(fill="x")

    def arrangeRight(self):
        """设置右侧区域，显示使用提示"""
        self.text_frame = TextWidget(self.right_frame, **MAIN_FRAME_CONFIG)
        self.text_frame.pack(fill="both", expand=True)
        self.text_frame.append(self.get_usage_instructions())

    def get_usage_instructions(self):
        """返回软件使用提示文本"""
        return (
            "欢迎使用数学建模论文写作辅助软件 MCM Aid Assistant v1.0.0！\n\n"
            "使用说明：\n"
            "1. 本软件提供四种主要功能，通过四个界面实现：\n"
            "   - MCM论文辅助：欢迎界面，仅提供软件使用说明。\n"
            "   - LaTeX提取器：从LaTeX文件中提取特定章节或问题内容。\n"
            "   - Text替换器：对文本中的标记对进行批量替换。\n"
            "   - 写作编辑器：仿 Atom 的编辑/导航界面，支持按大纲与“问题一/二/三”快速汇总浏览。\n"
            "2. 请在左侧下拉菜单中选择所需的功能模式。\n"
            "3. 切换到各功能界面后，您可以打开文件、编辑内容或执行其他操作。\n"
            "4. 更多帮助信息，请参考软件文档或联系支持团队。\n\n"
            "作者：非非大人"
        )

    def addInfoLabel(self):
        """添加底部信息标签"""
        tmp = ttk.Frame(self.left_frame)
        tmp.pack(side="bottom", fill="x")
        self.info_label = ttk.Label(tmp, text="作者：非非大人", anchor="center")
        self.info_label.pack(fill="x")
