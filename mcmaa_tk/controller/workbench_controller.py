# %% controller/workbench_controller.py
# -*- coding: utf-8 -*-

"""
AgentBridge — 适配 MathModelAgent 的两段式客户端（HTTP 提交 + WS 订阅）
------------------------------------------------------------------
- agent_connect(base_url, ws_base, ...): 仅初始化客户端，不立刻连 WS
- agent_submit_and_connect(...): HTTP 提交建模 -> 获得 task_id -> 连接该任务的 WS
- agent_connect_task(task_id): 已有 task_id 时，直接连该任务的 WS
- agent_close(): 断开
- agent_send_json(): 若后端/客户端支持任务流上的下行消息，则可发送；多数部署会不支持
- agent_request(): 标记为不支持（raise NotImplementedError）

保留：
- set_agent_handlers(on_status/on_message/on_error)
- 最近消息缓存、状态/错误查询
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Deque, Dict, Optional, Iterable, Tuple, List
from collections import deque
import logging
import ssl
import time

from service.agents.mathmodelagent_client import MathModelAgentClient
from utils.aid_loader import list_aid_files

logger = logging.getLogger(__name__)


class AgentBridge:
    """为控制器提供与 Agent 的连接/通信能力（Mixin）。"""

    # WS 任务流路径模板（按你的后端路由改这里即可）
    WS_TASK_PATH_TPL = "/ws/tasks/{task_id}"

    # ------------------------ 生命周期 / 状态 ------------------------
    def __init__(self) -> None:
        # 运行态
        self._agent: Optional[MathModelAgentClient] = None
        self._agent_connected: bool = False
        self._agent_last_status: str = "disconnected"
        self._agent_last_error: Optional[str] = None
        self._agent_msgs: Deque[Any] = deque(maxlen=200)

        # 任务态
        self._current_task_id: Optional[str] = None
        self._base_url: Optional[str] = None
        self._ws_base: Optional[str] = None
        self._token: Optional[str] = None
        self._proxy: Optional[str] = None

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

    # ------------------------ 连接管理（初始化阶段） ------------------------
    def agent_connect(
        self,
        base_url: str,
        ws_base: Optional[str] = None,
        token: Optional[str] = None,
        proxy: Optional[str] = None,
        ping_interval: float = 20.0,
        insecure_skip_tls_verify: bool = False,
    ) -> None:
        """
        初始化客户端（不立刻建立 WS 连接）。
        - base_url: HTTP 基地址，如 http://127.0.0.1:8000
        - ws_base:  WS 基地址，如 ws://127.0.0.1:8000；不传则由 base_url 推断
        """
        self.agent_close()

        self._base_url = base_url.strip().rstrip("/")
        self._ws_base = (ws_base or "").strip().rstrip("/") or None
        self._token = (token or "").strip() or None
        self._proxy = (proxy or "").strip() or None

        sslopt = {"cert_reqs": ssl.CERT_NONE} if insecure_skip_tls_verify else None
        self._agent = MathModelAgentClient(
            base_url=self._base_url,
            ws_base=self._ws_base,
            token=self._token,
            proxy=self._proxy,
            ping_interval=ping_interval,
            sslopt=sslopt,
        )

        # 绑定底层回调（这些回调在 WS 线程里触发；若要切 UI 线程请在 View 层 after）
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

        # 仅初始化，不连 WS
        self._current_task_id = None
        self._set_status("ready")

    # ------------------------ 提交并连接（推荐流程） ------------------------
    def agent_submit_and_connect(
        self,
        problem_text: str,
        files: Optional[Iterable[Tuple[str, Tuple[str, Any, str]]]] = None,
        template: str = "mcm",
        output_format: str = "latex",
        language: str = "zh",
        extra_form: Optional[Dict[str, Any]] = None,
        timeout: float = 60.0,
    ) -> str:
        """
        1) HTTP 提交建模 -> 获得 task_id（从 JSON 中提取）
        2) 连接该 task 的 WS 流（后台线程）
        :return: task_id
        """
        if not self._agent:
            raise RuntimeError("agent is not initialized, call agent_connect(base_url, ...) first")

        # --- 构造 payload（JSON 方式） ---
        payload = {
            "problem_text": problem_text,
            "template": template,
            "output_format": output_format,
            "language": language,
            "extra_form": extra_form or {},
            "timeout": timeout,
            # 如需传文件且后端只收 JSON，可将 files 转成 base64 后放入自定义字段
            # "files": [...],
        }

        self._set_status("submitting...")
        resp = self._agent.submit_modeling(payload)  # -> Dict

        # --- 提取 task_id（兼容常见返回结构） ---
        task_id = (
            (resp.get("task_id"))
            or (isinstance(resp.get("data"), dict) and resp["data"].get("task_id"))
            or resp.get("id")
        )
        if not task_id:
            raise RuntimeError(f"submit response missing task_id: {resp!r}")

        self._current_task_id = str(task_id)

        # --- 连接任务 WS ---
        self._set_status(f"connecting task {self._current_task_id}...")
        ws_path = self.WS_TASK_PATH_TPL.format(task_id=self._current_task_id)
        self._agent.connect_ws(path=ws_path, block=False)
        return self._current_task_id

    # ------------------------ 已有 task_id 时直接连接 ------------------------
    def agent_connect_task(self, task_id: str) -> None:
        """
        已有 task_id（例如从历史记录拿到）时，直接连接该任务的 WS。
        """
        if not self._agent:
            raise RuntimeError("agent is not initialized, call agent_connect(base_url, ...) first")
        self._current_task_id = task_id.strip()
        self._set_status(f"connecting task {self._current_task_id}...")
        ws_path = self.WS_TASK_PATH_TPL.format(task_id=self._current_task_id)
        self._agent.connect_ws(path=ws_path, block=False)

    # ------------------------ 断开 ------------------------
    def agent_close(self) -> None:
        if self._agent:
            try:
                self._agent.close()
            except Exception:  # noqa
                pass
            finally:
                self._agent = None
        self._agent_connected = False
        self._current_task_id = None
        self._set_status("disconnected")

    def agent_is_connected(self) -> bool:
        return bool(self._agent and self._agent.is_connected())

    # ------------------------ 发送 API（多数后端不支持） ------------------------
    def agent_send_text(self, text: str) -> None:
        """
        若底层客户端实现了 send_text，则透传；否则抛出“不支持”。
        注意：MathModelAgent 的任务 WS 通道通常为只读流。
        """
        if not self._agent:
            raise RuntimeError("agent not connected")
        if not hasattr(self._agent, "send_text"):
            raise NotImplementedError("current backend does not accept client->server messages on task stream")
        self._agent.send_text(text)  # type: ignore[attr-defined]

    def agent_send_json(self, payload: Dict[str, Any]) -> None:
        """
        同上：若后端开放了任务通道指令，且客户端实现了 send_json，这里才可用。
        """
        if not self._agent:
            raise RuntimeError("agent not connected")
        if not hasattr(self._agent, "send_json"):
            raise NotImplementedError("current backend does not accept JSON messages on task stream")
        # 有些后端会要求附带 task_id；如需可在此注入 payload["task_id"] = self._current_task_id
        self._agent.send_json(payload)  # type: ignore[attr-defined]

    def agent_request(self, payload: Dict[str, Any], timeout: float = 15.0) -> Any:
        """
        经典“请求-响应”模式对任务流通常不适用，这里明确不支持。
        如果未来后端提供 request_id 语义，可在底层客户端实现后再开放。
        """
        raise NotImplementedError("request/response is not supported on the task WebSocket stream")

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
        logging.info("AID_DIR=%s exists=%s", d, os.path.isdir(d))
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

    def get_aid_choices(self):
        """下拉：返回显示名列表"""
        return [name for name, _ in list_aid_files()]

    def read_aid_file(self, display_name: str) -> str:
        """根据显示名读取文本内容"""
        for name, full in list_aid_files():
            if name == display_name:
                try:
                    return Path(full).read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    # 尝试 GBK（国内文件常见）
                    return Path(full).read_text(encoding="gbk", errors="ignore")
        return ""
