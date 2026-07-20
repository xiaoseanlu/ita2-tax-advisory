"""
Expert Advisory E2E — baseline setup → prior-year actual tax (same calc as web_ui_server).

Run from repo root:
  python3 expert_advisory_e2e.py

Open http://127.0.0.1:5002/

Through a tunnel (same as Tax UI script): APP=expert_e2e ./run_with_tunnel.sh

Requires .env / GenOS like the main Tax Advisory app for Calculate Tax.

If Continue shows an old green "not built yet" message and never navigates, you are
on cached HTML or an old process — restart this server and hard-refresh the browser.
This app is not web_ui_server.py (port 5000).

LLM outputs are printed to stderr by default (two blocks: tax calc text, then schema JSON).
Disable with: EXPERT_E2E_LOG_LLM=0

Baseline projection year defaults to 2026; override with EXPERT_E2E_PROJECTION_YEAR.
Projection compute timeout defaults to 660s; override with EXPERT_E2E_PROJECTION_TIMEOUT_SEC (0 = no limit).
"""

from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import Flask, jsonify, request, Response
from werkzeug.utils import secure_filename

from tax_fact_extractor import normalize_tax_situation

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env")
except ImportError:
    pass
except Exception:
    pass

from pdf_pipeline_local import (
    pdf_pipeline_dir,
    pdf_pipeline_local_available,
    pdf_pipeline_missing_message,
    pdf_pipeline_run_script,
)

_upload_dir = Path(os.environ.get("EXPERT_E2E_UPLOAD_DIR", _root / ".expert_advisory_e2e_uploads"))
_upload_dir.mkdir(parents=True, exist_ok=True)

# Saved next to upload PDF: full DES document list + scenario text (no per-schedule files on disk).
_DES_EXTRACTION_SUFFIX = ".des_extraction.json"


def _e2e_pdf_scenario_style() -> str:
    v = (os.environ.get("EXPERT_E2E_IAM_SCENARIO_STYLE") or "statements").strip()
    return v or "statements"


def _des_extraction_path(upload_id: str) -> Path:
    return _upload_dir / f"{upload_id}{_DES_EXTRACTION_SUFFIX}"


