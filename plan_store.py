"""
Plan store: strategies added to plan with strategy-specific inputs.
Schema: list of plan entries per scenario. Each strategy type has its own input schema.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Per-scenario plan: scenario_id -> list of plan entries
_plans: dict[str, list[dict[str, Any]]] = {}

# Strategy input schemas (for validation / documentation)
# S-Corp (ita_002): "Reasonable comp" stored as reasonable_comp_percentage
STRATEGY_INPUT_SCHEMAS = {
    "ita_002": {
        "description": "S-Corp Conversion",
        "inputs": {
            "schedule_c_income": {"type": "number", "label": "Schedule C Business Income"},
            "reasonable_comp_percentage": {"type": "number", "label": "Reasonable comp", "min": 30, "max": 60},
        },
    },
    "ita_025": {
        "description": "Bonus Depreciation",
        "inputs": {
            "equipment_cost": {"type": "number", "label": "Equipment/Asset Cost"},
            "bonus_percentage": {"type": "number", "label": "Bonus Depreciation %"},
            "tax_rate": {"type": "number", "label": "Marginal Tax Rate"},
        },
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_plan(scenario_id: str) -> list[dict[str, Any]]:
    """Read full plan for a scenario."""
    return list(_plans.get(scenario_id, []))


def add_to_plan(
    scenario_id: str,
    strategy_id: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Add or update a strategy in the plan (upsert by strategy_id)."""
    if scenario_id not in _plans:
        _plans[scenario_id] = []
    entries = _plans[scenario_id]
    idx = next((i for i, e in enumerate(entries) if e.get("strategy_id") == strategy_id), None)
    now = _now_iso()
    entry = {
        "strategy_id": strategy_id,
        "inputs": dict(inputs),
        "added_at": now,
        "updated_at": now,
    }
    if idx is not None:
        entry["added_at"] = entries[idx].get("added_at", now)
        entries[idx] = entry
    else:
        entries.append(entry)
    return entry


def update_plan_entry(
    scenario_id: str,
    strategy_id: str,
    inputs: dict[str, Any],
) -> dict[str, Any] | None:
    """Update an existing plan entry. Returns entry or None if not found."""
    entries = _plans.get(scenario_id, [])
    idx = next((i for i, e in enumerate(entries) if e.get("strategy_id") == strategy_id), None)
    if idx is None:
        return None
    now = _now_iso()
    entries[idx]["inputs"] = dict(inputs)
    entries[idx]["updated_at"] = now
    return entries[idx]


def delete_from_plan(scenario_id: str, strategy_id: str) -> bool:
    """Remove a strategy from the plan. Returns True if removed."""
    if scenario_id not in _plans:
        return False
    entries = _plans[scenario_id]
    idx = next((i for i, e in enumerate(entries) if e.get("strategy_id") == strategy_id), None)
    if idx is None:
        return False
    entries.pop(idx)
    return True


def get_plan_entry(scenario_id: str, strategy_id: str) -> dict[str, Any] | None:
    """Get a single plan entry by strategy_id."""
    entries = _plans.get(scenario_id, [])
    return next((e for e in entries if e.get("strategy_id") == strategy_id), None)


def replace_plan(scenario_id: str, entries: list[dict[str, Any]]) -> None:
    """Replace the full plan for a scenario (workspace restore)."""
    _plans[scenario_id] = [dict(e) for e in entries]


def clear_all_plans() -> None:
    """Remove all plans (workspace restore)."""
    _plans.clear()
