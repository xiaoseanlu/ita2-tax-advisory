#!/usr/bin/env python3
"""
Parse Intuit Tax Advisor table HTML (entire-table.php) into structured JSON and Markdown.
"""

import json
import re
import sys
from pathlib import Path


def extract_text(html: str) -> str:
    """Strip HTML tags and return clean text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_table(html: str) -> list[dict]:
    """Parse the table HTML into a list of row dicts with hierarchy."""
    rows = []
    # Match each <tr id="X">...</tr>
    tr_pattern = re.compile(
        r'<tr id="([\d.]+)"[^>]*>([\s\S]*?)</tr>',
        re.DOTALL
    )
    
    for match in tr_pattern.finditer(html):
        row_id = match.group(1)
        row_html = match.group(2)
        
        # Extract each column by td id
        def get_cell(col_id: str, raw: bool = False) -> str:
            td_pattern = rf'<td id="{col_id}"[^>]*>([\s\S]*?)</td>'
            m = re.search(td_pattern, row_html)
            if not m:
                return ""
            return m.group(1) if raw else extract_text(m.group(1))
        
        source = get_cell("source")
        actual = get_cell("actual")
        difference = get_cell("difference")
        basecase = get_cell("basecase")
        basecase_raw = get_cell("basecase", raw=True)
        # Input vs calculated: 2026 Baseline column has <input>/<select> for editable fields
        is_input = bool(basecase_raw and ("<input" in basecase_raw or "<select" in basecase_raw))
        
        # Extract tags from source cell (W-2, BOX 1, etc.)
        td_source = re.search(r'<td id="source"[^>]*>([\s\S]*?)</td>', row_html)
        tags = []
        if td_source:
            tags = re.findall(
                r'<span[^>]*class="[^"]*[Tt]ag[^"]*"[^>]*>([^<]+)</span>',
                td_source.group(1)
            )
        
        rows.append({
            "id": row_id,
            "source": source,
            "actual": actual,
            "difference": difference,
            "baseline": basecase,
            "tags": tags if tags else None,
            "depth": row_id.count("."),
            "type": "input" if is_input else "calculated",
        })
    
    return rows


def build_hierarchy(rows: list[dict]) -> list[dict]:
    """Convert flat list to nested structure by parent id."""
    id_to_node = {}
    roots = []
    
    for row in rows:
        node = {k: v for k, v in row.items() if k != "depth" and v is not None}
        node = {k: v for k, v in node.items() if v != "" and v != []}
        row_id = row["id"]
        id_to_node[row_id] = node
        
        if "." not in row_id:
            roots.append(node)
        else:
            parent_id = row_id.rsplit(".", 1)[0]
            parent = id_to_node.get(parent_id)
            if parent:
                if "children" not in parent:
                    parent["children"] = []
                parent["children"].append(node)
    
    return roots


def display_level(row: dict) -> int:
    """W-2 subsection (0.0, 0.0.x, 0.1, 0.2) starts at Level 2 per UI's sticky-second-level-header."""
    depth = row["depth"]
    rid = row.get("id", "")
    if rid.startswith("0.") and rid != "0":
        return depth + 1
    return depth


def to_markdown(rows: list[dict]) -> str:
    """Render rows as Markdown table with hierarchy."""
    lines = []
    lines.append("# Intuit Tax Advisor — Pre-Strategy Baseline Table")
    lines.append("")
    lines.append(
        "| Level | ID | Source | 2024 Actual | Difference | 2026 Baseline | Type | "
        "ITA data model path from metadata |"
    )
    lines.append(
        "|-------|-----|--------|-------------|------------|---------------|------|"
        "----------------------------------|"
    )

    for row in rows:
        level = display_level(row)
        indent = "  " * level
        source = indent + (row.get("source") or "")
        row_type = row.get("type", "")
        meta_path = row.get("ita_data_model_path_from_metadata", "") or ""
        lines.append(
            f"| {level} | {row['id']} | {source} | {row.get('actual', '')} | "
            f"{row.get('difference', '')} | {row.get('baseline', '')} | {row_type} | {meta_path} |"
        )
    
    return "\n".join(lines)