def _save_des_extraction(
    upload_id: str,
    document_id: str | None,
    documents: list[Any],
    scenario_text: str,
) -> None:
    path = _des_extraction_path(upload_id)
    payload: dict[str, Any] = {
        "version": 1,
        "document_id": document_id,
        "documents": documents,
        "scenario_text": scenario_text,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_des_extraction(upload_id: str) -> dict[str, Any] | None:
    path = _des_extraction_path(upload_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _des_cache_exists(upload_id: str) -> bool:
    return _des_extraction_path(upload_id).is_file()


def _scenario_from_des_documents(
    documents: list[Any],
    *,
    verbose: bool = False,
) -> tuple[str | None, str | None]:
    """CSV/statements path (same as iam_pdf_extraction), then semantic flatten fallback."""
    if not isinstance(documents, list) or not documents:
        return None, "No documents in cached extraction."
    try:
        from iam_pdf_extraction import (
            build_scenario_text_from_documents,
            build_tax_input_summary_from_documents,
        )

        desc, err, _ = build_scenario_text_from_documents(
            documents,
            scenario_style=_e2e_pdf_scenario_style(),
            verbose=verbose,
        )
        if desc and not err:
            return desc.strip(), None
        flat = build_tax_input_summary_from_documents(documents)
        if flat and len(flat) > 120:
            return flat.strip(), None
        return None, (err or "Could not build scenario text from cached DES documents.")
    except Exception as e:
        return None, str(e)


def _pdf_force_reextract_on_continue() -> bool:
    return os.environ.get("EXPERT_E2E_PDF_FORCE_REEXTRACT", "").lower() in ("1", "true", "yes")


app = Flask(__name__)

# In-memory POC sessions: session_id -> payload
_sessions: dict[str, dict] = {}

# Serialize projection LLM work per session dict (threaded Flask: concurrent /baseline-projection GETs).
_projection_locks_guard = threading.Lock()
_projection_compute_locks: dict[int, threading.Lock] = {}


def _session_projection_lock(session: dict) -> threading.Lock:
    key = id(session)
    with _projection_locks_guard:
        if key not in _projection_compute_locks:
            _projection_compute_locks[key] = threading.Lock()
        return _projection_compute_locks[key]


def _projection_payload_complete(proj: Any) -> bool:
    """True when projection step finished (error recorded or non-empty LLM result)."""
    if not isinstance(proj, dict):
        return False
    if proj.get("error"):
        return True
    r = proj.get("result")
    return isinstance(r, str) and bool(r.strip())

# Target year for baseline projection step (actual return year is bumped forward to this).
PROJECTION_YEAR = int(os.environ.get("EXPERT_E2E_PROJECTION_YEAR", "2026"))

# Max seconds for projection's full _compute_tax (two GenOS calls). Prevents indefinite browser hang.
_PROJECTION_COMPUTE_TIMEOUT_SEC = float(os.environ.get("EXPERT_E2E_PROJECTION_TIMEOUT_SEC", "660"))

# Form 1040 summary lines shown on Actual return (codes + short descriptions; amounts from LLM `form_1040_output_lines`).
FORM_1040_LINE_SPECS: list[tuple[str, str]] = [
    ("1a", "Total amount from Form(s) W-2, box 1"),
    ("1z", "Lines 1a through 1h — total wage-related and similar income"),
    ("2b", "Taxable interest"),
    ("3b", "Ordinary dividends"),
    ("4b", "IRA distributions — taxable amount"),
    ("5b", "Pensions and annuities — taxable amount"),
    ("6b", "Taxable Social Security benefits"),
    ("7", "Capital gain or (loss) — attach Schedule D if required"),
    ("8", "Other income from Schedule 1, line 10"),
    ("9", "Total income — add lines 1z, 2b through 3b, 4b through 8"),
    ("10", "Adjustments to income from Schedule 1, line 26"),
    ("11", "Adjusted gross income (AGI) — subtract line 10 from line 9"),
    ("12", "Standard deduction or itemized deductions (from Schedule A)"),
    ("13", "Qualified business income (QBI) deduction"),
    ("14", "Add lines 12 and 13"),
    ("15", "Taxable income — subtract line 14 from line 11"),
    ("16", "Tax — from Form 1040 tables or worksheets"),
    ("17", "Other taxes (Schedule 2, line 3)"),
    ("19", "Child tax credit / credit for other dependents"),
    ("21", "Total credits — add lines 19 and 20"),
    ("22", "Tax after credits — subtract line 21 from line 16"),
    ("23", "Other taxes including self-employment tax (Schedule 2, line 21)"),
    ("24", "Total tax — add lines 22 and 23"),
    ("25d", "Federal income tax withheld (Forms W-2, 1099, etc.)"),
    ("26", "Estimated tax payments and amount applied from prior year return"),
    ("32", "Other payments and refundable credits"),
    ("33", "Total payments and refundable credits"),
    ("34", "Refund or amount you owe — overpayment or balance due"),
]

# Inputs table section order (matches schema `tax_situation` groups).
INPUT_SECTION_SPECS: list[tuple[str, str]] = [
    ("Personal", "personal"),
    ("Income", "income"),
    ("Itemized deductions", "itemized_deductions"),
    ("Credits", "credits"),
    ("Payments", "payments"),
]


def _format_situation_cell(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def _titleize_segment(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _flatten_tax_situation_rows(obj: Any, prefix_parts: list[str] | None = None) -> list[tuple[str, str]]:
    if prefix_parts is None:
        prefix_parts = []
    if obj is None:
        return []
    if isinstance(obj, dict):
        rows: list[tuple[str, str]] = []
        for k in sorted(obj.keys(), key=lambda x: str(x).lower()):
            v = obj[k]
            parts = prefix_parts + [_titleize_segment(str(k))]
            if isinstance(v, dict):
                rows.extend(_flatten_tax_situation_rows(v, parts))
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    ip = parts + [f"#{i + 1}"]
                    if isinstance(item, dict):
                        rows.extend(_flatten_tax_situation_rows(item, ip))
                    else:
                        rows.append((" › ".join(ip), _format_situation_cell(item)))
            else:
                rows.append((" › ".join(parts), _format_situation_cell(v)))
        return rows
    return []


def _flatten_credits_rows(arr: Any) -> list[tuple[str, str]]:
    """One table row per credit: Field = name, Value = amount (optional extras in parentheses on Field)."""
    if not isinstance(arr, list) or not arr:
        return []
    rows: list[tuple[str, str]] = []
    for i, item in enumerate(arr):
        if not isinstance(item, dict):
            continue
        raw_name = item.get("credit_name")
        name = raw_name.strip() if isinstance(raw_name, str) else None
        label = name or f"Credit #{i + 1}"
        amt = item.get("amount")
        extras: list[str] = []
        for k, v in sorted(item.items(), key=lambda x: str(x[0]).lower()):
            if k in ("credit_name", "amount"):
                continue
            if v is None or v == "":
                continue
            extras.append(f"{_titleize_segment(str(k))}: {_format_situation_cell(v)}")
        if extras:
            label = f"{label} ({'; '.join(extras)})"
        rows.append((label, _format_situation_cell(amt)))
    return rows


def _tax_situation_input_sections(ts: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    """Build (section title, rows) for grouped or legacy flat tax_situation."""
    if not ts or not isinstance(ts, dict):
        return []
    if isinstance(ts.get("personal"), dict):
        out: list[tuple[str, list[tuple[str, str]]]] = []
        for title, key in INPUT_SECTION_SPECS:
            sub = ts.get(key)
            if key == "credits":
                rows = _flatten_credits_rows(sub or ts.get("credits_mentioned"))
            else:
                rows = _flatten_tax_situation_rows(sub) if sub else []
            if rows:
                out.append((title, rows))
        return out
    personal_block = {k: ts[k] for k in ("tax_year", "filing_status", "primary_taxpayer", "spouse", "dependents") if k in ts}
    chunks = [
        ("Personal", _flatten_tax_situation_rows(personal_block if personal_block else None)),
        ("Income", _flatten_tax_situation_rows(ts.get("income"))),
        ("Itemized deductions", _flatten_tax_situation_rows(ts.get("itemized_deductions"))),
        ("Credits", _flatten_credits_rows(ts.get("credits") or ts.get("credits_mentioned"))),
        ("Payments", _flatten_tax_situation_rows(ts.get("payments"))),
    ]
    return [(t, r) for t, r in chunks if r]


def _format_money_cell(n: Any) -> str:
    if n is None:
        return "—"
    try:
        x = float(n)
    except (TypeError, ValueError):
        return html.escape(str(n), quote=False)
    if abs(x - round(x)) < 1e-9:
        return f"${int(round(x)):,}"
    return f"${x:,.2f}"


def _merge_1040_line_amounts(dm: dict | None) -> dict[str, Any]:
    """Prefer `form_1040_output_lines`; fill gaps from `form_1040_calculated_lines` (LLM often leaves line 34 null)."""
    amounts: dict[str, Any] = {}
    if not dm or not isinstance(dm, dict):
        return amounts
    for item in dm.get("form_1040_output_lines") or []:
        if not isinstance(item, dict):
            continue
        code = item.get("line")
        if code is not None:
            amounts[str(code).strip()] = item.get("amount")
    calc = dm.get("form_1040_calculated_lines")
    if not isinstance(calc, dict):
        return amounts
    fb = {
        "11": calc.get("adjusted_gross_income"),
        "15": calc.get("taxable_income"),
        "16": calc.get("tax_before_credits"),
        "22": calc.get("tax_after_credits"),
        "24": calc.get("total_tax_liability"),
        "34": calc.get("amount_owed_or_refund"),
    }
    for k, v in fb.items():
        if v is not None and (k not in amounts or amounts[k] is None):
            amounts[k] = v
    return amounts


def _html_inputs_tbody(dm: dict | None) -> str:
    ts = None
    if dm and isinstance(dm, dict):
        ts = dm.get("tax_situation")
    if not ts or not isinstance(ts, dict):
        return (
            '<tr><td colspan="2" class="muted">No input data yet. Complete a tax calculation first, '
            "or use AI recalc.</td></tr>"
        )
    sections = _tax_situation_input_sections(ts)
    if not sections:
        return '<tr><td colspan="2" class="muted">No fields extracted.</td></tr>'
    parts: list[str] = []
    for sec_title, rows in sections:
        parts.append(
            f'<tr class="inputs-section"><td colspan="2">{html.escape(sec_title, quote=False)}</td></tr>'
        )
        for label, val in rows:
            parts.append(
                f'<tr><td class="col-field">{html.escape(label, quote=False)}</td>'
                f'<td class="col-value">{html.escape(val, quote=False)}</td></tr>'
            )
    return "".join(parts)


def _html_form1040_tbody(dm: dict | None) -> str:
    amounts = _merge_1040_line_amounts(dm)
    parts: list[str] = []
    for code, desc in FORM_1040_LINE_SPECS:
        amt = _format_money_cell(amounts.get(code))
        parts.append(
            f'<tr><td class="col-line">{html.escape(code, quote=False)}</td>'
            f'<td class="col-desc">{html.escape(desc, quote=False)}</td>'
            f'<td class="col-amt">{amt}</td></tr>'
        )
    return "".join(parts)


def _flat_input_key_rows(ts: dict | None) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for sec_title, pairs in _tax_situation_input_sections(ts or {}):
        for lab, val in pairs:
            rows.append((sec_title, lab, val))
    return rows


def _inputs_maps_for_comparison(
    dm_a: dict | None, dm_b: dict | None
) -> tuple[list[tuple[str, str]], list[Any], list[Any]]:
    ts_a = dm_a.get("tax_situation") if isinstance(dm_a, dict) else None
    ts_b = dm_b.get("tax_situation") if isinstance(dm_b, dict) else None
    ma = {(s, l): v for s, l, v in _flat_input_key_rows(ts_a if isinstance(ts_a, dict) else None)}
    mb = {(s, l): v for s, l, v in _flat_input_key_rows(ts_b if isinstance(ts_b, dict) else None)}
    keys = sorted(set(ma) | set(mb), key=lambda x: (x[0].lower(), x[1].lower()))
    va = [ma.get(k) for k in keys]
    vb = [mb.get(k) for k in keys]
    return keys, va, vb


def _total_tax_from_dm(dm: dict | None) -> Any:
    if not dm or not isinstance(dm, dict):
        return None
    calc = dm.get("form_1040_calculated_lines")
    if isinstance(calc, dict) and calc.get("total_tax_liability") is not None:
        return calc.get("total_tax_liability")
    return _merge_1040_line_amounts(dm).get("24")


def _year_int_for_planning(y: str | None) -> int | None:
    if y is None:
        return None
    try:
        return int(str(y).strip())
    except ValueError:
        return None


def _sanitize_cmp_bootstrap_payload(obj: Any) -> Any:
    """Make nested payload safe for JSON.parse in the browser (NaN/Inf -> None; odd types -> str)."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, int) and not isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): _sanitize_cmp_bootstrap_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_cmp_bootstrap_payload(x) for x in obj]
    return str(obj)


def _comparison_payload_dict(session: dict) -> dict:
    """Build Quick Compare payload: merged tables, scenario texts, planning flags."""
    ay = str(session.get("actual_year") or "2024")
    proj = session.get("projection") or {}
    py = str(proj.get("projection_year") or PROJECTION_YEAR)
    dm_act = session.get("data_model") if isinstance(session.get("data_model"), dict) else {}
    dm_proj = proj.get("data_model") if isinstance(proj.get("data_model"), dict) else {}
    act_amt = _merge_1040_line_amounts(dm_act)
    prj_amt = _merge_1040_line_amounts(dm_proj)
    lines = [{"line": c, "description": d} for c, d in FORM_1040_LINE_SPECS]
    act_scen = (session.get("scenario_text") or "").strip()
    act_res = (session.get("result") or "").strip()
    if session.get("error"):
        act_res = f"(Tax calculation error)\n\n{session.get('error')}"
    prj_scen = (proj.get("scenario_text") or "").strip()
    prj_res = (proj.get("result") or "").strip()
    if proj.get("error"):
        prj_res = f"(Projection calculation error)\n\n{proj.get('error')}"
    yi_proj = _year_int_for_planning(py)
    planning_from_year = yi_proj is not None and yi_proj >= 2026
    scenarios = [
        {
            "id": "actual",
            "label": f"{ay} actual",
            "year": ay,
            "checked": True,
            "amounts": {c: act_amt.get(c) for c, _ in FORM_1040_LINE_SPECS},
            "totalTax": _total_tax_from_dm(dm_act),
            "scenarioText": act_scen,
            "resultText": act_res,
            "planningEligible": False,
        },
        {
            "id": "projection",
            "label": f"{py} projection",
            "year": py,
            "checked": True,
            "amounts": {c: prj_amt.get(c) for c, _ in FORM_1040_LINE_SPECS},
            "totalTax": _total_tax_from_dm(dm_proj),
            "scenarioText": prj_scen,
            "resultText": prj_res,
            "planningEligible": planning_from_year,
        },
    ]
    keys, va, vb = _inputs_maps_for_comparison(
        dm_act if dm_act else None,
        dm_proj if dm_proj else None,
    )
    inputs_rows: list[dict] = []
    prev_sec: str | None = None
    for i, (sec, lab) in enumerate(keys):
        if sec != prev_sec:
            inputs_rows.append({"kind": "section", "section": sec})
            prev_sec = sec
        inputs_rows.append({"kind": "row", "label": lab, "values": [va[i], vb[i]]})
    return {
        "lines": lines,
        "scenarios": scenarios,
        "inputsRows": inputs_rows,
        "maxCompare": 3,
        "planningThresholdYear": 2026,
    }


def _comparison_page_bootstrap(session: dict) -> str:
    """Base64 UTF-8 JSON for <script id=\"cmp-bootstrap\"> — immune to </script> / control chars in LLM text."""
    try:
        payload = _sanitize_cmp_bootstrap_payload(_comparison_payload_dict(session))
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as e:
        print(f"[expert_e2e] _comparison_page_bootstrap serialize failed: {e}", file=sys.stderr)
        raw = json.dumps(
            {
                "lines": [{"line": c, "description": d} for c, d in FORM_1040_LINE_SPECS],
                "scenarios": [
                    {
                        "id": "actual",
                        "label": "Error",
                        "year": None,
                        "checked": True,
                        "amounts": {c: None for c, _ in FORM_1040_LINE_SPECS},
                        "totalTax": None,
                        "scenarioText": f"(Server could not build compare data: {e})",
                        "resultText": "",
                        "planningEligible": False,
                    }
                ],
                "inputsRows": [],
                "maxCompare": 3,
                "planningThresholdYear": 2026,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )
    return base64.standard_b64encode(raw.encode("utf-8")).decode("ascii")


def _html_response(html: str) -> Response:
    r = Response(html, mimetype="text/html; charset=utf-8")
    r.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    r.headers["Pragma"] = "no-cache"
    return r


def _json_response(payload: dict, status: int = 200) -> Response:
    """JSON response safe for LLM blobs and nested dicts (uses default=str)."""
    try:
        body = json.dumps(payload, default=str, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        body = json.dumps({"ok": False, "error": f"Server could not serialize response: {e}"}, ensure_ascii=False)
        status = 500
    return Response(
        body,
        status=status,
        mimetype="application/json; charset=utf-8",
    )


def _debug_tax_calc() -> bool:
    v = os.environ.get("DEBUG_TAX_CALC", "0")
    return v.lower() in ("1", "true", "yes")


def _intuit_des_iam_configured() -> bool:
    """True when Financial Document extraction is configured (session cookies and/or DES IAM)."""
    try:
        from iam_pdf_extraction import financialdoc_extraction_configured

        return financialdoc_extraction_configured()
    except Exception:
        return bool(
            os.environ.get("INTUIT_APP_SECRET_FOR_DES")
            and os.environ.get("INTUIT_IAM_TICKET")
            and os.environ.get("INTUIT_AUTH_ID")
        )


def _iam_pdf_error_allows_local_fallback(err: str) -> bool:
    """
    When Intuit document extraction fails (e.g. \"all classifiers failed\" on odd PDFs),
    fall back to the local pdf_to_tax_situation pipeline unless disabled or error looks like auth/config.
    """
    if os.environ.get("EXPERT_E2E_IAM_NO_LOCAL_FALLBACK", "").lower() in ("1", "true", "yes"):
        return False
    low = (err or "").lower()
    # Do not mask credential, permission, or upload issues — user should fix env or file.
    hard = (
        "credentials missing",
        "authentication",
        "http 401",
        "http 403",
        "http 404",
        "no document id",
        "upload failed",
        "pdf not found",
        "request error",
        "timed out waiting for extraction",
    )
    if any(h in low for h in hard):
        return False
    return True


def _run_pdf_to_description(pdf_path: Path, output_dir: Path) -> tuple[str | None, str | None]:
    pipe_dir = pdf_pipeline_dir()
    script = pdf_pipeline_run_script()
    if not script.is_file():
        return None, pdf_pipeline_missing_message()
    desc_file = output_dir / "description.txt"
    cmd = [
        sys.executable,
        str(script),
        str(pdf_path),
        "--output-dir",
        str(output_dir),
        "-o",
        str(desc_file),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(pipe_dir),
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return None, "PDF pipeline timed out (extraction can take over a minute)."
    except FileNotFoundError:
        return None, pdf_pipeline_missing_message()
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "PDF pipeline failed.").strip()
        return None, err
    if not desc_file.exists():
        return None, "Description file was not produced."
    try:
        return desc_file.read_text(encoding="utf-8"), None
    except OSError as e:
        return None, str(e)


def _default_sample_scenario() -> str:
    path = _root / "tax_situations.txt"
    if not path.is_file():
        return (
            "Calculate the tax liability for this tax situation.\n\n"
            "--- Scenario (use only this case) ---\n\n"
            "Married Filing Jointly, tax year 2024.\n"
            "Taxpayer wage $100,000 federal wages, $10,000 federal withholding.\n"
        )
    raw = path.read_text(encoding="utf-8")
    marker = "--- Scenario (use only this case) ---"
    if marker not in raw:
        return raw[:4000]
    rest = raw.split(marker, 1)[1].strip()
    lines_out: list[str] = []
    for line in rest.splitlines():
        if line.strip() == "---" and lines_out:
            break
        lines_out.append(line)
    body = "\n".join(lines_out).strip()
    return f"Calculate the tax liability for this tax situation.\n\n{marker}\n\n{body}"


def _detect_actual_year(scenario: str) -> str:
    if re.search(r"\b2025\b", scenario) and not re.search(r"\b2024\b", scenario):
        return "2025"
    if re.search(r"\b2024\b", scenario):
        return "2024"
    if re.search(r"\b2025\b", scenario):
        return "2025"
    return "2024"


def _int_tax_year(val: Any) -> int:
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return 2024


def _adjust_scenario_years_and_ages(text: str, year_from: int, year_to: int) -> str:
    """Shift baseline tax year in narrative and bump common age phrases by (year_to - year_from)."""
    if not (text or "").strip():
        return text
    delta = year_to - year_from
    t = text
    if year_from != year_to:
        t = re.sub(rf"\b{year_from}\b", str(year_to), t)
    if delta == 0:
        return t

    def bump_age_of(m: re.Match) -> str:
        return f"{m.group(1)}{int(m.group(2)) + delta}"

    t = re.sub(r"(?i)(\bage\s+of\s+)(\d+)\b", bump_age_of, t)
    t = re.sub(r"(?i)(\bage\s+)(\d+)\b", bump_age_of, t)
    t = re.sub(
        r"(?i)\b(\d+)\s+years?\s+old\b",
        lambda m: f"{int(m.group(1)) + delta} years old",
        t,
    )
    return t


def _dependent_age_projection_lines(dm: dict | None, delta: int, projection_year: int) -> str:
    """Add explicit dependent age lines from structured data when ages are numeric."""
    if delta == 0 or not dm or not isinstance(dm, dict):
        return ""
    ts = dm.get("tax_situation")
    if not isinstance(ts, dict):
        return ""
    flat = normalize_tax_situation(ts)
    deps = flat.get("dependents")
    if not isinstance(deps, list):
        return ""
    lines: list[str] = []
    for i, d in enumerate(deps):
        if not isinstance(d, dict):
            continue
        raw = d.get("date_of_birth_or_age")
        if isinstance(raw, (int, float)) and raw == int(raw):
            o = int(raw)
            lines.append(
                f"- Dependent #{i + 1}: use age {o + delta} for tax year {projection_year} "
                f"(numeric age {o} was for the prior-year case)."
            )
        elif isinstance(raw, str) and raw.strip().isdigit():
            o = int(raw.strip())
            lines.append(
                f"- Dependent #{i + 1}: use age {o + delta} for tax year {projection_year} "
                f"(stated age {o} for the prior year)."
            )
    return "\n".join(lines)


def _build_projection_scenario(session: dict) -> tuple[str, int, int, int, str]:
    """
    Build scenario text for PROJECTION_YEAR from stored actual-return session.
    Returns (scenario_text, actual_year, projection_year, year_delta, summary_line).
    """
    base = (session.get("scenario_text") or "").strip()
    dm = session.get("data_model") if isinstance(session.get("data_model"), dict) else None
    actual_y = _int_tax_year(session.get("actual_year"))
    proj_y = PROJECTION_YEAR
    delta = proj_y - actual_y
    adjusted = _adjust_scenario_years_and_ages(base, actual_y, proj_y)
    struct_notes = _dependent_age_projection_lines(dm, delta, proj_y)
    extra = ""
    if delta != 0:
        extra = (
            f"\n\n--- Projection notes for tax year {proj_y} ---\n"
            f"The prior step modeled tax year {actual_y}. Calendar years in the scenario above are shifted to {proj_y}. "
            f"Numeric ages in the narrative are increased by {delta}. "
            "Apply current-law rules for the projection year as you compute tax.\n"
        )
        if struct_notes:
            extra += struct_notes + "\n"
    scenario = (adjusted + extra).strip()
    if "Calculate the tax liability" not in scenario and "--- Scenario" not in scenario:
        scenario = (
            "Calculate the tax liability for this tax situation.\n\n"
            "--- Scenario (use only this case) ---\n\n"
            f"{scenario}"
        )
    summary = (
        f"Prior year {actual_y} → {proj_y} projection (age shift +{delta} yr)"
        if delta
        else f"Tax year {proj_y} projection"
    )
    return scenario, actual_y, proj_y, delta, summary


def _log_llm_to_stderr(label: str, body: str) -> None:
    """Echo full LLM output to the terminal (stderr). Set EXPERT_E2E_LOG_LLM=0 to disable."""
    if os.environ.get("EXPERT_E2E_LOG_LLM", "1").lower() in ("0", "false", "no"):
        return
    sep = "=" * 72
    print(f"\n{sep}\n[expert_e2e] {label}\n{sep}", file=sys.stderr, flush=True)
    print(body, file=sys.stderr, flush=True)
    print(sep + "\n", file=sys.stderr, flush=True)


def _compute_tax(scenario: str) -> tuple[str, dict]:
    from genai_tax_core import get_tax_calculation_response
    from tax_schema_filler import fill_tax_data_model

    print(
        "[expert_e2e] _compute_tax: step 1/2 — get_tax_calculation_response (GenOS)…",
        file=sys.stderr,
        flush=True,
    )
    result = get_tax_calculation_response(
        scenario,
        include_reference=True,
        print_prompt=_debug_tax_calc(),
    )
    print("[expert_e2e] _compute_tax: step 1/2 done.", file=sys.stderr, flush=True)
    _log_llm_to_stderr("LLM output #1 — tax calculation (get_tax_calculation_response)", result)

    print(
        "[expert_e2e] _compute_tax: step 2/2 — fill_tax_data_model (GenOS)…",
        file=sys.stderr,
        flush=True,
    )
    data_model = fill_tax_data_model(result, scenario)
    print("[expert_e2e] _compute_tax: step 2/2 done.", file=sys.stderr, flush=True)
    try:
        dm_text = json.dumps(data_model, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        dm_text = repr(data_model)
    _log_llm_to_stderr(
        "LLM output #2 — schema fill (fill_tax_data_model, as structured JSON)",
        dm_text,
    )
    return result, data_model


def _ensure_projection_computed(session: dict) -> None:
    """Populate session['projection'] with LLM result; reuse cache if baseline scenario unchanged."""
    base = session.get("scenario_text") or ""
    base_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()

    def cache_hit(p: dict | None) -> bool:
        return bool(
            isinstance(p, dict)
            and p.get("source_scenario_hash") == base_hash
            and int(p.get("projection_year") or 0) == PROJECTION_YEAR
            and _projection_payload_complete(p)
        )

    proj = session.get("projection")
    if cache_hit(proj):
        return
    lock = _session_projection_lock(session)
    with lock:
        proj = session.get("projection")
        if cache_hit(proj):
            return
        scen, ay, py, delta, summ = _build_projection_scenario(session)
        print(
            f"[expert_e2e] projection compute start projection_year={py} actual_year={ay} delta={delta}",
            file=sys.stderr,
            flush=True,
        )
        session["projection"] = {
            "source_scenario_hash": base_hash,
            "projection_year": py,
            "actual_year": ay,
            "age_delta_years": delta,
            "summary_line": summ,
            "scenario_text": scen,
            "result": None,
            "data_model": None,
            "error": None,
        }
        try:
            timeout = _PROJECTION_COMPUTE_TIMEOUT_SEC
            if timeout and timeout > 0:
                ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                fut = ex.submit(_compute_tax, scen)
                try:
                    result, data_model = fut.result(timeout=timeout)
                except TimeoutError:
                    session["projection"]["error"] = (
                        f"Projection timed out after {timeout:.0f}s waiting for GenOS (two LLM passes). "
                        "Check the server terminal for the last [expert_e2e] _compute_tax line. "
                        "Set EXPERT_E2E_PROJECTION_TIMEOUT_SEC to wait longer, or fix GenOS/network."
                    )
                    print(
                        f"[expert_e2e] projection compute TIMEOUT after {timeout:.0f}s",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    session["projection"]["result"] = result
                    session["projection"]["data_model"] = data_model
                    session["projection"]["error"] = None
                    print("[expert_e2e] projection compute OK", file=sys.stderr, flush=True)
                finally:
                    ex.shutdown(wait=False)
            else:
                result, data_model = _compute_tax(scen)
                session["projection"]["result"] = result
                session["projection"]["data_model"] = data_model
                session["projection"]["error"] = None
                print("[expert_e2e] projection compute OK", file=sys.stderr, flush=True)
        except Exception as e:
            session["projection"]["error"] = str(e)
            print(f"[expert_e2e] projection compute failed: {e}", file=sys.stderr, flush=True)


def _projection_total_tax_display(dm: dict | None) -> tuple[str, str]:
    """(label, html-safe value) for headline liability."""
    if not dm or not isinstance(dm, dict):
        return ("Total tax liability", "—")
    calc = dm.get("form_1040_calculated_lines")
    if isinstance(calc, dict):
        tt = calc.get("total_tax_liability")
        if tt is not None:
            return ("Total tax liability", html.escape(_format_money_cell(tt), quote=False))
    amounts = _merge_1040_line_amounts(dm)
    line24 = amounts.get("24")
    if line24 is not None:
        return ("Total tax (Form 1040 line 24)", html.escape(_format_money_cell(line24), quote=False))
    return ("Total tax liability", "—")


def _projection_refund_owed_html(dm: dict | None) -> str:
    if not dm or not isinstance(dm, dict):
        return ""
    calc = dm.get("form_1040_calculated_lines")
    if not isinstance(calc, dict):
        return ""
    v = calc.get("amount_owed_or_refund")
    if v is None:
        return ""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return ""
    if x > 0:
        return f'<p class="e2e-liability-sub">Balance due: {html.escape(_format_money_cell(x), quote=False)}</p>'
    if x < 0:
        return f'<p class="e2e-liability-sub e2e-liability-sub--refund">Refund: {html.escape(_format_money_cell(abs(x)), quote=False)}</p>'
    return '<p class="e2e-liability-sub">No net refund or amount owed (after payments).</p>'


def _session_payload(session: dict) -> dict:
    return {
        "scenario_text": session.get("scenario_text") or "",
        "source": session.get("source") or "",
        "actual_year": session.get("actual_year") or "2024",
        "result": session.get("result"),
        "data_model": session.get("data_model"),
        "error": session.get("error"),
    }


def _build_scenario_from_baseline(data: dict, upload_id: str | None) -> tuple[str | None, str | None]:
    source = (data.get("source") or "").strip()
    if source == "direct":
        text = (data.get("scenario_text") or "").strip()
        if not text:
            return None, "scenario_text required for direct entry."
        return text, None
    if source == "pdf":
        if not upload_id:
            return None, "upload_id required for PDF flow."
        pdf_path = _upload_dir / f"{upload_id}.pdf"
        if not pdf_path.is_file():
            return None, "Uploaded PDF not found. Upload again."

        client_text = (data.get("scenario_text") or "").strip()
        if client_text:
            return client_text, None

        build_err: str | None = None
        cached = _load_des_extraction(upload_id)
        if cached:
            st = (cached.get("scenario_text") or "").strip()
            if st:
                return st, None
            docs = cached.get("documents")
            if isinstance(docs, list) and docs:
                desc, build_err = _scenario_from_des_documents(docs, verbose=False)
                if desc and not build_err:
                    return desc.strip(), None

        if _des_cache_exists(upload_id) and not _pdf_force_reextract_on_continue():
            cache_path = _des_extraction_path(upload_id)
            detail = f" Detail: {build_err}" if build_err else ""
            return (
                None,
                "A DES extraction JSON is already saved for this upload, but no usable scenario text was produced. "
                "Edit the scenario box and paste a summary, or set EXPERT_E2E_PDF_FORCE_REEXTRACT=1 to call Intuit again, "
                f"or remove {cache_path} and re-upload.{detail}"
            )

        # First upload did not persist .des_extraction.json (e.g. ConnectError while polling). A second immediate
        # POST often fails the same way; do not call Intuit again unless EXPERT_E2E_PDF_FORCE_REEXTRACT=1.
        if (
            not _des_cache_exists(upload_id)
            and _intuit_des_iam_configured()
            and not _pdf_force_reextract_on_continue()
        ):
            if pdf_pipeline_local_available():
                out_dir = Path(tempfile.mkdtemp(prefix="e2e-pdf-"))
                desc, err = _run_pdf_to_description(pdf_path, out_dir)
                if desc and not err:
                    return (desc or "").strip(), None
            return (
                None,
                "Financial Document extraction did not finish for this upload (no "
                f"{_DES_EXTRACTION_SUFFIX} next to the PDF), so the server will not upload to Intuit again automatically "
                "(avoids duplicate POSTs and connection errors). Re-upload the PDF after checking your network/VPN, "
                "paste a scenario under Direct entry, set EXPERT_E2E_PDF_FORCE_REEXTRACT=1 to retry Intuit from Continue, "
                f"or install the local pdf_to_tax_situation pipeline. Files: {_upload_dir}",
            )

        intuit_err: str | None = None
        if _intuit_des_iam_configured():
            try:
                from iam_pdf_extraction import extract_1040_from_pdf_for_scenario

                desc, err = extract_1040_from_pdf_for_scenario(
                    pdf_path,
                    scenario_style=_e2e_pdf_scenario_style(),
                )
            except Exception as e:
                desc, err = None, f"Intuit document extraction failed: {e}"
            if (desc or "").strip() and not err:
                return (desc or "").strip(), None
            if err:
                intuit_err = err
            if err and _iam_pdf_error_allows_local_fallback(err):
                print(
                    f"[expert_e2e] IAM PDF extraction failed ({err}); falling back to local PDF pipeline.",
                    file=sys.stderr,
                )
            elif err:
                return None, err
        if not pdf_pipeline_local_available():
            msg = pdf_pipeline_missing_message()
            if intuit_err:
                return None, (
                    f"Financial Document extraction did not produce a scenario ({intuit_err}).\n\n{msg}"
                )
            return None, msg
        out_dir = Path(tempfile.mkdtemp(prefix="e2e-pdf-"))
        desc, err = _run_pdf_to_description(pdf_path, out_dir)
        if err:
            return None, err
        return (desc or "").strip(), None
    if source == "proconnect":
        return (
            "[Prior-year narrative pending ProConnect/Lacerte import — sample situation below until connected.]\n\n"
            + _default_sample_scenario(),
            None,
        )
    if source == "turbotax":
        return (
            "[Prior-year narrative pending TurboTax import — sample situation below until connected.]\n\n"
            + _default_sample_scenario(),
            None,
        )
    return None, "Invalid source."


PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Expert Advisory — Baseline setup</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    :root {
      --bg: #f3f2f7;
      --surface: #ffffff;
      --text: #1c1b22;
      --text-muted: #6b6b70;
      --primary: #5e5ce6;
      --primary-hover: #4c4ad4;
      --primary-subtle: rgba(94, 92, 230, 0.08);
      --border: #e5e4eb;
      --border-light: #ebeaf0;
      --shadow: 0 2px 8px rgba(28, 27, 34, 0.06);
      --radius: 14px;
      --radius-sm: 10px;
      --sparkle: #5b9bd5;
    }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 16px;
      line-height: 1.5;
      color: var(--text);
      background: var(--bg);
      min-height: 100vh;
    }
    .e2e-wrap { max-width: 720px; margin: 0 auto; padding: 2rem 1.5rem 3rem; min-height: 100vh; }
    .e2e-agent-header { margin-bottom: 1.5rem; }
    .e2e-agent-line1 { margin: 0 0 0.35rem; font-size: 1.125rem; font-weight: 400; color: var(--text); letter-spacing: -0.01em; }
    .e2e-agent-line2 { margin: 0; display: flex; align-items: flex-start; gap: 0.5rem; font-size: 1rem; font-weight: 700; color: var(--text); }
    .e2e-sparkle { flex-shrink: 0; margin-top: 0.15rem; }
    .e2e-card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow); border: 1px solid var(--border-light); padding: 2rem; }
    .e2e-fieldset { border: none; margin: 0; padding: 0; }
    .e2e-legend { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; white-space: nowrap; }
    .e2e-option { display: flex; align-items: flex-start; gap: 0.65rem; margin-bottom: 1rem; cursor: pointer; }
    .e2e-option:last-of-type { margin-bottom: 0; }
    .e2e-option input { margin-top: 0.35rem; accent-color: var(--primary); cursor: pointer; }
    .e2e-option-body { flex: 1; min-width: 0; }
    .e2e-option-label { font-weight: 500; color: var(--text); }
    .e2e-file-row { margin-top: 0.5rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
    .e2e-file-name { font-size: 0.8125rem; color: var(--text-muted); }
    .btn {
      display: inline-flex; align-items: center; justify-content: center;
      padding: 0.5rem 1rem; font: inherit; font-size: 0.9375rem; font-weight: 500;
      border-radius: var(--radius-sm); cursor: pointer; border: 1px solid var(--border);
      background: var(--surface); color: var(--text); transition: background 0.15s, border-color 0.15s;
    }
    .btn:hover { background: var(--bg); }
    .btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); border-color: var(--primary-hover); }
    .btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }
    .e2e-direct-wrap { margin-top: 1.25rem; padding-top: 1.25rem; border-top: 1px solid var(--border-light); }
    .e2e-direct-wrap[hidden] { display: none !important; }
    .label { display: block; margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 500; color: var(--text); }
    .scenario-textarea {
      width: 100%; min-height: 220px; padding: 0.75rem 1rem; font: inherit; font-size: 0.9375rem; line-height: 1.5;
      color: var(--text); background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); resize: vertical;
    }
    .scenario-textarea::placeholder { color: var(--text-muted); }
    .scenario-textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-subtle); }
    .scenario-textarea:disabled { opacity: 0.55; cursor: not-allowed; background: var(--bg); }
    .e2e-footer { margin-top: 1.75rem; padding-top: 1.25rem; border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; align-items: flex-end; gap: 1rem; flex-wrap: wrap; }
    .e2e-status-block { flex: 1; min-width: 220px; display: flex; flex-direction: column; gap: 0.65rem; }
    .e2e-status { margin: 0; font-size: 0.875rem; color: var(--text-muted); }
    .e2e-status--error { color: #b91c1c; }
    .e2e-status--ok { color: #15803d; }
    .e2e-elapsed {
      display: none; flex-direction: column; gap: 0.45rem; max-width: 14rem;
      padding: 0.65rem 0.9rem; background: linear-gradient(145deg, var(--primary-subtle), rgba(91, 155, 213, 0.06));
      border: 1px solid var(--border-light); border-radius: var(--radius-sm); box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
    }
    .e2e-elapsed:not([hidden]) { display: flex; }
    .e2e-elapsed-label { font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
    .e2e-elapsed-readout { display: flex; align-items: baseline; gap: 0.3rem; }
    .e2e-elapsed-value { font-size: 1.75rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primary); line-height: 1; letter-spacing: -0.02em; }
    .e2e-elapsed-unit { font-size: 0.9375rem; font-weight: 500; color: var(--text-muted); }
    .e2e-elapsed--active .e2e-elapsed-value { animation: e2e-tick-pulse 2s ease-in-out infinite; }
    @keyframes e2e-tick-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.82; } }
    .e2e-elapsed-hint { margin: 0; font-size: 0.75rem; color: var(--text-muted); line-height: 1.35; }
  </style>
</head>
<body>
  <script type="application/json" id="e2e-baseline-config">__E2E_BASELINE_CLIENT_CONFIG__</script>
  <div class="e2e-wrap">
    <header class="e2e-agent-header">
      <p class="e2e-agent-line1">Let's get a baseline setup for Bob's 2026 using a prior year Tax return.</p>
      <p class="e2e-agent-line2">
        <svg class="e2e-sparkle" width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="var(--sparkle)" d="M12 1.5l1.8 5.5h5.9l-4.8 3.5 1.8 5.5L12 12.5 7.3 16l1.8-5.5L4.3 7h5.9L12 1.5z"/>
        </svg>
        <span>You will have an opportunity to update the projection in the next screen.</span>
      </p>
    </header>
    <main class="e2e-card">
      <form id="baseline-form" novalidate>
        <fieldset class="e2e-fieldset">
          <legend class="e2e-legend">Prior year source</legend>
          <label class="e2e-option">
            <input type="radio" name="source" value="proconnect" checked />
            <span class="e2e-option-body"><span class="e2e-option-label">ProConnect/Lacerte return</span></span>
          </label>
          <label class="e2e-option">
            <input type="radio" name="source" value="turbotax" />
            <span class="e2e-option-body"><span class="e2e-option-label">TurboTax return</span></span>
          </label>
          <label class="e2e-option">
            <input type="radio" name="source" value="pdf" />
            <span class="e2e-option-body">
              <span class="e2e-option-label">1040 PDF upload</span>
              <div class="e2e-file-row">
                <button type="button" class="btn" id="btn-pick-pdf">Choose 1040 PDF</button>
                <input type="file" id="file-1040" accept=".pdf,application/pdf" hidden />
                <span class="e2e-file-name" id="pdf-file-label">No file chosen</span>
              </div>
            </span>
          </label>
          <label class="e2e-option">
            <input type="radio" name="source" value="direct" />
            <span class="e2e-option-body"><span class="e2e-option-label">Direct Input Entry</span></span>
          </label>
        </fieldset>
        <div class="e2e-direct-wrap" id="direct-panel" hidden>
          <label for="scenario-text" class="label">Scenario for tax calculation</label>
          <textarea id="scenario-text" class="scenario-textarea" rows="12" disabled
            placeholder="Choose a source above. For direct entry, type or paste the situation. For PDF, the extracted text appears after upload."></textarea>
        </div>
        <div class="e2e-footer">
          <div class="e2e-status-block">
            <p class="e2e-status" id="form-status" hidden></p>
            <div class="e2e-elapsed" id="elapsed-wrap" hidden aria-live="polite" aria-atomic="true">
              <span class="e2e-elapsed-label" id="elapsed-label">Computing</span>
              <div class="e2e-elapsed-readout">
                <span class="e2e-elapsed-value" id="elapsed-sec">0</span>
                <span class="e2e-elapsed-unit">s</span>
              </div>
              <p class="e2e-elapsed-hint" id="elapsed-hint">Tax engine and AI passes can take a minute or two.</p>
            </div>
          </div>
          <button type="submit" class="btn btn-primary" id="btn-continue">Continue</button>
        </div>
      </form>
    </main>
  </div>
  <script>
(function () {
  const BASELINE_CFG = (function () {
    try {
      var el = document.getElementById("e2e-baseline-config");
      if (!el || !el.textContent) return {};
      return JSON.parse(el.textContent);
    } catch (e) { return {}; }
  })();
  const form = document.getElementById("baseline-form");
  const radios = form.querySelectorAll('input[name="source"]');
  const directPanel = document.getElementById("direct-panel");
  const scenarioText = document.getElementById("scenario-text");
  const fileInput = document.getElementById("file-1040");
  const btnPickPdf = document.getElementById("btn-pick-pdf");
  const pdfLabel = document.getElementById("pdf-file-label");
  const statusEl = document.getElementById("form-status");
  const btnContinue = document.getElementById("btn-continue");
  const elapsedWrap = document.getElementById("elapsed-wrap");
  const elapsedSec = document.getElementById("elapsed-sec");
  const elapsedLabel = document.getElementById("elapsed-label");
  const elapsedHint = document.getElementById("elapsed-hint");
  let elapsedTimerId = null;
  function stopElapsedTimer() {
    if (elapsedTimerId) { clearInterval(elapsedTimerId); elapsedTimerId = null; }
    if (elapsedWrap) { elapsedWrap.hidden = true; elapsedWrap.classList.remove("e2e-elapsed--active"); }
  }
  function startElapsedTimer(mode) {
    stopElapsedTimer();
    mode = mode || "tax";
    if (elapsedLabel) {
      elapsedLabel.textContent = mode === "pdf_iam" ? "Processing" : "Computing";
    }
    if (elapsedHint) {
      if (mode === "pdf_iam") {
        elapsedHint.textContent = "Upload, Intuit 1040 extraction, then tax engine — often several minutes total. Timer runs for the full wait.";
      } else {
        elapsedHint.textContent = "Tax engine and AI passes can take a minute or two.";
      }
    }
    if (!elapsedWrap || !elapsedSec) return;
    elapsedWrap.hidden = false;
    elapsedWrap.classList.add("e2e-elapsed--active");
    const t0 = Date.now();
    elapsedSec.textContent = "0";
    elapsedTimerId = setInterval(function () {
      elapsedSec.textContent = String(Math.floor((Date.now() - t0) / 1000));
    }, 250);
  }
  function setStatus(msg, kind) {
    if (!msg) {
      statusEl.hidden = true; statusEl.textContent = ""; statusEl.className = "e2e-status";
      stopElapsedTimer();
      return;
    }
    statusEl.hidden = false; statusEl.textContent = msg;
    statusEl.className = "e2e-status" + (kind === "error" ? " e2e-status--error" : kind === "ok" ? " e2e-status--ok" : "");
  }
  function currentSource() { const r = form.querySelector('input[name="source"]:checked'); return r ? r.value : ""; }
  function syncUi() {
    const src = currentSource();
    btnPickPdf.disabled = src !== "pdf";
    fileInput.disabled = src !== "pdf";
    const showScenario = src === "direct" || src === "pdf";
    directPanel.hidden = !showScenario;
    scenarioText.disabled = !showScenario;
    if (src === "pdf") {
      scenarioText.placeholder = "After upload with Financial Document, extracted scenario text appears here (editable).";
    } else if (src === "direct") {
      scenarioText.placeholder = "Paste or type the tax situation (e.g. filing status, income, deductions, credits…).";
    }
  }
  radios.forEach(function (r) { r.addEventListener("change", function () { setStatus(""); syncUi(); }); });
  btnPickPdf.addEventListener("click", function () { if (!btnPickPdf.disabled) fileInput.click(); });
  fileInput.addEventListener("change", function () {
    const f = fileInput.files && fileInput.files[0];
    pdfLabel.textContent = f ? f.name : "No file chosen";
    scenarioText.value = "";
  });
  syncUi();
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    setStatus("");
    const source = currentSource();
    const usePdfIam = source === "pdf" && !!BASELINE_CFG.pdfIntuitIam;
    let uploadId = null;
    let timerStarted = false;
    if (source === "pdf") {
      if (!fileInput.files || !fileInput.files[0]) { setStatus("Choose a 1040 PDF to continue.", "error"); return; }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);
      btnContinue.disabled = true;
      if (usePdfIam) {
        setStatus("Uploading PDF…", "ok");
        startElapsedTimer("pdf_iam");
        timerStarted = true;
      }
      try {
        const up = await fetch("/api/upload-1040", { method: "POST", body: fd });
        const data = await up.json();
        if (!up.ok || !data.ok) {
          setStatus(data.error || "Upload failed.", "error");
          if (timerStarted) stopElapsedTimer();
          btnContinue.disabled = false;
          return;
        }
        uploadId = data.upload_id;
        if (data.scenario_text) {
          scenarioText.value = data.scenario_text;
        }
        if (data.extraction_error) {
          setStatus(
            String(data.extraction_error) +
              " — No scenario was saved. Check VPN/network, then choose the same PDF again, or use Direct entry to paste a scenario.",
            "error"
          );
          if (!data.scenario_text) {
            if (timerStarted) stopElapsedTimer();
            btnContinue.disabled = false;
            return;
          }
        } else if (usePdfIam && data.scenario_text) {
          setStatus("Extraction complete — review the scenario below, then Continue.", "ok");
        } else if (usePdfIam) {
          setStatus("PDF saved — Continue to run extraction and tax calculation.", "ok");
        } else {
          setStatus("PDF saved — Continue to build scenario and calculate tax.", "ok");
        }
      } catch (err) {
        setStatus("Upload failed.", "error");
        if (timerStarted) stopElapsedTimer();
        btnContinue.disabled = false;
        return;
      }
    }
    if (source === "direct") {
      if (!(scenarioText.value || "").trim()) { setStatus("Enter a scenario description or choose another option.", "error"); return; }
    }
    btnContinue.disabled = true;
    if (!timerStarted) {
      setStatus("Computing actual return (this may take a minute)…", "ok");
      startElapsedTimer("tax");
    }
    try {
      const body = {
        source,
        upload_id: uploadId,
        scenario_text: (source === "direct" || source === "pdf") ? scenarioText.value.trim() : null
      };
      const res = await fetch("/api/baseline-continue", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const raw = await res.text();
      let data;
      try { data = JSON.parse(raw); } catch (e) {
        setStatus("Bad response from server. Check terminal logs.", "error");
        return;
      }
      if (!res.ok || !data.ok) { setStatus(data.error || "Request failed.", "error"); return; }
      if (!data.session_id) {
        setStatus("This page is out of date. Restart expert_advisory_e2e.py and hard-refresh (Cmd+Shift+R).", "error");
        return;
      }
      try {
        sessionStorage.setItem("expert_e2e_session_v1", JSON.stringify({
          session_id: data.session_id,
          scenario_text: data.scenario_text,
          source: data.source,
          actual_year: data.actual_year,
          result: data.result,
          data_model: data.data_model,
          error: data.error
        }));
      } catch (e) { /* quota */ }
      window.location.replace("/actual-return?session=" + encodeURIComponent(data.session_id));
    } catch (err) { setStatus("Request failed. Try again.", "error"); }
    finally { stopElapsedTimer(); btnContinue.disabled = false; }
  });
})();
  </script>
