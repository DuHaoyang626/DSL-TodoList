"""Interactive single assistant test using the real LLM backend."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.assistant import TodoAssistant


def main() -> None:
    parser = argparse.ArgumentParser(description="Single assistant test runner (real LLM)")
    parser.add_argument(
        "--text",
        help="可选: 直接提供自然语言指令；若缺省则在终端交互输入",
    )
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="仅生成 JSON，不调用后端 API",
    )
    args = parser.parse_args()

    nl_text = args.text
    if not nl_text:
        print("请输入自然语言指令，按 Enter 确认 (Ctrl+C 退出)。")
        try:
            nl_text = input("NL> ").strip()
        except EOFError:
            print("未输入任何内容，退出。")
            return
    if not nl_text:
        print("空指令，退出。")
        return

    assistant = TodoAssistant()
    result = assistant.run_instruction(nl_text, apply_changes=not args.no_apply)
    print("=== Assistant Operation ===")
    print(json.dumps(result.operation, ensure_ascii=False, indent=2))
    print("=== Summary ===")
    print(result.summary)
    if result.api_response is not None:
        print("=== API Response ===")
        print(json.dumps(result.api_response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