def to_markdown_tree(nested: list[dict], depth: int = 0, parent_id: str = "") -> str:
    """Render nested structure as Markdown with proper list nesting (sub-lists under parents)."""
    lines = []
    for node in nested:
        rid = node.get("id", "")
        # W-2 subsection starts at Level 2 (add 1 to indent for 0.0, 0.0.x, 0.1, 0.2)
        level = depth + (1 if rid.startswith("0.") and rid != "0" else 0)
        indent = "  " * level  # 2 spaces per level for Markdown list nesting
        source = node.get("source") or ""
        meta_path = node.get("ita_data_model_path_from_metadata", "") or ""
        tags = f" `{'` `'.join(node['tags'])}`" if node.get("tags") else ""
        values = []
        if node.get("actual"):
            values.append(f"Actual: {node['actual']}")
        if node.get("difference"):
            values.append(f"Diff: {node['difference']}")
        if node.get("baseline"):
            values.append(f"Baseline: {node['baseline']}")
        val_str = f" — {', '.join(values)}" if values else ""
        meta_str = f" [metadata: `{meta_path}`]" if meta_path else ""
        lines.append(f"{indent}- **{source}**{tags}{meta_str}{val_str}")
        if node.get("children"):
            lines.append(to_markdown_tree(node["children"], depth + 1, rid))
    return "\n".join(lines)


# W-2 expansion seed: injected when HTML has row 0 but no children (collapsed when copied)
# display_level() adds 1 for W-2 subsection so these show at Level 2+ in output
# type: input = editable 2026 Baseline, calculated = read-only
W2_EXPANSION_SEED = [
    {"id": "0.0", "source": "(S) W-2 Wages BOX 1", "actual": "320,000", "difference": "(220,000)", "baseline": "100,000", "tags": None, "depth": 1, "type": "input"},
    {"id": "0.0.0", "source": "EIN", "actual": "", "difference": "", "baseline": "", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.1", "source": "Retirement plan", "actual": "", "difference": "", "baseline": "", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.2", "source": "Federal withholding BOX 2", "actual": "30,000", "difference": "0", "baseline": "30,000", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.3", "source": "Social Security wages BOX 3", "actual": "168,600", "difference": "(68,600)", "baseline": "100,000", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.4", "source": "Social Security tax withheld BOX 4", "actual": "10,453", "difference": "(4,253)", "baseline": "6,200", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.5", "source": "Medicare wages BOX 5", "actual": "320,000", "difference": "(220,000)", "baseline": "100,000", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.0.6", "source": "Medicare withheld BOX 6", "actual": "", "difference": "", "baseline": "1,450", "tags": None, "depth": 2, "type": "input"},
    {"id": "0.1", "source": "(T) W-2 Wages BOX 1", "actual": "0", "difference": "0", "baseline": "", "tags": None, "depth": 1, "type": "input"},
    {"id": "0.2", "source": "Total W-2 wages", "actual": "320,000", "difference": "(220,000)", "baseline": "100,000", "tags": None, "depth": 1, "type": "calculated"},
]


# GenOS / ITA metadata (metadata.json): skip "No impact" source and duplicate QBI aggregate row
_METADATA_SKIP_SOURCES = {0, 22}


def _sort_line_items(items: list | None) -> list:
    if not items:
        return []
    return sorted(items, key=lambda x: (x.get("order", 0), str(x.get("type", ""))))


def _metadata_children(node: dict) -> list:
    ch = node.get("children")
    if ch:
        return ch
    agg = node.get("aggregate")
    if isinstance(agg, dict) and agg.get("children"):
        return agg["children"]
    return []


def _aggregate_sibling(node: dict) -> dict | None:
    """PARENT_AGGREGATE often has a sibling `aggregate` row (e.g. Total W-2) not in `children`."""
    agg = node.get("aggregate")
    return agg if isinstance(agg, dict) else None


def _skip_root_line_item(li: dict) -> bool:
    lab = (li.get("valueKeyLabel") or "").strip()
    return bool(lab.startswith("<#if"))


def build_filtered_metadata_roots(meta: dict) -> list[tuple[int, int, dict]]:
    """Top-level table rows in UI order: (source_index, line_item_index, node)."""
    roots: list[tuple[int, int, dict]] = []
    for i in range(len(meta.get("sources") or [])):
        if i in _METADATA_SKIP_SOURCES:
            continue
        src = meta["sources"][i]
        lis = _sort_line_items(src.get("lineItems"))
        for j, li in enumerate(lis):
            if _skip_root_line_item(li):
                continue
            roots.append((i, j, li))
    return roots


