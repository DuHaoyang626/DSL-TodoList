"""JSON-based CRUD interface for DSL-TodoList."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import mysql.connector

from db_utils import ensure_schema, get_connection

DATETIME_FMT = "%Y-%m-%d %H:%M"
VALID_STATUS = {"pending", "completed"}


def handle_json_request(payload: str) -> str:
    """Handle a CRUD request encoded as JSON and return a JSON response."""
    ensure_schema()
    try:
        request = json.loads(payload)
    except json.JSONDecodeError:
        return _error("JSON 解析失败")

    action = request.get("action")
    data = request.get("data", {})

    try:
        if action == "create":
            return _success(_create(data))
        if action == "read":
            return _success(_read(data))
        if action == "update":
            return _success(_update(data))
        if action == "delete":
            return _success(_delete(data))
        if action == "list":
            return _success(_list_items(data))
    except ValueError as exc:
        return _error(str(exc))
    except mysql.connector.Error as exc:
        return _error(f"数据库错误: {exc.msg}")

    return _error("不支持的 action")


def _create(data: Dict[str, Any]) -> Dict[str, Any]:
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title 不能为空")
    details = data.get("details")
    due_at = _parse_datetime(data.get("due_at"))
    status = data.get("status", "pending")
    if status not in VALID_STATUS:
        raise ValueError("status 必须是 pending 或 completed")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "INSERT INTO todos (title, details, due_at, status) VALUES (%s, %s, %s, %s)",
        (title, details, due_at, status),
    )
    todo_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return _fetch_by_id(todo_id)


def _read(data: Dict[str, Any]) -> Dict[str, Any]:
    todo_id = data.get("id")
    if not todo_id:
        raise ValueError("读取操作需要 id")
    return _fetch_by_id(int(todo_id))


def _update(data: Dict[str, Any]) -> Dict[str, Any]:
    todo_id = data.get("id")
    if not todo_id:
        raise ValueError("更新操作需要 id")
    todo_id = int(todo_id)

    fields = []
    values: List[Any] = []

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("title 不能为空")
        fields.append("title = %s")
        values.append(title)

    if "details" in data:
        fields.append("details = %s")
        values.append(data.get("details"))

    if "due_at" in data:
        fields.append("due_at = %s")
        values.append(_parse_datetime(data.get("due_at")))

    if "status" in data:
        status = data.get("status")
        if status not in VALID_STATUS:
            raise ValueError("status 必须是 pending 或 completed")
        fields.append("status = %s")
        values.append(status)

    if not fields:
        raise ValueError("更新操作需要至少一个可修改字段")

    values.append(todo_id)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE todos SET {', '.join(fields)} WHERE id = %s", tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return _fetch_by_id(todo_id)


def _delete(data: Dict[str, Any]) -> Dict[str, Any]:
    todo_id = data.get("id")
    if not todo_id:
        raise ValueError("删除操作需要 id")
    todo_id = int(todo_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return {"deleted": deleted}


def _list_items(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = ["SELECT id, title, details, due_at, status FROM todos WHERE 1=1"]
    params: List[Any] = []

    keyword = (filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        query.append("AND (title LIKE %s OR details LIKE %s)")
        params.extend([like, like])

    status = filters.get("status")
    now = datetime.now()
    if status == "pending":
        query.append("AND status = 'pending'")
    elif status == "completed":
        query.append("AND status = 'completed'")
    elif status == "overdue":
        query.append("AND status = 'pending' AND due_at IS NOT NULL AND due_at < %s")
        params.append(now)

    due_from = _parse_optional_datetime(filters.get("due_from"))
    if due_from is not None:
        query.append("AND due_at IS NOT NULL AND due_at >= %s")
        params.append(due_from)

    due_to = _parse_optional_datetime(filters.get("due_to"))
    if due_to is not None:
        query.append("AND due_at IS NOT NULL AND due_at <= %s")
        params.append(due_to)

    query.append("ORDER BY status = 'completed', due_at IS NULL, due_at")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(" ".join(query), tuple(params))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [_serialize_row(row) for row in rows]


def _fetch_by_id(todo_id: int) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, details, due_at, status FROM todos WHERE id = %s", (todo_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        raise ValueError("指定的待办不存在")
    return _serialize_row(row)


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    due_at = row.get("due_at")
    return {
        "id": row["id"],
        "title": row["title"],
        "details": row.get("details"),
        "due_at": due_at.strftime(DATETIME_FMT) if due_at else None,
        "status": row["status"],
    }


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    try:
        return datetime.strptime(str(value), DATETIME_FMT)
    except ValueError as exc:
        raise ValueError("日期格式必须为 YYYY-MM-DD HH:MM") from exc


def _parse_optional_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    return _parse_datetime(value)


def _success(data: Any) -> str:
    return json.dumps({"status": "ok", "data": data}, ensure_ascii=False)


def _error(message: str) -> str:
    return json.dumps({"status": "error", "message": message}, ensure_ascii=False)
