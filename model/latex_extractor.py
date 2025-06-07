import re


class LatexExtractor:
    def __init__(self, file_path, max_level=4):
        """Initialize LaTeX extractor with file path and maximum section level"""
        self.file_path = file_path
        self.max_level = max_level
        with open(self.file_path, "r", encoding="utf-8") as file:
            self.content = file.read().splitlines()
        self.sections = self.extract_sections()

    def extract_sections(self):
        """Extract all sections including type, title, level, and line number"""
        sections = []
        section_types = {
            "section": 1,
            "subsection": 2,
            "subsubsection": 3,
            "numtitle": 4,
            "circtitle": 4,
            "dingtitle": 4,
            "squatitle": 4,
        }
        pattern = r"\\(section|subsection|subsubsection|numtitle|circtitle|dingtitle|squatitle)(\[\])?\{([^\}]*)\}"
        for i, line in enumerate(self.content):
            match = re.match(pattern, line.strip())
            if match:
                section_type = match.group(1)
                title = match.group(3).strip()
                level = section_types[section_type]
                if level <= self.max_level:
                    sections.append((section_type, title, level, i))
        return sections

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
        """Extract content from start line to next section of same or higher level"""
        end_line = len(self.content)
        for _, _, level, line_num in self.sections:
            if line_num > start_line and level <= start_level:
                end_line = line_num
                break
        return self.content[start_line:end_line]

    def get_unique_keywords(self):
        """Extract unique problem numbers from Problem Restatement section"""
        keywords = set()
        restate_section = self.find_section(r"问题重述")
        if restate_section:
            _, _, level, line_num = restate_section
            content = self.extract_content(line_num, level)
            pattern = r"\\textbf\{问题([一二三四五六七八九十]+)：\}"
            for line in content:
                match = re.search(pattern, line)
                if match:
                    keywords.add(match.group(1))
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
        """Extract abstract parts: introduction, specific problem, and summary"""
        abstract_content = []
        intro_lines = []
        problem_lines = []
        summary_lines = []
        in_abstract = False
        target_found = False

        with open(self.file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
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

        return (
            abstract_content[:1]
            + intro_lines
            + problem_lines
            + summary_lines
            + abstract_content[-1:]
        )

    def extract_problem_parts(self, problem_num):
        """Extract problem restatement, analysis, and modeling parts"""
        parts = {}

        # Extract Problem Restatement
        restate_section = self.find_section(r"问题重述")
        if restate_section:
            _, _, level, line_num = restate_section
            content = self.extract_content(line_num, level)
            restate_lines = [f"\\section{{问题重述}}"]
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
            parts["Analysis"] = [
                f"\\section{{问题分析}}",
                f"\\{section_type}{{{title}}}",
            ] + self.extract_content(line_num + 1, level)

        # Extract Modeling and Solution
        modeling_pattern = f"问题{problem_num}模型的建立与求解"
        modeling_section = self.find_section(modeling_pattern)
        if modeling_section:
            section_type, title, level, line_num = modeling_section
            parts["Modeling"] = [
                f"\\section{{模型建立与求解}}",
                f"\\{section_type}{{{title}}}",
            ] + self.extract_content(line_num + 1, level)

        return parts

    def extract_section(self, section_title):
        """Extract complete content of a specified top-level section"""
        for section_type, title, level, line_num in self.sections:
            if title == section_title and level == 1:
                return self.extract_content(line_num, level)
        return []

    def save_to_file(self, content, output_file):
        """Save content to file"""
        try:
            with open(output_file, "w", encoding="utf-8") as file:
                file.writelines(line + "\n" for line in content)
        except Exception as e:
            raise IOError(f"无法保存文件: {e}")
