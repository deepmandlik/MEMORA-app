from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid.uuid4())


def memory_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    result["metadata"] = json.loads(result["metadata"] or "{}")
    result["is_demo"] = bool(result["is_demo"])
    return result


class Database:
    """Small sqlite3 repository. Every public operation is transactional."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL CHECK (category IN (
                        'personal', 'career', 'projects', 'preferences', 'goals',
                        'decisions', 'commitments', 'work', 'health', 'finance', 'family'
                    )),
                    source_agent TEXT,
                    memory_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'outdated', 'superseded')),
                    metadata TEXT NOT NULL DEFAULT '{}',
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    conflict_status TEXT NOT NULL DEFAULT 'none'
                        CHECK (conflict_status IN ('none', 'pending')),
                    conflict_with TEXT REFERENCES memories(id) ON DELETE SET NULL,
                    superseded_by TEXT REFERENCES memories(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_owner ON memories(owner_id, status);
                CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(owner_id, memory_key);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(owner_id, category);

                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES agent_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    provider TEXT,
                    retrieved_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON agent_messages(session_id, id);

                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    agent_id TEXT,
                    level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error'))
                );
                CREATE INDEX IF NOT EXISTS idx_events_id ON events(id DESC);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO system_state(key, value) VALUES ('primary_outage', 'false')"
            )
            timestamp = utc_now()
            sessions = [
                (
                    "agent-a",
                    "Agent A",
                    "Context partner",
                    "Primary conversation with access to your durable Memora context.",
                    timestamp,
                ),
                (
                    "agent-b",
                    "Agent B",
                    "Continuity verifier",
                    "An independent session that can retrieve the same durable context.",
                    timestamp,
                ),
            ]
            connection.executemany(
                "INSERT OR IGNORE INTO agent_sessions(id, name, role, description, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                sessions,
            )
            if connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0:
                demos = [
                    (
                        "demo-preferences",
                        "user",
                        "Prefers concise summaries with practical next steps.",
                        "preferences",
                        "seed",
                        "preferences.response_style",
                        timestamp,
                        timestamp,
                        "active",
                        json.dumps({"seeded": True}),
                        1,
                        "none",
                        None,
                        None,
                    ),
                    (
                        "demo-project",
                        "user",
                        "Building Memora, a local-first context continuity layer.",
                        "projects",
                        "seed",
                        "projects.memora",
                        timestamp,
                        timestamp,
                        "active",
                        json.dumps({"seeded": True}),
                        1,
                        "none",
                        None,
                        None,
                    ),
                    (
                        "demo-goal",
                        "user",
                        "Demonstrate reliable context continuity across independent agents.",
                        "goals",
                        "seed",
                        "goals.memora_demo",
                        timestamp,
                        timestamp,
                        "active",
                        json.dumps({"seeded": True}),
                        1,
                        "none",
                        None,
                        None,
                    ),
                ]
                connection.executemany(
                    """
                    INSERT INTO memories(
                        id, owner_id, content, category, source_agent, memory_key,
                        created_at, updated_at, status, metadata, is_demo,
                        conflict_status, conflict_with, superseded_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    demos,
                )

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return memory_from_row(row)

    def list_memories(
        self,
        owner_id: str,
        query: str = "",
        category: str | None = None,
        status: str | None = None,
        include_demo: bool = True,
    ) -> list[dict[str, Any]]:
        clauses = ["owner_id = ?"]
        parameters: list[Any] = [owner_id]
        if query:
            clauses.append("LOWER(content || ' ' || COALESCE(memory_key, '') || ' ' || category) LIKE ?")
            parameters.append(f"%{query.lower()}%")
        if category:
            clauses.append("category = ?")
            parameters.append(category)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        if not include_demo:
            clauses.append("is_demo = 0")
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM memories WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC, id DESC",
                parameters,
            ).fetchall()
            return [memory_from_row(row) for row in rows]

    def save_memory(self, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        with self.connection() as connection:
            duplicate = connection.execute(
                """
                SELECT * FROM memories
                WHERE owner_id = ? AND content = ? AND memory_key IS ?
                ORDER BY created_at ASC, id ASC LIMIT 1
                """,
                (data["owner_id"], data["content"], data.get("memory_key")),
            ).fetchone()
            if duplicate:
                return memory_from_row(duplicate), False

            timestamp = utc_now()
            memory_id = new_id()
            memory_key = data.get("memory_key")
            conflict_status = "none"
            conflict_with = None
            status = data.get("status", "active")
            conflicts: list[sqlite3.Row] = []
            if memory_key:
                conflicts = connection.execute(
                    """
                    SELECT * FROM memories
                    WHERE owner_id = ? AND memory_key = ? AND status = 'active' AND content <> ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (data["owner_id"], memory_key, data["content"]),
                ).fetchall()
            if conflicts:
                status = "active"
                conflict_status = "pending"
                conflict_with = conflicts[0]["id"]

            connection.execute(
                """
                INSERT INTO memories(
                    id, owner_id, content, category, source_agent, memory_key,
                    created_at, updated_at, status, metadata, is_demo,
                    conflict_status, conflict_with, superseded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    memory_id,
                    data["owner_id"],
                    data["content"],
                    data["category"],
                    data.get("source_agent"),
                    memory_key,
                    timestamp,
                    timestamp,
                    status,
                    json.dumps(data.get("metadata") or {}, separators=(",", ":")),
                    int(data.get("is_demo", False)),
                    conflict_status,
                    conflict_with,
                ),
            )
            for conflict in conflicts:
                connection.execute(
                    "UPDATE memories SET conflict_status = 'pending', conflict_with = ?, "
                    "updated_at = ? WHERE id = ?",
                    (memory_id, timestamp, conflict["id"]),
                )
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return memory_from_row(row), True

    def update_memory(self, memory_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self.connection() as connection:
            current = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if current is None:
                return None
            assignments: list[str] = []
            parameters: list[Any] = []
            for key in ("content", "category", "status", "memory_key"):
                if key in updates:
                    assignments.append(f"{key} = ?")
                    parameters.append(updates[key])
            if "metadata" in updates:
                assignments.append("metadata = ?")
                parameters.append(json.dumps(updates["metadata"] or {}, separators=(",", ":")))
            timestamp = utc_now()
            assignments.append("updated_at = ?")
            parameters.append(timestamp)
            if assignments:
                parameters.append(memory_id)
                connection.execute(
                    f"UPDATE memories SET {', '.join(assignments)} WHERE id = ?", parameters
                )
            updated = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if updated["status"] == "active" and updated["memory_key"]:
                conflicts = connection.execute(
                    """
                    SELECT * FROM memories
                    WHERE owner_id = ? AND memory_key = ? AND id <> ?
                      AND status = 'active' AND content <> ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (updated["owner_id"], updated["memory_key"], memory_id, updated["content"]),
                ).fetchall()
                if conflicts:
                    connection.execute(
                        "UPDATE memories SET conflict_status = 'pending', conflict_with = ?, "
                        "updated_at = ? WHERE id = ?",
                        (conflicts[0]["id"], timestamp, memory_id),
                    )
                    for conflict in conflicts:
                        connection.execute(
                            "UPDATE memories SET conflict_status = 'pending', conflict_with = ?, "
                            "updated_at = ? WHERE id = ?",
                            (memory_id, timestamp, conflict["id"]),
                        )
                elif current["conflict_status"] == "pending":
                    connection.execute(
                        "UPDATE memories SET conflict_status = 'none', conflict_with = NULL, "
                        "updated_at = ? WHERE id = ?",
                        (timestamp, memory_id),
                    )
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return memory_from_row(row)

    def delete_memory(self, memory_id: str) -> bool:
        with self.connection() as connection:
            result = connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return result.rowcount > 0

    def resolve_memory(self, memory_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            selected = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            if selected is None:
                return None
            timestamp = utc_now()
            if selected["memory_key"]:
                connection.execute(
                    """
                    UPDATE memories
                    SET status = 'superseded', conflict_status = 'none', conflict_with = NULL,
                        superseded_by = ?, updated_at = ?
                    WHERE owner_id = ? AND memory_key = ? AND id <> ?
                    """,
                    (
                        memory_id,
                        timestamp,
                        selected["owner_id"],
                        selected["memory_key"],
                        memory_id,
                    ),
                )
            connection.execute(
                """
                UPDATE memories SET status = 'active', conflict_status = 'none',
                    conflict_with = NULL, superseded_by = NULL, updated_at = ? WHERE id = ?
                """,
                (timestamp, memory_id),
            )
            return memory_from_row(
                connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            )

    def export_memories(self, owner_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM memories WHERE owner_id = ? ORDER BY created_at ASC, id ASC",
                (owner_id,),
            ).fetchall()
            return [memory_from_row(row) for row in rows]

    def retrieval_candidates(
        self, owner_id: str, include_demo: bool, categories: list[str] | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["owner_id = ?", "status = 'active'"]
        parameters: list[Any] = [owner_id]
        if not include_demo:
            clauses.append("is_demo = 0")
        if categories:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"category IN ({placeholders})")
            parameters.extend(categories)
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM memories WHERE {' AND '.join(clauses)} ORDER BY created_at ASC, id ASC",
                parameters,
            ).fetchall()
            return [memory_from_row(row) for row in rows]

    def counts(self) -> dict[str, int]:
        with self.connection() as connection:
            return {
                "memories": connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
                "active_goals": connection.execute(
                    "SELECT COUNT(*) FROM memories WHERE category = 'goals' AND status = 'active'"
                ).fetchone()[0],
                "agents": connection.execute("SELECT COUNT(*) FROM agent_sessions").fetchone()[0],
                "conflicts": connection.execute(
                    "SELECT COUNT(*) FROM memories WHERE conflict_status = 'pending'"
                ).fetchone()[0],
            }

    def get_state(self, key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_state(self, key: str, value: str | None) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO system_state(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def sessions(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, name, role, description, created_at FROM agent_sessions "
                "ORDER BY created_at ASC, id ASC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id, name, role, description, created_at FROM agent_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    def create_session(self, name: str, role: str | None, description: str | None) -> dict[str, Any]:
        session_id = new_id()
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO agent_sessions(id, name, role, description, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, name, role, description, utc_now()),
            )
            row = connection.execute(
                "SELECT id, name, role, description, created_at FROM agent_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return dict(row)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        provider: str | None,
        retrieved_count: int,
    ) -> dict[str, Any]:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO agent_messages(
                    session_id, role, content, created_at, provider, retrieved_count
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, utc_now(), provider, retrieved_count),
            )
            row = connection.execute(
                "SELECT * FROM agent_messages WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)

    def messages(self, session_id: str) -> list[dict[str, Any]] | None:
        with self.connection() as connection:
            session = connection.execute(
                "SELECT 1 FROM agent_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            rows = connection.execute(
                "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY id ASC", (session_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def log_event(
        self,
        event_type: str,
        message: str,
        agent_id: str | None = None,
        level: str = "info",
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO events(timestamp, event_type, message, agent_id, level) VALUES (?, ?, ?, ?, ?)",
                (utc_now(), event_type, message[:2_000], agent_id, level),
            )

    def events(self, limit: int) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT id, timestamp, event_type, message, agent_id, level FROM events "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
