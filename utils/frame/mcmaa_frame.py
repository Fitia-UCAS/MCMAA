# -*- coding: utf-8 -*-

# 内置库
import os
from tkinter import *
import tkinter.filedialog as filedialog
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk

# 全局配置
DATA_CONFIG = {
    "app": None,
    "window": None,
    "screen": None,
    "py_path": os.path.dirname(os.path.abspath(__file__)),
}

SCREEN_CONFIG = {"borderwidth": 5, "relief": "raised"}
MAIN_FRAME_CONFIG = {"borderwidth": 5, "relief": "sunken"}
RAISED_SUBFRAME_CONFIG = {"borderwidth": 1, "relief": "raised"}
FLAT_SUBFRAME_CONFIG = {"borderwidth": 2}
ENTRY_LABEL_CONFIG = {"padding": 2}


# --- 通用组件: TextWidget ---
class TextWidget(ttk.Frame):
    """带有滚动条的文本框组件"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.textbox = ScrolledText(self, undo=True)
        self.textbox.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.textbox.config(state="normal")
        self.textbox.bind("<Control-z>", lambda event: self.textbox.edit_undo())
        self.textbox.bind("<Control-a>", self.select_all)

    def append(self, s):
        """追加文本内容"""
        self.textbox.delete(1.0, "end")
        self.textbox.insert("end", s)

    def clear(self):
        """清空文本内容"""
        self.textbox.delete(1.0, "end")

    def get_content(self):
        """获取文本内容"""
        return self.textbox.get(1.0, "end-1c")

    def select_all(self, event):
        """全选文本"""
        self.textbox.tag_add("sel", "1.0", "end")
        return "break"


# --- 子界面1: Screen1_MCMAA ---
class Screen1_MCMAA(ttk.Frame):
    """MCM论文辅助初始界面"""

    def __init__(self, master):
        super().__init__(master)
        self.paned_window = ttk.PanedWindow(self, orient="horizontal")
        self.paned_window.pack(fill="both", expand=True)
        self.left_frame = ttk.Frame(self.paned_window, **MAIN_FRAME_CONFIG)
        self.right_frame = ttk.Frame(self.paned_window, **MAIN_FRAME_CONFIG)
        self.paned_window.add(self.left_frame, weight=1)
        self.paned_window.add(self.right_frame, weight=3)
        self.arrangeLeft()
        self.arrangeRight()

    def arrangeLeft(self):
        """左侧布局：模式切换下拉菜单"""
        tmp = ttk.Frame(self.left_frame, **FLAT_SUBFRAME_CONFIG)
        tmp.pack(fill="x")
        self.button_mode = ttk.OptionMenu(
            tmp,
            DATA_CONFIG["mode"],
            "MCM论文辅助",
            "MCM论文辅助",
            "LaTeX提取器",
            "Text替换器",
            command=lambda *args: None,
        )
        self.button_mode.pack(fill="x")

    def arrangeRight(self):
        """右侧布局：显示欢迎信息"""
        self.text_frame = TextWidget(self.right_frame, **MAIN_FRAME_CONFIG)
        self.text_frame.pack(fill="both", expand=True)
        self.text_frame.append("欢迎使用数学建模论文写作辅助软件 MCM Aid Assistant v1.0.0！\n")


# --- 子界面2: Screen2_LaTeX_Extractor ---
class Screen2_LaTeX_Extractor(ttk.Frame):
    """LaTeX提取器界面"""

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(self.left_paned, weight=30)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=70)
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.button_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.button_frame, weight=1)
        self.info_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.info_frame, weight=2)
        self.keyword_var = StringVar(value="问题编号")
        self.section_var = StringVar(value="选择章节")
        self.arrangeLeft()
        self.add_text_box(15)
        self.add_info_label()

    def arrangeLeft(self):
        """左侧布局：按钮和下拉菜单"""
        button_height = 50
        total_buttons = 7
        total_height = total_buttons * button_height
        self.button_frame.config(height=total_height)
        tmp0 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp0.place(relx=0, y=0, relwidth=1, height=button_height)
        self.button_mode = ttk.OptionMenu(
            tmp0,
            DATA_CONFIG["mode"],
            "LaTeX提取器",
            "MCM论文辅助",
            "LaTeX提取器",
            "Text替换器",
            command=lambda *args: None,
        )
        self.button_mode.place(relx=0, rely=0, relwidth=1, height=button_height)
        tmp1 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp1.place(relx=0, y=button_height, relwidth=1, height=button_height)
        self.button_open = ttk.Button(tmp1, text="选择文件", command=lambda: None)
        self.button_open.place(relx=0, rely=0, relwidth=1, height=button_height)
        tmp2 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp2.place(relx=0, y=2 * button_height, relwidth=1, height=button_height)
        self.button_keyword = ttk.OptionMenu(tmp2, self.keyword_var, "问题编号", "问题编号")
        self.button_keyword.place(relx=0, rely=0, relwidth=1, height=button_height)
        tmp4 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp4.place(relx=0, y=3 * button_height, relwidth=1, height=button_height)
        self.button_section = ttk.OptionMenu(tmp4, self.section_var, "选择章节", "选择章节")
        self.button_section.place(relx=0, rely=0, relwidth=1, height=button_height)
        tmp3 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp3.place(relx=0, y=4 * button_height, relwidth=1, height=button_height)
        self.button_save_problem = ttk.Button(tmp3, text="问题提取并保存", command=lambda: None)
        self.button_save_problem.place(relx=0, rely=0, relwidth=1, height=button_height)
        tmp6 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp6.place(relx=0, y=5 * button_height, relwidth=1, height=button_height)
        self.button_save_section = ttk.Button(tmp6, text="章节提取并保存", command=lambda: None)
        self.button_save_section.place(relx=0, rely=0, relwidth=1, height=button_height)

    def add_text_box(self, weight):
        """右侧布局：文本预览框"""
        self.text_preview = TextWidget(self.right_paned, **MAIN_FRAME_CONFIG)
        self.right_paned.add(self.text_preview, weight=weight)
        self.text_preview.append("欢迎来到MAT数学建模论文辅助写作软件。\n")

    def add_info_label(self):
        """底部布局：信息显示框"""
        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.info_text.config(
            font=("Arial", 10),
            bg=self.text_preview.textbox.cget("bg"),
            fg=self.text_preview.textbox.cget("fg"),
            relief="flat",
        )


# --- 子界面3: Screen3_Text_Replacer ---
class Screen3_Text_Replacer(ttk.Frame):
    """文本替换器界面"""

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.master = master
        self.selected_pair_index = StringVar(value="选择标记对")
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(self.left_paned, weight=30)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=70)
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.button_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.input_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.info_frame = ttk.Frame(self.left_paned, **MAIN_FRAME_CONFIG)
        self.left_paned.add(self.button_frame, weight=1)
        self.left_paned.add(self.input_frame, weight=2)
        self.left_paned.add(self.info_frame, weight=1)
        self.arrange_left()
        self.arrange_input()
        self.add_right_paned()
        self.add_info_label()

    def arrange_left(self):
        """左侧布局：按钮和下拉菜单"""
        tmp0 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp0.place(relx=0, rely=0, relwidth=1, height=50)
        self.button_mode = ttk.OptionMenu(
            tmp0,
            DATA_CONFIG["mode"],
            "Text替换器",
            "MCM论文辅助",
            "LaTeX提取器",
            "Text替换器",
            command=lambda *args: None,
        )
        self.button_mode.place(relx=0, rely=0, relwidth=1, relheight=1)
        tmp1 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp1.place(relx=0, rely=0.2, relwidth=1, height=50)
        self.button_open = ttk.Button(tmp1, text="打开文件", command=lambda: None)
        self.button_open.place(relx=0, rely=0, relwidth=1, relheight=1)
        tmp2 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp2.place(relx=0, rely=0.4, relwidth=1, height=50)
        self.pair_menu = ttk.OptionMenu(tmp2, self.selected_pair_index, "选择标记对")
        self.pair_menu.place(relx=0, rely=0, relwidth=1, relheight=1)
        tmp4 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp4.place(relx=0, rely=0.6, relwidth=1, height=50)
        self.button_replace = ttk.Button(tmp4, text="执行替换", command=lambda: None)
        self.button_replace.place(relx=0, rely=0, relwidth=1, relheight=1)
        tmp5 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp5.place(relx=0, rely=0.8, relwidth=1, height=50)
        self.button_save = ttk.Button(tmp5, text="保存文件", command=lambda: None)
        self.button_save.place(relx=0, rely=0, relwidth=1, relheight=1)

    def arrange_input(self):
        """中间布局：替换输入框"""
        self.replace_input_label = ttk.Label(self.input_frame, text="输入替换内容:")
        self.replace_input_label.place(relx=0, rely=0, relwidth=1, height=20)
        self.replace_input = ScrolledText(self.input_frame, height=5)
        self.replace_input.place(relx=0, rely=0.1, relwidth=1, relheight=0.9)
        self.replace_input.bind("<Control-a>", self.select_all)

    def add_right_paned(self):
        """右侧布局：文本显示区域"""
        self.notebook = ttk.Notebook(self.right_paned)
        self.right_paned.add(self.notebook, weight=7)
        self.original_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.original_tab, text="原始文本")
        self.replaced_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.replaced_tab, text="替换后文本")
        self.original_textbox = ScrolledText(self.original_tab, wrap="word")
        self.original_textbox.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.replaced_textbox = ScrolledText(self.replaced_tab, wrap="word")
        self.replaced_textbox.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.original_textbox.bind("<Control-a>", self.select_all)
        self.replaced_textbox.bind("<Control-a>", self.select_all)

    def add_info_label(self):
        """底部布局：信息显示框"""
        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.info_text.config(
            font=("Arial", 10),
            bg=self.original_textbox.cget("bg"),
            fg=self.original_textbox.cget("fg"),
            relief="flat",
        )

    def select_all(self, event):
        """全选文本"""
        widget = event.widget
        if isinstance(widget, ScrolledText):
            widget.tag_add("sel", "1.0", "end")
            return "break"
        return None


# --- 主界面管理: Screen ---
class Screen(ttk.Frame):
    """主界面管理类，负责子界面切换"""

    def __init__(self):
        super().__init__(DATA_CONFIG["window"], **SCREEN_CONFIG)
        DATA_CONFIG["screen"] = self
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frames = {
            "MCM论文辅助": Screen1_MCMAA(self),
            "LaTeX提取器": Screen2_LaTeX_Extractor(self),
            "Text替换器": Screen3_Text_Replacer(self),
        }
        self.current_frame = self.frames["MCM论文辅助"]
        self.current_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        for frame_name, frame in self.frames.items():
            if frame != self.current_frame:
                frame.place_forget()
        DATA_CONFIG["mode"].set("MCM论文辅助")

    def change_mode(self, *args):
        """切换子界面"""
        new_mode = DATA_CONFIG["mode"].get()
        self.current_frame.place_forget()
        self.current_frame = self.frames[new_mode]
        self.current_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        DATA_CONFIG["screen"] = self.current_frame


# --- 应用主体: App ---
class App:
    """应用主体类，设置窗口并启动程序"""

    def __init__(self, py_path=os.path.dirname(os.path.abspath(__file__))):
        DATA_CONFIG["app"] = self
        DATA_CONFIG["py_path"] = py_path
        DATA_CONFIG["window"] = ttk.Window(
            themename="sandstone",
            title="数学建模论文写作辅助软件 MCM Aid Assistant v1.0.0",
        )
        # Create StringVar after the root window exists
        DATA_CONFIG["mode"] = StringVar(master=DATA_CONFIG["window"])

        min_height = 960
        min_width = int(min_height * 4 / 3)
        DATA_CONFIG["window"].minsize(min_width, min_height)
        DATA_CONFIG["window"].geometry(f"{min_width}x{min_height}")
        DATA_CONFIG["screen"] = Screen()
        DATA_CONFIG["window"].mainloop()


# --- 主程序入口 ---
if __name__ == "__main__":
    App()
