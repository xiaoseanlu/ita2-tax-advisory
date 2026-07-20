#!/usr/bin/env python3
"""
Outline the input fields a given ITA strategy reads from its .spe source.

Uses the same extraction / classification logic as the 1040 feasibility analysis,
but for one strategy at a time (no ita-mapping-service required).

Examples:
  python3 outline_strategy_inputs.py --list
  python3 outline_strategy_inputs.py "Bunching Itemized Deductions"
  python3 outline_strategy_inputs.py bunching --user-only
  python3 outline_strategy_inputs.py "Scorp" --json
  python3 outline_strategy_inputs.py "401k Employee Contribution Calculator" \\
      --content ~/Documents/GitHub/tax-strategy-content
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Allow running from repo root or from ita-rules/
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from spe_inputs import (  # noqa: E402
    extract_strategy_inputs,
    list_strategies,
    resolve_strategy_name,
    summarize,
)

DEFAULT_CONTENT = Path.home() / "Documents" / "GitHub" / "tax-strategy-content"

CATEGORY_LABELS = {
    "user-data": "USER INPUTS (must supply)",
    "calculated": "ENGINE-CALCULATED (strategy reads; engine derives)",
    "prior-year": "PRIOR-YEAR (actual.return…)",
    "undeterminable-template": "DYNAMIC / TEMPLATE (path not fully static)",
}


def default_content_repo() -> Path:
    env = Path(__file__).resolve().parents[1]  # project-air
    # Prefer sibling repos under Documents/GitHub, then env override handled by argparse
    candidates = [
        Path.home() / "Documents" / "GitHub" / "tax-strategy-content",
        env.parent / "tax-strategy-content",
        DEFAULT_CONTENT,
    ]
    for c in candidates:
        if (c / "IndUS" / "strategies").is_dir():
            return c
    return DEFAULT_CONTENT


def print_outline(
    name: str,
    fields: list[dict],
    *,
    user_only: bool,
    show_paths: bool,
    include_files: list[dict] | None = None,
    missing_includes: list[str] | None = None,
) -> None:
    counts = summarize(fields)
    live_user = [
        f
        for f in fields
        if f["category"] == "user-data" and not f.get("dead_reference")
    ]
    print(f"Strategy: {name}")
    print(f"Fields extracted: {len(fields)}  "
          f"(user live={len(live_user)}, "
          + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
          + ")")
    print()

    if include_files is not None:
        print("## Resolved %include tree")
        print()
        for meta in include_files:
            indent = "  " * meta["depth"]
            tag = "entry" if meta["is_entry"] else "include"
            via = f"  ← {meta['included_from']}" if meta.get("included_from") else ""
            print(f"{indent}• [{tag}] {meta['rel_path']}{via}")
        if missing_includes:
            print()
            print("  Missing includes (referenced but not found):")
            for m in missing_includes:
                print(f"    ✗ {m}")
        print()

    by_cat: dict[str, list] = defaultdict(list)
    for f in fields:
        if user_only and f["category"] != "user-data":
            continue
        if f.get("dead_reference"):
            by_cat["_dead"].append(f)
            continue
        by_cat[f["category"]].append(f)

    order = ["user-data", "prior-year", "calculated", "undeterminable-template"]
    for cat in order:
        bucket = by_cat.get(cat, [])
        if not bucket:
            continue
        print(f"## {CATEGORY_LABELS.get(cat, cat)} ({len(bucket)})")
        print()
        seen_leaves: set[str] = set()
        for f in bucket:
            leaf = f["leaf"]
            if cat == "user-data" and leaf in seen_leaves and not show_paths:
                continue
            seen_leaves.add(leaf)
            flags = []
            defined = f.get("defined_in") or ""
            if defined:
                flags.append(f"in {defined}")
            if f["source_kind"] != "base":
                flags.append(f"kind={f['source_kind']}")
            flag_s = f"  [{', '.join(flags)}]" if flags else ""
            if show_paths or cat != "user-data":
                print(f"  • {f['path']}{flag_s}")
            else:
                print(f"  • {leaf}{flag_s}")
            if cat == "user-data" and f.get("likely_source_doc"):
                print(f"      ← {f['likely_source_doc']}")
            if f.get("override_note"):
                print(f"      note: {f['override_note']}")
        print()

    dead = by_cat.get("_dead", [])
    if dead and not user_only:
        print(f"## DEAD REFERENCES (commented in .spe; not live) ({len(dead)})")
        print()
        for f in dead:
            print(f"  • {f['leaf']}: {f['dead_reference']}")
        print()

    if live_user:
        by_doc: dict[str, set[str]] = defaultdict(set)
        for f in live_user:
            by_doc[f["likely_source_doc"] or "?"].add(f["leaf"])
        print("## Likely source documents (user inputs)")
        print()
        for doc, leaves in sorted(by_doc.items(), key=lambda x: (-len(x[1]), x[0])):
            print(f"  {doc} ({len(leaves)}): {', '.join(sorted(leaves))}")
        print()


def main() -> int:
    p = argparse.ArgumentParser(
        description="Outline inputs for one ITA strategy (.spe extraction)."
    )
    p.add_argument(
        "strategy",
        nargs="?",
        help='Strategy folder name or unique substring (e.g. "Bunching", "Scorp")',
    )
    p.add_argument(
        "--content",
        type=Path,
        default=None,
        help=f"Path to tax-strategy-content repo (default: {DEFAULT_CONTENT})",
    )
    p.add_argument("--list", action="store_true", help="List all strategy names")
    p.add_argument(
        "--user-only",
        action="store_true",
        help="Only show user-data inputs (hide calculated / prior-year)",
    )
    p.add_argument(
        "--full-paths",
        action="store_true",
        help="Always print full ITA paths (default: leaf names for user inputs)",
    )
    p.add_argument(
        "--show-includes",
        action="store_true",
        help="Print the recursively resolved %%include tree",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = p.parse_args()

    content = args.content or default_content_repo()
    if not (content / "IndUS" / "strategies").is_dir():
        print(
            f"error: tax-strategy-content not found at {content}\n"
            "Pass --content /path/to/tax-strategy-content",
            file=sys.stderr,
        )
        return 1

    if args.list:
        for name in list_strategies(content):
            print(name)
        return 0

    if not args.strategy:
        p.print_help()
        print("\nTip: python3 outline_strategy_inputs.py --list", file=sys.stderr)
        return 2

    try:
        name = resolve_strategy_name(content, args.strategy)
        fields, include_files, missing = extract_strategy_inputs(
            content, name, return_include_tree=True
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "strategy": name,
            "content_repo": str(content.resolve()),
            "summary": summarize(fields),
            "include_tree": include_files,
            "missing_includes": missing,
            "fields": fields,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"(content: {content})")
    print()
    print_outline(
        name,
        fields,
        user_only=args.user_only,
        show_paths=args.full_paths,
        include_files=include_files if args.show_includes else None,
        missing_includes=missing if args.show_includes else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
