#!/usr/bin/env python3
"""Build web_ui/ita-tps-field-catalog.json from biztax-savings tax-model-schema.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = Path(
    os.environ.get(
        "TAX_MODEL_SCHEMA",
        str(ROOT / "ita-rules" / "tax-model-schema.json"),
    )
)
OUT = ROOT / "web_ui" / "ita-tps-field-catalog.json"


def index_by_name(obj, trail=None, idx=None):
    if idx is None:
        idx = {}
    if trail is None:
        trail = []
    if isinstance(obj, dict):
        n = obj.get("name")
        t = trail + ([n] if n else [])
        if n and obj.get("products"):
            path = ".".join(t)
            existing = {p for p, _ in idx.get(n, [])}
            if path not in existing:
                idx.setdefault(n, []).append((path, obj))
        for c in obj.get("children") or []:
            index_by_name(c, t, idx)
    return idx


def collect_schema_names(obj, names=None):
    """Every node `name` in the schema (with or without product mappings)."""
    if names is None:
        names = set()
    if isinstance(obj, dict):
        n = obj.get("name")
        if n:
            names.add(n)
        for c in obj.get("children") or []:
            collect_schema_names(c, names)
    return names


def tps_label(node: dict) -> dict:
    """Extract TURBO_TAX native mapping only (no Lacerte / ProSeries fallback)."""
    prods = node.get("products") or []
    turbo = next(
        (pr for pr in prods if "TURBO_TAX" in (pr.get("ids") or [])),
        None,
    )
    out: dict = {"tps": None, "has_turbo_tax": False}
    if not turbo:
        return out

    out["has_turbo_tax"] = True
    addr = turbo.get("nativeAddress") or ""
    parts = dict(p.split("=", 1) for p in addr.split(", ") if "=" in p)
    form = parts.get("form")
    field = parts.get("field")
    transforms = turbo.get("transformations") or []

    # Prefer transformation "fields" when present (e.g. mapSelected →
    # FSCHC.OWNT,FSCHC.OWNS,FSCHC.OWNJ → FSCHC.OWNT/FSCHC.OWNS/FSCHC.OWNJ).
    fields_val = None
    for tr in transforms:
        for a in tr.get("args") or []:
            if a.get("name") == "fields" and a.get("value"):
                fields_val = str(a["value"])
                break
        if fields_val:
            break
    if fields_val:
        out["tps"] = "/".join(
            f.strip() for f in fields_val.replace(";", ",").split(",") if f.strip()
        )
    elif form and field:
        out["tps"] = f"{form}.{field}"
    elif transforms:
        for tr in transforms:
            args = {
                a["name"]: a.get("value")
                for a in (tr.get("args") or [])
                if "name" in a
            }
            if tr.get("type") == "constant":
                out["tps"] = f"{form or 'const'}={args.get('value')}"
                break
            if tr.get("type") == "taxMlTableRow":
                out["tps"] = (
                    f"{args.get('formId')}.{args.get('tableId')}."
                    f"{args.get('fieldId')}[row={args.get('tableRow')}]"
                )
                break
        if not out["tps"]:
            out["tps"] = form or addr or None
    else:
        out["tps"] = f"{form}.{field}" if form and field else (form or addr or None)
    return out


SCORP = [
    {
        "ui_key": "net_income",
        "label": "Net income",
        "schema_name": "itaNetProfitLoss",
        "prefer_path_contains": "usBusIncInp",
        "role": "input",
        "value_from": "activity.net_income",
    },
    {
        "ui_key": "ownership_pct",
        "label": "Ownership %",
        "schema_name": "ownershipPct",
        "prefer_path_contains": "usPShipInp",
        "role": "input",
        "value_from": "activity.ownership_pct",
    },
    {
        "ui_key": "owner_code",
        "label": "Owned by (busTpSpJt)",
        "schema_name": "busTpSpJt",
        "prefer_path_contains": "usBusIncInp",
        "role": "input",
        "value_from": "activity.taxpayer_spouse_or_joint",
    },
    {
        "ui_key": "fed_rate",
        "label": "Federal marginal %",
        "schema_name": "marginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.federal_marginal_rate_pct",
    },
    {
        "ui_key": "state_rate",
        "label": "State marginal %",
        "schema_name": "stateMarginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.state_marginal_rate_pct",
    },
    {
        "ui_key": "ss_wage_base",
        "label": "SS wage base (maxSSwage)",
        "schema_name": "maxSSwage",
        "prefer_path_contains": "usITAIndexedAmount",
        "role": "constant",
        "value_from": "rates.ss_wage_base",
    },
    {
        "ui_key": "ss_already",
        "label": "W-2 already toward SS",
        "schema_name": "incomeTaxedBySocSec",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "rates.income_already_taxed_by_ss",
    },
    {
        "ui_key": "all_se_income",
        "label": "Owner all SE income",
        "schema_name": "allSEIncome",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "rates.starting_se_income",
    },
    {
        "ui_key": "net_earnings_ratio",
        "label": "SE net earnings ratio",
        "schema_name": "netEarningRatio",
        "prefer_path_contains": "usITAIndexedAmount",
        "role": "constant",
        "value_from": "rates.net_earnings_ratio",
    },
    {
        "ui_key": "ss_rate",
        "label": "SS rate (employee in SPE; schema may show combined)",
        "schema_name": "marginalRateSocialSecurity",
        "prefer_path_contains": "usITAIndexedAmount",
        "role": "constant",
        "value_from": "rates.ss_rate",
    },
    {
        "ui_key": "med_rate",
        "label": "Medicare rate (employee in SPE)",
        "schema_name": "marginalRateMedicare",
        "prefer_path_contains": "usITAIndexedAmount",
        "role": "constant",
        "value_from": "rates.med_rate",
    },
    {
        "ui_key": "reasonable_wage",
        "label": "Reasonable wage → new W-2",
        "schema_name": "wgFedwages",
        "prefer_path_contains": "usWageInp",
        "role": "lever",
        "value_from": "reasonable_wage",
    },
]

SOLO = [
    {
        "ui_key": "all_se_income",
        "label": "All SE income",
        "schema_name": "allSEIncome",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "person.all_se_income",
    },
    {
        "ui_key": "earned_income",
        "label": "Earned income",
        "schema_name": "earnedIncome",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "person.earned_income",
    },
    {
        "ui_key": "max_solo",
        "label": "Max Solo 401k allowed",
        "schema_name": "maxSolo401kContributionAllowed",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "engine",
        "value_from": "retirement.max_solo401k_contribution_allowed",
    },
    {
        "ui_key": "combined_limit",
        "label": "Combined 401k limit",
        "schema_name": "combined401KLimit",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "engine",
        "value_from": "retirement.combined_401k_limit",
    },
    {
        "ui_key": "solo_elective",
        "label": "Solo elective deferral write",
        "schema_name": "tpSEElectDef",
        "prefer_path_contains": "tpSEElectDef",
        "role": "lever",
        "value_from": "strategy_change",
    },
    {
        "ui_key": "fed_rate",
        "label": "Federal marginal %",
        "schema_name": "marginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.federal_marginal_rate_pct",
    },
    {
        "ui_key": "state_rate",
        "label": "State marginal %",
        "schema_name": "stateMarginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.state_marginal_rate_pct",
    },
]

EE401K = [
    {
        "ui_key": "wg_fed_wages",
        "label": "Federal wages (Box 1)",
        "schema_name": "wgFedwages",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.wg_fed_wages",
    },
    {
        "ui_key": "wages_401k",
        "label": "401(k) EE contribution (Box 12-D)",
        "schema_name": "wages401kContribution",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.wages_401k_contribution",
    },
    {
        "ui_key": "wages_403b",
        "label": "403(b) on this W-2",
        "schema_name": "wages403bContribution",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.wages_403b_contribution",
    },
    {
        "ui_key": "wg_457b",
        "label": "457(b) on this W-2",
        "schema_name": "wg457b",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.wg_457b",
    },
    {
        "ui_key": "wg_tp_sp",
        "label": "Owned by (wgTpSp)",
        "schema_name": "wgTpSp",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.wg_tp_sp",
    },
    {
        "ui_key": "nam_emp",
        "label": "Employer name",
        "schema_name": "namEmp",
        "prefer_path_contains": "usWageInp",
        "role": "input",
        "value_from": "w2.nam_emp",
    },
    {
        "ui_key": "max_401k",
        "label": "Max 401k allowed (engine)",
        "schema_name": "max401kContributionAllowed",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "engine",
        "value_from": "retirement.max_401k_contribution_allowed",
    },
    {
        "ui_key": "combined_limit",
        "label": "Combined 401k limit",
        "schema_name": "combined401KLimit",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "engine",
        "value_from": "retirement.combined_401k_limit",
    },
    {
        "ui_key": "total_401k",
        "label": "Baseline total 401k",
        "schema_name": "total401kContribution",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "retirement.total_401k",
    },
    {
        "ui_key": "solo_baseline",
        "label": "Baseline Solo 401k",
        "schema_name": "solo401kContribution",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "input",
        "value_from": "retirement.baseline_solo401k",
    },
    {
        "ui_key": "absorbed_ee",
        "label": "Employee limit absorbed",
        "schema_name": "employee401kcontributionlimitabsorbed",
        "prefer_path_contains": "usITATaxpayerItems",
        "role": "engine",
        "value_from": "retirement.employee_limit_absorbed",
    },
    {
        "ui_key": "strategy_change",
        "label": "STRATEGY_CHANGE (401k EE increase)",
        "schema_name": "wages401kContribution",
        "prefer_path_contains": "usWageInp",
        "role": "lever",
        "value_from": "strategy_change",
    },
    {
        "ui_key": "fed_rate",
        "label": "Federal marginal %",
        "schema_name": "marginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.federal_marginal_rate_pct",
    },
    {
        "ui_key": "state_rate",
        "label": "State marginal %",
        "schema_name": "stateMarginalRate",
        "prefer_path_contains": "usITASummary",
        "role": "input",
        "value_from": "rates.state_marginal_rate_pct",
    },
]


def classify_turbo_tax_attention(
    *,
    in_schema: bool,
    has_turbo_tax: bool,
    schema_name: str,
) -> dict:
    """
    Redline when there is no TURBO_TAX product mapping in tax-model-schema.json.
    Lacerte / ProSeries-only fields are NOT_AVAILABLE for TTO.
    """
    if not in_schema:
        return {
            "attention": True,
            "attention_severity": "error",
            "attention_tag": "NOT_AVAILABLE",
            "attention_reason": f"`{schema_name}` has no reference in tax-model-schema.json",
            "in_schema": False,
            "has_turbo_tax": False,
        }
    if not has_turbo_tax:
        return {
            "attention": True,
            "attention_severity": "error",
            "attention_tag": "NOT_AVAILABLE",
            "attention_reason": "No TURBO_TAX product mapping in tax-model-schema.json",
            "in_schema": True,
            "has_turbo_tax": False,
        }
    return {
        "attention": False,
        "attention_severity": "none",
        "attention_tag": None,
        "attention_reason": None,
        "in_schema": True,
        "has_turbo_tax": True,
    }


def resolve(entry, idx, schema_names: set[str] | None = None):
    name = entry["schema_name"]
    in_schema = name in (schema_names or set()) or bool(idx.get(name))
    nodes = idx.get(name) or []
    prefer = entry.get("prefer_path_contains")
    chosen = None
    if prefer:
        for path, node in nodes:
            if prefer in path:
                chosen = (path, node)
                break
    if not chosen and nodes:
        chosen = nodes[0]
    if not chosen:
        attn = classify_turbo_tax_attention(
            in_schema=in_schema, has_turbo_tax=False, schema_name=name
        )
        return {
            **entry,
            "ita_path": None,
            "tps_name": None,
            "turbo_tax_code": None,
            **attn,
        }
    path, node = chosen
    meta = tps_label(node)
    attn = classify_turbo_tax_attention(
        in_schema=True,
        has_turbo_tax=bool(meta.get("has_turbo_tax")),
        schema_name=name,
    )
    return {
        **entry,
        "ita_path": f"$.{path}",
        "tps_name": meta["tps"],
        "turbo_tax_code": meta["tps"],
        "value_type": node.get("valueType") or node.get("type"),
        "alt_paths": [f"$.{p}" for p, _ in nodes if p != path][:4],
        **attn,
    }


def main() -> None:
    schema_path = DEFAULT_SCHEMA
    if not schema_path.is_file():
        raise SystemExit(f"Schema not found: {schema_path}")
    root = json.load(schema_path.open())[0]
    idx = index_by_name(root)
    schema_names = collect_schema_names(root)
    catalog = {
        "source_schema": str(schema_path),
        "tps_product_ids": ["TURBO_TAX"],
        "scorp": [resolve(e, idx, schema_names) for e in SCORP],
        "solo401k": [resolve(e, idx, schema_names) for e in SOLO],
        "ee401k": [resolve(e, idx, schema_names) for e in EE401K],
    }
    OUT.write_text(json.dumps(catalog, indent=2))
    print(
        f"Wrote {OUT} "
        f"({len(catalog['scorp'])} scorp, {len(catalog['solo401k'])} solo, "
        f"{len(catalog['ee401k'])} ee401k)"
    )


if __name__ == "__main__":
    main()
