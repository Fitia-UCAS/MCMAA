# %% mathmodelagent_client.py
# -*- coding: utf-8 -*-

"""
mathmodelagent_client.py — HTTP+WebSocket 双栈客户端（兼容旧用法）
================================================================

特性
----
- 依赖 `websocket-client`（而非已弃用/冷门的 `websocket` + gevent）。
- HTTP 使用 `requests`。
- “两项配置”模型：
  1) Base URL（HTTP），例如 http://host:port
  2) WS Base（可选），若不填则自动从 Base URL 推断（http→ws / https→wss）
- WebSocket：线程安全，内置自动重连（指数退避），支持 Ping 保活。
- 统一回调：on_open / on_message / on_error / on_close / on_reconnect。
- 同步/异步两种发送：
  - send_json / send_text：异步发送
  - request()：带 request_id 的同步请求，等待指定超时的对应响应。
- 支持 Token 认证（Authorization: Bearer <token>）、HTTP 代理、TLS 自定义。
- 兼容旧构造方式：若仅传入 `url="wss://host/ws"` 也能工作（等价于仅 WS 客户端）。

安装
----
    pip install websocket-client requests
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List, Union
from urllib.parse import urlparse, urlunparse

import requests  # HTTP
import websocket  # 来自 websocket-client 包（包名即 websocket）


# ------------------------- 日志配置 -------------------------

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _h.setFormatter(_fmt)
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# --------------------------- 内部结构 ---------------------------


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    response: Any | None = None
    error: Exception | None = None


def _infer_ws_base_from_http(base_url: str) -> str:
    """
    从 HTTP 基址推断 WS 基址：
    http://host:port -> ws://host:port
    https://host:port -> wss://host:port
    """
    u = urlparse(base_url)
    scheme = {"http": "ws", "https": "wss"}.get(u.scheme, "ws")
    return urlunparse((scheme, u.netloc, "", "", "", ""))


# --------------------------- 主客户端 ---------------------------


class MathModelAgentClient:
    def __init__(
        self,
        # 新用法（推荐）
        base_url: Optional[str] = None,  # HTTP 基址，如 http://host:port
        ws_base: Optional[str] = None,  # WS 基址，如 ws://host:port（可省略）
        # 旧用法（兼容）：直接传完整 WS URL
        url: Optional[str] = None,  # 完整 wss://host:port/ws
        # 通用参数
        token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,  # 形如 http://127.0.0.1:7890
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        reconnect: bool = True,
        max_reconnect_delay: float = 60.0,
        sslopt: Optional[Dict[str, Any]] = None,
        http_timeout: float = 30.0,
    ) -> None:
        """
        说明：
        - 推荐：传 base_url（HTTP），可选 ws_base；WS 可用 connect_ws() 建立。
        - 兼容：若只传 url（完整 WS），则作为仅 WS 客户端工作（connect() 生效）。
        """
        # HTTP
        self.base_url = (base_url or "").rstrip("/")
        self.ws_base = (ws_base or (_infer_ws_base_from_http(self.base_url) if self.base_url else "")).rstrip("/")

        # 旧用法：直接给完整 WS URL
        self._legacy_ws_url = url  # 若提供，则 connect() 走它

        self.token = token
        self.base_headers = headers or {}
        self.proxy = proxy
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.reconnect = reconnect
        self.max_reconnect_delay = max_reconnect_delay
        self.sslopt = sslopt or {"cert_reqs": ssl.CERT_REQUIRED}
        self.http_timeout = http_timeout

        # WS 状态
        self._wsapp: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = threading.Event()

        # 同步请求映射表
        self._pending: Dict[str, _PendingRequest] = {}
        self._pending_lock = threading.Lock()

        # 回调
        self._on_open_cb: Optional[Callable[[], None]] = None
        self._on_message_cb: Optional[Callable[[Any], None]] = None
        self._on_error_cb: Optional[Callable[[Exception], None]] = None
        self._on_close_cb: Optional[Callable[[int, str], None]] = None
        self._on_reconnect_cb: Optional[Callable[[int, float], None]] = None

    # ---------------------- 装饰器：绑定回调 ----------------------
    def on_open(self, func: Callable[[], None]):
        self._on_open_cb = func
        return func

    def on_message(self, func: Callable[[Any], None]):
        self._on_message_cb = func
        return func

    def on_error(self, func: Callable[[Exception], None]):
        self._on_error_cb = func
        return func

    def on_close(self, func: Callable[[int, str], None]):
        self._on_close_cb = func
        return func

    def on_reconnect(self, func: Callable[[int, float], None]):
        """当触发自动重连时调用；参数为 (attempt, delay_seconds)。"""
        self._on_reconnect_cb = func
        return func

    # ======================= HTTP 能力 =======================
    def _http_headers(self) -> Dict[str, str]:
        h = dict(self.base_headers)
        if self.token:
            h.setdefault("Authorization", f"Bearer {self.token}")
        h.setdefault("Content-Type", "application/json")
        return h

    def post(self, path: str, json_obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        通用 POST。path 必须以 "/" 开头。
        例：post("/api/modeling/submit", {...})
        """
        if not self.base_url:
            raise RuntimeError("base_url is not set")
        url = f"{self.base_url}{path}"
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        resp = requests.post(
            url,
            headers=self._http_headers(),
            json=json_obj,
            timeout=self.http_timeout,
            proxies=proxies,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"ok": True, "text": resp.text}

    def submit_modeling(
        self,
        payload: Dict[str, Any],
        file_paths: Optional[Dict[str, Union[str, List[str]]]] = None,
        path: str = "/modeling",
    ) -> Dict[str, Any]:
        """
        提交建模任务到 MathModelAgent:
        - 路由：POST /modeling
        - 表单：ques_all, comp_template, format_output, language
        - 文件：files（可多个）
        """
        if not self.base_url:
            raise RuntimeError("base_url is not set")
        url = f"{self.base_url}{path}"

        # 直接从 UI 下拉获取，保证合法
        data = {
            "ques_all": payload.get("ques_all") or payload.get("problem_text") or "",
            "comp_template": payload.get("comp_template") or "CHINA",
            "format_output": payload.get("format_output") or "Markdown",
            "language": payload.get("language") or "zh",
        }

        files = []
        if file_paths:
            for field, p_or_list in file_paths.items():
                if isinstance(p_or_list, list):
                    for p in p_or_list:
                        files.append((field, (os.path.basename(p), open(p, "rb"))))
                else:
                    p = p_or_list
                    files.append((field, (os.path.basename(p), open(p, "rb"))))

        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        resp = requests.post(
            url,
            data=data,
            files=files or None,
            headers=self.base_headers,
            timeout=self.http_timeout,
            proxies=proxies,
        )

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            detail = ""
            try:
                detail = resp.text
            except Exception:
                pass
            raise requests.HTTPError(f"{e} :: {detail}") from None
        finally:
            for _, f in files:
                try:
                    f[1].close()
                except Exception:
                    pass

        return resp.json()

    # ======================= WebSocket 能力 =======================
    def connect_ws(self, path: str = "/ws", block: bool = False) -> None:
        """
        使用 ws_base + path 建立 WS 连接。
        - ws_base 为空时，会尝试从 base_url 推断（http→ws / https→wss）。
        """
        if not self.ws_base and not self._legacy_ws_url:
            raise RuntimeError("ws_base/url is not set (provide base_url or url)")
        ws_url = self._legacy_ws_url or f"{self.ws_base}{path}"
        self._start_ws_thread(ws_url)
        if block and self._thread is not None:
            self._thread.join()

    def connect(self, block: bool = False) -> None:
        """
        兼容旧版 API：当 __init__ 提供了 url（完整 WS 地址）时可用。
        """
        if not self._legacy_ws_url:
            raise RuntimeError("legacy url not provided; use connect_ws(base_url/ws_base) instead")
        self._start_ws_thread(self._legacy_ws_url)
        if block and self._thread is not None:
            self._thread.join()

    def close(self) -> None:
        """优雅关闭连接与线程（仅 WS 部分需要关闭；HTTP 无需关闭）"""
        self._stop_event.set()
        if self._wsapp is not None:
            try:
                self._wsapp.close()
            except Exception as e:  # noqa
                logger.debug("close error: %s", e)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._connected.clear()

    def is_connected(self) -> bool:
        return self._connected.is_set()

    # ---------------------- 发送 API（WS） ----------------------
    def send_text(self, text: str) -> None:
        if not self._wsapp:
            raise RuntimeError("WebSocket is not connected")
        self._wsapp.send(text)

    def send_json(self, obj: Dict[str, Any]) -> None:
        self.send_text(json.dumps(obj, ensure_ascii=False))

    def request(self, obj: Dict[str, Any], timeout: float = 10.0) -> Any:
        """
        同步请求-响应：附加 request_id 并阻塞等待对应响应或超时。
        要求后端在响应中原样返回 `request_id` 字段。
        """
        req_id = obj.get("request_id") or str(uuid.uuid4())
        obj["request_id"] = req_id

        pend = _PendingRequest()
        with self._pending_lock:
            self._pending[req_id] = pend

        try:
            self.send_json(obj)
        except Exception as e:  # 发送失败
            with self._pending_lock:
                self._pending.pop(req_id, None)
            raise e

        ok = pend.event.wait(timeout=timeout)
        with self._pending_lock:
            self._pending.pop(req_id, None)
        if not ok:
            raise TimeoutError(f"request timeout: {req_id}")
        if pend.error:
            raise pend.error
        return pend.response

    # ---------------------- 内部：WS 循环 ----------------------
    def _http_like_headers(self) -> List[str]:
        """将 HTTP 头转为 websocket-client 需要的 header 列表形式。"""
        headers: List[str] = []
        merged = self._http_headers()
        for k, v in merged.items():
            headers.append(f"{k}: {v}")
        return headers

    def _start_ws_thread(self, ws_url: str) -> None:
        self._stop_event.clear()
        if self._thread and self._thread.is_alive():
            return
        t = threading.Thread(target=self._run_forever, args=(ws_url,), name="MathModelAgentWS", daemon=True)
        t.start()
        self._thread = t

    def _run_forever(self, ws_url: str) -> None:
        attempt = 0
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                self._wsapp = websocket.WebSocketApp(
                    ws_url,
                    header=self._http_like_headers(),
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_pong=self._on_pong,
                )

                # 代理拆分给 websocket-client
                http_proxy_host = http_proxy_port = None
                if self.proxy:
                    try:
                        scheme, rest = self.proxy.split("://", 1)
                        host_port = rest.split("/", 1)[0]
                        host, port = host_port.split(":", 1)
                        http_proxy_host = host
                        http_proxy_port = int(port)
                    except Exception:
                        logger.warning("proxy format invalid, expecting http://host:port")

                self._connected.clear()
                self._wsapp.run_forever(
                    sslopt=self.sslopt,
                    http_proxy_host=http_proxy_host,
                    http_proxy_port=http_proxy_port,
                    ping_interval=self.ping_interval if self.ping_interval > 0 else None,
                    ping_timeout=self.ping_timeout if self.ping_interval > 0 else None,
                )
            except Exception as e:
                logger.error("WebSocket error: %s", e)
                self._connected.clear()

            if not self.reconnect or self._stop_event.is_set():
                break

            # 自动重连
            attempt += 1
            delay = min(backoff, self.max_reconnect_delay)
            if self._on_reconnect_cb:
                try:
                    self._on_reconnect_cb(attempt, delay)
                except Exception:
                    pass
            logger.info("reconnecting in %.1fs (attempt %d)", delay, attempt)
            self._sleep(delay)
            backoff = min(backoff * 2, self.max_reconnect_delay)

    # ---------------------- WS 回调 ----------------------
    def _on_open(self, ws: websocket.WebSocketApp):  # noqa: ARG002
        self._connected.set()
        logger.info("WebSocket connected")
        if self._on_open_cb:
            try:
                self._on_open_cb()
            except Exception as e:
                logger.debug("on_open callback error: %s", e)

    def _on_message(self, ws: websocket.WebSocketApp, message: str | bytes):  # noqa: ARG002
        try:
            parsed = self.parse_message(message)
            self._route_response(parsed)
            if self._on_message_cb:
                self._on_message_cb(parsed)
        except Exception as e:
            logger.error("on_message error: %s", e)

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception):  # noqa: ARG002
        logger.error("WebSocket error: %s", error)
        if self._on_error_cb:
            try:
                self._on_error_cb(error)
            except Exception:
                pass

    def _on_close(self, ws: websocket.WebSocketApp, status_code: int, msg: str):  # noqa: ARG002
        self._connected.clear()
        logger.info("WebSocket closed (%s): %s", status_code, msg)
        if self._on_close_cb:
            try:
                self._on_close_cb(status_code, msg)
            except Exception:
                pass

    def _on_pong(self, ws: websocket.WebSocketApp, data: str | bytes):  # noqa: ARG002
        logger.debug("< PONG %s", data)

    # ---------------------- 解析与路由 ----------------------
    def parse_message(self, message: str | bytes) -> Any:
        """优先按 JSON 解析；不是 JSON 则返回原始文本/二进制。"""
        if isinstance(message, (bytes, bytearray)):
            try:
                return json.loads(message.decode("utf-8"))
            except Exception:
                return message
        try:
            return json.loads(message)
        except Exception:
            return message

    def _route_response(self, payload: Any) -> None:
        """若是带 request_id 的响应，唤醒对应等待的 request()；否则由 on_message 处理。"""
        if not isinstance(payload, dict):
            return
        req_id = payload.get("request_id")
        if not req_id:
            return
        with self._pending_lock:
            pend = self._pending.get(req_id)
        if pend is None:
            return
        if payload.get("ok") is False and "error" in payload:
            pend.error = RuntimeError(str(payload["error"]))
        else:
            pend.response = payload
        pend.event.set()

    # ---------------------- 工具 ----------------------
    @staticmethod
    def _sleep(seconds: float) -> None:
        try:
            time.sleep(seconds)
        except KeyboardInterrupt:
            pass


