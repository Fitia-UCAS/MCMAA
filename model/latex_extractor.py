# -*- coding: utf-8 -*-
# model/latex_extractor.py

import re


class LatexExtractor:
    def __init__(self, file_path, max_level=4):
        """Initialize LaTeX extractor with file path and maximum section level"""
        self.file_path = file_path
        self.max_level = max_level
        with open(self.file_path, "r", encoding="utf-8") as file:
            self.content = file.read().splitlines()

        # 先识别 codeblock 区间，供后续解析时跳过
        self.codeblocks = self._extract_codeblocks()
        # 便于快速判断某一行是否在 codeblock 内
        self._codeblock_ranges = [(cb["start"], cb["end"]) for cb in self.codeblocks]
        # 起始行 -> 结束行 的映射（仅对 codeblock 有值）
        self._codeblock_end_by_start = {cb["start"]: cb["end"] for cb in self.codeblocks}

        # 再解析章节（会忽略 codeblock 里的 section 等）
        self.sections = self.extract_sections()

    # ---------- 基础工具 ----------

    def _in_codeblock(self, idx):
        """当前行号是否位于任意 codeblock 内"""
        for s, e in self._codeblock_ranges:
            if s <= idx <= e:
                return True
        return False

    def _strip_codeblocks(self, lines):
        """给定若干行文本，去掉 codeblock 区域内的行"""
        out = []
        in_block = False
        for line in lines:
            if (not in_block) and re.search(r"\\begin\{codeblock\}", line):
                in_block = True
                continue
            if in_block and re.search(r"\\end\{codeblock\}", line):
                in_block = False
                continue
            if not in_block:
                out.append(line)
        return out

    # ---------- 代码块解析 ----------

    def _extract_codeblocks(self):
        r"""
        识别 \begin{codeblock}[可选label]{lang} ... \end{codeblock}
        返回列表：[{index, start, end, label, lang, title}]
        其中 title 用于大纲显示，例如：'codeblock 1 [LaTeX代码]{TeX}'
        """
        blocks = []
        in_block = False
        start = -1
        label = ""
        lang = ""
        idx = 0
        counter = 0

        begin_pat = re.compile(r"\\begin\{codeblock\}(?:\[(?P<label>.*?)\])?(?:\{(?P<lang>.*?)\})?")
        end_pat = re.compile(r"\\end\{codeblock\}")

        while idx < len(self.content):
            line = self.content[idx]
            if not in_block:
                m = begin_pat.search(line)
                if m:
                    in_block = True
                    start = idx
                    label = (m.group("label") or "").strip()
                    lang = (m.group("lang") or "").strip()
            else:
                if end_pat.search(line):
                    counter += 1
                    end = idx
                    if label and lang:
                        title = f"codeblock {counter} [{label}]{{{lang}}}"
                    elif label:
                        title = f"codeblock {counter} [{label}]"
                    elif lang:
                        title = f"codeblock {counter} {{{lang}}}"
                    else:
                        title = f"codeblock {counter}"
                    blocks.append(
                        {
                            "index": counter,
                            "start": start,
                            "end": end,
                            "label": label,
                            "lang": lang,
                            "title": title,
                        }
                    )
                    in_block = False
                    start = -1
                    label = ""
                    lang = ""
            idx += 1
        return blocks

    # ---------- 章节解析（忽略 codeblock 内部） ----------

    def extract_sections(self):
        """Extract all sections including type, title, level, and line number"""
        sections = []

        # 先把每个 codeblock 当作一个虚拟 section（level=4）
        for cb in self.codeblocks:
            sections.append(("codeblock", cb["title"], 4, cb["start"]))

        section_types = {
            "section": 1,
            "subsection": 2,
            "subsubsection": 3,
            "numtitle": 4,
            "circtitle": 4,
            "dingtitle": 4,
            "squatitle": 4,
        }
        pattern = re.compile(
            r"\\(section|subsection|subsubsection|numtitle|circtitle|dingtitle|squatitle)(\[\])?\{([^\}]*)\}"
        )

        for i, raw in enumerate(self.content):
            # 跳过 codeblock 内部的任何 \section 等
            if self._in_codeblock(i):
                continue
            line = raw.strip()
            m = pattern.match(line)
            if m:
                section_type = m.group(1)
                title = m.group(3).strip()
                level = section_types[section_type]
                if level <= self.max_level:
                    sections.append((section_type, title, level, i))

        # 维持出现顺序（按照行号排序）
        sections.sort(key=lambda x: x[3])
        return sections

    # ---------- 搜索/提取 ----------

    def find_section(self, pattern):
        """Find section matching the given pattern"""
        for section in self.sections:
            if re.search(pattern, section[1]):
                return section
        return None

    def find_section_startswith(self, pattern):
        """Find section starting with the given pattern"""
        for section_type, title, level, line_num in self.sections:
            if re.match(pattern, title):
                return section_type, title, level, line_num
        return None

    def extract_content(self, start_line, start_level):
        r"""
        Extract content from start line to:
        - next section of same or higher level; or
        - if it's a codeblock item, to its \end{codeblock}
        """
        # 若这是一个 codeblock 节点，直接提取到结束
        if start_line in self._codeblock_end_by_start:
            end_line = self._codeblock_end_by_start[start_line]
            return self.content[start_line : end_line + 1]

        end_line = len(self.content)
        for _, _, level, line_num in self.sections:
            if line_num > start_line and level <= start_level:
                end_line = line_num
                break
        return self.content[start_line:end_line]

    # ---------- 业务相关：问题编号 / 摘要 / 各部分 ----------

    def get_unique_keywords(self):
        """Extract unique problem numbers from Problem Restatement section (skip codeblocks)"""
        keywords = set()
        restate_section = self.find_section(r"问题重述")
        if restate_section:
            _, _, level, line_num = restate_section
            content = self.extract_content(line_num, level)
            # 跳过 codeblock 的内容
            content = self._strip_codeblocks(content)
            pattern = re.compile(r"\\textbf\{问题([一二三四五六七八九十]+)：\}")
            for line in content:
                m = pattern.search(line)
                if m:
                    keywords.add(m.group(1))
        return sorted(list(keywords), key=self.chinese_to_number)

    def chinese_to_number(self, chinese):
        """Convert Chinese numerals to Arabic numbers for sorting"""
        num_dict = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        return num_dict.get(chinese, 0)

    def extract_abstract_parts(self, problem_num):
        """Extract abstract parts: introduction, specific problem, and summary (skip codeblocks)"""
        abstract_content = []
        intro_lines = []
        problem_lines = []
        summary_lines = []
        in_abstract = False
        target_found = False
        in_codeblock = False

        with open(self.file_path, "r", encoding="utf-8") as file:
            for raw in file:
                line = raw.strip()

                # codeblock 屏蔽
                if not in_codeblock and r"\begin{codeblock}" in line:
                    in_codeblock = True
                    continue
                if in_codeblock and r"\end{codeblock}" in line:
                    in_codeblock = False
                    continue
                if in_codeblock:
                    continue

                if r"\begin{abstract}" in line:
                    abstract_content.append(line)
                    in_abstract = True
                elif r"\end{abstract}" in line:
                    abstract_content.append(line)
                    in_abstract = False
                    break
                elif in_abstract:
                    if r"\textbf{针对问题" in line:
                        problem = re.search(r"\\textbf\{针对问题([一二三四五六七八九十]+)\}", line)
                        if problem and problem.group(1) == problem_num:
                            problem_lines.append(line)
                            target_found = True
                        elif target_found:
                            target_found = False
                    elif r"\keywords" in line:
                        summary_lines.append(line)
                        target_found = False
                    elif not problem_lines and not summary_lines:
                        intro_lines.append(line)
                    elif target_found:
                        problem_lines.append(line)
                    elif problem_lines and not target_found:
                        summary_lines.append(line)

        return abstract_content[:1] + intro_lines + problem_lines + summary_lines + abstract_content[-1:]

    def extract_problem_parts(self, problem_num):
        """Extract problem restatement, analysis, and modeling parts (skip codeblocks when scanning)"""
        parts = {}

        # Extract Problem Restatement
        restate_section = self.find_section(r"问题重述")
        if restate_section:
            _, _, level, line_num = restate_section
            content = self.extract_content(line_num, level)
            content = self._strip_codeblocks(content)
            restate_lines = [r"\section{问题重述}"]
            in_background = False
            in_restate = False
            in_target_problem = False

            for line in content:
                if r"\subsection{问题背景}" in line:
                    restate_lines.append(line)
                    in_background = True
                    in_restate = False
                elif r"\subsection{问题重述}" in line:
                    restate_lines.append(line)
                    in_background = False
                    in_restate = True
                elif f"\\textbf{{问题{problem_num}：}}" in line:
                    restate_lines.append(line)
                    in_target_problem = True
                    in_background = False
                    in_restate = False
                elif r"\textbf{问题" in line and in_target_problem:
                    in_target_problem = False
                elif in_background or in_restate or in_target_problem:
                    restate_lines.append(line)

            parts["Restatement"] = restate_lines

        # Extract Problem Analysis
        analysis_pattern = f"问题{problem_num}的分析"
        analysis_section = self.find_section(analysis_pattern)
        if analysis_section:
            section_type, title, level, line_num = analysis_section
            # 直接用章节边界提取，内部若含 codeblock 也原样返回（编辑预览更真实）
            parts["Analysis"] = [
                r"\section{问题分析}",
                f"\\{section_type}{{{title}}}",
            ] + self.extract_content(line_num + 1, level)

        # Extract Modeling and Solution
        modeling_pattern = f"问题{problem_num}模型的建立与求解"
        modeling_section = self.find_section(modeling_pattern)
        if modeling_section:
            section_type, title, level, line_num = modeling_section
            parts["Modeling"] = [
                r"\section{模型建立与求解}",
                f"\\{section_type}{{{title}}}",
            ] + self.extract_content(line_num + 1, level)

        return parts

    def extract_section(self, section_title):
        """Extract complete content of a specified top-level section"""
        for section_type, title, level, line_num in self.sections:
            if title == section_title and level == 1:
                return self.extract_content(line_num, level)
        return []

    # ---------- 保存 ----------

    def save_to_file(self, content, output_file):
        """Save content to file"""
        try:
            with open(output_file, "w", encoding="utf-8") as file:
                file.writelines(line + "\n" for line in content)
        except Exception as e:
            raise IOError(f"无法保存文件: {e}")
