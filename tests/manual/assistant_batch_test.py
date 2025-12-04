"""Batch assistant test harness using the real LLM backend."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.assistant import TodoAssistant

# Edit these before running to force mock behavior without CLI args.
# - USE_MOCK_API: when True, swap the API handler to `dsl_todolist.mock_api`.
# - USE_MOCK_ASSISTANT: when True, use `dsl_todolist.mock_assistant.MockAssistant`.
USE_MOCK_API = False
USE_MOCK_ASSISTANT = False

if USE_MOCK_API:
    try:
        from dsl_todolist import mock_api  # type: ignore
        from dsl_todolist import api as _real_api

        _real_api.handle_json_request = mock_api.handle_json_request  # type: ignore[attr-defined]
    except Exception:
        pass

if USE_MOCK_ASSISTANT:
    try:
        from dsl_todolist.mock_assistant import MockAssistant as _MockAssistant  # type: ignore
    except Exception:
        _MockAssistant = None
else:
    _MockAssistant = None


def parse_cases(path: Path) -> list[tuple[int, str, str, str]]:
    cases: list[tuple[int, str, str, str]] = []
    for idx, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|||")
        if len(parts) != 3:
            raise ValueError(f"行 {idx} 格式错误（需要三段）: {raw_line}")
        nl_input, expected_action, expected_summary = (part.strip() for part in parts)
        cases.append((idx, nl_input, expected_action, expected_summary))
    return cases


def run_cases(cases: list[tuple[int, str, str, str]], apply_changes: bool) -> None:
    if _MockAssistant is not None:
        assistant = _MockAssistant()
    else:
        assistant = TodoAssistant()
    results = []
    for idx, nl_input, expected_action, expected_summary in cases:
        try:
            result = assistant.run_instruction(nl_input, apply_changes=apply_changes)
            action = result.operation.get("action")
            summary = result.summary
            ok = action == expected_action
            results.append((idx, ok, nl_input, expected_action, expected_summary, action, summary, result.operation))
            if ok:
                print(f"CASE {idx}: 正确")
            else:
                print(
                    f"CASE {idx}: 错误\n"
                    f"  指令: {nl_input}\n"
                    f"  期望 action={expected_action},\n"
                    f"  实际 action={action},\n"
                    f"  完整操作: {json.dumps(result.operation, ensure_ascii=False)}"
                )
        except Exception as exc:
            print(f"CASE {idx}: 错误 - {exc}")
            results.append((idx, False, nl_input, expected_action, expected_summary, None, str(exc), None))

    # Summary
    passed = sum(1 for _idx, ok, *_rest in results if ok)
    total = len(results)
    print("\n=== Summary ===")
    print(f"通过: {passed}/{total}")
    for idx, ok, *_rest in results:
        print(f"CASE {idx}: {'正确' if ok else '错误'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch assistant test runner (real LLM)")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("assistant_cases.txt"),
        help="批量测试用例（nl_input|||expected_action|||expected_summary）",
    )
    parser.add_argument(
        "--no-apply",
        action="store_true",
        help="仅生成 JSON，不调用后端 API",
    )
    args = parser.parse_args()
    cases = parse_cases(args.cases)
    if not cases:
        print("未找到任何测试用例")
        return
    run_cases(cases, apply_changes=not args.no_apply)


if __name__ == "__main__":
    main()
