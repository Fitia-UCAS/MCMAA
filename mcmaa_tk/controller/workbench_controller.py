# %% controller/workbench_controller.py
# -*- coding: utf-8 -*-

"""
AgentBridge — 将 MathModelAgentClient 接入到 WorkbenchController 的最小适配层
================================================================================
使用方式
--------
1) 将本文件保存为：controller/agent_bridge.py
2) 修改 controller/workbench_controller.py：
   - 增加导入：
       from controller.agent_bridge import AgentBridge
   - 让 WorkbenchController 继承该混入：
       class WorkbenchController(AgentBridge):
           def __init__(self):
               AgentBridge.__init__(self)
               ... 原有初始化 ...
3) 在 View 层注册回调（示例）——比如在 Screen_Workbench.__init__ 里：
       ctrl.set_agent_handlers(
           on_status=lambda s: self._show_status(s),
           on_message=lambda m: self._append_console(m),
           on_error=lambda e: self._show_error(e),
       )
4) 连接与发送：
       ctrl.agent_connect(url, token="xxx")
       ctrl.agent_send_json({"type":"ping"})
       resp = ctrl.agent_request({"type":"infer","payload":{"text":"hello"}}, timeout=15)

备注
----
- 采用后台线程 + 回调通知；回调均在接收线程里触发，如需切 UI 线程请在 View 层自行调度（tkinter 用 after）。
- 维护最近 N 条消息缓存（默认 200）以便 View 拉取。
- 仅依赖 service.agents.mathmodelagent_client.MathModelAgentClient。
"""
from __future__ import annotations

from typing import Any, Callable, Deque, Dict, Optional
from collections import deque
import logging
import ssl
import time

from service.agents.mathmodelagent_client import MathModelAgentClient

logger = logging.getLogger(__name__)


