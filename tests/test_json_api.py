"""Interactive JSON API runner that consumes JSON files step by step.

The real database is used directly (no reset between steps). Each JSON fixture
describes a single request and optional expectations. After a file finishes
executing the script will prompt for the next JSON path so you can chain the
four CRUD actions in whatever order you need.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dsl_todolist.db import ensure_schema
from dsl_todolist.api import handle_json_request


def main() -> None:
    parser = argparse.ArgumentParser(description="Run JSON fixtures sequentially")
    parser.add_argument(
        "fixture",
        nargs="?",
        help="optional path to the first JSON file (otherwise you will be prompted)",
    )
    args = parser.parse_args()

    ensure_schema()
    context: Dict[str, Any] = {"last": None}
    next_file = args.fixture

    while True:
        if not next_file:
            next_file = input("下一步 JSON 文件路径 (直接回车退出): ").strip()
            if not next_file:
                print("流程结束。")
                break

        try:
            response = _execute_fixture(Path(next_file), context)
        except Exception as exc:  # pragma: no cover - interactive diagnostics
            print(f"[ERROR] {exc}")
        else:
            context["last"] = response
        finally:
            next_file = None


def _execute_fixture(path: Path, context: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"找不到文件: {path}")

    fixture = json.loads(path.read_text(encoding="utf-8"))
    description = fixture.get("description")
    if description:
        print(f"\n=== {description} ===")
    print(f"执行文件: {path}")

    request = fixture.get("request", fixture)
    request = _resolve_refs(request, context)
    request_json = json.dumps(request, ensure_ascii=False)
    print(f"请求: {request_json}")

    response_json = handle_json_request(request_json)
    print(f"响应: {response_json}")
    response = json.loads(response_json)

    expected = fixture.get("expect")
    if expected is not None:
        _assert_subset(_resolve_refs(expected, context), response)
        print("字段校验通过。")

    expected_len = fixture.get("expect_len")
    if expected_len is not None:
        data = response.get("data")
        if not isinstance(data, list):
            raise AssertionError("expect_len 只能用于列表响应")
        if len(data) != expected_len:
            raise AssertionError(
                f"列表长度期望 {expected_len} 实际 {len(data)}"
            )
        print("列表长度校验通过。")

    return response


def _resolve_refs(payload: Any, context: Dict[str, Any]) -> Any:
    if isinstance(payload, dict):
        if set(payload.keys()) == {"$ref"}:
            return _lookup_context(context, payload["$ref"])
        return {key: _resolve_refs(value, context) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_resolve_refs(item, context) for item in payload]
    return payload


def _lookup_context(context: Dict[str, Any], ref: str) -> Any:
    if ref == "last":
        return context.get("last")

    current: Any = context.get("last")
    if current is None:
        raise ValueError("尚未有可引用的上一步响应，先运行 create 测试。")

    for part in ref.split('.'):
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"last 中缺少字段: {part}")
            current = current[part]
        elif isinstance(current, list):
            if not part.isdigit():
                raise ValueError(f"不能在 list 上使用非数字索引: {part}")
            index = int(part)
            if index >= len(current):
                raise IndexError(f"list 索引越界: {part}")
            current = current[index]
        else:
            raise ValueError(f"无法解析引用: {ref}")

    return current


def _assert_subset(expected: Dict[str, Any], actual: Dict[str, Any]) -> None:
    for key, value in expected.items():
        if isinstance(value, dict):
            if key not in actual:
                raise AssertionError(f"响应缺少字段 {key}")
            _assert_subset(value, actual[key])
        else:
            if actual.get(key) != value:
                raise AssertionError(f"字段 {key} 期望 {value} 实际 {actual.get(key)}")


if __name__ == "__main__":
    main()
