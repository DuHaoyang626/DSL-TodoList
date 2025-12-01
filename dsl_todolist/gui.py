"""Tkinter GUI for viewing and managing todos through the JSON API."""
from __future__ import annotations

import json
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Callable, List, Optional, Tuple

from markdown import markdown
from tkhtmlview import HTMLScrolledText
from tkinter import messagebox, scrolledtext, ttk

from .api import handle_json_request
from .assistant import AssistantResult, TodoAssistant
from .db import ensure_schema

DATETIME_FMT = "%Y-%m-%d %H:%M"


@dataclass
class Todo:
    todo_id: int
    title: str
    details: Optional[str]
    due_at: Optional[datetime]
    status: str


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
        self.content_row = 1 if title else 0
        self.frame.rowconfigure(self.content_row, weight=1)

        if title:
            ttk.Label(
                self.frame,
                text=title,
                font=("Microsoft YaHei", 14, "bold"),
                foreground=accent,
            ).grid(row=0, column=0, sticky="w")

        self.canvas = tk.Canvas(self.frame, highlightthickness=0)
        self.canvas.grid(row=self.content_row, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollbar.grid(row=self.content_row, column=1, sticky="ns")
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
        due_text = "无截止时间" if not todo.due_at else todo.due_at.strftime(DATETIME_FMT)
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


class AssistantChatPanel:
    """Right-side chat panel that proxies NL requests to the Todo assistant."""

    def __init__(
        self,
        master: tk.Widget,
        assistant: TodoAssistant,
        on_operation_applied: Callable[[], None],
    ) -> None:
        self.assistant = assistant
        self.on_operation_applied = on_operation_applied

        self.frame = ttk.Frame(master)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)

        header = ttk.Frame(self.frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Copilot 助手", font=("Microsoft YaHei", 14, "bold")).grid(row=0, column=0, sticky="w")

        self.chat_display = scrolledtext.ScrolledText(
            self.frame,
            wrap="word",
            state=tk.DISABLED,
            font=("Microsoft YaHei", 10),
        )
        self.chat_display.grid(row=1, column=0, sticky="nsew")

        input_frame = ttk.Frame(self.frame)
        input_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        input_frame.columnconfigure(0, weight=1)

        self.input_box = tk.Text(input_frame, height=4, wrap="word")
        self.input_box.grid(row=0, column=0, sticky="ew")
        self.input_box.bind("<Control-Return>", self._on_send_event)

        button_column = ttk.Frame(input_frame)
        button_column.grid(row=0, column=1, padx=(8, 0), sticky="ns")
        self.send_button = ttk.Button(button_column, text="发送", command=self._on_send_click, width=8)
        self.send_button.pack(fill="x")
        self.status_var = tk.StringVar(value="")
        ttk.Label(button_column, textvariable=self.status_var, foreground="#7f8c8d").pack(pady=(6, 0))

        self._append_message("助手", "你好！请用自然语言描述想要执行的待办操作。")

    def _append_message(self, role: str, message: str) -> None:
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[{role}] {message}\n\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _on_send_event(self, _event=None):  # type: ignore[override]
        self._on_send_click()
        return "break"

    def _on_send_click(self) -> None:
        text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return
        self.input_box.delete("1.0", tk.END)
        self._append_message("用户", text)
        self._set_busy(True)
        worker = threading.Thread(target=self._process_message, args=(text,), daemon=True)
        worker.start()

    def _process_message(self, text: str) -> None:
        try:
            result = self.assistant.run_instruction(text, apply_changes=True)
        except Exception as exc:  # noqa: BLE001 - surface raw error text for clarity
            self.frame.after(0, lambda: self._handle_error(str(exc)))
            return
        self.frame.after(0, lambda: self._handle_success(result))

    def _handle_success(self, result: AssistantResult) -> None:
        self._append_message("助手", result.summary)
        self._set_busy(False)
        self.status_var.set("已完成")
        self.frame.after(0, self.on_operation_applied)

    def _handle_error(self, message: str) -> None:
        self._append_message("系统", f"请求失败：{message}")
        self._set_busy(False)
        self.status_var.set("发送失败")

    def _set_busy(self, is_busy: bool) -> None:
        state = tk.DISABLED if is_busy else tk.NORMAL
        self.send_button.configure(state=tk.NORMAL if not is_busy else tk.DISABLED)
        self.input_box.configure(state=state)
        if not is_busy:
            self.input_box.configure(state=tk.NORMAL)
            self.input_box.focus_set()
            self.status_var.set("")
        else:
            self.status_var.set("处理中…")


class TodoDetailDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Tk,
        todo: Todo,
        on_confirm: Callable[[str, Optional[datetime], str], bool],
        on_delete: Callable[[], bool],
    ) -> None:
        super().__init__(master)
        self.todo = todo
        self.on_confirm = on_confirm
        self.on_delete = on_delete
        self.title("待办详情")
        self.geometry("520x640")
        self.minsize(520, 640)
        self.config(padx=20, pady=20)
        self.grab_set()

        self.no_deadline_var = tk.BooleanVar(value=todo.due_at is None)
        self.completed_var = tk.BooleanVar(value=todo.status == "completed")
        due_str = todo.due_at.strftime(DATETIME_FMT) if todo.due_at else ""
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
        tk.Button(
            button_group,
            text="删除",
            command=self._handle_delete,
            fg="#c0392b",
            bd=0,
            font=("Microsoft YaHei", 11, "bold"),
        ).pack(side="left", padx=4)
        tk.Button(button_group, text="✕", command=self.destroy, fg="#7f8c8d", bd=0, font=("Segoe UI", 14, "bold")).pack(
            side="left",
            padx=4,
        )
        tk.Button(button_group, text="✔", command=self._handle_confirm, fg="#27ae60", bd=0, font=("Segoe UI", 14, "bold")).pack(
            side="left"
        )

    def _build_fields(self) -> None:
        info_frame = ttk.Frame(self)
        info_frame.pack(fill="x", pady=(0, 15))
        info_frame.columnconfigure(1, weight=1)

        ttk.Label(info_frame, text="标题：", font=("Microsoft YaHei", 11)).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(info_frame, text=self.todo.title, font=("Microsoft YaHei", 11, "bold"), wraplength=360).grid(
            row=0,
            column=1,
            sticky="w",
            pady=4,
        )

        ttk.Label(info_frame, text="截止时间 (YYYY-MM-DD HH:MM)：", font=("Microsoft YaHei", 11)).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(10, 4),
        )
        self.due_entry = ttk.Entry(info_frame, textvariable=self.due_var, width=30)
        self.due_entry.grid(row=2, column=0, columnspan=2, sticky="we")

        checkbox_frame = ttk.Frame(info_frame)
        checkbox_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(checkbox_frame, text="永不截止", variable=self.no_deadline_var, command=self._toggle_due_entry).pack(
            side="left",
            padx=(0, 15),
        )
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
                due_value = datetime.strptime(due_str, DATETIME_FMT)
            except ValueError:
                messagebox.showerror("输入错误", "截止时间格式应为 YYYY-MM-DD HH:MM")
                return

        status = "completed" if self.completed_var.get() else "pending"
        details_md = self.detail_editor.get("1.0", tk.END).strip()
        if self.on_confirm(status, due_value, details_md):
            self.destroy()

    def _handle_delete(self) -> None:
        if not messagebox.askyesno("删除确认", "确定要删除该待办吗？该操作不可恢复。"):
            return
        if self.on_delete():
            self.destroy()


