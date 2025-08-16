# %% mathmodelagent_client.py
# -*- coding: utf-8 -*-

"""
mathmodelagent_client.py — 使用 websocket-client 的简洁稳定版客户端
=================================================================

特性
----
- 依赖 `websocket-client`（而非已弃用/冷门的 `websocket` + gevent）。
- 线程安全，内置自动重连（指数退避），并支持心跳 Ping 保活。
- 统一回调：on_open / on_message / on_error / on_close / on_reconnect。
- 同步/异步两种发送：
  - send_json / send_text：异步发送，不等待结果；
  - request()：带 `request_id` 的同步请求，等待指定超时的对应响应。
- 支持 Token 认证（可在 Header 中带入 Authorization），HTTP 代理，TLS 自定义。
- 仅标准库 + websocket-client，无额外依赖。

安装
----
    pip install websocket-client

最简示例
--------
```python
from mathmodelagent_client import MathModelAgentClient

client = MathModelAgentClient(
    url="wss://your-agent-server/ws",
    token="YOUR_TOKEN",              # 可选
)

# 绑定消息回调（可选）
@client.on_message
def _on_msg(message: dict | str):
    print("[MSG]", message)

client.connect(block=False)  # 后台线程运行

# 异步发送
client.send_json({"type": "ping"})

# 同步请求-响应（带 request_id）
resp = client.request({"type": "infer", "payload": {"text": "hello"}}, timeout=15.0)
print("sync resp:", resp)

client.close()
```

与后端协议约定
--------------
- 默认以 JSON 通信，消息结构建议：
  - 请求：`{"request_id": "uuid", "type": "...", "payload": {...}}`
  - 响应：`{"request_id": "uuid", "ok": true, "data": {...}}`
- 若返回为纯文本，客户端会原样转交。

注意
----
- 若你的后端不是以上 JSON 协议，请在 `parse_message`/`_route_response` 按需调整。
- Windows/conda 环境无需 gevent/zope 依赖。
"""
from __future__ import annotations

import json
import logging
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import websocket  # 来自 websocket-client 包


# ------------------------- 日志配置（可按需接入你项目的 logger） -------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.StreamHandler()
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    _h.setFormatter(_fmt)
    logger.addHandler(_h)
logger.setLevel(logging.INFO)


# ------------------------------- 内部数据结构 -------------------------------
@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    response: Any | None = None
    error: Exception | None = None


