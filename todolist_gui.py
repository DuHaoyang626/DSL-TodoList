"""Simple GUI to view and manage todos stored in MySQL."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
from math import ceil

from tkinter import messagebox, ttk
import mysql.connector
from markdown import markdown
from tkhtmlview import HTMLScrolledText
from tkinter import scrolledtext

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
    def __init__(
        self,
        master: tk.Widget,
        title: str,
        on_toggle: Callable[[Todo], None],
        on_view: Callable[[Todo], None],
        accent: str,
    ) -> None:
        self.on_toggle = on_toggle
        self.on_view = on_view
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
            tile = TodoTile(
                self.inner,
                todo,
                self.on_toggle,
                self.on_view,
                is_completed=is_completed,
                overdue=overdue,
            )
            tile.pack(fill="x", expand=True, pady=6, padx=4)


class TodoTile(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        todo: Todo,
        on_toggle: Callable[[Todo], None],
        on_view: Callable[[Todo], None],
        *,
        is_completed: bool,
        overdue: bool,
    ) -> None:
        bg = "#eafaf1" if is_completed else ("#fdecea" if overdue else "#ffffff")
        super().__init__(master, bg=bg, bd=0, highlightthickness=0, padx=14, pady=10)
        self.todo = todo
        self.on_toggle = on_toggle
        self.on_view = on_view
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
        info.bind("<Button-1>", self._handle_view)
        title_font = ("Microsoft YaHei", 12, "bold")
        meta_font = ("Microsoft YaHei", 10)

        title_label = tk.Label(info, text=todo.title, font=title_font, fg=text_color, bg=bg)
        title_label.pack(anchor="w")
        title_label.bind("<Button-1>", self._handle_view)
        due_text = "无截止时间" if not todo.due_at else todo.due_at.strftime("%Y-%m-%d %H:%M")
        meta_text = f"截止：{due_text}"
        meta_label = tk.Label(info, text=meta_text, font=meta_font, fg="#7f8c8d", bg=bg)
        meta_label.pack(anchor="w", pady=(4, 0))
        meta_label.bind("<Button-1>", self._handle_view)

        badge_text, badge_bg, badge_fg = self._badge_props()
        badge_frame = tk.Frame(self, bg=bg)
        badge_frame.pack(side="right", anchor="n")
        badge_frame.bind("<Button-1>", self._handle_view)
        badge_label = tk.Label(
            badge_frame,
            text=badge_text,
            font=("Microsoft YaHei", 10, "bold"),
            fg=badge_fg,
            bg=badge_bg,
            padx=10,
            pady=4,
        )
        badge_label.pack()
        badge_label.bind("<Button-1>", self._handle_view)

        self._draw_indicator(indicator_color)
        self.bind("<Button-1>", self._handle_view)

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
        return "break"

    def _handle_view(self, _event=None) -> None:
        self.on_view(self.todo)
        return "break"

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


class TodoDetailDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        todo: Todo,
        on_confirm: Callable[[str, Optional[datetime], str], bool],
    ) -> None:
        super().__init__(master)
        self.todo = todo
        self.on_confirm = on_confirm
        self.title("待办详情")
        self.geometry("520x640")
        self.minsize(520, 640)
        self.config(padx=20, pady=20)
        self.grab_set()

        self.no_deadline_var = tk.BooleanVar(value=todo.due_at is None)
        self.completed_var = tk.BooleanVar(value=todo.status == "completed")
        due_str = todo.due_at.strftime("%Y-%m-%d %H:%M") if todo.due_at else ""
        self.due_var = tk.StringVar(value=due_str)

        self._build_header()
        self._build_fields()
        self._build_markdown_section()

    def _build_header(self) -> None:
        header = tk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="待办详情", font=("Microsoft YaHei", 16, "bold")).pack(side="left")

        button_group = tk.Frame(header)
        button_group.pack(side="right")
        tk.Button(button_group, text="✕", command=self.destroy, fg="#c0392b", bd=0, font=("Segoe UI", 14, "bold")).pack(side="left", padx=4)
        tk.Button(button_group, text="✔", command=self._handle_confirm, fg="#27ae60", bd=0, font=("Segoe UI", 14, "bold")).pack(side="left")

    def _build_fields(self) -> None:
        info_frame = ttk.Frame(self)
        info_frame.pack(fill="x", pady=(0, 15))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="标题：", font=("Microsoft YaHei", 11)).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(info_frame, text=self.todo.title, font=("Microsoft YaHei", 11, "bold"), wraplength=360).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(info_frame, text="截止时间 (YYYY-MM-DD HH:MM)：", font=("Microsoft YaHei", 11)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.due_entry = ttk.Entry(info_frame, textvariable=self.due_var, width=30)
        self.due_entry.grid(row=2, column=0, columnspan=2, sticky="we")

        checkbox_frame = ttk.Frame(info_frame)
        checkbox_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(checkbox_frame, text="永不截止", variable=self.no_deadline_var, command=self._toggle_due_entry).pack(side="left", padx=(0, 15))
        ttk.Checkbutton(checkbox_frame, text="标记为完成", variable=self.completed_var).pack(side="left")

        self._toggle_due_entry()

    def _build_markdown_section(self) -> None:
        self.markdown_frame = ttk.Frame(self)
        self.markdown_frame.pack(fill="both", expand=True)
        header = ttk.Frame(self.markdown_frame)
        header.pack(fill="x")

        ttk.Label(header, text="详情 (Markdown)", font=("Microsoft YaHei", 11, "bold")).pack(side="left")
        self.edit_button = ttk.Button(header, text="编辑内容", command=self._switch_to_edit)
        self.edit_button.pack(side="right")
        self.preview_button = ttk.Button(header, text="查看预览", command=self._switch_to_preview, state=tk.DISABLED)
        self.preview_button.pack(side="right", padx=(0, 8))

        self.detail_editor = scrolledtext.ScrolledText(self.markdown_frame, height=12, wrap="word")
        self.detail_editor.insert("1.0", self.todo.details or "")

        self.preview_container = ttk.Frame(self.markdown_frame)
        self.preview_container.pack(fill="both", expand=True, pady=(6, 0))
        self.preview_container.bind("<Double-Button-1>", self._switch_to_edit)

        self.html_view = HTMLScrolledText(
            self.preview_container,
            html=self._render_markdown(self._current_details()),
            width=60,
            height=18,
        )
        self.html_view.pack(fill="both", expand=True)
        self.html_view.bind("<Double-Button-1>", self._switch_to_edit)

        self.edit_mode = False

    def _switch_to_edit(self, _event=None) -> None:
        if self.edit_mode:
            return "break"
        self.edit_mode = True
        self.preview_container.pack_forget()
        self.detail_editor.pack(fill="both", expand=True, pady=(6, 0))
        self.preview_button.configure(state=tk.NORMAL)
        return "break"

    def _switch_to_preview(self) -> None:
        if not self.edit_mode:
            return
        content = self._current_details()
        self.html_view.set_html(self._render_markdown(content))
        self.detail_editor.pack_forget()
        self.preview_container.pack(fill="both", expand=True, pady=(6, 0))
        self.edit_mode = False
        self.preview_button.configure(state=tk.DISABLED)

    def _current_details(self) -> str:
        return self.detail_editor.get("1.0", tk.END).strip()

    def _render_markdown(self, text: Optional[str] = None) -> str:
        body = (text if text is not None else self._current_details()) or "暂无详情"
        return markdown(body, extensions=["fenced_code", "tables"])

    def _toggle_due_entry(self) -> None:
        state = "disabled" if self.no_deadline_var.get() else "normal"
        self.due_entry.configure(state=state)

    def _handle_confirm(self) -> None:
        due_value: Optional[datetime] = None
        if not self.no_deadline_var.get():
            due_str = self.due_var.get().strip()
            if not due_str:
                messagebox.showerror("输入错误", "请输入截止时间或选择永不截止")
                return
            try:
                due_value = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
            except ValueError:
                messagebox.showerror("输入错误", "截止时间格式应为 YYYY-MM-DD HH:MM")
                return

        status = "completed" if self.completed_var.get() else "pending"
        details_md = self.detail_editor.get("1.0", tk.END).strip()
        if self.on_confirm(status, due_value, details_md):
            self.destroy()
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

        self.active_panel = TodoListPanel(left_frame, "未完成", self.mark_complete, self._open_detail, accent="#2980b9")
        self.active_panel.frame.grid(row=0, column=0, sticky="nsew")

        self.completed_panel = TodoListPanel(right_frame, "已完成", self.mark_pending, self._open_detail, accent="#27ae60")
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

    def _open_detail(self, todo: Todo) -> None:
        TodoDetailDialog(
            self.root,
            todo,
            lambda status, due, details: self._apply_detail_change(todo, status, due, details),
        )

    def _apply_detail_change(self, todo: Todo, status: str, due: Optional[datetime], details: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "UPDATE todos SET status=%s, due_at=%s, details=%s WHERE id=%s",
                (status, due, details, todo.todo_id),
            )
            self.conn.commit()
            cursor.close()
        except mysql.connector.Error as exc:
            messagebox.showerror("数据库错误", f"无法更新待办：{exc}")
            return False
        self.refresh_lists()
        return True

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