class TodoCreateDialog(tk.Toplevel):
    def __init__(self, master: tk.Tk, on_create: Callable[[str, Optional[datetime], str, bool], bool]) -> None:
        super().__init__(master)
        self.on_create = on_create
        self.title("新建待办")
        self.geometry("520x640")
        self.minsize(520, 640)
        self.config(padx=20, pady=20)
        self.grab_set()

        self.title_var = tk.StringVar()
        default_due = (datetime.now() + timedelta(hours=1)).strftime(DATETIME_FMT)
        self.due_var = tk.StringVar(value=default_due)
        self.no_deadline_var = tk.BooleanVar(value=False)
        self.completed_var = tk.BooleanVar(value=False)

        self._build_create_header()
        self._build_create_fields()
        self._build_markdown_editor()

    def _build_create_header(self) -> None:
        header = tk.Frame(self)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="新建待办", font=("Microsoft YaHei", 16, "bold")).pack(side="left")

        buttons = tk.Frame(header)
        buttons.pack(side="right")
        tk.Button(buttons, text="✕", command=self.destroy, fg="#c0392b", bd=0, font=("Segoe UI", 14, "bold")).pack(
            side="left",
            padx=4,
        )
        tk.Button(buttons, text="✔", command=self._handle_create, fg="#27ae60", bd=0, font=("Segoe UI", 14, "bold")).pack(
            side="left"
        )

    def _build_create_fields(self) -> None:
        wrapper = ttk.Frame(self)
        wrapper.pack(fill="x", pady=(0, 12))
        wrapper.columnconfigure(1, weight=1)

        ttk.Label(wrapper, text="标题：", font=("Microsoft YaHei", 11)).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(wrapper, textvariable=self.title_var).grid(row=0, column=1, sticky="we", pady=4)

        ttk.Label(wrapper, text="截止时间 (YYYY-MM-DD HH:MM)：", font=("Microsoft YaHei", 11)).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(10, 4),
        )
        self.create_due_entry = ttk.Entry(wrapper, textvariable=self.due_var)
        self.create_due_entry.grid(row=2, column=0, columnspan=2, sticky="we")

        flag_row = ttk.Frame(wrapper)
        flag_row.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Checkbutton(flag_row, text="永不截止", variable=self.no_deadline_var, command=self._toggle_create_due).pack(
            side="left",
            padx=(0, 15),
        )
        ttk.Checkbutton(flag_row, text="标记为完成", variable=self.completed_var).pack(side="left")

        self._toggle_create_due()

    def _build_markdown_editor(self) -> None:
        self.md_section = ttk.Frame(self)
        self.md_section.pack(fill="both", expand=True)

        top = ttk.Frame(self.md_section)
        top.pack(fill="x")
        ttk.Label(top, text="详情 (Markdown)", font=("Microsoft YaHei", 11, "bold")).pack(side="left")
        self.md_preview_btn = ttk.Button(top, text="查看预览", command=self._leave_md_edit, state=tk.DISABLED)
        self.md_preview_btn.pack(side="right")
        self.md_edit_btn = ttk.Button(top, text="编辑内容", command=self._enter_md_edit)
        self.md_edit_btn.pack(side="right", padx=(0, 8))

        self.md_editor = scrolledtext.ScrolledText(self.md_section, height=12, wrap="word")
        self.md_editor.insert("1.0", "")

        self.md_preview_frame = ttk.Frame(self.md_section)
        self.md_preview_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.md_preview_frame.bind("<Double-Button-1>", self._enter_md_edit)
        self.md_view = HTMLScrolledText(self.md_preview_frame, html=self._markdown_html(""), width=60, height=18)
        self.md_view.pack(fill="both", expand=True)
        self.md_view.bind("<Double-Button-1>", self._enter_md_edit)

        self.md_editing = False

    def _enter_md_edit(self, _event=None) -> None:
        if self.md_editing:
            return "break"
        self.md_editing = True
        self.md_preview_frame.pack_forget()
        self.md_editor.pack(fill="both", expand=True, pady=(6, 0))
        self.md_preview_btn.configure(state=tk.NORMAL)
        return "break"

    def _leave_md_edit(self) -> None:
        if not self.md_editing:
            return
        self.md_view.set_html(self._markdown_html(self._current_md()))
        self.md_editor.pack_forget()
        self.md_preview_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.md_editing = False
        self.md_preview_btn.configure(state=tk.DISABLED)

    def _current_md(self) -> str:
        return self.md_editor.get("1.0", tk.END).strip()

    def _markdown_html(self, text: str) -> str:
        return markdown(text or "暂无详情", extensions=["fenced_code", "tables"])

    def _toggle_create_due(self) -> None:
        state = "disabled" if self.no_deadline_var.get() else "normal"
        self.create_due_entry.configure(state=state)

    def _handle_create(self) -> None:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showerror("输入错误", "标题不能为空")
            return

        due_value: Optional[datetime] = None
        if not self.no_deadline_var.get():
            due_text = self.due_var.get().strip()
            if due_text:
                try:
                    due_value = datetime.strptime(due_text, DATETIME_FMT)
                except ValueError:
                    messagebox.showerror("输入错误", "截止时间格式为 YYYY-MM-DD HH:MM")
                    return

        details = self._current_md()
        completed = self.completed_var.get()

        if self.on_create(title, due_value, details, completed):
            self.destroy()


