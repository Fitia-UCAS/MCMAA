# %% backend_client.py
# -*- coding: utf-8 -*-
import json
import threading
import requests
from typing import Any, Dict, List, Optional, Tuple, Union


class BackendClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.openapi = None

    # ---------- 基础 ----------
    def ping(self) -> Tuple[bool, str]:
        """用 /openapi.json 判断后端是否在线，并缓存 schema。"""
        try:
            r = requests.get(f"{self.base_url}/openapi.json", timeout=10)
            if r.status_code == 200:
                self.openapi = r.json()
                return True, "Backend is up."
            return False, f"OpenAPI not available, status={r.status_code}"
        except Exception as e:
            return False, f"Ping failed: {e}"

    def list_paths(self) -> List[str]:
        if not self.openapi:
            ok, _ = self.ping()
            if not ok:
                return []
        return list(self.openapi.get("paths", {}).keys())

    # ---------- 查 /modeling 的请求体定义 ----------
    def _get_modeling_op(self) -> Optional[Dict[str, Any]]:
        """寻找 POST /modeling 的 OpenAPI 定义"""
        if not self.openapi:
            ok, _ = self.ping()
            if not ok:
                return None
        paths = self.openapi.get("paths", {})
        # 常见命名：/modeling
        for p, item in paths.items():
            post = item.get("post")
            if not post:
                continue
            # 兼容路径大小写或前缀
            if p.lower().endswith("/modeling") or p == "/modeling":
                return {"path": p, "op": post}
        # 没找到就返回 None
        return None

    def _infer_request_body(self) -> Dict[str, Any]:
        """
        返回请求体信息:
        {
          "path": "/modeling",
          "content_type": "application/json" 或 "multipart/form-data",
          "schema": {...},
          "field_map": {"files": ["字段A","字段B"], "json": {...}}  # 可选
        }
        """
        info = self._get_modeling_op()
        if not info:
            return {}

        post = info["op"]
        req_body = post.get("requestBody", {})
        content = req_body.get("content", {}) if isinstance(req_body, dict) else {}
        # 优先判断 multipart
        if "multipart/form-data" in content:
            return {
                "path": info["path"],
                "content_type": "multipart/form-data",
                "schema": content["multipart/form-data"].get("schema", {}),
            }
        # 其次 JSON
        if "application/json" in content:
            return {
                "path": info["path"],
                "content_type": "application/json",
                "schema": content["application/json"].get("schema", {}),
            }
        # 兜底
        return {
            "path": info["path"],
            "content_type": "application/json",
            "schema": {},
        }

    # ---------- 高层：提交一次建模任务 ----------
    def run_modeling(
        self,
        payload: Dict[str, Any],
        file_paths: Optional[Dict[str, Union[str, List[str]]]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """
        payload: 结构化参数（会按 openapi 判断用 JSON 还是 form 字段）
        file_paths: 需要上传的文件，格式示例：
            {
              "files": ["abs.pdf", "data.csv"],  # 或单个字符串
              "extra_doc": "note.md"
            }
        extra_headers: 额外 header，比如鉴权
        """
        body_info = self._infer_request_body()
        if not body_info:
            raise RuntimeError("未在 OpenAPI 中找到 POST /modeling。")

        url = f"{self.base_url}{body_info['path']}"
        headers = extra_headers.copy() if extra_headers else {}

        if body_info["content_type"] == "multipart/form-data":
            data = {}
            files = []

            # 把 payload 当作普通字段放入 data
            # （若后端 schema 有更细字段名，你可以在这里按 schema 重命名）
            for k, v in payload.items():
                data[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)

            # 处理文件
            if file_paths:
                for field, path_or_list in file_paths.items():
                    if isinstance(path_or_list, list):
                        for p in path_or_list:
                            files.append((field, (p.split("\\")[-1], open(p, "rb"))))
                    else:
                        p = path_or_list
                        files.append((field, (p.split("\\")[-1], open(p, "rb"))))

            return requests.post(url, data=data, files=files or None, headers=headers, timeout=self.timeout)

        else:
            # 默认 JSON
            headers["Content-Type"] = "application/json"
            body = payload
            # 如果含文件但接口是 JSON，通常要先把文件放到某个 “上传接口” 返回路径，再把路径放到 JSON；这里只演示直接 JSON。
            return requests.post(url, json=body, headers=headers, timeout=self.timeout)


# —— 一个方便放到 Tk 线程里的简易调用封装 ——
def run_in_thread(fn, on_done=None, on_error=None):
    def _wrap():
        try:
            res = fn()
            if on_done:
                on_done(res)
        except Exception as e:
            if on_error:
                on_error(e)

    t = threading.Thread(target=_wrap, daemon=True)
    t.start()
    return t
