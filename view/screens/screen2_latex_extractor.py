# %% view/screens/screen2_latex_extractor.py

from tkinter import *
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import os
import tkinter.filedialog as filedialog

from ..common_widgets import (
    TextWidget,
)
from ..config import (
    DATA_CONFIG,
    SCREEN_CONFIG,
    MAIN_FRAME_CONFIG,
    FLAT_SUBFRAME_CONFIG,
)
from model.latex_extractor import LatexExtractor


class Screen2_LaTeX_Extractor(ttk.Frame):
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
        self.current_start_line = None
        self.current_end_line = None

        self.arrangeLeft()
        self.add_text_box(15)
        self.add_info_label()

    def arrangeLeft(self):
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
            command=self.master.change_mode,
        )
        self.button_mode.place(relx=0, rely=0, relwidth=1, height=button_height)

        tmp1 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp1.place(relx=0, y=button_height, relwidth=1, height=button_height)
        self.button_open = ttk.Button(tmp1, text="选择文件", command=self.select_file)
        self.button_open.place(relx=0, rely=0, relwidth=1, height=button_height)

        tmp2 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp2.place(relx=0, y=2 * button_height, relwidth=1, height=button_height)
        self.button_keyword = ttk.OptionMenu(
            tmp2, self.keyword_var, "问题编号", "问题编号"
        )
        self.button_keyword.place(relx=0, rely=0, relwidth=1, height=button_height)
        self.keyword_var.trace_add(
            "write", lambda *args: self.update_preview(self.keyword_var.get())
        )

        tmp4 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp4.place(relx=0, y=3 * button_height, relwidth=1, height=button_height)
        self.button_section = ttk.OptionMenu(
            tmp4, self.section_var, "选择章节", "选择章节"
        )
        self.button_section.place(relx=0, rely=0, relwidth=1, height=button_height)
        self.section_var.trace_add(
            "write", lambda *args: self.update_section_preview(self.section_var.get())
        )

        tmp3 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp3.place(relx=0, y=4 * button_height, relwidth=1, height=button_height)
        self.button_save_problem = ttk.Button(
            tmp3, text="问题提取并保存", command=self.extract_and_save_problem
        )
        self.button_save_problem.place(relx=0, rely=0, relwidth=1, height=button_height)

        tmp6 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp6.place(relx=0, y=5 * button_height, relwidth=1, height=button_height)
        self.button_save_section = ttk.Button(
            tmp6, text="章节提取并保存", command=self.extract_and_save_section
        )
        self.button_save_section.place(relx=0, rely=0, relwidth=1, height=button_height)

    def add_text_box(self, weight):
        self.text_preview = TextWidget(self.right_paned, **MAIN_FRAME_CONFIG)
        self.right_paned.add(self.text_preview, weight=weight)
        self.text_preview.append("欢迎来到MAT数学建模论文辅助写作软件。\n")

    def add_info_label(self):
        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.info_text.config(
            font=("Arial", 10),
            bg=self.text_preview.textbox.cget("bg"),
            fg=self.text_preview.textbox.cget("fg"),
            relief="flat",
        )

    def info_text_append(self, text):
        self.info_text.config(state="normal")
        self.info_text.insert("end", text + "\n")
        self.info_text.config(state="disabled")
        self.info_text.see("end")

    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 LaTeX 文件",
            filetypes=[
                ("LaTeX files", "*.tex"),
                ("LaTeX Template files", "*.template"),
                ("All files", "*.*"),
            ],
        )
        if file_path:
            if not (
                file_path.lower().endswith(".tex")
                or file_path.lower().endswith(".template")
            ):
                self.info_text_append("警告: 请选择 .tex 或 .template 文件")
                return
            self.file_path = file_path
            try:
                self.update_extractor()
            except Exception as e:
                self.info_text_append(f"文件操作失败: {str(e)}")

    def update_extractor(self):
        try:
            self.extractor = LatexExtractor(self.file_path, max_level=3)
            self.keywords = self.extractor.get_unique_keywords()
            self.button_keyword.set_menu("问题编号", *self.keywords)
            self.section_titles = [
                title for _, title, level, _ in self.extractor.sections if level == 1
            ]
            self.button_section.set_menu("选择章节", *self.section_titles)
            self.info_text_append(f"文件已加载: {self.file_path}")
        except Exception as e:
            self.info_text_append(f"错误: {str(e)}")

    def update_preview(self, keyword):
        if keyword == "问题编号":
            self.text_preview.clear()
            self.text_preview.append("请选择一个问题编号以查看预览。\n")
            return
        parts = self.extractor.extract_problem_parts(keyword)
        abstract_parts = self.extractor.extract_abstract_parts(keyword)
        if not parts or not abstract_parts:
            self.info_text_append("错误: 未找到相关章节")
            return
        all_content = []

        # 摘要部分
        all_content.extend(abstract_parts)

        # 问题重述部分
        if "Restatement" in parts:
            all_content.extend(parts["Restatement"])

        # 问题分析部分
        if "Analysis" in parts:
            all_content.extend(parts["Analysis"])

        # 模型建立与求解部分
        if "Modeling" in parts:
            all_content.extend(parts["Modeling"])

        self.text_preview.clear()
        self.text_preview.append("\n".join(all_content))
        self.info_text_append("预览已更新")

    def extract_and_save_problem(self):
        keyword = self.keyword_var.get()
        if keyword == "问题编号":
            self.info_text_append("错误: 请选择一个问题编号")
            return
        parts = self.extractor.extract_problem_parts(keyword)
        abstract_parts = self.extractor.extract_abstract_parts(keyword)
        if not parts or not abstract_parts:
            self.info_text_append("错误: 未找到相关章节")
            return
        all_content = []

        # 摘要部分
        all_content.extend(abstract_parts)

        # 问题重述部分
        if "Restatement" in parts:
            all_content.extend(parts["Restatement"])

        # 问题分析部分
        if "Analysis" in parts:
            all_content.extend(parts["Analysis"])

        # 模型建立与求解部分
        if "Modeling" in parts:
            all_content.extend(parts["Modeling"])

        output_file = os.path.join(
            os.path.dirname(self.file_path), f"问题{keyword}.tex"
        )
        try:
            self.extractor.save_to_file(all_content, output_file)
            self.info_text_append(f"成功: 内容已保存到 {output_file}")
        except Exception as e:
            self.info_text_append(f"错误: {str(e)}")

    def update_section_preview(self, section):
        if section == "选择章节":
            return
        content = self.extractor.extract_section(section)
        if not content:
            self.info_text_append("错误: 未找到相关章节")
            return
        self.text_preview.clear()
        self.text_preview.append("\n".join(content))
        self.info_text_append("预览已更新")

    def extract_and_save_section(self):
        section = self.section_var.get()
        if section == "选择章节":
            self.info_text_append("错误: 请选择一个章节")
            return
        content = self.extractor.extract_section(section)
        if not content:
            self.info_text_append("错误: 未找到相关章节")
            return
        all_content = [f"\\section{{{section}}}"] + content
        output_file = os.path.join(os.path.dirname(self.file_path), f"{section}.tex")
        try:
            self.extractor.save_to_file(all_content, output_file)
            self.info_text_append(f"成功: 章节已保存到 {output_file}")
        except Exception as e:
            self.info_text_append(f"错误: {str(e)}")
