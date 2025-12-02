"""LLM-powered assistant for TodoList operations."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "todo_prompt.dsl"


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
        self._prompt_template: Optional[str] = None

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
        context_block = self._format_context_block(context)
        template = self._load_prompt_template()
        return template.format(
            current_time=f"{now_str}，{weekday_str}",
            instruction=nl_text.strip(),
            context_block=context_block,
        )

    def _load_prompt_template(self) -> str:
        if self._prompt_template is None:
            if not PROMPT_FILE.exists():
                raise FileNotFoundError(f"未找到 DSL 提示词文件: {PROMPT_FILE}")
            self._prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
        return self._prompt_template

    def _format_context_block(self, context: Optional[Dict[str, Any]]) -> str:
        if not context:
            return "无补充上下文"
        request_str = json.dumps(context.get("list_request"), ensure_ascii=False, indent=2)
        candidates_str = json.dumps(context.get("candidates"), ensure_ascii=False, indent=2)
        return (
            "你已经执行过一次列表操作，以下是模型必须参考的补充信息：\n"
            "LIST_REQUEST:\n"
            f"{request_str}\n"
            "CANDIDATES (JSON Array):\n"
            f"{candidates_str}\n"
            "后续所有 delete/update 指令必须从上述候选的 id 中挑选。"
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