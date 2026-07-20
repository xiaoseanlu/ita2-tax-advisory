"""
Extract and classify ITA strategy input fields from .spe source.

Shared by outline_strategy_inputs.py and (optionally) the full 1040 feasibility
report. No third-party deps — stdlib only.
"""
from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Any

INPUT_PHASE_RE = re.compile(
    r"input\s+'?(?:result\.)?(base|projection|actual)\.(return\.[A-Za-z0-9_.]+)"
)
INPUT_JSONPATH_RE = re.compile(r"input\s+'(\$\.[^']+)'")
INCLUDE_RE = re.compile(r"%include\s+'([^']+)'")
EXPR_LEAF_RE = re.compile(r"\.(?:federal|general|state)\.([A-Za-z0-9_]+)")
TEMPLATE_RE = re.compile(r"\$\{")

CALCULATED_SECTIONS = (
    "usITAIndexedAmount",
    "usITATaxpayerItems",
    "usITASpouseItems",
    "usITASummary",
    "usITAQBI",
    "usITADependents",
    "usSummReport",
    "usMain",
)

USER_INPUT_LEAF_OVERRIDES = {
    "filingStatus": "Taxpayer selection (single/MFJ/MFS/HOH/QW).",
    "taxYear": "Context/input value, not an engine computation.",
    "primaryResidentState": "Entered/selected home state.",
    "primaryResidentFullStateName": "Entered/selected home state (full name).",
    "nonDeductibleIRA": "Form 8606 nondeductible IRA basis — user-tracked.",
    "rothCont": "Actual Roth contribution elected by taxpayer.",
    "sepIRA": "Actual SEP-IRA contribution — preparer/taxpayer entry.",
    "solo401kContribution": "Actual solo 401(k) contribution — entered.",
    "sePremiums": "Self-employed health insurance premiums paid.",
    "studentLoanInterestPaid": "Interest paid (e.g. Form 1098-E).",
    "familyCoverageHSA": "HSA coverage type (family) — plan fact.",
    "selfOnlyCoverageHSA": "HSA coverage type (self-only) — plan fact.",
    "resEnergyInput": "Residential energy credit qualifying expenditure.",
}

DEAD_REFERENCE_LEAVES = {
    "qbiLimitation": "Commented out in QBI/qbi.spe — not a live input.",
    "spouse": "retirement.spouse commented out in SEP-IRA.spe — not live.",
}

# Infer likely source document from ITA path (heuristic; same rules as feasibility script).
SRC_DOC_RULES = [
    (r"usWageInp|usWageSum|^wg[A-Z0-9]|^wages[0-9A-Za-z]", "W-2",
     "Wage & withholding detail — W-2 boxes."),
    (r"wages401kContribution|designated401kRoth", "W-2 Box 12 code D/AA",
     "401(k) elective deferral — W-2 Box 12."),
    (r"wages403bContribution|designated403bRoth", "W-2 Box 12 code E/BB",
     "403(b) deferral — W-2 Box 12."),
    (r"wg457b|designated457bRoth", "W-2 Box 12 code G/EE",
     "457(b) deferral — W-2 Box 12."),
    (r"wgDCB", "W-2 Box 10", "Dependent-care benefits — W-2 Box 10."),
    (r"healthSavingsAccount|wg501c", "W-2 Box 12 code W",
     "HSA contributions — W-2 Box 12 code W."),
    (r"eINemp|namEmp", "W-2 employer info", "Employer name / EIN from W-2."),
    (r"distCode|nameOfPensPayer|pensionTpSp", "1099-R",
     "Pension/IRA distribution detail — Form 1099-R."),
    (r"usDivSum|federalDividend", "1099-DIV", "Per-payer dividend detail."),
    (r"usIntSum|federalInterest", "1099-INT", "Per-payer interest detail."),
    (r"usCapGain|federalCapital|form4797", "1099-B / broker",
     "Per-lot capital-gain detail."),
    (r"iraSepSimple|IRAContr|spIRAContr|tpIRAContr", "IRA statement / Form 5498",
     "IRA/SEP/SIMPLE contribution."),
    (r"SEElectDef|SEPContr|EElectDef|EPContr|spsE", "Self-employed plan records",
     "Self-employed retirement contribution."),
    (r"usPShipInp", "Schedule K-1 (1065)", "Partnership K-1 detail."),
    (r"usScorpInp", "Schedule K-1 (1120-S)", "S-corp K-1 detail."),
    (r"usBusIncInp", "Sole-prop books", "Schedule C line detail."),
    (r"usRentRoyInp", "Rental records", "Schedule E per-property detail."),
    (r"usFarmIncInp", "Farm records", "Schedule F detail."),
    (r"substantiatedEmployeeExp|AccountableReimbursement", "Employee-expense records",
     "Substantiated employee expenses."),
    (r"fsaContribution", "Benefits statement", "FSA contribution."),
    # --- Schedule A (itemized) ---
    (r"mortgageInterest|mtgeIntPts|totIntPd", "Schedule A", "Mortgage interest — Schedule A."),
    (r"realEstTax", "Schedule A", "Real-estate tax — Schedule A."),
    (r"itemDedAll|itemizedDeduction|usItemDed", "Schedule A", "Itemized deductions — Schedule A."),
    (r"CharCont|totAllContr|totalAvailCharCont|cash50Lim|noncash", "Schedule A",
     "Charitable contributions — Schedule A."),
    (r"medExp|totAllowMedExp|usItemDedSumAGI75", "Schedule A",
     "Medical expenses — Schedule A."),
    (r"usTaxesLimitation|usTaxesTotalStateandLocal|sALT", "Schedule A",
     "SALT / taxes — Schedule A."),
]


