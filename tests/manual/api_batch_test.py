"""Batch API test harness based on plain-text cases.

Each non-empty, non-comment line in the cases file must be in the form:
    <json payload>|||<expected substring>
If the substring is contained in the API result, the script prints "正确";
otherwise it prints an error message for that line.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.api import handle_json_request

# Edit these before running to force mock behavior without CLI args.
# - USE_MOCK_API: when True, swap the API handler to `dsl_todolist.mock_api`.
# - USE_MOCK_ASSISTANT: present for parity with other scripts (unused here).
USE_MOCK_API = False

if USE_MOCK_API:
    try:
        from dsl_todolist import mock_api  # type: ignore
        handle_json_request = mock_api.handle_json_request  # type: ignore[attr-defined]
    except Exception:
        # allow the script to run and error later if mock_api not available
        pass


def run_case(line_no: int, payload: str, expected: str) -> None:
    response = handle_json_request(payload)
    if expected in response:
        print(f"CASE {line_no}: 正确")
        return True
    else:
        print(f"CASE {line_no}: 错误\n  期望包含: {expected}\n  实际响应: {response}")
        return False


def parse_cases(path: Path) -> list[tuple[int, str, str]]:
    cases: list[tuple[int, str, str]] = []
    for idx, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            payload, expected = line.split("|||", 1)
        except ValueError as exc:  # pragma: no cover - manual usage guard
            raise ValueError(f"第 {idx} 行缺少 '|||' 分隔符: {raw_line}") from exc
        cases.append((idx, payload.strip(), expected.strip()))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch test runner for API JSON interface")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("api_cases.txt"),
        help="路径: 包含 JSON|||expected substring 的测试用例文件",
    )
    args = parser.parse_args()
    cases = parse_cases(args.cases)
    if not cases:
        print("未找到任何测试用例")
        return
    results = []
    for line_no, payload, expected in cases:
        ok = run_case(line_no, payload, expected)
        results.append((line_no, ok))

    # Summary
    passed = sum(1 for _n, ok in results if ok)
    total = len(results)
    print("\n=== Summary ===")
    print(f"通过: {passed}/{total}")
    for line_no, ok in results:
        print(f"CASE {line_no}: {'正确' if ok else '错误'}")


if __name__ == "__main__":
    main()