</body>
</html>
"""

def _render_actual_return(session_id: str, session: dict) -> str:
    """Build Actual return HTML with data inlined (no client bootstrap). Content is HTML-escaped."""
    year = session.get("actual_year") or "2024"
    source = (session.get("source") or "").strip()
    scenario = session.get("scenario_text") or ""
    err = session.get("error")
    result_raw = session.get("result") or ""
    if err:
        result_block = f"(Calculation error)\n\n{err}"
    else:
        result_block = result_raw
    dm = session.get("data_model")
    if not isinstance(dm, dict):
        dm = None

    badge_attr = "" if source else " hidden"
    projection_href = f"/baseline-projection?session={quote(session_id, safe='')}"
    repl = {
        "__E2E_SESSION__": html.escape(session_id, quote=True),
        "__E2E_PROJECTION_HREF__": projection_href,
        "__E2E_YEAR__": html.escape(year, quote=False),
        "__E2E_BADGE_ATTR__": badge_attr,
        "__E2E_BADGE_TEXT__": html.escape(source, quote=False),
        "__E2E_SCENARIO__": html.escape(scenario, quote=False),
        "__E2E_RESULT__": html.escape(result_block, quote=False),
        "__E2E_INPUTS_TBODY__": _html_inputs_tbody(dm),
        "__E2E_FORM1040_TBODY__": _html_form1040_tbody(dm),
    }
    out = ACTUAL_RETURN_TEMPLATE
    for key, val in repl.items():
        out = out.replace(key, val)
    return out


def _render_baseline_projection(session_id: str, session: dict) -> str:
    """HTML shell for baseline projection. Quick Compare loads via /api/session/<id>/comparison (avoids tunnel timeouts)."""
    proj = session.get("projection") if isinstance(session.get("projection"), dict) else {}
    _, _ay_built, py_int, delta, summ_line = _build_projection_scenario(session)
    py = str(py_int)
    ay = str(session.get("actual_year") or _ay_built or "—")
    delta_s = str(delta) if delta is not None else "0"
    summ = (summ_line or "").strip()
    err = proj.get("error")
    err_banner = (
        f'<div class="e2e-card e2e-card--error"><p class="err-banner">{html.escape(str(err), quote=False)}</p></div>'
        if err
        else ""
    )

    repl = {
        "__EPROJ_SESSION__": html.escape(session_id, quote=True),
        "__EPROJ_ACTUAL_HREF__": f"/actual-return?session={quote(session_id, safe='')}",
        "__EPROJ_YEAR__": html.escape(py, quote=False),
        "__EPROJ_ACTUAL_YEAR__": html.escape(ay, quote=False),
        "__EPROJ_DELTA__": html.escape(delta_s, quote=False),
        "__EPROJ_SUMMARY__": html.escape(summ, quote=False),
        "__EPROJ_ERROR_BANNER__": err_banner,
    }
    out = BASELINE_PROJECTION_TEMPLATE
    for key, val in repl.items():
        out = out.replace(key, val)
    return out


SCENARIO_DETAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Expert Advisory — __EDET_TITLE__</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    :root {
      --bg: #f3f2f7; --surface: #ffffff; --text: #1c1b22; --text-muted: #6b6b70;
      --primary: #5e5ce6; --primary-subtle: rgba(94, 92, 230, 0.08);
      --border-light: #ebeaf0; --shadow: 0 2px 8px rgba(28, 27, 34, 0.06);
      --radius: 14px; --radius-sm: 10px;
    }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 16px; line-height: 1.5; color: var(--text); background: var(--bg); min-height: 100vh; }
    .e2e-wrap { max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }
    .e2e-nav { display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; margin-bottom: 1rem; font-size: 0.875rem; }
    .e2e-nav a { color: var(--primary); text-decoration: none; }
    .e2e-nav a:hover { text-decoration: underline; }
    .e2e-card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow);
      border: 1px solid var(--border-light); padding: 1.75rem; margin-bottom: 1.25rem; }
    .e2e-section-title { margin: 0 0 0.75rem; font-size: 0.8125rem; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.03em; }
    details.llm-details { border: 1px solid var(--border-light); border-radius: var(--radius-sm); overflow: hidden; background: var(--surface); }
    summary.llm-summary { cursor: pointer; padding: 0.75rem 1rem; margin: 0; font-size: 0.8125rem; font-weight: 600;
      color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; list-style: none; user-select: none; }
    summary.llm-summary::-webkit-details-marker { display: none; }
    summary.llm-summary::before { content: "▸ "; display: inline-block; transition: transform 0.12s ease; }
    details.llm-details[open] summary.llm-summary::before { transform: rotate(90deg); }
    .mono-block { margin: 0; padding: 1rem; background: var(--bg); font-size: 0.8125rem; line-height: 1.45;
      white-space: pre-wrap; word-break: break-word; max-height: 360px; overflow: auto; border: none;
      border-top: 1px solid var(--border-light); }
    .table-wrap { overflow-x: auto; margin: 0 -0.25rem; }
    table.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    table.data-table th, table.data-table td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-light); vertical-align: top; }
    table.data-table thead th { font-size: 0.6875rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;
      letter-spacing: 0.04em; background: var(--bg); }
    table.data-table .col-line { width: 3.25rem; font-variant-numeric: tabular-nums; font-weight: 600; }
    table.data-table .col-amt { text-align: right; font-variant-numeric: tabular-nums; }
    table.data-table .col-field { color: var(--text-muted); }
    table.data-table tr.inputs-section td { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--text-muted); background: var(--bg); padding-top: 0.85rem; }
    .muted { color: var(--text-muted); font-style: italic; }
    .insight-block { margin-bottom: 1.25rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-light); }
    .insight-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
    .insight-block h3 { margin: 0 0 0.5rem; font-size: 1rem; }
    .insight-actions { margin-top: 0.65rem; padding: 0.65rem; background: var(--bg); border-radius: var(--radius-sm); font-size: 0.875rem; }
    .insight-actions ul { margin: 0.35rem 0 0; padding-left: 1.2rem; }
    .events-list { margin: 0.35rem 0 0; padding-left: 1.2rem; color: var(--text-muted); font-size: 0.9rem; }
    .chat-seed { width: 100%; min-height: 8rem; padding: 0.75rem; font: inherit; font-size: 0.875rem;
      border: 1px solid var(--border-light); border-radius: var(--radius-sm); background: var(--bg); resize: vertical; }
    .btn { display: inline-flex; align-items: center; padding: 0.45rem 1rem; margin-top: 0.65rem; font: inherit; font-size: 0.875rem;
      font-weight: 500; border-radius: var(--radius-sm); cursor: pointer; border: 1px solid #d1d0d6; background: #e8e7ec; color: var(--text); }
    .btn:hover { background: #dddce3; }
    .copy-toast { margin-top: 0.5rem; font-size: 0.8125rem; color: #15803d; min-height: 1.25rem; }
  </style>
</head>
<body data-session-id="__EDET_SESSION__">
  <div class="e2e-wrap">
    <nav class="e2e-nav" aria-label="Flow">
      <a href="/">← Baseline setup</a>
      <a href="__EDET_BASELINE_HREF__">← Quick compare</a>
      <a href="__EDET_ACTUAL_HREF__">Prior-year actual return</a>
    </nav>
    <header class="e2e-agent-header">
      <p style="margin:0 0 0.35rem;font-size:1.25rem;font-weight:600;">__EDET_TITLE__</p>
      <p class="muted" style="margin:0;font-size:0.9rem;">Session: <code>__EDET_SESSION__</code> · Scenario id: <code>__EDET_SID__</code></p>
    </header>
    <div class="e2e-card">
      <details class="llm-details" open>
        <summary class="llm-summary">Scenario sent to the tax model</summary>
        <pre class="mono-block" id="blk-scenario">__EDET_SCENARIO__</pre>
      </details>
    </div>
    <div class="e2e-card">
      <details class="llm-details" open>
        <summary class="llm-summary">Tax calculation (LLM result)</summary>
        <pre class="mono-block" id="blk-result">__EDET_RESULT__</pre>
      </details>
    </div>
    <div class="e2e-card">
      <h2 class="e2e-section-title">Structured inputs</h2>
      <div class="table-wrap">
        <table class="data-table" aria-label="Structured inputs">
          <thead><tr><th class="col-field">Field</th><th>Value</th></tr></thead>
          <tbody>__EDET_INPUTS_TBODY__</tbody>
        </table>
      </div>
    </div>
    <div class="e2e-card">
      <h2 class="e2e-section-title">Form 1040 lines</h2>
      <div class="table-wrap">
        <table class="data-table" aria-label="Form 1040">
          <thead><tr><th class="col-line">Line</th><th>Description</th><th class="col-amt">Amount</th></tr></thead>
          <tbody>__EDET_FORM1040_TBODY__</tbody>
        </table>
      </div>
    </div>
    <div class="e2e-card">
      <h2 class="e2e-section-title">Tax events, insights &amp; savings opportunities</h2>
      <div class="insight-block">
        <h3>Events</h3>
        <p class="muted" style="margin:0;font-size:0.875rem;">Upcoming items to watch in your timeline.</p>
        <ul class="events-list">
          <li><strong>Deadlines</strong> — Estimated tax due dates, extension filing, and year-end moves aligned to your tax year.</li>
          <li><strong>Age-related milestones</strong> — RMD ages, catch-up eligibility, and other age triggers as they apply.</li>
          <li><strong>Marginal rate change potential</strong> — Income bands where small changes could shift the marginal bracket.</li>
          <li><strong>Phaseouts</strong> — Credits and deductions that taper with AGI near your income level.</li>
        </ul>
      </div>
      <div class="insight-block">
        <h3>Insights</h3>
        <p style="margin:0 0 0.5rem;font-size:0.9rem;">Patterns worth discussing with your advisor for this scenario.</p>
        <div class="insight-actions">
          <strong>Actions you could take</strong>
          <ul>
            <li>Revisit withholding and estimated payments relative to modeled liability.</li>
            <li>Model changes (retirement contributions, conversions) and compare on Quick compare.</li>
            <li>Stress-test income moves against phaseout thresholds.</li>
          </ul>
        </div>
      </div>
      <div class="insight-block">
        <h3>Savings opportunities</h3>
        <div class="insight-actions">
          <strong>Actions you could take</strong>
          <ul>
            <li>Maximize pre-tax retirement where cash flow allows.</li>
            <li>Review tax-loss harvesting and wash-sale rules for taxable investments.</li>
            <li>Consider timing of deductions or charitable giving in high-income years.</li>
          </ul>
        </div>
      </div>
    </div>
    <div class="e2e-card">
      <h2 class="e2e-section-title">Discuss this scenario</h2>
      <p style="margin:0 0 0.75rem;font-size:0.9rem;color:var(--text-muted);">Copy the scenario text into your tax assistant, advisor chat, or notes to go deeper. (A full in-app chat can be wired to the same GenOS path as Calculate Tax.)</p>
      <label for="chat-seed" class="muted" style="font-size:0.8125rem;">Scenario text to copy</label>
      <textarea id="chat-seed" class="chat-seed" readonly>__EDET_SCENARIO_PLAIN__</textarea>
      <button type="button" class="btn" id="btn-copy-scenario">Copy scenario text</button>
      <p class="copy-toast" id="copy-toast" aria-live="polite"></p>
    </div>
  </div>
  <script>
(function () {
  var b = document.getElementById("btn-copy-scenario");
  var t = document.getElementById("chat-seed");
  var toast = document.getElementById("copy-toast");
  if (b && t) {
    b.addEventListener("click", function () {
      t.select();
      t.setSelectionRange(0, 99999);
      try {
        navigator.clipboard.writeText(t.value).then(function () {
          if (toast) toast.textContent = "Copied to clipboard.";
        }).catch(function () {
          if (toast) toast.textContent = "Select the text and copy manually (⌘C / Ctrl+C).";
        });
      } catch (e) {
        if (toast) toast.textContent = "Select the text and copy manually (⌘C / Ctrl+C).";
      }
    });
  }
})();
  </script>
</body>
</html>
"""


