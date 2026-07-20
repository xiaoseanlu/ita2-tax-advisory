"""
Durable assistant memory per scenario (UC-6 / UC-7).
In-memory process store; same lifetime as plan_store (resets on server restart).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# scenario_id -> list of { id, text, created_at }
_memory: dict[str, list[dict[str, Any]]] = {}


def list_memory(scenario_id: str) -> list[dict[str, Any]]:
    """Return memory items for a scenario, oldest first."""
    return list(_memory.get(scenario_id, []))


def add_memory(scenario_id: str, text: str) -> dict[str, Any]:
    """Append a durable note. Returns { id, text, created_at }."""
    t = (text or "").strip()
    if not t:
        raise ValueError("Memory text cannot be empty")
    if scenario_id not in _memory:
        _memory[scenario_id] = []
    item = {
        "id": str(uuid.uuid4()),
        "text": t,
        "created_at": _now_iso(),
    }
    _memory[scenario_id].append(item)
    return item


def delete_memory(scenario_id: str, memory_id: str) -> bool:
    """Remove one item by id. Returns True if removed."""
    entries = _memory.get(scenario_id)
    if not entries:
        return False
    idx = next((i for i, e in enumerate(entries) if e.get("id") == memory_id), None)
    if idx is None:
        return False
    entries.pop(idx)
    return True


def clear_scenario_memory(scenario_id: str) -> int:
    """Remove all items for a scenario. Returns count removed."""
    n = len(_memory.get(scenario_id, []))
    if scenario_id in _memory:
        del _memory[scenario_id]
    return n


def set_memory(scenario_id: str, items: list[dict[str, Any]]) -> None:
    """Replace all memory items for a scenario (workspace restore)."""
    _memory[scenario_id] = [dict(x) for x in items]


def clear_all_memory() -> None:
    """Remove all assistant memory (workspace restore)."""
    _memory.clear()
