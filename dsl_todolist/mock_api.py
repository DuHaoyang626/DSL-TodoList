"""In-memory mock API for testing the GUI without a real database.

This exposes `handle_json_request(payload: str) -> str` with the same
response shape as the real `dsl_todolist.api` so the GUI can swap it in.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

DATETIME_FMT = "%Y-%m-%d %H:%M"

# Simple in-memory store
_store: List[Dict[str, Any]] = []
_next_id = 1


def _now_str() -> str:
    return datetime.now().strftime(DATETIME_FMT)


def handle_json_request(payload: str) -> str:
    global _store, _next_id
    try:
        req = json.loads(payload)
    except json.JSONDecodeError:
        return json.dumps({"status": "error", "message": "JSON 解析失败"}, ensure_ascii=False)

    action = req.get("action")
    data = req.get("data") or {}

    try:
        if action == "create":
            title = (data.get("title") or "").strip()
            if not title:
                return json.dumps({"status": "error", "message": "title 不能为空"}, ensure_ascii=False)
            details = data.get("details")
            due_at = data.get("due_at")
            status = data.get("status", "pending")
            item = {"id": _next_id, "title": title, "details": details, "due_at": due_at, "status": status}
            _store.append(item)
            _next_id += 1
            return json.dumps({"status": "ok", "data": item}, ensure_ascii=False)

        if action == "read":
            todo_id = data.get("id")
            if not todo_id:
                return json.dumps({"status": "error", "message": "读取操作需要 id"}, ensure_ascii=False)
            for row in _store:
                if row["id"] == int(todo_id):
                    return json.dumps({"status": "ok", "data": row}, ensure_ascii=False)
            return json.dumps({"status": "error", "message": "指定的待办不存在"}, ensure_ascii=False)

        if action == "update":
            todo_id = data.get("id")
            if not todo_id:
                return json.dumps({"status": "error", "message": "更新操作需要 id"}, ensure_ascii=False)
            todo_id = int(todo_id)
            for row in _store:
                if row["id"] == todo_id:
                    if "title" in data:
                        row["title"] = (data.get("title") or "").strip()
                    if "details" in data:
                        row["details"] = data.get("details")
                    if "due_at" in data:
                        row["due_at"] = data.get("due_at")
                    if "status" in data:
                        row["status"] = data.get("status")
                    return json.dumps({"status": "ok", "data": row}, ensure_ascii=False)
            return json.dumps({"status": "error", "message": "指定的待办不存在"}, ensure_ascii=False)

        if action == "delete":
            todo_id = data.get("id")
            if not todo_id:
                return json.dumps({"status": "error", "message": "删除操作需要 id"}, ensure_ascii=False)
            todo_id = int(todo_id)
            for i, row in enumerate(_store):
                if row["id"] == todo_id:
                    _store.pop(i)
                    return json.dumps({"status": "ok", "data": {"deleted": 1}}, ensure_ascii=False)
            return json.dumps({"status": "ok", "data": {"deleted": 0}}, ensure_ascii=False)

        if action == "list":
            # very small subset of filter support: keyword & status
            keyword = (data.get("keyword") or "").strip()
            status = data.get("status")
            results = []
            for row in _store:
                if keyword:
                    if keyword not in (row.get("title") or "") and keyword not in (row.get("details") or ""):
                        continue
                if status:
                    if status == "overdue":
                        # simple check: due_at exists and is older than now
                        if not row.get("due_at"):
                            continue
                        try:
                            due = datetime.strptime(row.get("due_at"), DATETIME_FMT)
                        except Exception:
                            continue
                        if due >= datetime.now():
                            continue
                    elif row.get("status") != status:
                        continue
                results.append(row)
            return json.dumps({"status": "ok", "data": results}, ensure_ascii=False)

        return json.dumps({"status": "error", "message": "不支持的 action"}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)
