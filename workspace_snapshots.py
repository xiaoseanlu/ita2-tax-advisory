"""
Named workspace snapshots (SQLite): full UI + server-side chat, memory, and plan state.

Environment: WORKSPACE_DB_PATH (optional) defaults to <repo>/data/workspace.sqlite
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent


def _db_path() -> Path:
    env = (os.environ.get("WORKSPACE_DB_PATH") or "").strip()
    if env:
        return Path(env).expanduser()
    p = _root / "data" / "workspace.sqlite"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_workspace_db() -> None:
    with _connect() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY,
                label TEXT,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        c.commit()


def apply_server_state(server_by_scenario: dict[str, Any]) -> None:
    """Replace all chat threads, memory, and plans with snapshot content."""
    from chat_memory_store import clear_all_memory, set_memory
    from chat_thread_store import clear_all_threads, set_messages
    from plan_store import clear_all_plans, replace_plan

    clear_all_threads()
    clear_all_memory()
    clear_all_plans()
    for sid, block in (server_by_scenario or {}).items():
        if not isinstance(block, dict):
            continue
        set_messages(sid, block.get("chat") or [])
        set_memory(sid, block.get("memory") or [])
        replace_plan(sid, block.get("plan") or [])


def save_snapshot(label: str | None, state: dict[str, Any]) -> dict[str, Any]:
    """Persist ``state`` JSON. Returns { id, label, created_at }."""
    init_workspace_db()
    sid = str(uuid.uuid4())
    created = _now_iso()
    lab = (label or "").strip() or None
    payload = json.dumps(state, ensure_ascii=False)
    with _connect() as c:
        c.execute(
            "INSERT INTO snapshots (id, label, created_at, payload_json) VALUES (?, ?, ?, ?)",
            (sid, lab, created, payload),
        )
        c.commit()
    return {"id": sid, "label": lab, "created_at": created}


def list_snapshots() -> list[dict[str, Any]]:
    init_workspace_db()
    with _connect() as c:
        rows = c.execute(
            "SELECT id, label, created_at FROM snapshots ORDER BY created_at DESC"
        ).fetchall()
    return [
        {"id": r["id"], "label": r["label"], "created_at": r["created_at"]}
        for r in rows
    ]


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    init_workspace_db()
    with _connect() as c:
        row = c.execute(
            "SELECT id, label, created_at, payload_json FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row["id"],
        "label": row["label"],
        "created_at": row["created_at"],
        "state": payload,
    }


def delete_snapshot(snapshot_id: str) -> bool:
    init_workspace_db()
    with _connect() as c:
        cur = c.execute("DELETE FROM snapshots WHERE id = ?", (snapshot_id,))
        c.commit()
    return cur.rowcount > 0
