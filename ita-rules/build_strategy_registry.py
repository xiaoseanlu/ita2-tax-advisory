#!/usr/bin/env python3
"""One-shot builder: strategy-registry.json + strategy-outlines/* from SPE extraction."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from spe_inputs import extract_strategy_inputs, list_strategies, resolve_strategy_name  # noqa: E402

CONTENT = Path.home() / "Documents" / "GitHub" / "tax-strategy-content"
OUTLINES = _HERE / "strategy-outlines"
REGISTRY = _HERE / "strategy-registry.json"
OUTLINE_SCRIPT = _HERE / "outline_strategy_inputs.py"

# display_name, slug, spe_folder, category, ita_id, skill_dir (optional)
STRATEGIES = [
    ("401(k) Employee Contribution", "401k-employee", "401k Employee Contribution", "retirement", "ita_034", None),
    ("Flex Spending Account", "fsa-contribution", "FSA Contribution", "health", "ita_013", None),
    ("401(k) Employer Contribution", "401k-employer", "401k Employer Contribution", "retirement", "ita_035", None),
    ("Traditional IRA", "traditional-ira", "Traditional IRA", "retirement", "ita_045", None),
    ("Bonus depreciation", "bonus-depreciation", "Bonus Depreciation", "business", "ita_025", None),
    ("S-Corporation entity selection", "scorp-conversion", "Scorp", "business", "ita_002", "skills/income_tax/assisted/scorp-conversion"),
    ("Augusta Rule - tax-free rental income", "augusta-rule-rental", "Augusta Rule-Rental Income (Tax Free)", "business", "ita_018", None),
    ("Section 179", "section-179", "Section 179", "business", "ita_026", None),
    ("Accountable Reimbursement Plan as Employer", "accountable-reimb-employer", "Accountable Reimbursement Plan as Employer", "business", "ita_007", None),
    ("SEP-IRA", "sep-ira", "SEP-IRA", "retirement", "ita_043", None),
    ("S Corp Compensation Analysis", "scorp-compensation", "Scorp Compensation Analysis", "business", "ita_003", None),
    ("Bunching Itemized Deductions", "bunching-itemized", "Bunching Itemized Deductions", "deduction", "ita_008", None),
    ("Residential Energy Credit", "residential-energy-credit", "Residential Energy Credit", "credit", "ita_048", None),
    ("Solo 401(k)", "solo-401k", "Solo 401k Contribution", "retirement", "ita_044", "skills/income_tax/assisted/solo-401k"),
    ("Roth IRA conversion", "roth-ira-conversion", "Roth IRA Conversion", "retirement", "ita_042", None),
    ("Donor Advised Fund To Time Contributions", "donor-advised-fund", "Donor Advised Fund To Time Contributions", "charity", "ita_050", None),
    ("Business Use of Home", "business-use-of-home", "business use of home", "deduction", "ita_009", None),
    ("Medical Expense Reimbursement Plan", "merp", "Medical Expense Reimbursement Plan", "business", "ita_016", None),
    ("Optimize QBI", "qbi-minimize-phase-out", "QBI Minimize Phase Out", "business", "ita_029", None),
    ("Tax loss harvesting (long-term)", "tax-loss-harvesting-lt", "Tax Loss Harvesting - LT", "capital", "ita_022", None),
    ("Accountable Reimbursement Plan as Employee", "accountable-reimb-employee", "Accountable Reimbursement Plan as Employee", "business", "ita_006", None),
    ("Capital gain timing", "capital-gain-timing", "Capital Gain Timing", "capital", "ita_019", None),
    ("HSA Contribution", "hsa-contribution", "HSA Contribution", "health", "ita_015", None),
    ("Cost Segregation Study", "cost-segregation", "Cost Segregation Study", "business", "ita_027", None),
    ("Donating Appreciated Stock", "donate-appreciated-stock", "Donating Appreciated Stock to Charity", "charity", "ita_049", None),
    ("Hire Your Kids", "hire-your-kids", "Hire Your Kids", "business", "ita_020", None),
    ("Dependent Care Reimbursement", "dependent-care-reimbursement", "Dependent Care Reimbursement", "health", "ita_012", None),
    ("Roth IRA contribution", "roth-ira-contribution", "Roth IRA Contribution", "retirement", "ita_041", None),
    ("Mega Backdoor Roth", "mega-backdoor-roth", "Mega Backdoor Roth", "retirement", "ita_040", None),
    ("Like-kind exchange", "like-kind-exchange", "Like Kind Exchange", "capital", "ita_017", None),
    ("Real Estate Professional", "real-estate-professional", "realEstateProfessional", "business", "ita_001", None),
    ("Backdoor Roth IRA", "backdoor-roth-ira", "Backdoor Roth IRA", "retirement", "ita_039", None),
    ("Tax loss harvesting (short-term)", "tax-loss-harvesting-st", "Tax Loss Harvesting - ST", "capital", "ita_023", None),
    ("Combine business and personal travel", "combined-business-travel", "Combined Business and Personal Travel", "deduction", "ita_010", None),
    ("403(b) Employee Contribution", "403b-employee", "403b Employee Contribution", "retirement", "ita_036", None),
    ("Third party installment sale", "third-party-installment-sale", "Third Party Installment Sale", "capital", "ita_024", None),
    ("Pass-through-Entity-Tax", "ptet", "PTET", "business", None, None),
    ("Hire your Spouse", "hire-your-spouse", "Hire Your Spouse", "business", "ita_021", None),
    ("Child Tax Credit", "child-tax-credit", "Child Tax Credit", "credit", "ita_047", None),
    ("QBI Deduction", "qbi-deduction", "QBI", "business", "ita_028", None),
    ("IRA QCD", "ira-qcd", "IRA QCD", "charity", "ita_051", None),
    ("Stock Gift For Childrens Tution", "stock-gift-children-tuition", "Stock gift for childrens tuition", "capital", None, None),
    ("Student loan payments made by employer", "student-loan-employer", "Student loan payments made by employer", "deduction", "ita_011", None),
    ("Startup Amortize", "startup-amortize", "Startup Amortize", "business", "ita_030", None),
    ("Startup Expense", "startup-expense", "Startup Expense", "business", "ita_031", None),
]

GATE_PATTERNS = [
    (re.compile(r"applicability\s+\w+", re.I), "applicability"),
    (re.compile(r"recommend\w*\s*=", re.I), "recommendation"),
    (re.compile(r"\bmarriedMAGI\b"), "married filing status"),
    (re.compile(r"deleteNextYear\s*==\s*0"), "active activity (deleteNextYear==0)"),
    (re.compile(r"sepIRA\s*==\s*0"), "no SEP-IRA conflict"),
    (re.compile(r"maxAllowedContribution\s*>\s*0"), "contribution headroom"),
    (re.compile(r"seIncome\s*>\s*0"), "positive SE income"),
    (re.compile(r"netIncome\s*>\s*0|netEarnings\s*>\s*0", re.I), "positive net income"),
    (re.compile(r"filingStatus", re.I), "filing status check"),
]

LEVER_LEAVES = {
    "strategyChange", "strategy_change", "STRATEGY_CHANGE",
    "wagePopup", "netIncomeAllocatedToWages", "reasonableWage",
    "wages401kContribution", "wages403bContribution", "solo401kContribution",
    "sepIRA", "rothCont", "fsaContribution", "healthSavingsAccount",
    "resEnergyInput", "CharCont", "totalAvailCharCont",
}

SAVINGS_LEAVES = {
    "projectedTaxSavings", "PROJECTED_TAX_SAVINGS", "taxSavings",
    "marginalRate", "marginalRateTotal", "MARGINAL_RATE_TOTAL",
    "stateMarginalRate", "marginalNYC",
}


def spe_found(folder: str, all_names: set[str]) -> bool:
    if folder in all_names:
        return True
    try:
        resolve_strategy_name(CONTENT, folder)
        return True
    except (ValueError, FileNotFoundError):
        return False


def extract_gates(resolved_name: str, include_tree: list[dict]) -> list[str]:
    gates: list[str] = []
    entry_paths = [
        CONTENT / "IndUS" / "strategies" / resolved_name / f"{resolved_name.replace(' ', '')}.spe",
    ]
    for meta in include_tree or []:
        if meta.get("is_entry"):
            entry_paths.append(CONTENT / "IndUS" / "strategies" / meta["rel_path"])
    # Also glob primary .spe in folder
    folder = CONTENT / "IndUS" / "strategies" / resolved_name
    if folder.is_dir():
        entry_paths.extend(folder.glob("*.spe"))

    seen_text = set()
    for path in entry_paths:
        if not path.is_file():
            continue
        key = str(path)
        if key in seen_text:
            continue
        seen_text.add(key)
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for pat, label in GATE_PATTERNS:
            if pat.search(text) and label not in gates:
                gates.append(label)
    return gates[:12]


def advisor_lever_guess(fields: list[dict]) -> str:
    leaves = {f.get("leaf", "") for f in fields}
    hits = []
    if leaves & {"strategyChange", "STRATEGY_CHANGE"}:
        hits.append("STRATEGY_CHANGE")
    if leaves & {"wagePopup", "netIncomeAllocatedToWages", "reasonableWage"}:
        hits.append("reasonable wage / W-2")
    for c in ("wages401kContribution", "wages403bContribution", "solo401kContribution", "sepIRA", "rothCont"):
        if c in leaves:
            hits.append(f"contribution ({c})")
    if leaves & {"fsaContribution", "healthSavingsAccount"}:
        hits.append("benefits contribution")
    if leaves & {"CharCont", "totalAvailCharCont"}:
        hits.append("charitable amount")
    if leaves & {"resEnergyInput"}:
        hits.append("energy expenditure")
    return "; ".join(hits) if hits else "Not obvious from extracted field leaves — inspect primary .spe"


def savings_formula_note(fields: list[dict]) -> str:
    leaves = {f.get("leaf", "") for f in fields}
    has_savings = bool(leaves & SAVINGS_LEAVES or any("taxSavings" in (f.get("path") or "") for f in fields))
    has_marginal = bool(leaves & SAVINGS_LEAVES or any("marginal" in (f.get("leaf") or "").lower() for f in fields))
    if has_savings and has_marginal:
        return "Likely `PROJECTED_TAX_SAVINGS ≈ STRATEGY_CHANGE × MARGINAL_RATE` pattern — verify in primary .spe"
    if has_marginal:
        return "Marginal rate fields present; savings formula may multiply strategy change by combined marginal rate"
    if has_savings:
        return "Tax savings fields referenced; formula in primary .spe / strategyCard"
    return "No PROJECTED_TAX_SAVINGS / MARGINAL_RATE leaves in extracted inputs — savings may be computed only in engine scope"


def write_markdown(
    slug: str,
    display_name: str,
    resolved_name: str,
    payload: dict,
) -> None:
    fields = payload["fields"]
    summary = payload["summary"]
    live_user = [
        f for f in fields
        if f["category"] == "user-data" and not f.get("dead_reference")
    ]
    # dedupe by leaf for table
    by_leaf: dict[str, dict] = {}
    for f in live_user:
        leaf = f["leaf"]
        if leaf not in by_leaf:
            by_leaf[leaf] = f

    gates = extract_gates(resolved_name, payload.get("include_tree") or [])
    lever = advisor_lever_guess(fields)
    savings = savings_formula_note(fields)

    lines = [
        f"# {display_name}",
        "",
        f"**SPE folder:** `{resolved_name}`",
        "",
    ]
    if gates:
        lines.extend(["## Applicable gates (heuristic from .spe)", ""] + [f"- {g}" for g in gates] + [""])
    else:
        lines.extend(["## Applicable gates", "", "_Not extractable from static outline — review primary .spe._", ""])

    lines.extend(["## USER INPUTS (live user-data fields)", ""])
    if by_leaf:
        lines.append("| Field | Likely source | Notes |")
        lines.append("|-------|---------------|-------|")
        for leaf in sorted(by_leaf):
            f = by_leaf[leaf]
            doc = f.get("likely_source_doc") or "—"
            note = f.get("override_note") or ""
            lines.append(f"| `{leaf}` | {doc} | {note} |")
    else:
        lines.append("_No live user-data fields extracted._")
    lines.append("")

    lines.extend(["## ENGINE fields summary", ""])
    for cat, count in sorted(summary.items()):
        lines.append(f"- **{cat}:** {count}")
    lines.append(f"- **total extracted:** {len(fields)}")
    lines.append("")

    lines.extend(["## Advisor lever (guess)", "", lever, ""])
    lines.extend(["## Savings formula note", "", savings, ""])

    (OUTLINES / f"{slug}.md").write_text("\n".join(lines) + "\n")


def run_outline_json(spe_folder: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(OUTLINE_SCRIPT), spe_folder, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return json.loads(proc.stdout)


def main() -> int:
    OUTLINES.mkdir(parents=True, exist_ok=True)
    all_names = set(list_strategies(CONTENT))
    registry = []
    outlined = 0
    missing_spe: list[str] = []

    for display_name, slug, spe_folder, category, ita_id, skill_dir in STRATEGIES:
        found = spe_found(spe_folder, all_names)
        if skill_dir:
            status = "implemented"
        elif found:
            status = "outlined"
        else:
            status = "missing_spe"
            missing_spe.append(spe_folder)

        entry = {
            "id": slug,
            "display_name": display_name,
            "spe_folder": spe_folder,
            "spe_found": found,
            "skill_dir": skill_dir,
            "status": status if found or status == "missing_spe" else "missing_spe",
            "category": category,
        }
        if ita_id:
            entry["ita_id"] = ita_id
        registry.append(entry)

        if not found:
            continue

        try:
            payload = run_outline_json(spe_folder)
        except Exception as e:
            print(f"WARN outline failed for {spe_folder}: {e}", file=sys.stderr)
            entry["status"] = "missing_spe"
            entry["spe_found"] = False
            missing_spe.append(spe_folder)
            continue

        resolved = payload["strategy"]
        (OUTLINES / f"{slug}.json").write_text(json.dumps(payload, indent=2) + "\n")
        write_markdown(slug, display_name, resolved, payload)
        if status != "implemented":
            outlined += 1

    REGISTRY.write_text(json.dumps(registry, indent=2) + "\n")
    print(f"registry: {REGISTRY}")
    print(f"outlined (non-implemented): {outlined}")
    print(f"missing SPE: {len(missing_spe)}")
    if missing_spe:
        for m in missing_spe:
            print(f"  - {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