def _join_path(base: str, rel: str) -> str:
    if not rel:
        return base
    if rel.startswith("return."):
        return rel
    if base:
        return f"{base}.{rel}" if not base.endswith(".") else base + rel
    return rel


def _extend_ancestor_bases(bases: list[str], node: dict) -> list[str]:
    jp = (node.get("jsonPath") or "").strip()
    base = bases[-1] if bases else ""
    if jp.startswith("return."):
        return bases + [jp]
    if jp:
        if base:
            return bases + [_join_path(base, jp)]
        return bases + [jp]
    return bases


def _paths_from_node(node: dict, bases: list[str]) -> list[str]:
    base = bases[-1] if bases else ""
    out: list[str] = []
    jp = (node.get("jsonPath") or "").strip()
    if jp:
        if jp.startswith("return."):
            out.append(jp)
        elif base:
            out.append(_join_path(base, jp))
        else:
            out.append(jp)
    vti = (node.get("valueTemplateIdentifier") or "").strip()
    if vti:
        if base:
            out.append(_join_path(base, vti))
        else:
            out.append(vti)
    for d in node.get("data") or []:
        dj = (d.get("jsonPath") or "").strip()
        if not dj:
            continue
        if dj.startswith("return."):
            out.append(dj)
        elif base:
            out.append(_join_path(base, dj))
        else:
            out.append(dj)
    seen: set[str] = set()
    res: list[str] = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            res.append(x)
    return res


def metadata_node_for_row_id(row_id: str, roots: list[tuple[int, int, dict]]) -> dict | None:
    """Resolve metadata.json line item node for a table row id (same indexing as UI)."""
    parts = [int(x) for x in row_id.split(".")]
    if not parts or parts[0] >= len(roots):
        return None
    cur = roots[parts[0]][2]
    for p in parts[1:]:
        ch = _sort_line_items(_metadata_children(cur))
        if p >= len(ch):
            return None
        cur = ch[p]
    return cur


def metadata_paths_for_row_id(row_id: str, roots: list[tuple[int, int, dict]]) -> str:
    """All schema paths from metadata for this row (semicolon-separated)."""
    # W-2: UI rows (S), (T), Total share one metadata template; (T) repeats (S); Total is `aggregate`.
    if row_id == "0.1":
        return metadata_paths_for_row_id("0.0", roots)
    if row_id == "0.2":
        parts = [0]
        if parts[0] >= len(roots):
            return ""
        cur = roots[parts[0]][2]
        bases: list[str] = []
        bases = _extend_ancestor_bases(bases, cur)
        agg = _aggregate_sibling(cur)
        if not agg:
            return ""
        bases = _extend_ancestor_bases(bases, agg)
        return "; ".join(_paths_from_node(agg, bases))

    parts = [int(x) for x in row_id.split(".")]
    if not parts or parts[0] >= len(roots):
        return ""
    cur = roots[parts[0]][2]
    bases = []
    bases = _extend_ancestor_bases(bases, cur)
    for p in parts[1:]:
        ch = _sort_line_items(_metadata_children(cur))
        if p >= len(ch):
            return ""
        cur = ch[p]
        bases = _extend_ancestor_bases(bases, cur)
    paths = _paths_from_node(cur, bases)
    return "; ".join(paths)


def load_metadata_json(output_dir: Path) -> dict | None:
    p = output_dir / "metadata.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_existing(output_dir: Path) -> tuple[list[dict], list[dict]]:
    """Load existing parsed data if present. Returns (flat_rows, nested_roots)."""
    json_path = output_dir / "intuit-table-parsed.json"
    if not json_path.exists():
        return [], []
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("flat", []), data.get("nested", [])
    except (json.JSONDecodeError, IOError):
        return [], []


