"""Quick utility to ask Ollama for TodoList JSON operations."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

PROMPT_TEMPLATE = """你是一个 TodoList JSON 生成器，只能返回符合 DSL-TodoList 项目所需结构的 JSON。

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

请根据以下自然语言指令生成 JSON：
{instruction}
"""


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    body: Dict[str, Any] = response.json()
    return body.get("response", "")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    return json.loads(match.group())


def nl_to_todo_operation(nl_text: str) -> Dict[str, Any]:
    prompt = PROMPT_TEMPLATE.format(instruction=nl_text.strip())
    raw_response = _call_ollama(prompt)
    parsed = _extract_json(raw_response)
    if parsed is None:
        raise ValueError(f"无法从模型响应中提取 JSON: {raw_response}")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert NL instructions to TodoList JSON via Ollama")
    parser.add_argument("instruction", help="自然语言描述，例如：新增一个任务……")
    parser.add_argument("--output", "-o", type=Path, help="可选：将 JSON 保存到文件路径")
    args = parser.parse_args()

    todo_json = nl_to_todo_operation(args.instruction)
    pretty = json.dumps(todo_json, ensure_ascii=False, indent=2)
    print(pretty)

    if args.output:
        args.output.write_text(pretty, encoding="utf-8")
        print(f"已输出到 {args.output}")


if __name__ == "__main__":
    main()
