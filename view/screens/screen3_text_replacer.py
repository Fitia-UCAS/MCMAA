# %% view/screens/screen3_text_replacer.py

from tkinter import StringVar
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
import re
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from model.text_replacer import find_marker_pairs, replace_contents
from ..config import DATA_CONFIG, SCREEN_CONFIG, MAIN_FRAME_CONFIG, FLAT_SUBFRAME_CONFIG


class Screen3_Text_Replacer(ttk.Frame):

    MODE_NAME = "Text替换器"

    def __init__(self, master):
        super().__init__(master, **SCREEN_CONFIG)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.master = master
        self.current_file = None
        self.original_text = ""
        self.replaced_text = ""
        self.marker_pairs = []
        self.replacements = {}
        self.selected_pair_index = StringVar(value="选择标记对")

        # Main layout
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.left_paned = ttk.PanedWindow(main_paned, orient="vertical")
        main_paned.add(self.left_paned, weight=30)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=70)
        self.right_paned = ttk.PanedWindow(right_frame, orient="vertical")
        self.right_paned.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Left subframes
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

        # Bind events
        self.selected_pair_index.trace_add("write", self.on_pair_select)

    def arrange_left(self):
        """Arrange left button controls"""
        # Mode selection
        tmp0 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp0.place(relx=0, rely=0, relwidth=1, height=50)
        self.button_mode = ttk.OptionMenu(tmp0, DATA_CONFIG["mode"], "", command=self.master.change_mode)
        self.button_mode.set_menu(self.MODE_NAME, *DATA_CONFIG["modes"])
        self.button_mode.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Open file
        tmp1 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp1.place(relx=0, rely=0.2, relwidth=1, height=50)
        self.button_open = ttk.Button(tmp1, text="打开文件", command=self.select_file)
        self.button_open.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Marker pair selection
        tmp2 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp2.place(relx=0, rely=0.4, relwidth=1, height=50)
        self.pair_menu = ttk.OptionMenu(tmp2, self.selected_pair_index, "选择标记对")
        self.pair_menu.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Replace button
        tmp4 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp4.place(relx=0, rely=0.6, relwidth=1, height=50)
        self.button_replace = ttk.Button(tmp4, text="执行替换", command=self.replace_text)
        self.button_replace.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Save file
        tmp5 = ttk.Frame(self.button_frame, **FLAT_SUBFRAME_CONFIG)
        tmp5.place(relx=0, rely=0.8, relwidth=1, height=50)
        self.button_save = ttk.Button(tmp5, text="保存文件", command=self.save_file)
        self.button_save.place(relx=0, rely=0, relwidth=1, relheight=1)

    def arrange_input(self):
        """Arrange replacement input area"""
        self.replace_input_label = ttk.Label(self.input_frame, text="输入替换内容:")
        self.replace_input_label.place(relx=0, rely=0, relwidth=1, height=20)
        self.replace_input = ScrolledText(self.input_frame, height=5)
        self.replace_input.place(relx=0, rely=0.1, relwidth=1, relheight=0.9)
        self.replace_input.bind("<Control-a>", self.select_all)
        self.replace_input.bind("<Control-s>", lambda event: self.replace_text())

    def add_right_paned(self):
        """Add right text display area with notebook"""
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
        """Add info display area"""
        self.info_text = ScrolledText(self.info_frame, wrap="word", state="disabled")
        self.info_text.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.info_text.config(
            font=("Arial", 10),
            bg=self.original_textbox.cget("bg"),
            fg=self.original_textbox.cget("fg"),
            relief="flat",
        )

    def select_all(self, event):
        """Custom select all functionality"""
        widget = event.widget
        if isinstance(widget, ScrolledText):
            widget.tag_add("sel", "1.0", "end")
            return "break"
        return None

    def info_text_append(self, text):
        """Append text to info box"""
        self.info_text.config(state="normal")
        self.info_text.insert("end", text + "\n")
        self.info_text.config(state="disabled")
        self.info_text.see("end")

    def select_file(self):
        """Open and load file"""
        file_path = filedialog.askopenfilename(
            title="打开文件",
            filetypes=[
                ("LaTeX 文件", "*.tex"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    self.original_text = file.read()
                self.original_textbox.delete(1.0, "end")
                self.original_textbox.insert("end", self.original_text)
                self.current_file = file_path
                self.refresh_pairs()
            except Exception as e:
                self.info_text_append(f"文件操作失败: {str(e)}")
                messagebox.showerror("错误", f"打开文件失败: {e}")

    def refresh_pairs(self):
        """Refresh marker pair list"""
        self.marker_pairs = find_marker_pairs(self.original_text)
        pair_display = ["选择标记对"]
        for pair in self.marker_pairs:
            marker_type = pair["marker_type"]
            match = re.search(r"<-----(.*?)----->", marker_type)
            display_text = match.group(1).strip() if match else marker_type
            pair_display.append(display_text)
        self.pair_menu.set_menu(*pair_display)
        (
            self.info_text_append(f"文件已加载，找到 {len(self.marker_pairs)} 个标记对")
            if self.marker_pairs
            else self.info_text_append("文件已加载，未找到标记对")
        )

    def on_pair_select(self, *args):
        """Handle marker pair selection"""
        selected_display = self.selected_pair_index.get()
        if selected_display == "选择标记对":
            self.replace_input.delete(1.0, "end")
            return
        for pair in self.marker_pairs:
            marker_type = pair["marker_type"]
            match = re.search(r"<-----(.*?)----->", marker_type)
            if match and match.group(1).strip() == selected_display:
                self.replace_input.delete(1.0, "end")
                if pair["index"] in self.replacements:
                    self.replace_input.insert("end", self.replacements[pair["index"]])
                else:
                    self.replace_input.insert("end", pair["content"])
                break

    def replace_text(self):
        """Perform text replacement"""
        selected_display = self.selected_pair_index.get()
        if selected_display == "选择标记对":
            self.info_text_append("请先选择一个标记对")
            return
        try:
            for pair in self.marker_pairs:
                marker_type = pair["marker_type"]
                match = re.search(r"<-----(.*?)----->", marker_type)
                if match and match.group(1).strip() == selected_display:
                    index = pair["index"]
                    break
            else:
                self.info_text_append("未找到匹配的标记对")
                return
            new_content = self.replace_input.get(1.0, "end-1c")
            self.replacements[index] = new_content
            self.replaced_text = replace_contents(self.original_text, self.replacements)
            self.replaced_textbox.delete(1.0, "end")
            self.replaced_textbox.insert("end", self.replaced_text)
            self.info_text_append(f"已替换标记对: {selected_display}")
        except Exception as e:
            self.info_text_append(f"替换失败: {str(e)}")
            messagebox.showerror("错误", f"替换失败: {str(e)}")

    def save_file(self):
        """Save replaced text"""
        if not self.replaced_text:
            self.info_text_append("没有替换后的文本可保存")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("LaTeX 文件", "*.tex"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
            title="保存文件",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(self.replaced_text)
                self.info_text_append(f"内容已保存到 {file_path}")
                messagebox.showinfo("成功", f"内容已保存到 {file_path}")
            except Exception as e:
                self.info_text_append(f"保存失败: {str(e)}")
                messagebox.showerror("错误", f"保存失败: {str(e)}")