# ------------------------------- 主客户端类 -------------------------------
class MathModelAgentClient:
    def __init__(
        self,
        url: str,
        token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        reconnect: bool = True,
        max_reconnect_delay: float = 60.0,
        sslopt: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        :param url: WebSocket 服务地址，例如 wss://host:port/ws
        :param token: 可选的 Bearer Token，会以 Authorization 头发送
        :param headers: 额外 HTTP 头
        :param proxy: 代理地址，例如 http://127.0.0.1:7890
        :param ping_interval: 心跳间隔（秒）；<=0 关闭心跳
        :param ping_timeout: 心跳超时（秒）
        :param reconnect: 网络异常/断线自动重连
        :param max_reconnect_delay: 自动重连的最大退避时间
        :param sslopt: 传入 websocket-client 的 sslopt，例如 {"cert_reqs": ssl.CERT_NONE}
        """
        self.url = url
        self.token = token
        self.base_headers = headers or {}
        self.proxy = proxy
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.reconnect = reconnect
        self.max_reconnect_delay = max_reconnect_delay
        self.sslopt = sslopt or {"cert_reqs": ssl.CERT_REQUIRED}

        # 回调
        self._on_open_cb: Optional[Callable[[], None]] = None
        self._on_message_cb: Optional[Callable[[Any], None]] = None
        self._on_error_cb: Optional[Callable[[Exception], None]] = None
        self._on_close_cb: Optional[Callable[[int, str], None]] = None
        self._on_reconnect_cb: Optional[Callable[[int, float], None]] = None

        # 基础状态
        self._wsapp: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = threading.Event()

        # 同步请求映射表
        self._pending: Dict[str, _PendingRequest] = {}
        self._pending_lock = threading.Lock()

    # ---------------------------- 装饰器形式绑定回调 ----------------------------
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

    # --------------------------------- 连接管理 ---------------------------------
    def connect(self, block: bool = False) -> None:
        """建立连接。
        :param block: True 则阻塞当前线程直到连接线程结束；False 则后台线程运行。
        """
        self._stop_event.clear()
        self._spawn_ws_thread()
        if block and self._thread is not None:
            self._thread.join()

    def close(self) -> None:
        """优雅关闭连接与线程"""
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

    # --------------------------------- 发送 API ---------------------------------
    def send_text(self, text: str) -> None:
        if not self._wsapp:
            raise RuntimeError("WebSocket is not connected")
        self._wsapp.send(text)

    def send_json(self, obj: Dict[str, Any]) -> None:
        self.send_text(json.dumps(obj, ensure_ascii=False))

    def request(self, obj: Dict[str, Any], timeout: float = 10.0) -> Any:
        """同步请求-响应：附加 request_id 并阻塞等待对应响应或超时。
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

    # --------------------------------- 内部逻辑 ---------------------------------
    def _spawn_ws_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        t = threading.Thread(target=self._run_forever, name="MathModelAgentWS", daemon=True)
        t.start()
        self._thread = t

    def _build_headers(self) -> list[str]:
        headers = []
        merged = dict(self.base_headers)
        if self.token:
            merged.setdefault("Authorization", f"Bearer {self.token}")
        # 明确 JSON
        merged.setdefault("Content-Type", "application/json")
        for k, v in merged.items():
            headers.append(f"{k}: {v}")
        return headers

    def _run_forever(self) -> None:
        attempt = 0
        backoff = 1.0
        while not self._stop_event.is_set():
            try:
                self._wsapp = websocket.WebSocketApp(
                    self.url,
                    header=self._build_headers(),
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_pong=self._on_pong,
                )

                # 代理拆分
                http_proxy_host = http_proxy_port = None
                if self.proxy:
                    try:
                        scheme, rest = self.proxy.split("://", 1)
                        host_port = rest.split("/", 1)[0]
                        host, port = host_port.split(":", 1)
                        http_proxy_host = host
                        http_proxy_port = int(port)
                    except Exception:  # noqa
                        logger.warning("proxy format invalid, expecting http://host:port")

                # 连接并阻塞，直到 close
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
                except Exception:  # noqa
                    pass
            logger.info("reconnecting in %.1fs (attempt %d)", delay, attempt)
            self._sleep(delay)
            backoff = min(backoff * 2, self.max_reconnect_delay)

    # ----------------------------- WebSocket 回调 -----------------------------
    def _on_open(self, ws: websocket.WebSocketApp):  # noqa: ARG002
        self._connected.set()
        logger.info("WebSocket connected: %s", self.url)
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
            except Exception:  # noqa
                pass

    def _on_close(self, ws: websocket.WebSocketApp, status_code: int, msg: str):  # noqa: ARG002
        self._connected.clear()
        logger.info("WebSocket closed (%s): %s", status_code, msg)
        if self._on_close_cb:
            try:
                self._on_close_cb(status_code, msg)
            except Exception:  # noqa
                pass

    def _on_pong(self, ws: websocket.WebSocketApp, data: str | bytes):  # noqa: ARG002
        logger.debug("< PONG %s", data)

    # ----------------------------- 解析与路由 -----------------------------
    def parse_message(self, message: str | bytes) -> Any:
        """将原始消息解析为 Python 对象。优先按 JSON 解析，不是 JSON 则返回原始文本/二进制。"""
        if isinstance(message, (bytes, bytearray)):
            try:
                return json.loads(message.decode("utf-8"))
            except Exception:
                return message  # 二进制按原样返回
        # str
        try:
            return json.loads(message)
        except Exception:
            return message

    def _route_response(self, payload: Any) -> None:
        """若是带 request_id 的响应，唤醒对应等待的 request()；否则忽略，由 on_message 处理。"""
        if not isinstance(payload, dict):
            return
        req_id = payload.get("request_id")
        if not req_id:
            return
        with self._pending_lock:
            pend = self._pending.get(req_id)
        if pend is None:
            return
        # 认为这是同步响应
        if payload.get("ok") is False and "error" in payload:
            pend.error = RuntimeError(str(payload["error"]))
        else:
            pend.response = payload
        pend.event.set()

    # --------------------------------- 工具 ---------------------------------
    @staticmethod
    def _sleep(seconds: float) -> None:
        try:
            time.sleep(seconds)
        except KeyboardInterrupt:
            pass


# ----------------------------- 可选：简单 CLI -----------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MathModelAgent WebSocket Client")
    parser.add_argument("url", help="wss://host/ws")
    parser.add_argument("--token", default=None, help="Bearer token")
    parser.add_argument("--proxy", default=None, help="http://host:port")
    parser.add_argument("--ping", type=float, default=20.0, help="ping interval seconds (<=0 to disable)")
    args = parser.parse_args()

    client = MathModelAgentClient(
        url=args.url,
        token=args.token,
        proxy=args.proxy,
        ping_interval=args.ping,
        sslopt={"cert_reqs": ssl.CERT_NONE},  # 如需跳过证书校验（内网自签名），请知晓安全风险
    )

    @client.on_open
    def _opened():
        logger.info("opened -> send hello")
        client.send_json({"type": "hello", "ts": time.time()})

    @client.on_message
    def _msg(m):
        logger.info("< %s", m)

    @client.on_reconnect
    def _reconn(attempt, delay):
        logger.info("reconnect attempt=%d delay=%.1fs", attempt, delay)

    client.connect(block=True)
