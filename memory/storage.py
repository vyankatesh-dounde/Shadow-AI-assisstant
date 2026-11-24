"""SQLite-backed storage and one-time migration for Shadow memory data."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
DB_FILE = MEMORY_DIR / "shadow.db"
_lock = threading.RLock()


def connect() -> sqlite3.Connection:
    MEMORY_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_FILE, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db() -> None:
    with _lock, connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS kv (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (namespace, key)
            );
            CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                trigger_time REAL NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS file_index (
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                type TEXT NOT NULL,
                PRIMARY KEY (path)
            );
            CREATE INDEX IF NOT EXISTS idx_file_index_name ON file_index(name);
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                record TEXT NOT NULL
            );
            """
        )


def _read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return default


def migrate_json_files() -> list[str]:
    init_db()
    migrated = []
    migrations = {
        "facts.json": ("facts", "data"),
        "preferences.json": ("preferences", "data"),
        "relationship.json": ("relationship", "data"),
        "wake_state.json": ("wake_state", "data"),
        "daily_memory.json": ("daily_memory", "data"),
        "agent_state.json": ("agent_state", "data"),
        "reminders.json": ("reminders", "data"),
        "call_book.json": ("call_book", "data"),
        "conversation.json": ("conversation", "json"),
    }
    with _lock, connect() as connection:
        for filename, (namespace, key) in migrations.items():
            path = MEMORY_DIR / filename
            if not path.exists():
                continue
            if namespace == "conversation":
                data = _read_json(path, [])
                if isinstance(data, list):
                    connection.execute("DELETE FROM conversation")
                    connection.executemany(
                        "INSERT INTO conversation(role, content, created_at) VALUES (?, ?, ?)",
                        [
                            (
                                item["role"],
                                item["content"],
                                datetime.utcnow().isoformat(),
                            )
                            for item in data
                            if isinstance(item, dict)
                            and item.get("role") in {"user", "assistant"}
                            and isinstance(item.get("content"), str)
                        ],
                    )
            elif namespace == "reminders":
                data = _read_json(path, [])
                if isinstance(data, list):
                    connection.execute("DELETE FROM reminders")
                    connection.executemany(
                        "INSERT OR REPLACE INTO reminders(id, text, trigger_time, done) VALUES (?, ?, ?, ?)",
                        [
                            (
                                item.get("id"),
                                item.get("text"),
                                item.get("time"),
                                1 if item.get("done") else 0,
                            )
                            for item in data
                            if isinstance(item, dict)
                            and isinstance(item.get("id"), str)
                            and isinstance(item.get("text"), str)
                            and isinstance(item.get("time"), (int, float))
                        ],
                    )
            else:
                data = _read_json(path, {})
                if isinstance(data, dict):
                    connection.execute(
                        "INSERT OR REPLACE INTO kv(namespace, key, value) VALUES (?, ?, ?)",
                        (namespace, key, json.dumps(data, ensure_ascii=False)),
                    )
            migrated.append(filename)

        action_path = MEMORY_DIR / "action_log.jsonl"
        if action_path.exists():
            records = []
            for line in action_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append((datetime.utcnow().isoformat(), line))
            if records:
                connection.executemany(
                    "INSERT INTO action_log(timestamp, record) VALUES (?, ?)",
                    records,
                )
            migrated.append(action_path.name)

    for filename in migrated:
        (MEMORY_DIR / filename).unlink(missing_ok=True)
    return migrated


def get_kv(namespace: str, default: Any = None) -> Any:
    init_db()
    with _lock, connect() as connection:
        row = connection.execute(
            "SELECT value FROM kv WHERE namespace=? AND key='data'",
            (namespace,),
        ).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def set_kv(namespace: str, value: Any) -> None:
    init_db()
    encoded = json.dumps(value, ensure_ascii=False)
    with _lock, connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO kv(namespace, key, value) VALUES (?, 'data', ?)",
            (namespace, encoded),
        )


def load_conversation(limit: int | None = None) -> list[dict]:
    init_db()
    with _lock, connect() as connection:
        query = "SELECT role, content FROM conversation ORDER BY id"
        rows = connection.execute(query).fetchall()
    result = [{"role": row["role"], "content": row["content"]} for row in rows]
    return result[-limit:] if limit is not None else result


def append_message(role: str, content: str) -> None:
    init_db()
    with _lock, connect() as connection:
        connection.execute(
            "INSERT INTO conversation(role, content, created_at) VALUES (?, ?, ?)",
            (role, content, datetime.utcnow().isoformat()),
        )
        count = connection.execute("SELECT COUNT(*) AS count FROM conversation").fetchone()["count"]
        if count > 12:
            connection.execute(
                "DELETE FROM conversation WHERE id IN "
                "(SELECT id FROM conversation ORDER BY id LIMIT ?)",
                (count - 12,),
            )


def clear_conversation() -> None:
    init_db()
    with _lock, connect() as connection:
        connection.execute("DELETE FROM conversation")


def load_reminders() -> list[dict]:
    init_db()
    with _lock, connect() as connection:
        rows = connection.execute(
            "SELECT id, text, trigger_time, done FROM reminders"
        ).fetchall()
    return [
        {
            "id": row["id"],
            "text": row["text"],
            "time": row["trigger_time"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]


def save_reminders(reminders: list[dict]) -> None:
    init_db()
    with _lock, connect() as connection:
        connection.execute("DELETE FROM reminders")
        connection.executemany(
            "INSERT OR REPLACE INTO reminders(id, text, trigger_time, done) VALUES (?, ?, ?, ?)",
            [
                (
                    item.get("id"),
                    item.get("text"),
                    item.get("time"),
                    1 if item.get("done") else 0,
                )
                for item in reminders
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and isinstance(item.get("text"), str)
                and isinstance(item.get("time"), (int, float))
            ],
        )


def log_action(record: dict) -> None:
    init_db()
    with _lock, connect() as connection:
        connection.execute(
            "INSERT INTO action_log(timestamp, record) VALUES (?, ?)",
            (record.get("timestamp", datetime.utcnow().isoformat()),
             json.dumps(record, ensure_ascii=False)),
        )


def search_file_index(query: str) -> str | None:
    init_db()
    cleaned = (query or "").strip().lower()
    if not cleaned:
        return None
    with _lock, connect() as connection:
        rows = connection.execute(
            "SELECT name, path, type FROM file_index"
        ).fetchall()
    best_path = None
    best_score = 0
    for row in rows:
        name = row["name"]
        score = 10 if cleaned in name else 0
        if score:
            score += sum(3 for word in cleaned.split() if word in name)
        if score > best_score:
            best_score = score
            best_path = row["path"]
    return best_path


def rebuild_file_index() -> int:
    import os

    init_db()
    noisy = {"node_modules", ".git", "appdata", "windows"}
    roots = []
    for base in ("C:\\Users", "D:\\", "E:\\"):
        if Path(base).exists():
            roots.append(base)

    items = []
    for base in roots:
        for root, dirs, files in os.walk(base):
            dirs[:] = [
                directory for directory in dirs
                if directory.lower() not in noisy
                and not directory.lower().startswith(".")
            ]
            for directory in dirs:
                items.append((directory.lower(), str(Path(root) / directory), "folder"))
            for filename in files:
                items.append((filename.lower(), str(Path(root) / filename), "file"))

    with _lock, connect() as connection:
        connection.execute("DELETE FROM file_index")
        connection.executemany(
            "INSERT OR IGNORE INTO file_index(name, path, type) VALUES (?, ?, ?)",
            items,
        )
    return len(items)


migrate_json_files()