class TodoApp:
    def __init__(self) -> None:
        ensure_schema()

        self.root = tk.Tk()
        self.root.title("DSL Todo List")
        self.root.geometry("1400x700")
        self.root.minsize(1100, 600)

        self.active_items: List[Todo] = []
        self.completed_items: List[Todo] = []

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="全部")
        self.due_start_var = tk.StringVar()
        self.due_end_var = tk.StringVar()
        self.status_mapping = {
            "全部": "all",
            "未完成": "pending",
            "已完成": "completed",
            "逾期": "overdue",
        }

        self.assistant = TodoAssistant()

        self._build_layout()
        self.refresh_lists()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=1)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky="nsew")

        left_container = ttk.Frame(paned)
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(1, weight=1)
        assistant_wrapper = ttk.Frame(paned, padding=16)
        assistant_wrapper.columnconfigure(0, weight=1)
        assistant_wrapper.rowconfigure(0, weight=1)
        paned.add(left_container, weight=3)
        paned.add(assistant_wrapper, weight=1)

        top_bar = ttk.Frame(left_container, padding=(20, 12))
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.columnconfigure(1, weight=3)
        top_bar.columnconfigure(3, weight=1)
        top_bar.columnconfigure(6, weight=1)

        ttk.Label(top_bar, text="关键词", font=("Microsoft YaHei", 10, "bold")).grid(row=0, column=0, padx=(0, 8))
        search_entry = ttk.Entry(top_bar, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew")
        search_entry.bind("<Return>", self.refresh_lists)

        ttk.Label(top_bar, text="状态", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=(12, 6))
        status_combo = ttk.Combobox(
            top_bar,
            textvariable=self.status_var,
            values=list(self.status_mapping.keys()),
            state="readonly",
            width=10,
        )
        status_combo.grid(row=0, column=3, sticky="ew")
        status_combo.current(0)

        ttk.Button(top_bar, text="搜索", command=self.refresh_lists).grid(row=0, column=4, padx=(12, 6))
        ttk.Button(top_bar, text="清除", command=self._reset_filters).grid(row=0, column=5, padx=(0, 6))
        ttk.Button(top_bar, text="+", width=3, command=self._open_create_dialog).grid(row=0, column=7, sticky="e")

        date_row = ttk.Frame(top_bar)
        date_row.grid(row=1, column=0, columnspan=8, sticky="ew", pady=(8, 0))
        date_row.columnconfigure(1, weight=1)
        date_row.columnconfigure(3, weight=1)

        ttk.Label(date_row, text="截止自", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=(0, 6))
        start_entry = ttk.Entry(date_row, textvariable=self.due_start_var)
        start_entry.grid(row=0, column=1, sticky="ew")
        start_entry.bind("<Return>", self.refresh_lists)

        ttk.Label(date_row, text="至", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=6)
        end_entry = ttk.Entry(date_row, textvariable=self.due_end_var)
        end_entry.grid(row=0, column=3, sticky="ew")
        end_entry.bind("<Return>", self.refresh_lists)

        list_area = ttk.Frame(left_container)
        list_area.grid(row=1, column=0, sticky="nsew")
        list_area.columnconfigure(0, weight=1, uniform="todo")
        list_area.columnconfigure(1, weight=1, uniform="todo")
        list_area.rowconfigure(0, weight=1)

        active_wrapper = ttk.Frame(list_area, padding=20)
        active_wrapper.grid(row=0, column=0, sticky="nsew")
        active_wrapper.columnconfigure(0, weight=1)
        active_wrapper.rowconfigure(0, weight=1)

        completed_wrapper = ttk.Frame(list_area, padding=20)
        completed_wrapper.grid(row=0, column=1, sticky="nsew")
        completed_wrapper.columnconfigure(0, weight=1)
        completed_wrapper.rowconfigure(0, weight=1)

        header_left = ttk.Frame(active_wrapper)
        header_left.grid(row=0, column=0, sticky="nsew")
        header_left.columnconfigure(0, weight=1)
        header_left.rowconfigure(1, weight=1)

        list_header = ttk.Frame(header_left)
        list_header.grid(row=0, column=0, sticky="ew")
        list_header.columnconfigure(0, weight=1)

        ttk.Label(list_header, text="未完成", font=("Microsoft YaHei", 14, "bold"), foreground="#2980b9").grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.active_panel = TodoListPanel(header_left, "", self.mark_complete, self._open_detail, accent="#2980b9")
        self.active_panel.frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.completed_panel = TodoListPanel(
            completed_wrapper,
            "已完成",
            self.mark_pending,
            self._open_detail,
            accent="#27ae60",
        )
        self.completed_panel.frame.grid(row=0, column=0, sticky="nsew")

        assistant_panel = AssistantChatPanel(assistant_wrapper, self.assistant, self.refresh_lists)
        assistant_panel.frame.grid(row=0, column=0, sticky="nsew")
        self.assistant_panel = assistant_panel

    def refresh_lists(self, *_args) -> None:
        filter_payload = self._build_filter_payload()
        if filter_payload is None:
            return
        try:
            records = self._call_api("list", filter_payload)
        except RuntimeError as exc:
            messagebox.showerror("接口错误", f"无法查询数据: {exc}")
            return

        now = datetime.now()
        self.active_items = []
        self.completed_items = []

        for row in records:
            due_value = datetime.strptime(row["due_at"], DATETIME_FMT) if row.get("due_at") else None
            todo = Todo(
                todo_id=row["id"],
                title=row["title"],
                details=row.get("details"),
                due_at=due_value,
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

    def _open_create_dialog(self) -> None:
        TodoCreateDialog(self.root, self._create_todo)

    def _open_detail(self, todo: Todo) -> None:
        TodoDetailDialog(
            self.root,
            todo,
            lambda status, due, details: self._apply_detail_change(todo, status, due, details),
            lambda: self._delete_todo(todo),
        )

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.status_var.set("全部")
        self.due_start_var.set("")
        self.due_end_var.set("")
        self.refresh_lists()

    def _create_todo(self, title: str, due_at: Optional[datetime], details: str, completed: bool) -> bool:
        status = "completed" if completed else "pending"
        payload = {
            "title": title,
            "details": details or None,
            "due_at": due_at.strftime(DATETIME_FMT) if due_at else None,
            "status": status,
        }
        try:
            self._call_api("create", payload)
        except RuntimeError as exc:
            messagebox.showerror("接口错误", f"无法创建待办：{exc}")
            return False
        self.refresh_lists()
        return True

    def _apply_detail_change(self, todo: Todo, status: str, due: Optional[datetime], details: str) -> bool:
        payload = {
            "id": todo.todo_id,
            "status": status,
            "details": details,
            "due_at": due.strftime(DATETIME_FMT) if due else None,
        }
        try:
            self._call_api("update", payload)
        except RuntimeError as exc:
            messagebox.showerror("接口错误", f"无法更新待办：{exc}")
            return False
        self.refresh_lists()
        return True

    def _delete_todo(self, todo: Todo) -> bool:
        try:
            self._call_api("delete", {"id": todo.todo_id})
        except RuntimeError as exc:
            messagebox.showerror("接口错误", f"无法删除待办：{exc}")
            return False
        self.refresh_lists()
        return True

    def _build_filter_payload(self) -> Optional[dict]:
        payload: dict = {}

        search_term = self.search_var.get().strip()
        if search_term:
            payload["keyword"] = search_term

        status_value = self.status_mapping.get(self.status_var.get(), "all")
        if status_value != "all":
            payload["status"] = status_value

        start_text = self.due_start_var.get().strip()
        if start_text:
            try:
                datetime.strptime(start_text, DATETIME_FMT)
            except ValueError:
                messagebox.showerror("输入错误", "开始时间格式应为 YYYY-MM-DD HH:MM")
                return None
            payload["due_from"] = start_text

        end_text = self.due_end_var.get().strip()
        if end_text:
            try:
                datetime.strptime(end_text, DATETIME_FMT)
            except ValueError:
                messagebox.showerror("输入错误", "结束时间格式应为 YYYY-MM-DD HH:MM")
                return None
            payload["due_to"] = end_text

        return payload

    def _update_status(self, todo_id: int, status: str) -> None:
        try:
            self._call_api("update", {"id": todo_id, "status": status})
        except RuntimeError as exc:
            messagebox.showerror("接口错误", f"无法更新状态: {exc}")

    def run(self) -> None:
        self.root.mainloop()

    def _call_api(self, action: str, data: dict):
        payload = json.dumps({"action": action, "data": data}, ensure_ascii=False)
        response = json.loads(handle_json_request(payload))
        print("\n=== API 调用 (GUI) ===")
        print(json.dumps({"action": action, "data": data}, ensure_ascii=False, indent=2))
        print("=== API 结果 ===")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        if response.get("status") != "ok":
            raise RuntimeError(response.get("message", "未知错误"))
        return response.get("data")


def main() -> None:
    app = TodoApp()
    app.run()


if __name__ == "__main__":
    main()
