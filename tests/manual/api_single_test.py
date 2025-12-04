"""Interactive single API test harness.

This script prompts the user for a raw JSON payload, forwards it to
`dsl_todolist.api.handle_json_request`, and prints the JSON response.
"""
from __future__ import annotations

import json

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.api import handle_json_request

# Edit these before running to force mock behavior without CLI args.
# - USE_MOCK_API: when True, swap the API handler to `dsl_todolist.mock_api`.
USE_MOCK_API = False

if USE_MOCK_API:
    try:
        from dsl_todolist import mock_api  # type: ignore
        handle_json_request = mock_api.handle_json_request  # type: ignore[attr-defined]
    except Exception:
        # ignore import errors here; running without mock_api available will raise later
        pass


def main() -> None:
    print("=== 单次 API 测试 ===")
    print("请输入完整的 JSON 请求，例如: {\"action\": \"list\", \"data\": {}}")
    try:
        raw = input("Payload> ").strip()
    except EOFError:
        print("未输入任何内容，退出。")
        return

    if not raw:
        print("空输入，退出。")
        return

    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"输入的 JSON 无法解析: {exc}")
        return

    response = handle_json_request(raw)
    print("=== API 响应 ===")
    print(response)


if __name__ == "__main__":
    main()
