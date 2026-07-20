"""Shared loader: import a strategy tool module by its repo-relative path.

Tools live under skills/income_tax/assisted/*/tools/*.py and are not a package,
so we load them by file path (stdlib only, no pytest required).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ita-rules/tests/spe_loader.py -> repo root is two parents up.
ROOT = Path(__file__).resolve().parents[2]


def load_tool(rel_path: str, name: str):
    path = ROOT / rel_path
    if not path.exists():
        raise FileNotFoundError(f"Tool module not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