# ----------------------------- 简单 CLI -----------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MathModelAgent HTTP+WS Client")
    # 新用法
    parser.add_argument("--base", dest="base_url", default=None, help="HTTP base, e.g. http://127.0.0.1:8000")
    parser.add_argument("--ws", dest="ws_base", default=None, help="WS base, e.g. ws://127.0.0.1:8000 (optional)")
    parser.add_argument("--ws-path", dest="ws_path", default="/ws", help="WS path, default: /ws")
    # 旧用法
    parser.add_argument("--url", dest="legacy_url", default=None, help="full WS url, e.g. wss://host/ws")
    # 通用
    parser.add_argument("--token", default=None, help="Bearer token")
    parser.add_argument("--proxy", default=None, help="http://host:port")
    parser.add_argument("--ping", type=float, default=20.0, help="WS ping interval seconds (<=0 to disable)")
    args = parser.parse_args()

    client = MathModelAgentClient(
        base_url=args.base_url,
        ws_base=args.ws_base,
        url=args.legacy_url,
        token=args.token,
        proxy=args.proxy,
        ping_interval=args.ping,
        sslopt={"cert_reqs": ssl.CERT_NONE},  # 内网自签名时可用；注意安全风险
    )

    @client.on_open
    def _opened():
        logger.info("opened -> send hello")
        try:
            client.send_json({"type": "hello", "ts": time.time()})
        except Exception as e:
            logger.error("send hello failed: %s", e)

    @client.on_message
    def _msg(m):
        logger.info("< %s", m)

    @client.on_reconnect
    def _reconn(attempt, delay):
        logger.info("reconnect attempt=%d delay=%.1fs", attempt, delay)

    # 选择连接方式
    if args.legacy_url:
        client.connect(block=True)
    else:
        client.connect_ws(path=args.ws_path, block=True)