def leaf_of(path: str) -> str:
    seg = path.rstrip(".").split(".")[-1]
    return re.sub(r"\[.*?\]", "", seg)


def read_spe(path: str | Path) -> str:
    try:
        return Path(path).read_text(errors="ignore")
    except OSError:
        return ""


def norm_jsonpath(jp: str) -> tuple[str | None, bool]:
    """Normalize jsonpath to return.<path>. Returns (path_or_None, is_template)."""
    if TEMPLATE_RE.search(jp):
        core = re.sub(r"\[\?\(@[^]]*\)\]", "", jp)
        m = re.search(r"return\.[A-Za-z0-9_.]+", core)
        if m and not TEMPLATE_RE.search(m.group(0)):
            return m.group(0), False
        return None, True
    core = re.sub(r"\[\?\(@[^]]*\)\]", "", jp)
    m = re.search(r"return\.[A-Za-z0-9_.]+", core)
    if m:
        return m.group(0), False
    return None, False


def categorize(path: str, source_kind: str) -> str:
    if source_kind == "prior-year":
        return "prior-year"
    if source_kind == "template":
        return "undeterminable-template"
    leaf = leaf_of(path)
    if leaf in USER_INPUT_LEAF_OVERRIDES:
        return "user-data"
    if any(sec in path for sec in CALCULATED_SECTIONS):
        return "calculated"
    return "user-data"


def infer_source_doc(path: str) -> tuple[str, str]:
    for pat, doc, note in SRC_DOC_RULES:
        if re.search(pat, path):
            return doc, note
    return (
        "user answer / source doc",
        "Not matched to a known IRS document pattern — likely a user question or source-doc field.",
    )


def list_strategies(content_repo: str | Path) -> list[str]:
    strat_dir = Path(content_repo) / "IndUS" / "strategies"
    if not strat_dir.is_dir():
        raise FileNotFoundError(f"Strategies dir not found: {strat_dir}")
    names = []
    for name in sorted(os.listdir(strat_dir)):
        sdir = strat_dir / name
        if not sdir.is_dir() or name == "common":
            continue
        if glob.glob(str(sdir / "*.spe")):
            names.append(name)
    return names