def main():
    input_path = Path(__file__).parent / "entire-table.php"
    output_dir = Path(__file__).parent
    
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)
    
    print("Parsing HTML...", file=sys.stderr)
    html = input_path.read_text(encoding="utf-8", errors="replace")
    
    new_rows = parse_table(html)
    print(f"Parsed {len(new_rows)} rows from HTML", file=sys.stderr)
    
    existing_flat, _ = load_existing(output_dir)
    existing_by_id = {r["id"]: r for r in existing_flat}
    new_ids = {r["id"] for r in new_rows}

    def to_flat(r: dict) -> dict:
        return {
            "id": r["id"],
            "source": r["source"],
            "actual": r["actual"],
            "difference": r["difference"],
            "baseline": r.get("basecase", r.get("baseline", "")),
            "tags": r.get("tags"),
            "depth": r["depth"],
            "type": r.get("type", "calculated"),
            "ita_data_model_path_from_metadata": r.get("ita_data_model_path_from_metadata", ""),
        }

    # Merge: keep existing rows that are missing from new HTML (e.g. collapsed sections),
    # add/update with rows from new parse. This preserves W-2 expansion when user
    # copies table with W-2 collapsed but other sections expanded.
    merged_by_id = dict(existing_by_id)
    for r in new_rows:
        merged_by_id[r["id"]] = to_flat(r)

    # If W-2 row 0 exists but 0.0 doesn't (collapsed when copied), inject W-2 expansion seed
    if "0" in merged_by_id and "0.0" not in merged_by_id:
        print("Injecting W-2 expansion seed (section was collapsed in HTML)", file=sys.stderr)
        for r in W2_EXPANSION_SEED:
            merged_by_id[r["id"]] = to_flat(r)

    # Ensure all rows have type; preserved rows from collapsed sections default to calculated
    for r in merged_by_id.values():
        if "type" not in r or r["type"] not in ("input", "calculated"):
            r["type"] = "calculated"

    for r in merged_by_id.values():
        r.pop("ita_data_model_path", None)

    # Enrich with schema paths from metadata.json (UI line-item definitions)
    meta_doc = load_metadata_json(output_dir)
    meta_roots = build_filtered_metadata_roots(meta_doc) if meta_doc else []
    if not meta_doc:
        print("metadata.json not found — ITA data model path from metadata left empty", file=sys.stderr)
    elif meta_roots:
        print(f"Loaded metadata.json ({len(meta_roots)} top-level rows for path resolution)", file=sys.stderr)
    for r in merged_by_id.values():
        r["ita_data_model_path_from_metadata"] = (
            metadata_paths_for_row_id(r["id"], meta_roots) if meta_roots else ""
        )

    # Sort by row id to maintain hierarchy (parent before child)
    def sort_key(rid: str) -> list:
        return [int(x) for x in rid.split(".")]

    merged_flat = sorted(merged_by_id.values(), key=lambda r: sort_key(r["id"]))
    merged_rows = merged_flat

    added = new_ids - set(existing_by_id)
    preserved = set(existing_by_id) - new_ids
    if added:
        print(f"Added {len(added)} rows from HTML", file=sys.stderr)
        for rid in sorted(added, key=sort_key)[:10]:
            print(f"  + {rid}: {merged_by_id[rid].get('source', '')}", file=sys.stderr)
        if len(added) > 10:
            print(f"  ... and {len(added) - 10} more", file=sys.stderr)
    if preserved:
        print(f"Preserved {len(preserved)} rows not in HTML (collapsed sections kept)", file=sys.stderr)

    nested = build_hierarchy(merged_rows)
    
    json_path = output_dir / "intuit-table-parsed.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "nested": nested,
            "flat": merged_flat,
            "row_count": len(merged_flat),
        }, f, indent=2, ensure_ascii=False)
    print(f"Wrote {json_path} ({len(merged_flat)} rows)", file=sys.stderr)
    
    md_path = output_dir / "intuit-table-parsed.md"
    tree_section = "## Hierarchical View (Nested)\n\n" + to_markdown_tree(nested)
    md_content = to_markdown(merged_rows) + "\n\n---\n\n" + tree_section
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Wrote {md_path}", file=sys.stderr)

    # Sources-only view: Level | ID | Source | Type | ITA data model path from metadata (no value columns)
    lines_src = ["# Intuit Tax Advisor — Pre-Strategy Baseline Table\n", ""]
    lines_src.append("| Level | ID | Source | Type | ITA data model path from metadata |")
    lines_src.append("|-------|-----|--------|------|----------------------------------|")
    for row in merged_flat:
        level = display_level(row)
        indent = "  " * level
        source = indent + (row.get("source") or "")
        meta_path = row.get("ita_data_model_path_from_metadata", "") or ""
        lines_src.append(
            f"| {level} | {row['id']} | {source} | {row.get('type', '')} | {meta_path} |"
        )
    src_path = output_dir / "intuit-table-parsed-sources-only.md"
    src_path.write_text("\n".join(lines_src), encoding="utf-8")
    print(f"Wrote {src_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
