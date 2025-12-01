"""LLM-powered assistant for TodoList operations."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

from .api import handle_json_request

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen3:4b"
# DEFAULT_MODEL = "gemma3:1b"
# DEFAULT_MODEL = "deepseek-r1:8b"
# DEFAULT_MODEL = "qwen3:30b"
# DEFAULT_MODEL = "qwen3:4b"
# DEFAULT_MODEL = "llama3.2:3b"

PROMPT_TEMPLATE = """你是一个 TodoList 智能助手，需要输出符合 DSL-TodoList 项目所需结构的 JSON。

当前的真实日期和时间是 {current_time}（24 小时制，UTC+8）。如果指令中提及了相对时间，请结合这个时间点进行解析。

输出要求：
1. JSON 顶层必须包含 action、data、summary 三个字段。
2. action 只允许 "create"、"read"、"update"、"delete"、"list"。
3. data 字段根据 action 自动调整。例如：
   - create: {{"title": str, "details": str|null, "due_at": "YYYY-MM-DD HH:MM"|null, "status": "pending"|"completed"}}
   - read/delete: {{"id": 正整数}}
   - update: {{"id": 正整数, 其他可选字段同 create}}
   - list: 可包含 keyword、status、due_from、due_to。
4. summary 是一句 20 字以内的中文概括，描述该操作的目的或结果。
5. 如果无截止时间，用 null。
6. 只返回 JSON，不要任何解释文字、反引号或 Markdown。
7. 如果你需要删除/更新但无法确认具体 id，可以先返回一个 action 为 "list" 的 JSON，说明筛选条件。
8. 当补充上下文提供了候选待办列表时，必须基于这些候选生成最终 JSON，并且 id 必须来自列表。

{context_block}

请根据以下自然语言指令生成 JSON：
{instruction}
"""


@dataclass
class AssistantResult:
    """Structured result returned by the Todo assistant."""

    operation: Dict[str, Any]
    summary: str
    api_response: Optional[Dict[str, Any]]


class TodoAssistant:
    """Facade around the Ollama API that enforces the TodoList DSL."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_OLLAMA_URL,
        timeout: int = 120,
        verbose: bool = False,
    ) -> None:
        self.model_name = model_name
        self.endpoint = endpoint
        self.timeout = timeout
        self.verbose = verbose

    def run_instruction(self, nl_text: str, *, apply_changes: bool = True) -> AssistantResult:
        """Convert NL text into a JSON operation and optionally execute it."""

        operation, summary = self._nl_to_todo_operation(nl_text)
        api_response: Optional[Dict[str, Any]] = None
        if apply_changes:
            api_response = self._execute_operation(operation)
        return AssistantResult(operation=operation, summary=summary, api_response=api_response)

    # ==== Core flow ========================================================
    def _nl_to_todo_operation(self, nl_text: str) -> Tuple[Dict[str, Any], str]:
        context: Optional[Dict[str, Any]] = None
        for _ in range(2):
            prompt = self._build_prompt(nl_text, context)
            raw_response = self._call_model(prompt)
            parsed = self._extract_json(raw_response)
            if parsed is None:
                raise ValueError(f"无法从模型响应中提取 JSON: {raw_response}")

            action = parsed.get("action")
            summary = parsed.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("模型响应缺少 summary 或 summary 为空")

            if action == "list" and context is None:
                candidates = self._fetch_list_candidates(parsed)
                context = {
                    "list_request": parsed,
                    "candidates": candidates,
                }
                continue
            if action == "list" and context is not None:
                raise ValueError("已提供候选列表，仍然返回 list，无法确定 id")

            self._ensure_action_data(parsed)
            return parsed, summary.strip()

        raise ValueError("多轮对话仍未确定待办 id，请尝试提供更精确的信息")

    def _execute_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        action = operation.get("action")
        data = operation.get("data") or {}
        if not isinstance(action, str):
            raise ValueError("操作缺少 action 字段")
        response = self._call_api(action, data)
        return response

    # ==== Helpers ==========================================================
    def _build_prompt(self, nl_text: str, context: Optional[Dict[str, Any]]) -> str:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")
        weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
        weekday_str = f"今天是星期{weekday_map[now.weekday()]}"
        context_block = ""
        if context:
            request_str = json.dumps(context.get("list_request"), ensure_ascii=False, indent=2)
            candidates_str = json.dumps(context.get("candidates"), ensure_ascii=False, indent=2)
            context_block = (
                "\n=== 补充上下文 ===\n"
                "你先前的列表请求：\n"
                f"{request_str}\n"
                "根据该条件得到的候选待办（JSON 数组）：\n"
                f"{candidates_str}\n"
                "请仅从这些候选中挑选合适的 id 来完成最终操作。\n"
            )

        return PROMPT_TEMPLATE.format(
            current_time=f"{now_str}，{weekday_str}",
            instruction=nl_text.strip(),
            context_block=context_block,
        )

    def _call_model(self, prompt: str) -> str:
        payload = {"model": self.model_name, "prompt": prompt, "stream": False}
        start = time.perf_counter()
        try:
            response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"调用大模型失败: {exc}") from exc

        duration = time.perf_counter() - start
        body: Dict[str, Any] = response.json()
        print("\n=== LLM Prompt ===")
        print(prompt)
        print(f"=== LLM 耗时: {duration:.2f} 秒 ===")
        raw_response = body.get("response", "")
        print("=== LLM Response ===")
        print(raw_response)
        return raw_response

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        return json.loads(match.group())

    def _fetch_list_candidates(self, list_operation: Dict[str, Any]) -> List[Dict[str, Any]]:
        if list_operation.get("action") != "list":
            raise ValueError("只有 list 操作可以触发候选查询")
        filters = list_operation.get("data") or {}
        response = self._call_api("list", filters)
        candidates = response.get("data")
        if not isinstance(candidates, list) or not candidates:
            filter_str = json.dumps(filters, ensure_ascii=False)
            raise ValueError(f"列表请求未返回任何待办（筛选条件: {filter_str}），无法确定 id")
        return candidates

    def _ensure_action_data(self, operation: Dict[str, Any]) -> None:
        data = operation.get("data")
        if not isinstance(data, dict):
            raise ValueError("data 字段必须是对象")
        action = operation.get("action")
        if action in {"update", "delete"}:
            todo_id = data.get("id")
            if todo_id is None:
                raise ValueError("更新/删除操作需要具体的 id")
            if not isinstance(todo_id, int):
                try:
                    data["id"] = int(todo_id)
                except (TypeError, ValueError) as exc:
                    raise ValueError("id 必须是正整数") from exc
            if data["id"] <= 0:
                raise ValueError("id 必须是正整数")

    def _call_api(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps({"action": action, "data": data}, ensure_ascii=False)
        response = json.loads(handle_json_request(payload))
        print("\n=== API 调用 (LLM) ===")
        print(json.dumps({"action": action, "data": data}, ensure_ascii=False, indent=2))
        print("=== API 结果 ===")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        if response.get("status") != "ok":
            raise ValueError(response.get("message", "未知错误"))
        return response