def _render_scenario_detail(session_id: str, session: dict, scenario_id: str) -> str:
    """Full-page drill-down for one scenario (actual, projection, or comparison-only id)."""
    proj = session.get("projection") or {}
    py = str(proj.get("projection_year") or PROJECTION_YEAR)
    ay = str(session.get("actual_year") or "2024")
    baseline_href = f"/baseline-projection?session={quote(session_id, safe='')}"
    actual_href = f"/actual-return?session={quote(session_id, safe='')}"
    dm: dict | None = None
    title = "Scenario"
    st_plain = ""
    res_plain = ""

    if scenario_id == "actual":
        title = f"{ay} actual"
        st_plain = (session.get("scenario_text") or "").strip()
        res_plain = (session.get("result") or "").strip()
        if session.get("error"):
            res_plain = f"(Tax calculation error)\n\n{session.get('error')}"
        dm = session.get("data_model") if isinstance(session.get("data_model"), dict) else None
    elif scenario_id == "projection":
        title = f"{py} projection"
        st_plain = (proj.get("scenario_text") or "").strip()
        res_plain = (proj.get("result") or "").strip()
        if proj.get("error"):
            res_plain = f"(Projection calculation error)\n\n{proj.get('error')}"
        dm = proj.get("data_model") if isinstance(proj.get("data_model"), dict) else None
    else:
        title = "Comparison scenario"
        st_plain = (
            "This scenario exists only in Quick Compare on the baseline projection page. "
            "No full scenario text or tax run is stored for it on the server. "
            "Use “2024 actual” or the projection scenario for a full drill-down, or add calculations in a future build."
        )
        res_plain = ""
        dm = None

    repl = {
        "__EDET_SESSION__": html.escape(session_id, quote=True),
        "__EDET_SID__": html.escape(scenario_id, quote=True),
        "__EDET_BASELINE_HREF__": baseline_href,
        "__EDET_ACTUAL_HREF__": actual_href,
        "__EDET_TITLE__": html.escape(title, quote=False),
        "__EDET_SCENARIO__": html.escape(st_plain or "—", quote=False),
        "__EDET_RESULT__": html.escape(res_plain or "—", quote=False),
        "__EDET_SCENARIO_PLAIN__": html.escape(st_plain, quote=False),
        "__EDET_INPUTS_TBODY__": _html_inputs_tbody(dm),
        "__EDET_FORM1040_TBODY__": _html_form1040_tbody(dm),
    }
    out = SCENARIO_DETAIL_TEMPLATE
    for key, val in repl.items():
        out = out.replace(key, val)
    return out


