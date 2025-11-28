"""Shared database helpers for the DSL-TodoList project."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "DSL-TodoListUser",
    "password": "qwertyui793789",
    "database": "DSL-TodoList",
    "auth_plugin": "mysql_native_password",
}


def get_connection() -> mysql.connector.MySQLConnection:
    """Return a new MySQL connection using the shared configuration."""
    return mysql.connector.connect(**DB_CONFIG)


def ensure_schema() -> None:
    """Create the todos table when it does not exist yet."""
    conn = get_connection()
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


def reset_tables() -> None:
    """Clear the todos table and reset the auto-increment counter (used in tests)."""
    ensure_schema()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE todos")
    conn.commit()
    cursor.close()
    conn.close()


@contextmanager
def managed_cursor() -> Iterator[mysql.connector.cursor.MySQLCursor]:
    """Yield a cursor and guarantee cleanup."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        yield cursor
        conn.commit()
    finally:
        cursor.close()
        conn.close()
