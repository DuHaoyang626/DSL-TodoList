"""Simple GUI to view and manage todos stored in MySQL."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from math import ceil

from tkinter import messagebox, ttk
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "DSL-TodoListUser",
    "password": "qwertyui793789",
    "database": "DSL-TodoList",
    "auth_plugin": "mysql_native_password",
}


@dataclass
class Todo:
    todo_id: int
    title: str
    details: Optional[str]
    due_at: Optional[datetime]
    status: str


def ensure_schema() -> None:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            details TEXT NULL,
            due_at DATETIME NULL,
            status ENUM('pending','completed') NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_due_at(due_at),
            INDEX idx_status(status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    conn.commit()
    cursor.close()
    conn.close()


class TodoListPanel:
    def __init__(self, master: tk.Widget, title: str, on_toggle: Callable[[Todo], None], accent: str) -> None:
        self.on_toggle = on_toggle
        self.frame = ttk.Frame(master)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        ttk.Label(self.frame, text=title, font=("Microsoft YaHei", 14, "bold"), foreground=accent).grid(
            row=0, column=0, sticky="w"
        )

        self.canvas = tk.Canvas(self.frame, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=1, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner = tk.Frame(self.canvas, bg="#f5f6fa")
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._sync_inner_width)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.inner.bind("<MouseWheel>", self._on_mousewheel)

    def _update_scrollregion(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_inner_width(self, event: tk.Event) -> None:  # type: ignore[name-defined]
        self.canvas.itemconfigure(self.inner_id, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:  # type: ignore[name-defined]
        delta = -1 * (event.delta // 120)
        self.canvas.yview_scroll(delta, "units")

    def populate(self, todos: List[Todo], overdue_flags: List[bool], is_completed: bool) -> None:
        for child in self.inner.winfo_children():
            child.destroy()
        for todo, overdue in zip(todos, overdue_flags):
            tile = TodoTile(self.inner, todo, self.on_toggle, is_completed=is_completed, overdue=overdue)
            tile.pack(fill="x", expand=True, pady=6, padx=4)


class TodoTile(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        todo: Todo,
        on_toggle: Callable[[Todo], None],
        *,
        is_completed: bool,
        overdue: bool,
    ) -> None:
        bg = "#eafaf1" if is_completed else ("#fdecea" if overdue else "#ffffff")
        super().__init__(master, bg=bg, bd=0, highlightthickness=0, padx=14, pady=10)
        self.todo = todo
        self.on_toggle = on_toggle
        self.is_completed = is_completed
        self.overdue = overdue
        self.bg = bg

        indicator_color = "#27ae60" if is_completed else ("#c0392b" if overdue else "#95a5a6")
        text_color = "#2c3e50" if not overdue else "#c0392b"

        self.indicator = tk.Canvas(self, width=32, height=32, bg=bg, highlightthickness=0, cursor="hand2")
        self.indicator.pack(side="left", padx=(0, 12))
        self.indicator.bind("<Button-1>", self._handle_toggle)

        info = tk.Frame(self, bg=bg)
        info.pack(side="left", fill="both", expand=True)
        title_font = ("Microsoft YaHei", 12, "bold")
        meta_font = ("Microsoft YaHei", 10)

        tk.Label(info, text=todo.title, font=title_font, fg=text_color, bg=bg).pack(anchor="w")
        due_text = "无截止时间" if not todo.due_at else todo.due_at.strftime("%Y-%m-%d %H:%M")
        meta_text = f"截止：{due_text}"
        tk.Label(info, text=meta_text, font=meta_font, fg="#7f8c8d", bg=bg).pack(anchor="w", pady=(4, 0))

        badge_text, badge_bg, badge_fg = self._badge_props()
        badge_frame = tk.Frame(self, bg=bg)
        badge_frame.pack(side="right", anchor="n")
        tk.Label(
            badge_frame,
            text=badge_text,
            font=("Microsoft YaHei", 10, "bold"),
            fg=badge_fg,
            bg=badge_bg,
            padx=10,
            pady=4,
        ).pack()

        self._draw_indicator(indicator_color)

    def _draw_indicator(self, color: str) -> None:
        self.indicator.delete("all")
        self.indicator.create_oval(4, 4, 28, 28, outline=color, width=2, fill="#27ae60" if self.is_completed else self.bg)
        if self.is_completed:
            self.indicator.create_line(10, 17, 14, 22, 22, 12, fill="#ffffff", width=3, capstyle="round")

    def _countdown_text(self, due: Optional[datetime]) -> str:
        if not due:
            return "未设截止"
        delta = due - datetime.now()
        hours = int(delta.total_seconds() // 3600)
        if delta.total_seconds() < 0:
            return "逾期"
        days = delta.days
        if days > 0:
            return f"剩余 {days} 天"
        return f"剩余 {hours} 小时"

    def _handle_toggle(self, _event=None) -> None:
        self.on_toggle(self.todo)

    def _badge_props(self) -> Tuple[str, str, str]:
        if self.is_completed:
            return ("完成", "#27ae60", "#ffffff")
        if self.overdue:
            return ("逾期", "#c0392b", "#ffffff")
        return self._countdown_badge(self.todo.due_at)

    def _countdown_badge(self, due: Optional[datetime]) -> Tuple[str, str, str]:
        if not due:
            return ("未设截止", "#ecf0f1", "#2c3e50")
        delta = due - datetime.now()
        seconds = delta.total_seconds()
        if seconds <= 0:
            return ("逾期", "#c0392b", "#ffffff")
        minutes = ceil(seconds / 60)
        if minutes <= 60:
            return (f"剩余 {minutes} 分钟", "#e67e22", "#ffffff")
        hours = minutes // 60
        if minutes <= 24 * 60:
            return (f"剩余 {hours} 小时", "#f1c40f", "#2c3e50")
        days = hours // 24
        return (f"剩余 {days} 天", "#ffffff", "#2c3e50")


class TodoApp:
    def __init__(self) -> None:
        ensure_schema()
        self.conn = mysql.connector.connect(**DB_CONFIG)

        self.root = tk.Tk()
        self.root.title("DSL Todo List")
        self.root.geometry("1100x640")
        self.root.minsize(960, 540)

        self.active_items: List[Todo] = []
        self.completed_items: List[Todo] = []

        self._build_layout()
        self.refresh_lists()

    def _build_layout(self) -> None:
        # uniform keeps both columns equally wide even when resizing
        self.root.columnconfigure(0, weight=1, uniform="half")
        self.root.columnconfigure(1, weight=1, uniform="half")
        self.root.rowconfigure(0, weight=1)

        left_frame = ttk.Frame(self.root, padding=20)
        left_frame.grid(row=0, column=0, sticky="nsew")
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        right_frame = ttk.Frame(self.root, padding=20)
        right_frame.grid(row=0, column=1, sticky="nsew")
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self.active_panel = TodoListPanel(left_frame, "未完成", self.mark_complete, accent="#2980b9")
        self.active_panel.frame.grid(row=0, column=0, sticky="nsew")

        self.completed_panel = TodoListPanel(right_frame, "已完成", self.mark_pending, accent="#27ae60")
        self.completed_panel.frame.grid(row=0, column=0, sticky="nsew")

    def refresh_lists(self) -> None:
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, title, details, due_at, status
                FROM todos
                ORDER BY status = 'completed', due_at IS NULL, due_at
                """
            )
            records = cursor.fetchall()
            cursor.close()
        except mysql.connector.Error as exc:
            messagebox.showerror("数据库错误", f"无法查询数据: {exc}")
            return

        now = datetime.now()
        self.active_items = []
        self.completed_items = []

        for row in records:
            todo = Todo(
                todo_id=row["id"],
                title=row["title"],
                details=row.get("details"),
                due_at=row.get("due_at"),
                status=row["status"],
            )
            if todo.status == "completed":
                self.completed_items.append(todo)
            else:
                self.active_items.append(todo)

        active_overdue = [bool(todo.due_at and todo.due_at < now) for todo in self.active_items]
        completed_flags = [False] * len(self.completed_items)
        self.active_panel.populate(self.active_items, active_overdue, is_completed=False)
        self.completed_panel.populate(self.completed_items, completed_flags, is_completed=True)

    def mark_complete(self, todo: Todo) -> None:
        self._update_status(todo.todo_id, "completed")
        self.refresh_lists()

    def mark_pending(self, todo: Todo) -> None:
        self._update_status(todo.todo_id, "pending")
        self.refresh_lists()

    def _update_status(self, todo_id: int, status: str) -> None:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE todos SET status=%s WHERE id=%s", (status, todo_id))
            self.conn.commit()
            cursor.close()
        except mysql.connector.Error as exc:
            messagebox.showerror("数据库错误", f"无法更新状态: {exc}")

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self.conn.close()


if __name__ == "__main__":
    app = TodoApp()
    app.run()
