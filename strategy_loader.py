"""
Strategy Loader - Manages tax strategy data from ITA (Intuit Tax Advisor).
Strategies content is pulled from ITA and maintained up to date.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent

# Compact LLM lines: "ita_XXX: Title — key signals" (em dash, not pipe).
STRATEGY_TITLE_SIGNALS_SEP = " — "
DEFAULT_STRATEGY_DIR = _root / "strategies"


def _format_one_strategy_json_for_insights(data: dict[str, Any]) -> str:
    """Build a readable block from one strategy JSON (original ITA-style content)."""
    sid = data.get("strategy_id", "")
    title = data.get("title", "")
    lines: list[str] = [f"{sid}: {title}"]
    if data.get("category"):
        lines.append(f"Category: {data['category']}")
    if data.get("strategy_type"):
        lines.append(f"Type: {data['strategy_type']}")

    req = data.get("requirements_for_qualification") or {}
    if isinstance(req, dict):
        if req.get("summary"):
            lines.append(f"Summary: {req['summary']}")
        crit = req.get("criteria") or []
        if isinstance(crit, list) and crit:
            lines.append("Qualification criteria:")
            for c in crit:
                lines.append(f"  - {c}")

    lim = data.get("limitations") or {}
    if isinstance(lim, dict):
        restr = lim.get("restrictions")
        if isinstance(restr, list) and restr:
            lines.append("Restrictions:")
            for r in restr:
                lines.append(f"  - {r}")

    steps = data.get("implementation_steps") or []
    if isinstance(steps, list) and steps:
        lines.append("Implementation steps:")
        for s in steps:
            lines.append(f"  - {s}")

    return "\n".join(lines)


def _iter_strategy_json_paths(strategy_dir: Path) -> list[Path]:
    """Sorted ita_strategy_NNN.json paths by numeric id."""
    paths = list(strategy_dir.rglob("ita_strategy_*.json"))

    def sort_key(p: Path) -> tuple[int, str]:
        m = re.search(r"ita_strategy_(\d+)", p.name)
        return (int(m.group(1)), p.name) if m else (9999, p.name)

    return sorted(paths, key=sort_key)


def _parse_strategy(data: dict) -> dict[str, Any]:
    """Parse strategy JSON into a flat dict for use across project-air."""
    requirements: list[str] = []
    if "requirements_for_qualification" in data:
        req_data = data["requirements_for_qualification"]
        if isinstance(req_data, dict) and "criteria" in req_data:
            requirements = req_data["criteria"]

    summary = data.get("summary", "")
    if not summary and "requirements_for_qualification" in data:
        req_data = data["requirements_for_qualification"]
        if isinstance(req_data, dict):
            summary = req_data.get("summary", data.get("title", ""))

    steps = data.get("implementation_steps") or []
    what_you_will_do = list(steps) if isinstance(steps, list) else []
    if not what_you_will_do:
        what_you_will_do = list(requirements) if requirements else []

    limitations = data.get("limitations") or {}
    restrictions = limitations.get("restrictions") if isinstance(limitations, dict) else []
    what_changes = list(restrictions) if isinstance(restrictions, list) else []

    return {
        "strategy_id": data.get("strategy_id", ""),
        "title": data.get("title", ""),
        "category": data.get("category", ""),
        "summary": summary,
        "requirements": requirements,
        "strategy_type": data.get("strategy_type", "Other"),
        "what_you_will_do": what_you_will_do,
        "what_changes": what_changes,
    }


class StrategyLoader:
    """Loads and manages tax strategies from strategies/ JSON files."""

    def __init__(self, strategy_dir: Path | str | None = None) -> None:
        self.strategy_dir = Path(strategy_dir) if strategy_dir else DEFAULT_STRATEGY_DIR
        self.strategies: dict[str, dict[str, Any]] = {}
        self.load_strategies()

    def load_strategies(self) -> None:
        """Load all strategy JSON files."""
        if not self.strategy_dir.exists():
            return
        for json_file in self.strategy_dir.rglob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    s = _parse_strategy(data)
                    if s.get("strategy_id"):
                        self.strategies[s["strategy_id"]] = s
            except Exception:
                pass

    def get_strategy(self, strategy_id: str) -> dict[str, Any] | None:
        """Get a specific strategy by ID."""
        return self.strategies.get(strategy_id)

    def get_all_strategies(self) -> list[dict[str, Any]]:
        """Get all loaded strategies."""
        return list(self.strategies.values())

    def get_strategy_count(self) -> int:
        """Get total number of loaded strategies."""
        return len(self.strategies)

    def _extract_key_restrictions(self, strategy: dict[str, Any]) -> str:
        """Extract key restrictions from strategy JSON for prompt."""
        restrictions: list[str] = []
        try:
            for json_file in self.strategy_dir.rglob(f"ita_strategy_{strategy['strategy_id'].split('_')[1]}.json"):
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                limitations = data.get("limitations") or {}
                if isinstance(limitations, dict) and "restrictions" in limitations:
                    rlist = limitations["restrictions"]
                    if isinstance(rlist, list) and rlist:
                        restrictions = [r[:100] + "..." if len(r) > 100 else r for r in rlist[:2]]
                break
        except Exception:
            pass
        return "; ".join(restrictions) if restrictions else ""

    def _extract_key_signals(self, strategy: dict[str, Any]) -> str:
        """Extract key search signals from strategy for prompt."""
        signals: set[str] = set()
        category_signals: dict[str, list[str]] = {
            "business": ["Schedule C", "business owner", "self-employed", "business income"],
            "retirement": ["retirement", "401k", "IRA", "savings"],
            "individual": ["personal", "family", "itemized", "deductions"],
            "entity": ["entity", "structure", "LLC", "S-Corp", "corporation"],
        }
        signals.update(category_signals.get(strategy.get("category", ""), []))
        title_keywords: dict[str, list[str]] = {
            "Section 179": ["equipment purchase", "asset purchase", "machinery", "vehicles"],
            "Child Tax Credit": ["children", "kids", "dependents", "family"],
            "HSA": ["health savings", "HDHP", "high deductible"],
            "Solo 401": ["self-employed 401k", "one-person 401k"],
            "S Corporation": ["S-Corp election", "self-employment tax", "SE tax"],
            "QBI": ["qualified business income", "20% deduction"],
            "Mileage": ["business miles", "driving", "vehicle expenses"],
        }
        title = (strategy.get("title") or "").lower()
        for key, terms in title_keywords.items():
            if key.lower() in title:
                signals.update(terms)
        for req in strategy.get("requirements") or []:
            r = req.lower()
            if "purchase" in r or "buy" in r:
                signals.add("purchasing")
            if "equipment" in r:
                signals.add("equipment")
            if "child" in r or "dependent" in r:
                signals.add("children")
            if "schedule c" in r:
                signals.add("Schedule C income")
            if "w-2" in r or "w2" in r:
                signals.add("W-2 income")
        return ", ".join(sorted(signals)) if signals else "general tax situation"

    def get_enriched_summary_for_genos(self) -> str:
        """
        Generate enriched strategy summaries for LLM prompt.
        Used to build context for ITA strategy recommendations.
        """
        parts: list[str] = []
        for strategy in sorted(self.strategies.values(), key=lambda s: s.get("strategy_id", "")):
            sid = strategy.get("strategy_id", "")
            title = strategy.get("title", "")
            stype = strategy.get("strategy_type", "Other")
            line = f"**{sid}: {title}** ({stype})"
            if strategy.get("summary"):
                s = strategy["summary"]
                line += f"\n   What: {s[:150] + '...' if len(s) > 150 else s}"
            reqs = strategy.get("requirements") or []
            if reqs:
                shown = reqs[:3]
                txt = "; ".join(shown)
                if len(reqs) > 3:
                    txt += f" (+{len(reqs) - 3} more)"
                line += f"\n   Qualifies: {txt}"
            restr = self._extract_key_restrictions(strategy)
            if restr:
                line += f"\n   Restrictions: {restr}"
            signals = self._extract_key_signals(strategy)
            line += f"\n   Look for: {signals}"
            line += f"\n   Category: {strategy.get('category', '')}"
            parts.append(line)
        return "\n\n".join(parts)

    def get_bulky_strategy_descriptions_for_insights(self, max_strategies: int | None = None) -> str:
        """
        Full strategy descriptions from JSON files: title, summary, qualification criteria,
        restrictions, implementation steps. Large prompt; use max_strategies to cap count.
        """
        blocks: list[str] = []
        for path in _iter_strategy_json_paths(self.strategy_dir):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                blocks.append(_format_one_strategy_json_for_insights(data))
            except Exception:
                continue
            if max_strategies is not None and len(blocks) >= max_strategies:
                break
        return "\n\n---\n\n".join(blocks)

    def get_compact_strategy_list_for_insights(self) -> str:
        """
        Generate compact strategy list for LLM insights.
        One line per strategy: ita_XXX: Title — key signals.
        Uses STRATEGIES.md (best signals) when available, else strategy-evaluation-input.json.
        """
        import re
        strategies_md = _root / "STRATEGIES.md"
        if strategies_md.exists():
            try:
                text = strategies_md.read_text(encoding="utf-8")
                signals_by_id: dict[str, str] = {}
                for m in re.finditer(r"\| (ita_\d+) \| ([^|]+) \| ([^|]+) \|", text):
                    sid, title, signals = m.group(1), m.group(2).strip(), m.group(3).strip()
                    signals_by_id[sid] = f"{title}{STRATEGY_TITLE_SIGNALS_SEP}{signals}"
                if signals_by_id:
                    return "\n".join(f"{sid}: {signals_by_id[sid]}" for sid in sorted(signals_by_id))
            except Exception:
                pass
        eval_path = _root / "strategy-evaluation-input.json"
        if eval_path.exists():
            try:
                with open(eval_path, encoding="utf-8") as f:
                    data = json.load(f)
                strategies = data.get("strategies") or []
                lines: list[str] = []
                for s in strategies:
                    sid = s.get("strategy_id", "")
                    title = s.get("title", "")
                    conditions = s.get("key_conditions")
                    reqs = s.get("inputs_required") or []
                    if conditions:
                        sig = "; ".join(conditions[:2])
                    elif reqs:
                        sig = "; ".join(reqs[:2]).replace("income.", "").replace("people.", "")
                    else:
                        sig = ""
                    line = f"{sid}: {title}" + (f"{STRATEGY_TITLE_SIGNALS_SEP}{sig}" if sig else "")
                    lines.append(line)
                return "\n".join(lines)
            except Exception:
                pass
        parts: list[str] = []
        for strategy in sorted(self.strategies.values(), key=lambda s: s.get("strategy_id", "")):
            sid = strategy.get("strategy_id", "")
            title = strategy.get("title", "")
            signals = self._extract_key_signals(strategy)
            parts.append(
                f"{sid}: {title}"
                + (f"{STRATEGY_TITLE_SIGNALS_SEP}{signals}" if signals else "")
            )
        return "\n".join(parts)
