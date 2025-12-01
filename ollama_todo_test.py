"""Quick utility to ask Ollama for TodoList JSON operations."""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import requests

from dsl_todolist.api import handle_json_request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b"
# MODEL_NAME = "llama3.2:3b"
PROMPT_TEMPLATE = """你是一个 TodoList JSON 生成器，只能返回符合 DSL-TodoList 项目所需结构的 JSON。

当前的真实日期和时间是 {current_time}（24 小时制，UTC+8）。如果指令中提及了相对时间，请结合这个时间点进行解析。

输出要求：
1. JSON 顶层包含 action 和 data 两个字段。
2. action 只允许 "create"、"read"、"update"、"delete"、"list"。
3. data 字段的键根据 action 自动调整。例如：
   - create: {{"title": str, "details": str|null, "due_at": "YYYY-MM-DD HH:MM"|null, "status": "pending"|"completed"}}
   - read/delete: {{"id": 正整数}}
   - update: {{"id": 正整数, 其他可选字段同 create}}
   - list: 可包含 keyword、status、due_from、due_to（同样使用 YYYY-MM-DD HH:MM）。
4. 如果无截止时间，用 null。
5. 只返回 JSON，不要任何解释文字、反引号或 Markdown。
 6. 如果你需要删除/更新但无法确认具体 id，可以先返回一个 action 为 "list" 的 JSON，说明筛选条件。
 7. 当补充上下文提供了候选待办列表时，必须基于这些候选生成最终 JSON，并且 id 必须来自列表。

{context_block}

请根据以下自然语言指令生成 JSON：
{instruction}
"""


def _call_ollama(prompt: str) -> str:
    start = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    body: Dict[str, Any] = response.json()
    duration = time.perf_counter() - start

    print("\n=== 发送给大模型的提示 ===")
    print(prompt)
    print(f"=== 模型响应耗时: {duration:.2f} 秒 ===\n")

    return body.get("response", "")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    return json.loads(match.group())


def nl_to_todo_operation(nl_text: str) -> Dict[str, Any]:
    context: Optional[Dict[str, Any]] = None
    for round_idx in range(2):
        prompt = _build_prompt(nl_text, context)
        raw_response = _call_ollama(prompt)
        parsed = _extract_json(raw_response)
        if parsed is None:
            raise ValueError(f"无法从模型响应中提取 JSON: {raw_response}")

        action = parsed.get("action")
        if action == "list" and context is None:
            candidates = _fetch_list_candidates(parsed)
            context = {
                "list_request": parsed,
                "candidates": candidates,
            }
            continue
        if action == "list" and context is not None:
            raise ValueError("已提供候选列表，仍然请求 list，无法确定 id")

        _ensure_action_data(parsed)
        return parsed

    raise ValueError("多轮对话仍未确定待办 id，请重新尝试更精确的指令")


def _build_prompt(nl_text: str, context: Optional[Dict[str, Any]]) -> str:
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
            "你先前请求的列表条件：\n"
            f"{request_str}\n"
            "根据上述条件得到的候选待办列表（JSON 数组）：\n"
            f"{candidates_str}\n"
            "请仅从候选列表中选择合适的 id 来完成最终操作。\n"
        )

    return PROMPT_TEMPLATE.format(
        current_time=f"{now_str}，{weekday_str}",
        instruction=nl_text.strip(),
        context_block=context_block,
    )


def _fetch_list_candidates(list_operation: Dict[str, Any]) -> List[Dict[str, Any]]:
    if list_operation.get("action") != "list":
        raise ValueError("只有 list 操作可以触发候选查询")

    api_result = execute_api(list_operation)
    if api_result.get("status") != "ok":
        message = api_result.get("message", "未知错误")
        raise ValueError(f"列表请求失败: {message}")

    candidates = api_result.get("data")
    if not isinstance(candidates, list) or not candidates:
        filters = json.dumps(list_operation.get("data", {}), ensure_ascii=False)
        raise ValueError(f"列表请求未返回待办（筛选条件: {filters}），无法确定 id")
    return candidates


def _ensure_action_data(operation: Dict[str, Any]) -> None:
    action = operation.get("action")
    data = operation.get("data")
    if not isinstance(data, dict):
        raise ValueError("data 字段必须是对象")

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



def execute_api(operation: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.dumps(operation, ensure_ascii=False)
    response_json = handle_json_request(payload)
    return json.loads(response_json)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert NL instructions to TodoList JSON via Ollama")
    parser.add_argument("instruction", help="自然语言描述，例如：新增一个任务……")
    parser.add_argument("--output", "-o", type=Path, help="可选：将 JSON 保存到文件路径")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只查看模型生成的 JSON，不执行最终的数据库写操作（仍可能读取列表用于辅助决策）",
    )
    args = parser.parse_args()

    try:
        todo_json = nl_to_todo_operation(args.instruction)
    except ValueError as exc:
        print(f"错误: {exc}")
        raise SystemExit(1) from exc
    pretty = json.dumps(todo_json, ensure_ascii=False, indent=2)
    print(pretty)

    if args.output:
        args.output.write_text(pretty, encoding="utf-8")
        print(f"已输出到 {args.output}")

    if args.dry_run:
        return

    api_result = execute_api(todo_json)
    print("\nAPI 执行结果:")
    print(json.dumps(api_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