class AgentBridge:
    """为控制器提供与 Agent 的连接/通信能力（Mixin）。"""

    # ------------------------ 生命周期 / 状态 ------------------------
    def __init__(self) -> None:
        # 运行态
        self._agent: Optional[MathModelAgentClient] = None
        self._agent_connected: bool = False
        self._agent_last_status: str = "disconnected"
        self._agent_last_error: Optional[str] = None
        self._agent_msgs: Deque[Any] = deque(maxlen=200)

        # 回调（由 View 注入）
        self._cb_on_status: Optional[Callable[[str], None]] = None
        self._cb_on_message: Optional[Callable[[Any], None]] = None
        self._cb_on_error: Optional[Callable[[str], None]] = None

    # ------------------------ 回调注册 ------------------------
    def set_agent_handlers(
        self,
        on_status: Optional[Callable[[str], None]] = None,
        on_message: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._cb_on_status = on_status
        self._cb_on_message = on_message
        self._cb_on_error = on_error

    # ------------------------ 连接管理 ------------------------
    def agent_connect(
        self,
        url: str,
        token: Optional[str] = None,
        proxy: Optional[str] = None,
        ping_interval: float = 20.0,
        insecure_skip_tls_verify: bool = False,
    ) -> None:
        """建立到 Agent 的 WebSocket 连接。后台线程运行。"""
        self.agent_close()

        sslopt = {"cert_reqs": ssl.CERT_NONE} if insecure_skip_tls_verify else None
        self._agent = MathModelAgentClient(
            url=url,
            token=token,
            proxy=proxy,
            ping_interval=ping_interval,
            sslopt=sslopt,
        )

        # 绑定底层回调
        @self._agent.on_open
        def _opened():
            self._agent_connected = True
            self._set_status("connected")

        @self._agent.on_message
        def _message(m):
            self._agent_msgs.append({"ts": time.time(), "data": m})
            if self._cb_on_message:
                try:
                    self._cb_on_message(m)
                except Exception as e:  # noqa
                    logger.debug("on_message UI cb error: %s", e)

        @self._agent.on_error
        def _error(e: Exception):
            self._agent_last_error = str(e)
            self._set_status("error")
            if self._cb_on_error:
                try:
                    self._cb_on_error(self._agent_last_error)
                except Exception:  # noqa
                    pass

        @self._agent.on_close
        def _closed(code: int, msg: str):
            self._agent_connected = False
            self._set_status(f"closed({code})")

        @self._agent.on_reconnect
        def _reconn(attempt: int, delay: float):
            self._set_status(f"reconnecting #{attempt} in {delay:.1f}s")

        # 后台线程启动
        self._set_status("connecting...")
        self._agent.connect(block=False)

    def agent_close(self) -> None:
        if self._agent:
            try:
                self._agent.close()
            except Exception:  # noqa
                pass
            finally:
                self._agent = None
        self._agent_connected = False
        self._set_status("disconnected")

    def agent_is_connected(self) -> bool:
        return bool(self._agent and self._agent.is_connected())

    # ------------------------ 发送 API ------------------------
    def agent_send_text(self, text: str) -> None:
        if not self._agent:
            raise RuntimeError("agent not connected")
        self._agent.send_text(text)

    def agent_send_json(self, payload: Dict[str, Any]) -> None:
        if not self._agent:
            raise RuntimeError("agent not connected")
        self._agent.send_json(payload)

    def agent_request(self, payload: Dict[str, Any], timeout: float = 15.0) -> Any:
        if not self._agent:
            raise RuntimeError("agent not connected")
        return self._agent.request(payload, timeout=timeout)

    # ------------------------ 消息缓存（可选给 View 拉取） ------------------------
    def agent_recent_messages(self, limit: int = 50) -> list[Any]:
        """返回最近收到的消息（新 → 旧）。"""
        out = list(self._agent_msgs)
        out.reverse()
        return out[:limit]

    def agent_last_error(self) -> Optional[str]:
        return self._agent_last_error

    def agent_status(self) -> str:
        return self._agent_last_status

    # ------------------------ 内部：状态 & 回调封装 ------------------------
    def _set_status(self, status: str) -> None:
        self._agent_last_status = status
        if self._cb_on_status:
            try:
                self._cb_on_status(status)
            except Exception:  # noqa
                pass


"""
WorkbenchController
===================

将“处理逻辑/业务逻辑”集中到 Controller，View 只负责显示与事件绑定。

职责边界：
- Controller 负责：文件读写、最近文件管理、LatexExtractor 构建与数据整形、
  标记对扫描与替换、辅助文本读取、纯内容片段提取（不含展示性分隔与文案）。
- View 负责：控件创建、布局、事件绑定、把用户输入/当前文本传给 Controller，
  并根据 Controller 返回的数据刷新界面（Treeview、文本框、消息提示等），
  同时负责生成所有用户可见的文案与分隔样式。

常用调用方式（示例，文案由 View 决定）：
- 打开文件：ctrl.open_path(path)  → 返回 {"text": 文本}
- 保存文件：ctrl.save_text(current_editor_text) → (ok, msg)；ok=True 时 msg 为空字符串
- 重载文件：ctrl.reload_from_disk() → {"text": 文本}
- 构建导航树：ctrl.make_outline_nodes(ctrl.extractor)、ctrl.make_problem_tree(ctrl.extractor)、
  ctrl.make_code_nodes(ctrl.extractor)  → 交给 View 填充 Treeview
- 预览：ctrl.render_outline_preview(...), ctrl.render_problem_preview(...), ctrl.render_code_preview(...)
- 替换页：
    ctrl.update_marker_pairs_from_text(editor_text) → 返回候选显示名列表
    ctrl.get_pair_content_by_display(sel_display)  → 返回已缓存/原始内容
    ctrl.apply_replace_for_display(editor_text, sel_display, new_content) → 返回 new_text
- 辅助页：
    files = ctrl.list_aid_txt()
    txt = ctrl.read_aid_txt(filename)

备注：
- 本 Controller 维护少量状态（current_file/current_text/extractor/recent_files 等），
  但不直接操作 UI；所有需要的输入（例如“当前编辑器文本”）在调用时作为参数传入。
"""


import os
import re
import pathlib
from typing import List, Dict, Any, Optional, Tuple

import appdirs

from model.latex_extractor import LatexExtractor
from model.text_replacer import find_marker_pairs, replace_contents
from utils.paths import resource_path


# ===== 常量 =====
RECENT_FILE_MAX = 5
RECENT_FILE_STORE = "recent_files.txt"


class WorkbenchController(AgentBridge):
    """一体化工作台的业务控制器"""

    # ---------- 生命周期 / 状态 ----------
    def __init__(self) -> None:
        # 初始化代理桥
        AgentBridge.__init__(self)
        # 文件/文本相关
        self.current_file: Optional[str] = None
        self.current_text: str = ""
        self.extractor: Optional[LatexExtractor] = None

        # 最近文件
        self.recent_files: List[str] = self.load_recent()

        # 替换相关
        self.marker_pairs: List[Dict[str, Any]] = []
        self.replacements: Dict[int, str] = {}  # 以“标记对索引”为 key 的缓存替换文本

    # ---------- 最近文件：读写 ----------
    @staticmethod
    def _recent_store_path() -> str:
        """
        将最近文件记录存放到用户数据目录，跨平台更稳：
        Windows:  C:\\Users\\<User>\\AppData\\Local\\mcm\\mcmaa\\recent_files.txt
        macOS:    ~/Library/Application Support/mcmaa/recent_files.txt
        Linux:    ~/.local/share/mcmaa/recent_files.txt
        """
        app_dir = appdirs.user_data_dir(appname="mcmaa", appauthor="mcm")
        pathlib.Path(app_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(app_dir, RECENT_FILE_STORE)

    def load_recent(self) -> List[str]:
        path = self._recent_store_path()
        items: List[str] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    p = line.strip()
                    if p and os.path.exists(p):
                        items.append(p)
        except Exception:
            pass
        return items[:RECENT_FILE_MAX]

    def save_recent(self, items: List[str]) -> None:
        path = self._recent_store_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                for p in items[:RECENT_FILE_MAX]:
                    f.write(p + "\n")
        except Exception:
            pass

    def add_recent(self, p: Optional[str]) -> None:
        """更新最近文件列表并写盘"""
        if not p:
            return
        if p in self.recent_files:
            self.recent_files.remove(p)
        self.recent_files.insert(0, p)
        self.recent_files = self.recent_files[:RECENT_FILE_MAX]
        self.save_recent(self.recent_files)

    def remove_recent_if_missing(self, p: str) -> None:
        """当文件不存在时，从最近列表清理"""
        try:
            if p in self.recent_files:
                self.recent_files.remove(p)
                self.save_recent(self.recent_files)
        except Exception:
            pass

    # ---------- 文件 I/O ----------
    @staticmethod
    def read_file(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def write_file(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # ---------- 打开/重载/保存：同时维护 extractor ----------
    def open_path(self, file_path: str) -> Dict[str, str]:
        """
        打开文件 -> 读取文本 -> 构建 extractor -> 维护最近文件。
        仅返回内容，不返回面向用户的 UI 文案。
        返回 {"text": 文本}
        """
        self.current_file = file_path
        text = self.read_file(file_path)
        self.current_text = text
        self.extractor = self.build_extractor(file_path, max_level=3)
        self.add_recent(file_path)
        # 开启新文件后，清空替换缓存 & 重新扫描标记
        self.replacements.clear()
        self.update_marker_pairs_from_text(text)
        return {"text": text}

    def reload_from_disk(self) -> Dict[str, str]:
        """
        从磁盘重载当前文件，不改动磁盘文件，只更新内存文本与 extractor。
        返回 {"text": 文本}（不返回 UI 文案）
        """
        if not self.current_file:
            return {"text": ""}
        text = self.read_file(self.current_file)
        self.current_text = text
        self.extractor = self.build_extractor(self.current_file, max_level=3)
        # 保持替换缓存策略简单：重载时清空，避免索引错位
        self.replacements.clear()
        self.update_marker_pairs_from_text(text)
        return {"text": text}

    def save_text(self, editor_text: str) -> Tuple[bool, str]:
        """
        保存编辑器文本到当前文件，并重建 extractor。
        成功时返回 (True, "") —— 留空文案交由 View 决定；
        失败时返回 (False, 技术错误字符串) —— 由 View 决定如何组织对用户的提示。
        """
        if not self.current_file:
            return False, "no file opened"
        try:
            self.write_file(self.current_file, editor_text)
            self.current_text = editor_text
            self.extractor = self.build_extractor(self.current_file, max_level=3)
            self.add_recent(self.current_file)
            # 保存后不强制清空 replacements；索引变化会在下一次扫描时自然覆盖
            self.update_marker_pairs_from_text(editor_text)
            return True, ""  # 文案交由 View
        except Exception as e:
            return False, str(e)  # 技术信息，非 UI 文案

    # ---------- 模型 ----------
    @staticmethod
    def build_extractor(tex_path: str, max_level: int = 3) -> LatexExtractor:
        return LatexExtractor(tex_path, max_level=max_level)

    # ---------- 导航树数据（仅数据组装，View 自行渲染） ----------
    @staticmethod
    def make_outline_nodes(extractor: Optional[LatexExtractor]) -> List[Dict[str, Any]]:
        """
        生成大纲节点数据（不含 codeblock）：
        返回列表，每个元素：{"title": str, "level": int, "line_num": int}
        视图侧按 level 构建层级关系。
        """
        nodes: List[Dict[str, Any]] = []
        if not extractor:
            return nodes
        for section_type, title, level, line_num in extractor.sections:
            if section_type == "codeblock":
                continue
            nodes.append({"title": title, "level": level, "line_num": line_num})
        return nodes

    @staticmethod
    def make_problem_tree(extractor: Optional[LatexExtractor]) -> List[Dict[str, Any]]:
        """
        生成问题树数据（结构化数据，文案与展示由 View 决定）：
        返回：
        [
          {"text": f"问题{k}", "values": (k,), "children": [
                {"text":"摘要片段", "values":(k, "abstract")},
                {"text":"问题重述","values":(k, "restate")},
                {"text":"问题分析","values":(k, "analysis")},
                {"text":"模型与求解","values":(k, "modeling")},
          ]},
          ...
        ]
        """
        items: List[Dict[str, Any]] = []
        if not extractor:
            return items
        try:
            keywords = extractor.get_unique_keywords()
        except Exception:
            keywords = []
        for k in keywords:
            node = {
                "text": f"问题{k}",
                "values": (k,),
                "children": [
                    {"text": "摘要片段", "values": (k, "abstract")},
                    {"text": "问题重述", "values": (k, "restate")},
                    {"text": "问题分析", "values": (k, "analysis")},
                    {"text": "模型与求解", "values": (k, "modeling")},
                ],
            }
            items.append(node)
        return items

    @staticmethod
    def make_code_nodes(extractor: Optional[LatexExtractor]) -> List[Dict[str, Any]]:
        """
        生成代码树节点数据（只列出 codeblock，保持出现顺序）：
        返回列表，每个元素：{"text": title, "values": (start_line, 4)}
        """
        nodes: List[Dict[str, Any]] = []
        if not extractor:
            return nodes
        for cb in extractor.codeblocks:
            nodes.append({"text": cb["title"], "values": (cb["start"], 4)})
        return nodes

    # ---------- 预览渲染（仅内容拼接，不做展示性分隔） ----------
    @staticmethod
    def render_outline_preview(
        extractor: Optional[LatexExtractor],
        start_line: int,
        start_level: int,
    ) -> str:
        """大纲点击后的预览：从起始行到下一个同级/更高级标题"""
        if not extractor:
            return ""
        lines = extractor.extract_content(start_line, start_level)
        return "\n".join(lines)

    def render_code_preview(
        self,
        extractor: Optional[LatexExtractor],
        start_line: int,
        level: int,
    ) -> str:
        """代码树点击后的预览：直接复用提取"""
        return self.render_outline_preview(extractor, start_line, level)

    @staticmethod
    def render_problem_preview(
        extractor: Optional[LatexExtractor],
        k: str,
        part: Optional[str] = None,
    ) -> str:
        """
        问题树项点击后的预览：
        - part 为 None：合并“摘要片段/重述/分析/建模”，不插入展示性分隔，交由 View 决定呈现样式
        - part in {"abstract","restate","analysis","modeling"}：只返回对应部分
        """
        if not extractor or not k:
            return ""
        parts = extractor.extract_problem_parts(k)
        abstract = extractor.extract_abstract_parts(k)

        if part is None:
            merged: List[str] = []
            if abstract:
                merged += abstract + [""]

            if "Restatement" in parts:
                merged += parts["Restatement"] + [""]

            if "Analysis" in parts:
                merged += parts["Analysis"] + [""]

            if "Modeling" in parts:
                merged += parts["Modeling"] + [""]

            return "\n".join(merged).strip() or ""

        # 单部分
        if part == "abstract":
            content = abstract
        elif part == "restate":
            content = parts.get("Restatement", [])
        elif part == "analysis":
            content = parts.get("Analysis", [])
        elif part == "modeling":
            content = parts.get("Modeling", [])
        else:
            content = []
        return "\n".join(content).strip()

    # ---------- 复制文本（供 View 放入剪贴板，保持纯内容） ----------
    @staticmethod
    def build_problem_merged_text(extractor: Optional[LatexExtractor], k: str) -> str:
        if not extractor or not k:
            return ""
        parts = extractor.extract_problem_parts(k)
        abstract = extractor.extract_abstract_parts(k)

        merged: List[str] = []
        if abstract:
            merged += abstract + [""]

        if "Restatement" in parts:
            merged += parts["Restatement"] + [""]

        if "Analysis" in parts:
            merged += parts["Analysis"] + [""]

        if "Modeling" in parts:
            merged += parts["Modeling"] + [""]

        return "\n".join(merged).strip()

    @staticmethod
    def build_problem_part_text(extractor: Optional[LatexExtractor], k: str, part: str) -> str:
        if not extractor or not k:
            return ""
        if part == "abstract":
            content = extractor.extract_abstract_parts(k)
        else:
            mapping = {"restate": "Restatement", "analysis": "Analysis", "modeling": "Modeling"}
            pieces = extractor.extract_problem_parts(k)
            content = pieces.get(mapping.get(part, ""), [])
        return "\n".join(content).strip()

    # ---------- 替换功能 ----------
    @staticmethod
    def _marker_display_name(marker_type: str) -> str:
        """
        将 “<----- xxx ----->” 提取为 “xxx”；若不匹配则返回原串。
        """
        m = re.search(r"<-----(.*?)----->", marker_type)
        return m.group(1).strip() if m else marker_type

    def update_marker_pairs_from_text(self, text: str) -> List[str]:
        """
        扫描标记对，更新 self.marker_pairs，并返回“可供下拉选择的显示名列表”。
        注意：下拉项可能不唯一（如果模板里有相同的 marker_type），此处保持与旧实现一致。
        """
        self.marker_pairs = find_marker_pairs(text)
        display = [self._marker_display_name(p["marker_type"]) for p in self.marker_pairs]
        return display

    def get_pair_content_by_display(self, display_name: str) -> str:
        """
        根据显示名找到对应标记对，返回“已缓存替换文本”或“原始内容”。
        规则与原实现一致：优先返回 self.replacements[idx]，否则返回 pair["content"]。
        """
        display_name = (display_name or "").strip()
        if not display_name:
            return ""
        for pair in self.marker_pairs:
            disp = self._marker_display_name(pair["marker_type"])
            if disp == display_name:
                idx = pair["index"]
                return self.replacements.get(idx, pair.get("content", ""))
        return ""

    def apply_replace_for_display(self, base_text: str, display_name: str, new_content: str) -> str:
        """
        对“当前选择的标记对”应用替换，返回新的整篇文本（View 写回到编辑器即可）。
        - base_text：通常是编辑器里的完整文本
        - display_name：下拉选中的项（例如 “摘要/关键词/引言” 等）
        - new_content：替换区域的完整新文本
        """
        display_name = (display_name or "").strip()
        if not display_name:
            return base_text

        # 1) 通过显示名定位 index
        idx: Optional[int] = None
        for pair in self.marker_pairs:
            disp = self._marker_display_name(pair["marker_type"])
            if disp == display_name:
                idx = pair["index"]
                break
        if idx is None:
            return base_text

        # 2) 记录到缓存并做整体替换
        self.replacements[idx] = new_content
        new_text = replace_contents(base_text, self.replacements)

        # 3) 替换后重新扫描标记对（索引可能重排）
        self.update_marker_pairs_from_text(new_text)
        return new_text

    # ---------- 辅助页 ----------
    @staticmethod
    def aid_dir() -> str:
        """
        返回 utils/ai-aid-mcmaa 目录（支持 pyinstaller 后的资源路径）
        """
        return resource_path("utils", "ai-aid-mcmaa")

    def list_aid_txt(self) -> List[str]:
        d = self.aid_dir()
        out: List[str] = []
        try:
            if os.path.isdir(d):
                for name in os.listdir(d):
                    if name.lower().endswith(".txt"):
                        out.append(name)
        except Exception:
            pass
        out.sort()
        return out

    def read_aid_txt(self, filename: str) -> str:
        fpath = os.path.join(self.aid_dir(), filename)
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read()

    # ---------- Quick Open：供菜单调用 ----------
    def quick_open(self, p: Optional[str]) -> Tuple[bool, str, str]:
        """
        给“Quick Open”使用：
        - 路径为空或文件不存在：返回 (False, 技术原因字符串, "")
        - 成功：等价于 open_path，返回 (True, "", text)
        （不返回 UI 文案，由 View 决定展示“文件已加载: ...”等）
        """
        if not p or not os.path.exists(p):
            self.remove_recent_if_missing(p or "")
            return False, "file not found or removed", ""
        data = self.open_path(p)
        return True, "", data.get("text", "")

    # ---------- 工具：将 Editor 的文本更新到 Controller（不保存磁盘） ----------
    def update_current_text_only(self, editor_text: str) -> None:
        """
        View 在需要时可以调用该方法同步“当前编辑器内容”到 Controller。
        注意：该方法不会写入磁盘，也不会重建 extractor。
        主要用于替换页/辅助页等需要 Controller 暂存当前文本参与计算的场景。
        """
        self.current_text = editor_text
