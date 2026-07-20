"""
Load tax situations from tax_situations.txt. Each scenario is preceded by a block:

---
id: <scenario_id>
---
<scenario text>

Use list_scenario_ids() to get all ids; use get_scenario_by_id() to get one by id.
Useful for regressions and picking a scenario by index/id.
"""

from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path(__file__).resolve().parent / "tax_situations.txt"


def load_tax_situations(path: Path | str | None = None) -> list[dict[str, Any]]:
    """
    Load all scenarios from the tax situations file.
    Returns a list of dicts with keys: id (str), text (str).
    """
    path = Path(path) if path is not None else _DEFAULT_PATH
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    # Split on "---\nid:" so each part (after first) is " id_value\n---\ncontent"
    parts = raw.split("\n---\nid:")
    result: list[dict[str, Any]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("---"):
            part = part[3:].lstrip()
        if not part:
            continue
        lines = part.split("\n", 1)
        scenario_id = lines[0].strip()
        if scenario_id.lower().startswith("id:"):
            scenario_id = scenario_id[3:].strip()
        body = lines[1].strip() if len(lines) > 1 else ""
        if body.startswith("---"):
            body = body.split("\n", 1)[1] if "\n" in body else ""
        result.append({"id": scenario_id, "text": body.strip()})
    return result


def list_scenario_ids(path: Path | str | None = None) -> list[str]:
    """Return list of scenario ids in file order."""
    return [s["id"] for s in load_tax_situations(path)]


def get_scenario_by_id(
    scenario_id: str,
    path: Path | str | None = None,
) -> str | None:
    """
    Return the scenario text for the given id, or None if not found.
    """
    for s in load_tax_situations(path):
        if s["id"] == scenario_id:
            return s["text"]
    return None
