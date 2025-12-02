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

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_FILES = {
    "router": PROMPT_DIR / "router.dsl",
    "create": PROMPT_DIR / "create.dsl",
    "read": PROMPT_DIR / "read.dsl",
    "list": PROMPT_DIR / "list.dsl",
    "delete_request": PROMPT_DIR / "delete_request.dsl",
    "delete_select": PROMPT_DIR / "delete_select.dsl",
    "update_request": PROMPT_DIR / "update_request.dsl",
    "update_select": PROMPT_DIR / "update_select.dsl",
}
ALLOWED_ACTIONS = {"create", "read", "update", "delete", "list", "noop"}


MODEL_PROVIDER = "deepseek"  # options: "ollama" or "deepseek"

# Deepseek / online model configuration (set your API key and model here)
# WARNING: storing API keys in source is insecure for production. This follows your request.
DEEPSEEK_API_KEY = "sk-75962c66cc36455ea3a33af41297456a"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


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
        self._prompt_cache: Dict[str, str] = {}

    def run_instruction(self, nl_text: str, *, apply_changes: bool = True) -> AssistantResult:
        """Convert NL text into a JSON operation and optionally execute it."""

        operation, summary = self._nl_to_todo_operation(nl_text)
        api_response: Optional[Dict[str, Any]] = None
        # 如果路由返回 noop，表示输入无意义，前端仅展示 summary，不执行任何 API 操作
        if apply_changes and operation.get("action") != "noop":
            api_response = self._execute_operation(operation)
        return AssistantResult(operation=operation, summary=summary, api_response=api_response)

    # ==== Core flow ========================================================
    def _nl_to_todo_operation(self, nl_text: str) -> Tuple[Dict[str, Any], str]:
        action = self._route_action(nl_text)
        # special-case noop: router determined input is meaningless
        if action == "noop":
            operation = {"action": "noop", "data": {}, "summary": "无意义的操作"}
            return operation, operation["summary"]
        if action == "create":
            operation = self._run_operation_prompt("create", nl_text, expected_action="create")
        elif action == "list":
            operation = self._run_operation_prompt("list", nl_text, expected_action="list")
        elif action == "read":
            operation = self._run_operation_prompt("read", nl_text, expected_action="read")
        elif action == "delete":
            operation = self._handle_delete_flow(nl_text)
        elif action == "update":
            operation = self._handle_update_flow(nl_text)
        else:
            raise ValueError(f"不支持的 action: {action}")

        summary = operation.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("模型响应缺少 summary 或 summary 为空")

        self._ensure_action_data(operation)
        return operation, summary.strip()

    def _route_action(self, nl_text: str) -> str:
        parsed = self._invoke_prompt("router", nl_text, context=None)
        action = parsed.get("action")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"路由脚本返回了非法 action: {action}")
        return action

    def _run_operation_prompt(
        self,
        template_name: str,
        instruction: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        expected_action: Optional[str] = None,
    ) -> Dict[str, Any]:
        parsed = self._invoke_prompt(template_name, instruction, context)
        action = parsed.get("action")
        if not isinstance(action, str):
            raise ValueError(f"{template_name} 模型响应缺少 action 字段")
        if expected_action and action != expected_action:
            raise ValueError(f"{template_name} 模板期望 action={expected_action}，实际为 {action}")
        return parsed

    def _invoke_prompt(
        self,
        template_name: str,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(template_name, instruction, context)
        raw_response = self._call_model(prompt)
        parsed = self._extract_json(raw_response)
        if parsed is None:
            raise ValueError(f"无法从模型响应中提取 JSON: {raw_response}")
        return parsed

    def _handle_delete_flow(self, nl_text: str) -> Dict[str, Any]:
        stage1 = self._run_operation_prompt("delete_request", nl_text)
        action = stage1.get("action")
        if action == "delete":
            return stage1
        if action != "list":
            raise ValueError("删除流程第一阶段需返回 delete 或 list")
        candidates = self._fetch_list_candidates(stage1)
        context = {
            "list_request": stage1,
            "candidates": candidates,
            "hint": "只能从 candidates 中挑选 id 用于删除",
        }
        return self._run_operation_prompt(
            "delete_select",
            nl_text,
            context=context,
            expected_action="delete",
        )

    def _handle_update_flow(self, nl_text: str) -> Dict[str, Any]:
        stage1 = self._run_operation_prompt("update_request", nl_text)
        action = stage1.get("action")
        if action == "update":
            return stage1
        if action != "list":
            raise ValueError("更新流程第一阶段需返回 update 或 list")
        candidates = self._fetch_list_candidates(stage1)
        context = {
            "list_request": stage1,
            "candidates": candidates,
            "hint": "只能从 candidates 中挑选 id 并按照原始需求更新字段",
        }
        return self._run_operation_prompt(
            "update_select",
            nl_text,
            context=context,
            expected_action="update",
        )

    def _execute_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        action = operation.get("action")
        data = operation.get("data") or {}
        if not isinstance(action, str):
            raise ValueError("操作缺少 action 字段")
        response = self._call_api(action, data)
        return response

    # ==== Helpers ==========================================================
    def _build_prompt(self, template_name: str, instruction: str, context: Optional[Dict[str, Any]]) -> str:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")
        weekday_map = ["一", "二", "三", "四", "五", "六", "日"]
        weekday_str = f"今天是星期{weekday_map[now.weekday()]}"
        context_block = self._format_context_block(context)
        template = self._load_prompt_template(template_name)
        return template.format(
            current_time=f"{now_str}，{weekday_str}",
            instruction=instruction.strip(),
            context_block=context_block,
        )

    def _load_prompt_template(self, name: str) -> str:
        if name not in PROMPT_FILES:
            raise ValueError(f"未知的模板: {name}")
        if name not in self._prompt_cache:
            path = PROMPT_FILES[name]
            if not path.exists():
                raise FileNotFoundError(f"未找到 DSL 提示词文件: {path}")
            self._prompt_cache[name] = path.read_text(encoding="utf-8")
        return self._prompt_cache[name]

    def _format_context_block(self, context: Optional[Dict[str, Any]]) -> str:
        if not context:
            return "NONE"
        return json.dumps(context, ensure_ascii=False, indent=2)

    def _call_model(self, prompt: str) -> str:
        # Branch by provider so switching is a single-constant change.
        provider = MODEL_PROVIDER.lower() if isinstance(MODEL_PROVIDER, str) else "ollama"
        if provider == "ollama":
            payload = {"model": self.model_name, "prompt": prompt, "stream": False}
            start = time.perf_counter()
            try:
                response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"调用本地 Ollama 失败: {exc}") from exc

            duration = time.perf_counter() - start
            body: Dict[str, Any] = response.json()
            print("\n=== LLM Prompt (ollama) ===")
            print(prompt)
            print(f"=== LLM 耗时: {duration:.2f} 秒 ===")
            raw_response = body.get("response", "")
            print("=== LLM Response ===")
            print(raw_response)
            return raw_response

        if provider == "deepseek":
            # Use OpenAI-compatible SDK (user must install `openai` and set DEEPSEEK_API_KEY)
            try:
                from openai import OpenAI
            except Exception as exc:  # pragma: no cover - runtime dependency
                raise RuntimeError("缺少 openai SDK。请运行: pip install openai") from exc

            api_key = DEEPSEEK_API_KEY
            if not api_key or api_key.startswith("<PUT_"):
                raise RuntimeError("请在代码中将 DEEPSEEK_API_KEY 设置为有效的 Deepseek API Key（不要使用环境变量）。")

            client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)

            # Build a short chat-style conversation. The DSL prompt becomes the user's message.
            messages = [
                {"role": "system", "content": "你是一个 TodoList 智能助手，输出仅为符合规范的 JSON。"},
                {"role": "user", "content": prompt},
            ]
            try:
                resp = client.chat.completions.create(model=DEEPSEEK_MODEL, messages=messages, stream=False)
            except Exception as exc:
                raise RuntimeError(f"调用 Deepseek API 失败: {exc}") from exc

            # resp.choices[0].message.content expected per the SDK example
            try:
                content = resp.choices[0].message.content
            except Exception:
                # Fallback: try to stringify response
                content = str(resp)

            print("\n=== LLM Prompt (deepseek) ===")
            print(prompt)
            print("=== LLM Response ===")
            print(content)
            return content

        raise RuntimeError(f"未知的模型提供者: {MODEL_PROVIDER}")

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