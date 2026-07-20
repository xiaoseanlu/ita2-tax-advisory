"""
In-memory chat threads per scenario (for Assistant chat UI). Resets on server restart.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# scenario_id -> list of { id, role, content, created_at }
_threads: dict[str, list[dict[str, Any]]] = {}


def get_messages(scenario_id: str) -> list[dict[str, Any]]:
    return list(_threads.get(scenario_id, []))


def append_message(scenario_id: str, role: str, content: str) -> dict[str, Any]:
    if scenario_id not in _threads:
        _threads[scenario_id] = []
    if role not in ("user", "assistant"):
        raise ValueError("role must be user or assistant")
    t = (content or "").strip()
    if not t:
        raise ValueError("content cannot be empty")
    item = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": t,
        "created_at": _now_iso(),
    }
    _threads[scenario_id].append(item)
    return item


def clear_thread(scenario_id: str) -> int:
    n = len(_threads.get(scenario_id, []))
    if scenario_id in _threads:
        del _threads[scenario_id]
    return n


def set_messages(scenario_id: str, messages: list[dict[str, Any]]) -> None:
    """Replace the entire thread for a scenario (workspace restore)."""
    _threads[scenario_id] = [dict(m) for m in messages]


def clear_all_threads() -> None:
    """Remove all chat threads (workspace restore)."""
    _threads.clear()