def resolve_strategy_name(content_repo: str | Path, query: str) -> str:
    """Exact match, else case-insensitive, else unique substring match."""
    names = list_strategies(content_repo)
    if query in names:
        return query
    lower = {n.lower(): n for n in names}
    if query.lower() in lower:
        return lower[query.lower()]
    hits = [n for n in names if query.lower() in n.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise ValueError(f"No strategy matching {query!r}. Use --list to see names.")
    raise ValueError(
        "Ambiguous strategy %r. Matches:\n  - %s" % (query, "\n  - ".join(hits))
    )


def _rel_under_indus(content_repo: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to((content_repo / "IndUS").resolve()))
    except ValueError:
        return str(path)


def resolve_include_closure(
    content_repo: str | Path,
    entry_spe_paths: list[str | Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Recursively resolve %include directives (cycle-safe).

    Returns:
      files: list of {rel_path, abs_path, depth, included_from, is_entry, missing}
      missing: list of include paths that were referenced but not found on disk
    """
    content_repo = Path(content_repo)
    indus = content_repo / "IndUS"
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    seen: set[str] = set()

    def walk(abs_path: Path, depth: int, included_from: str | None, is_entry: bool) -> None:
        abs_path = abs_path.resolve()
        key = str(abs_path)
        if key in seen:
            return
        if not abs_path.is_file():
            return
        seen.add(key)
        rel = _rel_under_indus(content_repo, abs_path)
        files.append({
            "rel_path": rel,
            "abs_path": str(abs_path),
            "depth": depth,
            "included_from": included_from,
            "is_entry": is_entry,
        })
        text = read_spe(abs_path)
        for inc in INCLUDE_RE.findall(text):
            child = (indus / inc).resolve()
            if not child.is_file():
                missing.append(inc)
                continue
            walk(child, depth + 1, rel, False)

    for entry in entry_spe_paths:
        walk(Path(entry), 0, None, True)

    # stable order: by depth then path
    files.sort(key=lambda f: (f["depth"], f["rel_path"]))
    return files, sorted(set(missing))


def extract_inputs_from_text(
    text: str,
    *,
    defined_in: str,
    fields: dict[tuple[str, str], dict[str, Any]],
    from_include: bool,
    extract_expr_leaves: bool = True,
) -> None:
    """Parse input / jsonpath / expr-leaf refs from one .spe body into `fields`."""

    def add_field(path: str, source_kind: str) -> None:
        key = (path, source_kind)
        if key in fields:
            existing = fields[key]
            if from_include:
                existing["shared"] = True
            # Keep first defined_in; record additional files
            extras = existing.setdefault("also_defined_in", [])
            if defined_in != existing["defined_in"] and defined_in not in extras:
                extras.append(defined_in)
            return
        leaf = leaf_of(path)
        cat = categorize(path, source_kind)
        doc, note = ("", "")
        if cat == "user-data" and not DEAD_REFERENCE_LEAVES.get(leaf):
            doc, note = infer_source_doc(path)
        fields[key] = {
            "path": path,
            "leaf": leaf,
            "source_kind": source_kind,
            "category": cat,
            "shared": from_include,
            "defined_in": defined_in,
            "also_defined_in": [],
            "dead_reference": DEAD_REFERENCE_LEAVES.get(leaf, ""),
            "override_note": USER_INPUT_LEAF_OVERRIDES.get(leaf, ""),
            "likely_source_doc": doc,
            "likely_source_note": note,
        }

    for phase, retpath in INPUT_PHASE_RE.findall(text):
        sk = "prior-year" if phase == "actual" else "base"
        add_field(retpath, sk)
    for jp in INPUT_JSONPATH_RE.findall(text):
        norm, is_tmpl = norm_jsonpath(jp)
        if is_tmpl:
            add_field(jp, "template")
        elif norm:
            sk = "prior-year" if ".actual." in jp else "jsonpath"
            add_field(norm, sk)
        else:
            add_field(jp, "template")
    if extract_expr_leaves:
        for leaf in EXPR_LEAF_RE.findall(text):
            add_field(leaf, "expr-leaf")


def strategy_entry_spe_files(sdir: Path) -> list[Path]:
    """
    Entry SPE files for a strategy folder.

    Prefer the main `{Name}.spe` (and any other non-*common* / non-test SPE).
    Local `* common.spe` files are reached via %include, same as shared
    `strategies/common/*.spe`.
    """
    all_spe = sorted(sdir.glob("*.spe"))
    if not all_spe:
        return []
    entries = [
        p
        for p in all_spe
        if not p.name.endswith(" common.spe")
        and "/test/" not in str(p)
        and not p.name.endswith("_test.spe")
    ]
    return entries or all_spe


def extract_strategy_inputs(
    content_repo: str | Path,
    strategy_name: str,
    *,
    return_include_tree: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """
    Return deduped field dicts for one strategy, with %include files resolved
    recursively (same idea as the original feasibility script, plus nesting).

    Each field includes `defined_in` (path under IndUS where the input appears).

    If return_include_tree=True, also returns (fields, include_files, missing_includes).
    """
    content_repo = Path(content_repo)
    name = resolve_strategy_name(content_repo, strategy_name)
    sdir = content_repo / "IndUS" / "strategies" / name
    entries = strategy_entry_spe_files(sdir)
    if not entries:
        raise FileNotFoundError(f"No .spe files in {sdir}")

    include_files, missing = resolve_include_closure(content_repo, entries)
    fields: dict[tuple[str, str], dict[str, Any]] = {}

    for meta in include_files:
        text = read_spe(meta["abs_path"])
        extract_inputs_from_text(
            text,
            defined_in=meta["rel_path"],
            fields=fields,
            from_include=not meta["is_entry"],
            # Expr leaves only from strategy/entry files — mirrors original
            # (common includes contributed phase/jsonpath inputs, not expr leaves).
            extract_expr_leaves=meta["is_entry"],
        )

    result = sorted(fields.values(), key=lambda f: (f["category"], f["path"]))
    if return_include_tree:
        return result, include_files, missing
    return result


def summarize(fields: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in fields:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    return counts