ACTUAL_RETURN_ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Expert Advisory — Actual return</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1.5rem;
      color: #1c1b22; background: #f3f2f7; }
    .card { background: #fff; border-radius: 14px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(28,27,34,.06); }
    .err { color: #b91c1c; }
    a { color: #5e5ce6; }
  </style>
</head>
<body>
  <p><a href="/">← Baseline setup</a></p>
  <div class="card">
    <h1>Actual return</h1>
    <p class="err">__E2E_ERR_MSG__</p>
    <p style="color:#6b6b70;font-size:0.875rem">Session id (if any): <code>__E2E_ERR_SID__</code></p>
  </div>
</body>
</html>"""


ACTUAL_RETURN_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Expert Advisory — Actual return</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    :root {
      --bg: #f3f2f7;
      --surface: #ffffff;
      --text: #1c1b22;
      --text-muted: #6b6b70;
      --primary: #5e5ce6;
      --primary-hover: #4c4ad4;
      --primary-subtle: rgba(94, 92, 230, 0.08);
      --border: #e5e4eb;
      --border-light: #ebeaf0;
      --shadow: 0 2px 8px rgba(28, 27, 34, 0.06);
      --radius: 14px;
      --radius-sm: 10px;
      --sparkle: #5b9bd5;
    }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 16px; line-height: 1.5; color: var(--text); background: var(--bg); min-height: 100vh; }
    .e2e-wrap { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }
    .e2e-back { display: inline-block; margin-bottom: 1rem; font-size: 0.875rem; color: var(--primary); text-decoration: none; }
    .e2e-back:hover { text-decoration: underline; }
    .e2e-agent-header { margin-bottom: 1.25rem; }
    .e2e-agent-line1 { margin: 0 0 0.35rem; font-size: 1.25rem; font-weight: 600; color: var(--text); }
    .e2e-agent-line2 { margin: 0; display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.9375rem; font-weight: 700; color: var(--text); }
    .e2e-card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow); border: 1px solid var(--border-light); padding: 1.75rem; margin-bottom: 1.25rem; }
    .e2e-section-title { margin: 0 0 0.75rem; font-size: 0.8125rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; }
    .label { display: block; margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 500; }
    .scenario-textarea {
      width: 100%; min-height: 180px; padding: 0.75rem 1rem; font: inherit; font-size: 0.9375rem;
      border: 1px solid var(--border); border-radius: var(--radius-sm); resize: vertical;
    }
    .scenario-textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-subtle); }
    .mono-block {
      margin: 0; padding: 1rem; background: var(--bg); border: 1px solid var(--border-light); border-radius: var(--radius-sm);
      font-size: 0.8125rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word; max-height: 560px; overflow: auto;
    }
    details.llm-details { border: 1px solid var(--border-light); border-radius: var(--radius-sm); overflow: hidden; background: var(--surface); }
    summary.llm-summary {
      cursor: pointer; padding: 0.75rem 1rem; margin: 0;
      font-size: 0.8125rem; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.03em; list-style: none; user-select: none;
    }
    summary.llm-summary::-webkit-details-marker { display: none; }
    summary.llm-summary::before { content: "▸ "; display: inline-block; transition: transform 0.12s ease; }
    details.llm-details[open] summary.llm-summary::before { transform: rotate(90deg); }
    .mono-block-llm { border: none; border-top: 1px solid var(--border-light); border-radius: 0; max-height: 320px; }
    .table-wrap { overflow-x: auto; margin: 0 -0.25rem; }
    table.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    table.data-table th, table.data-table td {
      text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-light); vertical-align: top;
    }
    table.data-table thead th {
      font-size: 0.6875rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;
      background: var(--bg);
    }
    table.data-table tbody tr:last-child td { border-bottom: none; }
    table.data-table .col-line { width: 3.25rem; font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
    table.data-table .col-amt { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    table.data-table .col-field { width: 44%; color: var(--text-muted); }
    table.data-table .col-desc { color: var(--text); }
    table.data-table tr.inputs-section td {
      font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--text-muted); background: var(--bg); border-bottom: 1px solid var(--border-light);
      padding-top: 0.85rem;
    }
    table.data-table tr.inputs-section:first-child td { padding-top: 0.55rem; }
    .muted { color: var(--text-muted); font-style: italic; }
    .actions { display: flex; flex-wrap: wrap; gap: 1.5rem; align-items: flex-start; margin-top: 1.5rem; padding-top: 1.25rem; border-top: 1px solid var(--border-light); }
    .btn {
      display: inline-flex; align-items: center; justify-content: center;
      padding: 0.5rem 1.25rem; font: inherit; font-size: 0.9375rem; font-weight: 500;
      border-radius: var(--radius-sm); cursor: pointer; border: 1px solid var(--border); transition: background 0.15s;
    }
    .btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
    a.btn-primary { text-decoration: none; color: #fff; }
    a.btn-primary:hover { color: #fff; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn-muted { background: #e8e7ec; border-color: #d1d0d6; color: var(--text); }
    .btn-muted:hover { background: #dddce3; }
    .btn-muted:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn-col { display: flex; flex-direction: column; align-items: flex-start; gap: 0.35rem; }
    .btn-hint { margin: 0; font-size: 0.8125rem; color: var(--text-muted); max-width: 14rem; line-height: 1.35; }
    .src-badge { display: inline-block; font-size: 0.75rem; padding: 0.2rem 0.5rem; background: var(--bg); border-radius: 6px; color: var(--text-muted); margin-left: 0.5rem; }
    .sr-hint { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
    .e2e-elapsed {
      display: none; flex-direction: column; gap: 0.45rem; max-width: 16rem;
      padding: 0.65rem 0.9rem; margin-top: 0.75rem;
      background: linear-gradient(145deg, var(--primary-subtle), rgba(91, 155, 213, 0.06));
      border: 1px solid var(--border-light); border-radius: var(--radius-sm); box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
    }
    .e2e-elapsed:not([hidden]) { display: flex; }
    .e2e-elapsed-label { font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
    .e2e-elapsed-readout { display: flex; align-items: baseline; gap: 0.3rem; }
    .e2e-elapsed-value { font-size: 1.75rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primary); line-height: 1; letter-spacing: -0.02em; }
    .e2e-elapsed-unit { font-size: 0.9375rem; font-weight: 500; color: var(--text-muted); }
    .e2e-elapsed--active .e2e-elapsed-value { animation: e2e-tick-pulse 2s ease-in-out infinite; }
    @keyframes e2e-tick-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.82; } }
    .e2e-elapsed-hint { margin: 0; font-size: 0.75rem; color: var(--text-muted); line-height: 1.35; }
    .projection-nav-status { margin: 0.75rem 0 0.5rem; font-size: 0.9375rem; font-weight: 500; color: #15803d; }
    .projection-nav-status[hidden] { display: none !important; }
    .btn-primary.is-navigating { opacity: 0.72; pointer-events: none; cursor: wait; }
  </style>
</head>
<body data-session-id="__E2E_SESSION__">
  <div class="e2e-wrap">
    <a class="e2e-back" href="/">← Baseline setup</a>
    <header class="e2e-agent-header">
      <p class="e2e-agent-line1">
        <span id="hdr-title">__E2E_YEAR__ Actual return</span>
        <span id="hdr-badge" class="src-badge"__E2E_BADGE_ATTR__>__E2E_BADGE_TEXT__</span>
      </p>
      <p class="e2e-agent-line2">
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="var(--sparkle)" d="M12 1.5l1.8 5.5h5.9l-4.8 3.5 1.8 5.5L12 12.5 7.3 16l1.8-5.5L4.3 7h5.9L12 1.5z"/></svg>
        <span>Computed from the textual description using the same tax engine as Tax Advisory.</span>
      </p>
    </header>
    <p class="sr-hint">Results below are rendered by the server; JavaScript is only for Recalculate.</p>
    <div class="e2e-card">
      <h2 class="e2e-section-title">Scenario description</h2>
      <label for="scenario-edit" class="label">Edit if needed, then use AI recalc</label>
      <textarea id="scenario-edit" class="scenario-textarea">__E2E_SCENARIO__</textarea>
    </div>
    <div class="e2e-card" id="result-card">
      <details class="llm-details">
        <summary class="llm-summary">Tax calculation (LLM result)</summary>
        <pre id="result-pre" class="mono-block mono-block-llm">__E2E_RESULT__</pre>
      </details>
    </div>
    <div class="e2e-card" id="inputs-card">
      <h2 class="e2e-section-title">Inputs</h2>
      <div class="table-wrap">
        <table class="data-table" aria-label="Tax situation inputs">
          <thead><tr><th>Field</th><th>Value</th></tr></thead>
          <tbody>__E2E_INPUTS_TBODY__</tbody>
        </table>
      </div>
    </div>
    <div class="e2e-card" id="form1040-card">
      <h2 class="e2e-section-title">1040 output</h2>
      <div class="table-wrap">
        <table class="data-table" aria-label="Form 1040 summary lines">
          <thead><tr><th>Line</th><th>Description</th><th>Amount</th></tr></thead>
          <tbody>__E2E_FORM1040_TBODY__</tbody>
        </table>
      </div>
    </div>
    <div class="e2e-card actions-wrap">
      <div class="actions">
        <div class="btn-col">
          <a class="btn btn-primary" id="btn-alls-well" href="__E2E_PROJECTION_HREF__">All's well</a>
          <p class="btn-hint">Continue to baseline projection</p>
        </div>
        <button type="button" class="btn btn-muted" id="btn-recalc">AI recalc</button>
      </div>
      <p class="projection-nav-status" id="projection-nav-status" hidden>Computing baseline projection (this may take a minute)…</p>
      <div class="e2e-elapsed" id="projection-elapsed-wrap" hidden aria-live="polite" aria-atomic="true">
        <span class="e2e-elapsed-label">Computing</span>
        <div class="e2e-elapsed-readout">
          <span class="e2e-elapsed-value" id="projection-elapsed-sec">0</span>
          <span class="e2e-elapsed-unit">s</span>
        </div>
        <p class="e2e-elapsed-hint">Tax engine and AI passes can take a minute or two.</p>
      </div>
      <div class="e2e-elapsed" id="recalc-elapsed-wrap" hidden aria-live="polite" aria-atomic="true">
        <span class="e2e-elapsed-label">Recalculating</span>
        <div class="e2e-elapsed-readout">
          <span class="e2e-elapsed-value" id="recalc-elapsed-sec">0</span>
          <span class="e2e-elapsed-unit">s</span>
        </div>
        <p class="e2e-elapsed-hint">Same pipeline as baseline — two LLM passes.</p>
      </div>
      <p id="action-status" class="btn-hint" style="margin-top:1rem" hidden></p>
    </div>
  </div>
  <script>
(function () {
  var sessionId = (document.body.getAttribute("data-session-id") || "").trim();
  if (!sessionId) {
    sessionId = (new URLSearchParams(location.search).get("session") || "").trim();
  }
  if (!sessionId) return;
  var scenarioEdit = document.getElementById("scenario-edit");
  var btnRecalc = document.getElementById("btn-recalc");
  var actionStatus = document.getElementById("action-status");
  var recalcElapsedWrap = document.getElementById("recalc-elapsed-wrap");
  var recalcElapsedSec = document.getElementById("recalc-elapsed-sec");
  var recalcTimerId = null;
  var btnAllsWell = document.getElementById("btn-alls-well");
  var projectionNavStatus = document.getElementById("projection-nav-status");
  var projectionElapsedWrap = document.getElementById("projection-elapsed-wrap");
  var projectionElapsedSec = document.getElementById("projection-elapsed-sec");
  var projectionTimerId = null;
  function stopRecalcElapsed() {
    if (recalcTimerId) { clearInterval(recalcTimerId); recalcTimerId = null; }
    if (recalcElapsedWrap) { recalcElapsedWrap.hidden = true; recalcElapsedWrap.classList.remove("e2e-elapsed--active"); }
  }
  function startRecalcElapsed() {
    stopRecalcElapsed();
    if (!recalcElapsedWrap || !recalcElapsedSec) return;
    recalcElapsedWrap.hidden = false;
    recalcElapsedWrap.classList.add("e2e-elapsed--active");
    var t0 = Date.now();
    recalcElapsedSec.textContent = "0";
    recalcTimerId = setInterval(function () {
      recalcElapsedSec.textContent = String(Math.floor((Date.now() - t0) / 1000));
    }, 250);
  }
  function setActionStatus(msg, isErr) {
    if (!msg) { actionStatus.hidden = true; actionStatus.textContent = ""; stopRecalcElapsed(); return; }
    actionStatus.hidden = false; actionStatus.textContent = msg;
    actionStatus.style.color = isErr ? "#b91c1c" : "var(--text-muted)";
  }
  function startProjectionNavElapsed() {
    if (projectionTimerId) { clearInterval(projectionTimerId); projectionTimerId = null; }
    if (projectionNavStatus) projectionNavStatus.hidden = false;
    if (!projectionElapsedWrap || !projectionElapsedSec) return;
    projectionElapsedWrap.hidden = false;
    projectionElapsedWrap.classList.add("e2e-elapsed--active");
    var t0 = Date.now();
    projectionElapsedSec.textContent = "0";
    projectionTimerId = setInterval(function () {
      projectionElapsedSec.textContent = String(Math.floor((Date.now() - t0) / 1000));
    }, 250);
    try {
      projectionElapsedWrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {}
  }
  if (btnAllsWell) {
    btnAllsWell.addEventListener("click", function (ev) {
      var href = (btnAllsWell.getAttribute("href") || "").trim();
      if (!href || href === "#") return;
      ev.preventDefault();
      btnAllsWell.classList.add("is-navigating");
      startProjectionNavElapsed();
      window.location.href = href;
    });
  }
  btnRecalc.addEventListener("click", async function () {
    setActionStatus("");
    btnRecalc.disabled = true;
    startRecalcElapsed();
    try {
      var res = await fetch("/api/session/" + encodeURIComponent(sessionId) + "/recalc", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_text: scenarioEdit.value })
      });
      var raw = await res.text();
      var data;
      try { data = JSON.parse(raw); } catch (e) { throw new Error("Bad JSON from recalc"); }
      if (!res.ok || !data.ok) throw new Error(data.error || "Recalc failed");
      window.location.reload();
    } catch (e) { setActionStatus(e.message || String(e), true); }
    finally { stopRecalcElapsed(); btnRecalc.disabled = false; }
  });
})();
  </script>
</body>
</html>"""

BASELINE_PROJECTION_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Expert Advisory — Baseline projection</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    :root {
      --bg: #f3f2f7; --surface: #ffffff; --text: #1c1b22; --text-muted: #6b6b70;
      --primary: #5e5ce6; --primary-hover: #4c4ad4; --primary-subtle: rgba(94, 92, 230, 0.08);
      --border: #e5e4eb; --border-light: #ebeaf0; --shadow: 0 2px 8px rgba(28, 27, 34, 0.06);
      --radius: 14px; --radius-sm: 10px; --sparkle: #5b9bd5;
    }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 16px; line-height: 1.5; color: var(--text); background: var(--bg); min-height: 100vh; }
    .e2e-wrap { max-width: 1400px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }
    .proj-layout { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 1.25rem; align-items: start; }
    @media (max-width: 900px) { .proj-layout { grid-template-columns: 1fr; } }
    .scen-sidebar { position: sticky; top: 1rem; background: var(--surface); border-radius: var(--radius);
      border: 1px solid var(--border-light); padding: 1rem; box-shadow: var(--shadow); }
    .scen-sidebar-title { margin: 0 0 0.5rem; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-muted); }
    .btn-add-scen { width: 100%; display: flex; align-items: center; justify-content: center; gap: 0.35rem;
      padding: 0.5rem; margin-top: 0.75rem; font: inherit; font-size: 0.875rem; font-weight: 600; cursor: pointer;
      border-radius: var(--radius-sm); border: 1px dashed var(--primary); background: var(--primary-subtle); color: var(--primary); }
    .btn-add-scen:hover { background: rgba(94, 92, 230, 0.15); }
    .scen-list { list-style: none; margin: 0; padding: 0; }
    .scen-item { display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.65rem; font-size: 0.8125rem; }
    .scen-item label { cursor: pointer; line-height: 1.35; flex: 1; }
    .scen-item input { margin-top: 0.2rem; accent-color: var(--primary); flex-shrink: 0; }
    .btn { display: inline-flex; align-items: center; justify-content: center; padding: 0.45rem 1rem;
      font: inherit; font-size: 0.875rem; font-weight: 500; border-radius: var(--radius-sm); cursor: pointer;
      border: 1px solid var(--border); background: var(--surface); color: var(--text); }
    .btn-muted { background: #e8e7ec; border-color: #d1d0d6; color: var(--text); }
    .btn-muted:hover { background: #dddce3; }
    .liability-cols { display: flex; flex-wrap: wrap; gap: 1rem; }
    .liability-col { flex: 1; min-width: 140px; padding: 0.75rem 1rem; background: var(--surface);
      border-radius: var(--radius-sm); border: 1px solid var(--border-light); }
    .cmp-col-hidden { display: none !important; }
    .insights-panel { scroll-margin-top: 1rem; }
    .insight-block { margin-bottom: 1.25rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border-light); }
    .insight-block:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
    .insight-block h3 { margin: 0 0 0.5rem; font-size: 1rem; color: var(--text); }
    .insight-actions { margin-top: 0.65rem; padding: 0.65rem; background: var(--bg); border-radius: var(--radius-sm); font-size: 0.875rem; }
    .insight-actions ul { margin: 0.35rem 0 0; padding-left: 1.2rem; }
    .events-list { margin: 0.35rem 0 0; padding-left: 1.2rem; color: var(--text-muted); font-size: 0.9rem; }
    table.data-table .col-desc { min-width: 8rem; }
    .scen-detail-links-title { margin: 1rem 0 0.4rem; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-muted); }
    .scen-detail-links { list-style: none; margin: 0; padding: 0; font-size: 0.8125rem; }
    .scen-detail-links li { margin-bottom: 0.45rem; }
    .scen-detail-links a { color: var(--primary); text-decoration: none; word-break: break-word; }
    .scen-detail-links a:hover { text-decoration: underline; }
    .compare-limit-hint { margin: 0.5rem 0 0; font-size: 0.75rem; color: #b45309; }
    .compare-text-grid { display: grid; gap: 1rem; align-items: start; }
    @media (min-width: 768px) {
      .compare-text-grid.cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .compare-text-grid.cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
    .cmp-text-col h4 { margin: 0 0 0.5rem; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-muted); }
    .cmp-text-col .mono-block { max-height: 320px; }
    .scen-nav-block { margin-bottom: 0.75rem; }
    .scen-nav-block .scen-full-link { display: block; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 0.25rem; }
    .scen-planning-toggle { display: inline; padding: 0; margin: 0; border: none; background: none; cursor: pointer;
      font: inherit; font-size: 0.8125rem; color: var(--primary); text-align: left; text-decoration: underline; }
    .scen-planning-toggle:hover { color: var(--primary-hover); }
    .scen-subnav { list-style: none; margin: 0.4rem 0 0 0.65rem; padding: 0; font-size: 0.78rem; border-left: 2px solid var(--border-light); }
    .scen-subnav li { margin-bottom: 0.35rem; }
    .scen-subnav a { color: var(--primary); text-decoration: none; }
    .scen-subnav a:hover { text-decoration: underline; }
    .planning-subcard { margin-bottom: 1rem; padding: 1.25rem; background: var(--bg); border: 1px solid var(--border-light); border-radius: var(--radius-sm); }
    .planning-subcard h3 { margin: 0 0 0.65rem; font-size: 0.9375rem; font-weight: 600; color: var(--text); }
    .planning-subcard .e2e-section-title { margin-bottom: 0.5rem; }
    .e2e-nav { display: flex; flex-wrap: wrap; gap: 0.75rem 1.25rem; margin-bottom: 1rem; font-size: 0.875rem; }
    .e2e-nav a { color: var(--primary); text-decoration: none; }
    .e2e-nav a:hover { text-decoration: underline; }
    .e2e-agent-header { margin-bottom: 1.25rem; }
    .e2e-agent-line1 { margin: 0 0 0.35rem; font-size: 1.25rem; font-weight: 600; color: var(--text); }
    .e2e-agent-line2 { margin: 0; font-size: 0.9375rem; color: var(--text-muted); }
    .e2e-card { background: var(--surface); border-radius: var(--radius); box-shadow: var(--shadow);
      border: 1px solid var(--border-light); padding: 1.75rem; margin-bottom: 1.25rem; }
    .e2e-card--error { border-color: #fecaca; background: #fef2f2; }
    .err-banner { margin: 0; color: #b91c1c; font-weight: 500; }
    .e2e-liability-card { background: linear-gradient(145deg, var(--primary-subtle), rgba(91, 155, 213, 0.06)); }
    .e2e-liability-label { margin: 0 0 0.35rem; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--text-muted); }
    .e2e-liability-value { margin: 0; font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--primary); }
    .e2e-liability-sub { margin: 0.65rem 0 0; font-size: 1rem; color: var(--text-muted); }
    .e2e-liability-sub--refund { color: #15803d; font-weight: 600; }
    .e2e-section-title { margin: 0 0 0.75rem; font-size: 0.8125rem; font-weight: 600; color: var(--text-muted);
      text-transform: uppercase; letter-spacing: 0.03em; }
    details.llm-details { border: 1px solid var(--border-light); border-radius: var(--radius-sm); overflow: hidden; background: var(--surface); }
    summary.llm-summary { cursor: pointer; padding: 0.75rem 1rem; margin: 0; font-size: 0.8125rem; font-weight: 600;
      color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.03em; list-style: none; user-select: none; }
    summary.llm-summary::-webkit-details-marker { display: none; }
    summary.llm-summary::before { content: "▸ "; display: inline-block; transition: transform 0.12s ease; }
    details.llm-details[open] summary.llm-summary::before { transform: rotate(90deg); }
    .mono-block { margin: 0; padding: 1rem; background: var(--bg); font-size: 0.8125rem; line-height: 1.45;
      white-space: pre-wrap; word-break: break-word; max-height: 280px; overflow: auto; border: none;
      border-top: 1px solid var(--border-light); }
    .table-wrap { overflow-x: auto; margin: 0 -0.25rem; }
    table.data-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    table.data-table th, table.data-table td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border-light); vertical-align: top; }
    table.data-table thead th { font-size: 0.6875rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;
      letter-spacing: 0.04em; background: var(--bg); }
    table.data-table .col-line { width: 3.25rem; font-variant-numeric: tabular-nums; font-weight: 600; white-space: nowrap; }
    table.data-table .col-amt { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    table.data-table .col-field { width: 44%; color: var(--text-muted); }
    table.data-table tr.inputs-section td { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--text-muted); background: var(--bg); border-bottom: 1px solid var(--border-light); padding-top: 0.85rem; }
    .muted { color: var(--text-muted); font-style: italic; }
  </style>
</head>
<body data-session-id="__EPROJ_SESSION__">
  <div class="e2e-wrap">
    <nav class="e2e-nav" aria-label="Flow">
      <a href="/">← Baseline setup</a>
      <a id="link-actual" href="__EPROJ_ACTUAL_HREF__">← Prior-year actual return</a>
    </nav>
    <header class="e2e-agent-header">
      <p class="e2e-agent-line1"><span id="hdr-title">__EPROJ_YEAR__ baseline projection</span></p>
      <p class="e2e-agent-line2">__EPROJ_SUMMARY__ Prior year in flow was __EPROJ_ACTUAL_YEAR__; ages in text and structured dependents are shifted by __EPROJ_DELTA__ year(s) where applicable.</p>
    </header>
    __EPROJ_ERROR_BANNER__
    <div class="e2e-card e2e-card--error" id="cmp-bootstrap-err-wrap" hidden role="alert">
      <p class="err-banner" id="cmp-bootstrap-err"></p>
    </div>
    <div class="proj-layout">
      <aside class="scen-sidebar" aria-label="Quick compare">
        <p class="scen-sidebar-title">Quick compare</p>
        <ul class="scen-list" id="scen-list"></ul>
        <p class="compare-limit-hint" id="compare-limit-hint" hidden>At most 3 scenarios can be shown at once. Uncheck one to add another.</p>
        <p class="scen-detail-links-title">Scenarios</p>
        <div id="scen-detail-links"></div>
        <button type="button" class="btn-add-scen" id="btn-add-scenario" title="Add a scenario column">Add scenario <span aria-hidden="true">+</span></button>
      </aside>
      <div class="proj-main">
        <p class="e2e-agent-line2" style="margin:0 0 1rem;font-size:0.875rem;">Checked scenarios appear as columns in each table. Fields in the first column are shared; values differ by scenario. Projection years from 2026 onward can open planning sections in the left pane.</p>
        <div class="e2e-card e2e-liability-card">
          <h2 class="e2e-section-title">Total tax liability</h2>
          <p id="cmp-loading-status" class="e2e-agent-line2" style="margin:0 0 0.75rem;font-size:0.9rem;color:var(--text-muted)">Loading Quick Compare — running the 2026 projection (two LLM passes). Starting…</p>
          <div class="liability-cols" id="liability-cols"></div>
        </div>
        <div class="e2e-card">
          <h2 class="e2e-section-title">Scenario sent to the model</h2>
          <div class="compare-text-grid" id="scenario-text-grid"></div>
        </div>
        <div class="e2e-card">
          <h2 class="e2e-section-title">Tax calculation (LLM result)</h2>
          <div class="compare-text-grid" id="result-text-grid"></div>
        </div>
        <div class="e2e-card">
          <h2 class="e2e-section-title">Projection inputs (structured)</h2>
          <div class="table-wrap">
            <table class="data-table" id="cmp-inputs-table" aria-label="Structured inputs comparison">
              <thead id="cmp-inputs-head"><tr><th class="col-field">Field</th></tr></thead>
              <tbody id="cmp-inputs-body"></tbody>
            </table>
          </div>
        </div>
        <div class="e2e-card">
          <h2 class="e2e-section-title">1040 output</h2>
          <div class="table-wrap">
            <table class="data-table" id="cmp-1040-table" aria-label="Form 1040 comparison">
              <thead id="cmp-1040-head"><tr><th class="col-line">Line</th><th class="col-desc">Description</th></tr></thead>
              <tbody id="cmp-1040-body"></tbody>
            </table>
          </div>
        </div>
        <div class="e2e-card" id="proj-planning-panel" hidden>
          <h2 class="e2e-section-title"><span id="planning-panel-head">Projection planning</span></h2>
          <p class="muted" style="margin:0 0 1.25rem;font-size:0.875rem;">Five views of the same projection. Jump from the left pane; all cards stay visible.</p>
          <div class="planning-subcard" id="card-tax-notes">
            <h3 class="e2e-section-title" id="planning-title-tax-notes">Tax Notes</h3>
            <pre class="mono-block" id="planning-pre-tax-notes"></pre>
          </div>
          <div class="planning-subcard" id="card-quarterly-planning">
            <h3 class="e2e-section-title">Quarterly Tax Planning</h3>
            <p style="margin:0 0 0.65rem;font-size:0.875rem;color:var(--text-muted);">Estimated payments, safe harbors, and timing for the projected year. Full model output is included below for reference.</p>
            <pre class="mono-block" id="planning-pre-quarterly"></pre>
          </div>
          <div class="planning-subcard" id="card-tax-saving-ideas">
            <h3 class="e2e-section-title">Tax Saving Ideas</h3>
            <ul class="events-list" style="margin-top:0">
              <li>Revisit withholding and estimated taxes versus projected liability.</li>
              <li>Model retirement contributions, Roth conversions, or deferrals in Quick compare.</li>
              <li>Stress-test income and phaseouts before year-end moves.</li>
            </ul>
            <pre class="mono-block" id="planning-pre-saving" style="margin-top:0.75rem;max-height:200px"></pre>
          </div>
          <div class="planning-subcard" id="card-wealth-planning">
            <h3 class="e2e-section-title">Wealth Planning</h3>
            <p style="margin:0;font-size:0.875rem;color:var(--text-muted);">Investment location, basis, and multi-year cash-flow alignment with the projected return — discuss with your advisor using the scenario and calculation above.</p>
            <pre class="mono-block" id="planning-pre-wealth" style="margin-top:0.75rem;max-height:180px"></pre>
          </div>
          <div class="planning-subcard" id="card-estate-planning">
            <h3 class="e2e-section-title">Estate Planning</h3>
            <p style="margin:0;font-size:0.875rem;color:var(--text-muted);">Exemption use, basis step-up considerations, and gifting timing relative to projected income — use the full scenario text as context.</p>
            <pre class="mono-block" id="planning-pre-estate" style="margin-top:0.75rem;max-height:180px"></pre>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script>
(function () {
  var id = document.body.getAttribute("data-session-id");
  var a = document.getElementById("link-actual");
  if (a && id) a.href = "/actual-return?session=" + encodeURIComponent(id);
})();
(function () {
  var errWrap = document.getElementById("cmp-bootstrap-err-wrap");
  var errP = document.getElementById("cmp-bootstrap-err");
  var loadStatus = document.getElementById("cmp-loading-status");
  var state = null;
  var maxCmp = 3;
  var planY = 2026;
  var sessId = document.body.getAttribute("data-session-id") || "";
  function showBootstrapErr(msg) {
    if (errP) errP.textContent = msg;
    if (errWrap) errWrap.hidden = false;
  }

  function fmtMoney(n) {
    if (n == null || n === "" || (typeof n === "number" && !isFinite(n))) return "—";
    var x = typeof n === "number" ? n : parseFloat(n);
    if (!isFinite(x)) return String(n);
    return x.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  }

  function countIfChecked(sid, wantChecked) {
    var n = 0;
    if (!state || !state.scenarios) return 0;
    state.scenarios.forEach(function (x) {
      var on = x.id === sid ? wantChecked : !!x.checked;
      if (on) n++;
    });
    return n;
  }

  function showLimitHint() {
    var h = document.getElementById("compare-limit-hint");
    if (!h) return;
    h.hidden = false;
    setTimeout(function () { h.hidden = true; }, 3200);
  }

  function colClass(sid, checked) {
    return "col-amt data-cmp-col cmp-col-" + sid + (checked ? "" : " cmp-col-hidden");
  }

  function refreshColumnVisibility() {
    if (!state || !state.scenarios) return;
    state.scenarios.forEach(function (s) {
      var on = !!s.checked;
      document.querySelectorAll(".cmp-col-" + s.id).forEach(function (cell) {
        if (on) cell.classList.remove("cmp-col-hidden");
        else cell.classList.add("cmp-col-hidden");
      });
    });
  }

  function visibleCount() {
    if (!state || !state.scenarios) return 0;
    return state.scenarios.filter(function (s) { return s.checked; }).length;
  }

  function renderTextGrids() {
    if (!state || !state.scenarios) return;
    var sg = document.getElementById("scenario-text-grid");
    var rg = document.getElementById("result-text-grid");
    if (!sg || !rg) return;
    sg.innerHTML = "";
    rg.innerHTML = "";
    var n = visibleCount();
    var cls = "compare-text-grid";
    if (n >= 3) cls += " cols-3";
    else if (n === 2) cls += " cols-2";
    sg.className = cls;
    rg.className = cls;
    state.scenarios.forEach(function (s) {
      if (!s.checked) return;
      function addCol(container, text) {
        var col = document.createElement("div");
        col.className = "cmp-text-col cmp-col-" + s.id;
        var h = document.createElement("h4");
        h.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "");
        var pre = document.createElement("pre");
        pre.className = "mono-block";
        pre.textContent = text || "—";
        col.appendChild(h);
        col.appendChild(pre);
        container.appendChild(col);
      }
      addCol(sg, s.scenarioText);
      addCol(rg, s.resultText);
    });
  }

  function renderLiability() {
    if (!state || !state.scenarios) return;
    var wrap = document.getElementById("liability-cols");
    if (!wrap) return;
    wrap.innerHTML = "";
    state.scenarios.forEach(function (s) {
      var div = document.createElement("div");
      div.className = "liability-col data-cmp-col cmp-col-" + s.id + (s.checked ? "" : " cmp-col-hidden");
      var lab = document.createElement("p");
      lab.className = "e2e-liability-label";
      lab.style.marginBottom = "0.35rem";
      lab.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "");
      var val = document.createElement("p");
      val.className = "e2e-liability-value";
      val.style.fontSize = "1.5rem";
      val.textContent = fmtMoney(s.totalTax);
      div.appendChild(lab);
      div.appendChild(val);
      wrap.appendChild(div);
    });
  }

  function render1040Head() {
    var thead = document.getElementById("cmp-1040-head");
    if (!thead) return;
    var tr = thead.querySelector("tr");
    if (!tr) return;
    while (tr.children.length > 2) tr.removeChild(tr.lastChild);
    if (!state || !state.scenarios) return;
    state.scenarios.forEach(function (s) {
      var th = document.createElement("th");
      th.className = colClass(s.id, s.checked);
      th.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "");
      tr.appendChild(th);
    });
  }

  function render1040Body() {
    var tb = document.getElementById("cmp-1040-body");
    if (!tb) return;
    tb.innerHTML = "";
    if (!state || !state.scenarios) return;
    (state.lines || []).forEach(function (ln) {
      var tr = document.createElement("tr");
      var tdL = document.createElement("td");
      tdL.className = "col-line";
      tdL.textContent = ln.line;
      var tdD = document.createElement("td");
      tdD.className = "col-desc";
      tdD.textContent = ln.description;
      tr.appendChild(tdL);
      tr.appendChild(tdD);
      state.scenarios.forEach(function (s) {
        var amt = (s.amounts && s.amounts[ln.line] != null) ? s.amounts[ln.line] : null;
        var td = document.createElement("td");
        td.className = colClass(s.id, s.checked);
        td.textContent = fmtMoney(amt);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
  }

  function renderInputsHead() {
    var thead = document.getElementById("cmp-inputs-head");
    if (!thead) return;
    var tr = thead.querySelector("tr");
    if (!tr) return;
    while (tr.children.length > 1) tr.removeChild(tr.lastChild);
    if (!state || !state.scenarios) return;
    state.scenarios.forEach(function (s) {
      var th = document.createElement("th");
      th.className = colClass(s.id, s.checked);
      th.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "");
      tr.appendChild(th);
    });
  }

  function renderInputsBody() {
    var tb = document.getElementById("cmp-inputs-body");
    if (!tb) return;
    tb.innerHTML = "";
    if (!state || !state.scenarios) return;
    var rows = state.inputsRows || [];
    if (!rows.length) {
      var tr0 = document.createElement("tr");
      var td0 = document.createElement("td");
      td0.colSpan = 1 + state.scenarios.length;
      td0.className = "muted";
      td0.textContent = "No aligned inputs to compare.";
      tr0.appendChild(td0);
      tb.appendChild(tr0);
      return;
    }
    rows.forEach(function (row) {
      if (row.kind === "section") {
        var trS = document.createElement("tr");
        trS.className = "inputs-section";
        var tdS = document.createElement("td");
        tdS.colSpan = 1 + state.scenarios.length;
        tdS.textContent = row.section;
        trS.appendChild(tdS);
        tb.appendChild(trS);
        return;
      }
      var tr = document.createElement("tr");
      var tdF = document.createElement("td");
      tdF.className = "col-field";
      tdF.textContent = row.label;
      tr.appendChild(tdF);
      state.scenarios.forEach(function (s, si) {
        var td = document.createElement("td");
        td.className = colClass(s.id, s.checked);
        var v = row.values && row.values[si] != null ? row.values[si] : "";
        td.textContent = v === "" ? "—" : String(v);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
  }

  function refreshCompareUi() {
    refreshColumnVisibility();
    renderLiability();
    renderTextGrids();
    render1040Head();
    render1040Body();
    renderInputsHead();
    renderInputsBody();
  }

  function isPlanningEligible(s) {
    if (s.planningEligible) return true;
    var y = parseInt(String(s.year || ""), 10);
    return !isNaN(y) && y >= planY;
  }

  function fillPlanningPanel(sid) {
    if (!state || !state.scenarios) return;
    var s = state.scenarios.find(function (x) { return x.id === sid; });
    if (!s) return;
    var y = String(s.year || planY);
    var st = s.scenarioText || "—";
    var rt = s.resultText || "—";
    var fullPack = st + "\n\n--- Tax calculation ---\n\n" + rt;
    var h = document.getElementById("planning-panel-head");
    if (h) h.textContent = y + " projection planning";
    var tn = document.getElementById("planning-title-tax-notes");
    if (tn) tn.textContent = y + " Tax Notes";
    var set = function (id, txt) {
      var e = document.getElementById(id);
      if (e) e.textContent = txt;
    };
    set("planning-pre-tax-notes", st);
    set("planning-pre-quarterly", rt);
    set("planning-pre-saving", rt);
    set("planning-pre-wealth", fullPack);
    set("planning-pre-estate", fullPack);
  }

  function showPlanningPanel(sid) {
    var panel = document.getElementById("proj-planning-panel");
    if (!panel) return;
    fillPlanningPanel(sid);
    panel.hidden = false;
  }

  function renderDetailLinks() {
    var container = document.getElementById("scen-detail-links");
    if (!container || !sessId || !state || !state.scenarios) return;
    container.innerHTML = "";
    state.scenarios.forEach(function (s) {
      var block = document.createElement("div");
      block.className = "scen-nav-block";
      var full = document.createElement("a");
      full.className = "scen-full-link";
      full.href = "/baseline-projection/scenario?session=" + encodeURIComponent(sessId) + "&sid=" + encodeURIComponent(s.id);
      full.textContent = "Open full page · " + s.label + (s.year != null ? " (" + s.year + ")" : "");
      block.appendChild(full);

      if (isPlanningEligible(s)) {
        var y = String(s.year || planY);
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scen-planning-toggle";
        btn.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "") + " — planning ▾";
        var sub = document.createElement("ul");
        sub.className = "scen-subnav";
        sub.hidden = true;
        var anchors = [
          ["card-tax-notes", y + " Tax Notes"],
          ["card-quarterly-planning", "Quarterly Tax Planning"],
          ["card-tax-saving-ideas", "Tax Saving Ideas"],
          ["card-wealth-planning", "Wealth Planning"],
          ["card-estate-planning", "Estate Planning"]
        ];
        anchors.forEach(function (pair) {
          var sli = document.createElement("li");
          var sa = document.createElement("a");
          sa.href = "#" + pair[0];
          sa.textContent = pair[1];
          sa.addEventListener("click", function (ev) {
            ev.preventDefault();
            showPlanningPanel(s.id);
            var target = document.getElementById(pair[0]);
            if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
          });
          sli.appendChild(sa);
          sub.appendChild(sli);
        });
        btn.addEventListener("click", function () {
          sub.hidden = !sub.hidden;
          showPlanningPanel(s.id);
          if (!sub.hidden) {
            var pp = document.getElementById("proj-planning-panel");
            if (pp) pp.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
        block.appendChild(btn);
        block.appendChild(sub);
      }
      container.appendChild(block);
    });
  }

  function renderSidebar() {
    var ul = document.getElementById("scen-list");
    if (!ul || !state || !state.scenarios) return;
    ul.innerHTML = "";
    state.scenarios.forEach(function (s) {
      var li = document.createElement("li");
      li.className = "scen-item";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.id = "scen-cb-" + s.id;
      cb.checked = !!s.checked;
      cb.setAttribute("data-sid", s.id);
      var lab = document.createElement("label");
      lab.htmlFor = cb.id;
      lab.textContent = s.label + (s.year != null ? " (" + s.year + ")" : "");
      li.appendChild(cb);
      li.appendChild(lab);
      ul.appendChild(li);
      cb.addEventListener("change", function () {
        if (cb.checked) {
          if (countIfChecked(s.id, true) > maxCmp) {
            cb.checked = false;
            showLimitHint();
            return;
          }
        }
        s.checked = cb.checked;
        refreshCompareUi();
      });
    });
    renderDetailLinks();
  }

  function addScenario() {
    if (!state || !state.scenarios) return;
    var n = state.scenarios.length + 1;
    var sid = "scen-" + n + "-" + Date.now();
    var nChecked = state.scenarios.filter(function (x) { return x.checked; }).length;
    var chk = nChecked < maxCmp;
    var amounts = {};
    (state.lines || []).forEach(function (ln) {
      amounts[ln.line] = null;
    });
    if (state.inputsRows && state.inputsRows.length) {
      state.inputsRows.forEach(function (r) {
        if (r.kind === "row" && r.values) r.values.push("");
      });
    }
    state.scenarios.push({
      id: sid,
      label: "Scenario " + n,
      year: null,
      checked: chk,
      totalTax: null,
      amounts: amounts,
      scenarioText: "",
      resultText: "",
      planningEligible: false
    });
    renderSidebar();
    refreshCompareUi();
  }

  var addBtn = document.getElementById("btn-add-scenario");
  var loadTick = null;
  var loadT0 = 0;
  function stopLoadingUi() {
    if (loadTick) {
      clearInterval(loadTick);
      loadTick = null;
    }
    if (loadStatus) loadStatus.hidden = true;
  }
  function startLoadingUi() {
    if (!loadStatus) return;
    loadStatus.hidden = false;
    loadT0 = Date.now();
    var hint = "If elapsed time grows past several minutes, watch the server terminal for [expert_e2e] GET /api/session/…/comparison and projection compute lines. Cloudflare quick tunnels sometimes cut off very long HTTP requests — try local http://127.0.0.1:5002 or ngrok.";
    if (loadTick) clearInterval(loadTick);
    loadTick = setInterval(function () {
      var sec = Math.floor((Date.now() - loadT0) / 1000);
      loadStatus.textContent =
        "Loading Quick Compare — running the 2026 projection (two LLM passes). Elapsed " + sec + "s. " + hint;
    }, 1000);
    loadStatus.textContent =
      "Loading Quick Compare — running the 2026 projection (two LLM passes). Elapsed 0s. " + hint;
  }

  if (!sessId) {
    showBootstrapErr("Missing session. Open this page from Prior-year actual return (All's well).");
    stopLoadingUi();
    return;
  }

  console.log("[baseline-projection] GET /api/session/…/comparison for", sessId.slice(0, 8) + "…");
  startLoadingUi();

  var cmpCtl = new AbortController();
  var cmpAbortMs = 20 * 60 * 1000;
  var cmpAbortTid = setTimeout(function () {
    try {
      cmpCtl.abort();
    } catch (e) {}
  }, cmpAbortMs);

  fetch("/api/session/" + encodeURIComponent(sessId) + "/comparison", {
    credentials: "same-origin",
    signal: cmpCtl.signal
  })
    .then(function (r) { return r.text().then(function (t) { return { ok: r.ok, status: r.status, text: t }; }); })
    .then(function (resp) {
      clearTimeout(cmpAbortTid);
      stopLoadingUi();
      var data;
      try {
        data = JSON.parse(resp.text);
      } catch (e) {
        showBootstrapErr("Invalid JSON from server (status " + resp.status + ").");
        return;
      }
      if (!resp.ok || !data.ok) {
        showBootstrapErr(data.error || ("HTTP " + resp.status));
        return;
      }
      state = {};
      Object.keys(data).forEach(function (k) { if (k !== "ok") state[k] = data[k]; });
      if (!state.scenarios || !state.scenarios.length) {
        showBootstrapErr("Comparison data is invalid (no scenarios). Try Baseline setup → Continue again.");
        return;
      }
      maxCmp = state.maxCompare || 3;
      planY = state.planningThresholdYear || 2026;
      try {
        renderSidebar();
        refreshCompareUi();
      } catch (e) {
        console.error("[baseline-projection] compare UI render failed:", e);
        showBootstrapErr("Quick compare failed to render (see browser console).");
      }
      if (addBtn) addBtn.addEventListener("click", addScenario);
    })
    .catch(function (e) {
      clearTimeout(cmpAbortTid);
      console.error("[baseline-projection] comparison fetch failed:", e);
      stopLoadingUi();
      var msg = e && e.message ? e.message : String(e);
      if (e && e.name === "AbortError") {
        msg = "Comparison request was aborted after " + (cmpAbortMs / 60000) + " minutes (or you left the page). The projection step can exceed tunnel limits — try opening the app at 127.0.0.1:" + (location.port || "?") + " without a tunnel, or check server logs.";
      }
      showBootstrapErr(msg);
    });
})();
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    cfg = json.dumps({"pdfIntuitIam": _intuit_des_iam_configured()})
    return _html_response(PAGE_HTML.replace("__E2E_BASELINE_CLIENT_CONFIG__", cfg))


def _render_actual_return_error(message: str, sid: str = "") -> str:
    return (
        ACTUAL_RETURN_ERROR_HTML.replace("__E2E_ERR_MSG__", html.escape(message, quote=False)).replace(
            "__E2E_ERR_SID__", html.escape(sid or "—", quote=False)
        )
    )


@app.get("/actual-return")
def actual_return_page():
    sid = (request.args.get("session") or "").strip()
    print(
        f"[expert_e2e] GET /actual-return session={sid[:12] if sid else '—'}… in_memory={sid in _sessions if sid else False}",
        file=sys.stderr,
    )
    if not sid:
        return _html_response(
            _render_actual_return_error(
                "Missing session in URL. Go back to Baseline setup and click Continue.",
            )
        )
    if sid not in _sessions:
        return _html_response(
            _render_actual_return_error(
                "Session not found (server restarted or wrong app). Go back to Baseline setup and click Continue again.",
                sid,
            )
        )
    return _html_response(_render_actual_return(sid, _sessions[sid]))


@app.get("/baseline-projection")
def baseline_projection_page():
    sid = (request.args.get("session") or "").strip()
    print(
        f"[expert_e2e] GET /baseline-projection session={sid[:12] if sid else '—'}… in_memory={sid in _sessions if sid else False}",
        file=sys.stderr,
    )
    if not sid:
        return _html_response(
            _render_actual_return_error(
                "Missing session in URL. Go back to Baseline setup and complete the flow, or open Prior-year actual return first.",
            )
        )
    if sid not in _sessions:
        return _html_response(
            _render_actual_return_error(
                "Session not found (server restarted or wrong app). Go back to Baseline setup and click Continue again.",
                sid,
            )
        )
    sess = _sessions[sid]
    # Projection LLM runs on GET /api/session/<id>/comparison (browser fetch after this HTML).
    print(
        f"[expert_e2e] GET /baseline-projection session={sid[:12]}… — next step: "
        f"browser should GET /api/session/…/comparison (target projection year {PROJECTION_YEAR})",
        file=sys.stderr,
        flush=True,
    )
    return _html_response(_render_baseline_projection(sid, sess))


@app.get("/baseline-projection/scenario")
def baseline_scenario_detail_page():
    sid = (request.args.get("session") or "").strip()
    scen = (request.args.get("sid") or "").strip()
    print(
        f"[expert_e2e] GET /baseline-projection/scenario session={sid[:12] if sid else '—'}… sid={scen!r}",
        file=sys.stderr,
    )
    if not sid or not scen:
        return _html_response(
            _render_actual_return_error(
                "Missing session or scenario id. Open Quick compare from baseline projection and use a scenario link.",
                sid,
            )
        )
    if sid not in _sessions:
        return _html_response(
            _render_actual_return_error(
                "Session not found (server restarted or wrong app). Go back to Baseline setup and click Continue again.",
                sid,
            )
        )
    sess = _sessions[sid]
    _ensure_projection_computed(sess)
    return _html_response(_render_scenario_detail(sid, sess, scen))


@app.get("/api/session/<session_id>")
def api_session_get(session_id: str):
    print(f"[expert_e2e] GET /api/session/{session_id[:12]}…", file=sys.stderr)
    session = _sessions.get(session_id)
    if not session:
        print("[expert_e2e] session not in memory (server restart or wrong port?)", file=sys.stderr)
        return _json_response(
            {"ok": False, "error": "Session not found. The dev server may have restarted — use Baseline setup → Continue again, or refresh if data was just cached."},
            404,
        )
    return _json_response({"ok": True, **_session_payload(session)})


@app.get("/api/session/<session_id>/comparison")
def api_session_comparison(session_id: str):
    """
    Quick Compare payload for baseline projection (actual vs projection scenarios).
    Runs projection LLM if needed — can take minutes; intended for fetch/XHR, not inline HTML.
    """
    t0 = time.perf_counter()
    print(
        f"[expert_e2e] GET /api/session/…/comparison session={session_id[:12]}… "
        f"(this is where {PROJECTION_YEAR} projection tax runs if not cached)",
        file=sys.stderr,
        flush=True,
    )
    session = _sessions.get(session_id)
    if not session:
        print("[expert_e2e] comparison: session not in memory", file=sys.stderr, flush=True)
        return _json_response({"ok": False, "error": "Session not found."}, 404)
    try:
        _ensure_projection_computed(session)
        payload = _sanitize_cmp_bootstrap_payload(_comparison_payload_dict(session))
        elapsed = time.perf_counter() - t0
        proj = session.get("projection") if isinstance(session.get("projection"), dict) else {}
        py = proj.get("projection_year")
        err = proj.get("error")
        print(
            f"[expert_e2e] comparison JSON ready in {elapsed:.1f}s projection_year={py!r} error={err!r}",
            file=sys.stderr,
            flush=True,
        )
        return _json_response({"ok": True, **payload})
    except (TypeError, ValueError) as e:
        print(f"[expert_e2e] comparison JSON build failed: {e}", file=sys.stderr, flush=True)
        return _json_response({"ok": False, "error": f"Could not build comparison data: {e}"}, 500)
    except Exception as e:
        print(f"[expert_e2e] comparison endpoint failed: {e}", file=sys.stderr, flush=True)
        return _json_response({"ok": False, "error": str(e)}, 500)


@app.post("/api/session/<session_id>/recalc")
def api_session_recalc(session_id: str):
    session = _sessions.get(session_id)
    if not session:
        return jsonify(ok=False, error="Session not found."), 404
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("scenario_text") if data.get("scenario_text") is not None else session.get("scenario_text") or "").strip()
    if not text:
        return jsonify(ok=False, error="scenario_text is empty."), 400
    session["scenario_text"] = text
    session["actual_year"] = _detect_actual_year(text)
    session.pop("projection", None)
    try:
        result, data_model = _compute_tax(text)
        session["result"] = result
        session["data_model"] = data_model
        session["error"] = None
    except Exception as e:
        session["result"] = None
        session["data_model"] = None
        session["error"] = str(e)
    return _json_response({"ok": True, **_session_payload(session)})


@app.post("/api/upload-1040")
def api_upload_1040():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, error="No file uploaded."), 400
    if not secure_filename(f.filename).lower().endswith(".pdf"):
        return jsonify(ok=False, error="Only PDF files are accepted."), 400
    upload_id = str(uuid.uuid4())
    dest = _upload_dir / f"{upload_id}.pdf"
    try:
        f.save(dest)
    except OSError as e:
        return jsonify(ok=False, error=str(e)), 500

    out: dict[str, Any] = {
        "ok": True,
        "upload_id": upload_id,
        "stored_filename": f"{upload_id}.pdf",
    }

    if _intuit_des_iam_configured():
        try:
            from iam_pdf_extraction import (
                build_scenario_text_from_documents,
                build_tax_input_summary_from_documents,
                extract_1040_jsons_from_pdf_sync,
            )
        except Exception as e:
            out["extraction_error"] = f"iam_pdf_extraction import failed: {e}"
            return jsonify(out)

        vb = os.environ.get("EXPERT_E2E_IAM_VERBOSE", "").lower() in ("1", "true", "yes")
        ext = extract_1040_jsons_from_pdf_sync(dest, None, verbose=vb)
        if not ext.get("success"):
            out["extraction_error"] = (ext.get("error") or "Financial Document extraction failed.").strip()
            return jsonify(out)

        documents = ext.get("documents") or []
        doc_id = ext.get("document_id")
        primary, scen_err, _meta = build_scenario_text_from_documents(
            documents,
            scenario_style=_e2e_pdf_scenario_style(),
            verbose=vb,
        )
        scenario_text = (primary or "").strip()
        if scen_err or not scenario_text:
            flat = build_tax_input_summary_from_documents(documents)
            if flat and len(flat) > 120:
                scenario_text = flat.strip()
                scen_err = None
        try:
            _save_des_extraction(upload_id, doc_id, documents, scenario_text)
        except OSError as e:
            return jsonify(ok=False, error=f"Saved PDF but failed to write extraction JSON: {e}"), 500

        if scen_err or not scenario_text:
            out["extraction_error"] = scen_err or "Extraction returned no scenario text."
            return jsonify(out)

        out["scenario_text"] = scenario_text

    return jsonify(out)


@app.post("/api/baseline-continue")
def api_baseline_continue():
    data = request.get_json(force=True, silent=True) or {}
    source = (data.get("source") or "").strip()
    upload_id = (data.get("upload_id") or "").strip() or None
    scenario, err = _build_scenario_from_baseline(data, upload_id)
    if err:
        print(f"[expert_e2e] baseline-continue 400: {err}", file=sys.stderr)
        return jsonify(ok=False, error=err), 400
    assert scenario is not None
    sid = str(uuid.uuid4())
    year = _detect_actual_year(scenario)
    session = {
        "scenario_text": scenario,
        "source": source,
        "actual_year": year,
        "result": None,
        "data_model": None,
        "error": None,
    }
    try:
        result, data_model = _compute_tax(scenario)
        session["result"] = result
        session["data_model"] = data_model
    except Exception as e:
        session["error"] = str(e)
    _sessions[sid] = session
    payload = {"ok": True, "session_id": sid, **_session_payload(session)}
    return _json_response(payload)


def main() -> None:
    port = int(os.environ.get("PORT", "5002"))
    print(f"Expert Advisory E2E: http://127.0.0.1:{port}/", file=sys.stderr)
    app.run(
        host="127.0.0.1",
        port=port,
        debug=os.environ.get("FLASK_DEBUG") == "1",
        threaded=True,
    )


if __name__ == "__main__":
    main()
