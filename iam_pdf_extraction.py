"""
IAM / Financial Document Platform — upload a Form 1040 PDF and retrieve extracted JSON.

Ported from tax-advisory-toolkit `test_iam_extraction.py`, with:
- Auth: session cookies (FINANCIALDOC_SESSION_COOKIES / SESSION_COOKIES) and/or DES IAM
  (INTUIT_APP_ID_FOR_DES, INTUIT_APP_SECRET_FOR_DES, INTUIT_IAM_TICKET, INTUIT_AUTH_ID)
- Optional: SESSION_COOKIES or FINANCIALDOC_SESSION_COOKIES (browser session). **auto** mode omits DES IAM when cookies are set, but still sends **FINANCIALDOC_API_KEY** if set (matches toolkit: cookies + Intuit_APIKey together).
- Optional: FINANCIALDOC_API_KEY — use with SESSION_COOKIES for the same behavior as `test_iam_extraction.py`. **EXPERT_E2E_IAM_AUTH_MODE=cookies** forces cookie-only (no API key header).
- Public API: extract_1040_from_pdf_for_scenario() (scenario text for LLM / E2E), extract_1040_jsons_from_pdf_sync(),
  build_scenario_text_from_documents() (same scenario text from in-memory DES ``documents`` JSON),
  build_tax_input_summary_from_documents() / build_tax_input_summary_from_extraction_dir() for narrative summaries,
  build_tax_engine_statement_text_from_documents() for deduped, sentence-style facts grouped by form.

Extraction keeps full document JSON in memory (`documents`); optional `output_dir` writes Form1040.json + schedules.
User-facing summaries use ``1040yaml-to-PDF-REVISED(1040yaml-to-PDF-string-mapping).csv`` by default:
rows with ``prep_data_classification`` in **direct user inputs** or **indirect user inputs** (calculated values are omitted).
Those fields are collected from each document's ``semanticData`` **and** ``entityData`` buckets (Document AI often populates only ``entityData``).

HTTP debug dumps: set IAM_EXTRACTION_DUMP_HTTP=1 (optional IAM_EXTRACTION_DUMP_HTTP_DIR).

Polling: after upload, waits EXPERT_E2E_IAM_INITIAL_WAIT seconds (default 60) before GET polling, like the legacy script; slower poll interval defaults reduce HTTP 429s.
POST /v2/documents: on HTTP 429, retries with backoff (see EXPERT_E2E_IAM_POST_MAX_ATTEMPTS, EXPERT_E2E_IAM_POST_429_BACKOFF, Retry-After).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from email import message_from_bytes
from email.policy import default
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

_REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_YAML_MAPPING_CSV = _REPO_ROOT / "1040yaml-to-PDF-REVISED(1040yaml-to-PDF-string-mapping).csv"
# CSV prep_data_classification: include these in extracted narrative; exclude calculated rows
# (e.g. ``calculated values`` on REVISED CSV; ``calculated-in-scope`` / ``calculated-outside-scope`` on legacy CSV).
YAML_INPUT_CLASSIFICATIONS = frozenset(
    {
        "direct user inputs",
        "indirect user inputs",
        "user inputs",  # legacy ``1040yaml-to-PDF-string-mapping.csv`` if passed as ``mapping_csv``
    }
)
_FORM_ORDER = [
    "Form 1040",
    "Schedule 1",
    "Schedule 2",
    "Schedule 3",
    "Schedule A",
    "Schedule B",
    "Schedule C",
    "Schedule D",
    "Schedule E",
    "Schedule F",
]

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass
except Exception:
    pass


def document_type_to_simple_name(
    doc_type: str, existing_names: Optional[set] = None
) -> str:
    if not doc_type or doc_type == "unknown":
        base = "Unknown"
    else:
        part = doc_type.split("::")[-1] if "::" in doc_type else doc_type
        if part == "Form1040Composite":
            base = "Form1040"
        elif part == "Form1040":
            base = "Form1040"
        elif part.startswith("Form1040"):
            base = part[len("Form1040") :] or "Form1040"
        else:
            base = part
    if existing_names is not None:
        name = base
        counter = 1
        while name in existing_names:
            counter += 1
            name = f"{base}_{counter}"
        existing_names.add(name)
        return name
    return base


def document_label_to_csv_form(label: str) -> str:
    """Map extraction label (e.g. ScheduleC, Form1040) to CSV `form_name`."""
    if label.startswith("Form1040"):
        return "Form 1040"
    if label.startswith("Schedule"):
        rest = label[len("Schedule") :]
        if rest.isdigit():
            return f"Schedule {rest}"
        return f"Schedule {rest}"
    return "Form 1040"


def _entity_bucket_key_to_csv_form(bucket_key: str) -> Optional[str]:
    """
    Map ``entityData`` bucket keys (e.g. ``Form1040``, ``Form1040ScheduleC``) to CSV ``form_name``.
    Skips ``meta`` and other non-form payloads.
    """
    if not isinstance(bucket_key, str) or not bucket_key:
        return None
    if bucket_key == "meta":
        return None
    if bucket_key == "Form1040" or (bucket_key.startswith("Form1040") and "Schedule" not in bucket_key):
        return "Form 1040"
    m = re.match(r"^Form1040Schedule(\d+|[A-Z]+)$", bucket_key)
    if m:
        suf = m.group(1)
        return f"Schedule {suf}" if suf.isdigit() else f"Schedule {suf}"
    m2 = re.match(r"^Schedule(\d+|[A-Z]+)$", bucket_key)
    if m2:
        suf = m2.group(1)
        return f"Schedule {suf}" if suf.isdigit() else f"Schedule {suf}"
    return None


def _schema_key_to_form_name(key: str) -> Optional[str]:
    """If `key` is a semantic schema bucket (e.g. tax::Form1040ScheduleC), return CSV form name."""
    if not isinstance(key, str):
        return None
    part = key.split("::")[-1]
    if part.startswith("Form1040Composite") or part == "Form1040":
        return "Form 1040"
    m = re.search(r"Schedule(\d+|[A-Z]+)", part)
    if m:
        suf = m.group(1)
        return f"Schedule {suf}" if suf.isdigit() else f"Schedule {suf}"
    if part.startswith("Form1040") and "Schedule" in part:
        m2 = re.search(r"Schedule(\d+|[A-Z]+)", part)
        if m2:
            suf = m2.group(1)
            return f"Schedule {suf}" if suf.isdigit() else f"Schedule {suf}"
    return None


def load_user_inputs_mapping(
    csv_path: Optional[Path] = None,
) -> Dict[tuple[str, str], str]:
    """
    Load (form_name, yaml_name) -> description_on_form for CSV rows whose
    ``prep_data_classification`` is direct or indirect user input (never calculated values).
    """
    path = Path(csv_path) if csv_path else DEFAULT_YAML_MAPPING_CSV
    if not path.is_file():
        return {}
    out: Dict[tuple[str, str], str] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cls = (row.get("prep_data_classification") or "").strip().lower()
            if cls not in YAML_INPUT_CLASSIFICATIONS:
                continue
            form = (row.get("form_name") or "").strip()
            yml = (row.get("yaml_name") or "").strip()
            desc = (row.get("description_on_form") or "").strip()
            if not desc:
                desc = (row.get("line_on_form") or "").strip()
            if form and yml and desc:
                out[(form, yml)] = desc
    return out


def _is_meaningful_leaf(v: Any) -> bool:
    if v is None:
        return False
    if v == "":
        return False
    if isinstance(v, dict):
        return False
    if isinstance(v, list) and len(v) == 0:
        return False
    return True


def _collect_entity_payload_user_inputs(
    obj: Any,
    form_name: str,
    by_form_yaml: Dict[tuple[str, str], str],
    found: Dict[tuple[str, str], Any],
) -> None:
    """
    Walk ``entityData.<bucket>`` payloads (flat or nested dicts) and collect mapped user-input fields.
    Document AI / FDP often fills ``entityData`` while ``semanticData`` is absent.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = (form_name, k)
            if key in by_form_yaml:
                if k == "dependentDetail" and isinstance(v, list):
                    if _dependent_detail_non_empty_rows(v) and key not in found:
                        found[key] = _normalize_dependent_detail_value(v)
                    continue
                if _is_meaningful_leaf(v) and key not in found:
                    found[key] = v
                elif isinstance(v, dict):
                    _collect_entity_payload_user_inputs(v, form_name, by_form_yaml, found)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            _collect_entity_payload_user_inputs(item, form_name, by_form_yaml, found)
            elif isinstance(v, dict):
                _collect_entity_payload_user_inputs(v, form_name, by_form_yaml, found)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _collect_entity_payload_user_inputs(item, form_name, by_form_yaml, found)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                _collect_entity_payload_user_inputs(item, form_name, by_form_yaml, found)


def _collect_from_entity_data(
    data: dict[str, Any],
    by_form_yaml: Dict[tuple[str, str], str],
    found: Dict[tuple[str, str], Any],
) -> None:
    entity_data = data.get("entityData")
    if not isinstance(entity_data, dict):
        return
    for bucket_key, payload in entity_data.items():
        form = _entity_bucket_key_to_csv_form(bucket_key)
        if not form or not isinstance(payload, dict):
            continue
        _collect_entity_payload_user_inputs(payload, form, by_form_yaml, found)


def _dependent_detail_non_empty_rows(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            continue
        if any(_is_meaningful_leaf(x) for x in item.values()):
            return True
    return False


def _normalize_dependent_detail_value(value: Any) -> list:
    """Drop empty dependent rows for cleaner scenario text."""
    if not isinstance(value, list):
        return [value]
    out: list[Any] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if any(_is_meaningful_leaf(x) for x in item.values()):
            out.append({k: v for k, v in item.items() if _is_meaningful_leaf(v)})
    return out


def _collect_semantic_user_inputs(
    sem: Any,
    form_name: str,
    by_form_yaml: Dict[tuple[str, str], str],
    found: Dict[tuple[str, str], Any],
) -> None:
    if isinstance(sem, dict):
        for k, v in sem.items():
            bucket_form = _schema_key_to_form_name(k)
            if bucket_form and isinstance(v, dict):
                _collect_semantic_user_inputs(v, bucket_form, by_form_yaml, found)
                continue
            key = (form_name, k)
            if key in by_form_yaml:
                if k == "dependentDetail" and isinstance(v, list):
                    if _dependent_detail_non_empty_rows(v) and key not in found:
                        found[key] = _normalize_dependent_detail_value(v)
                elif _is_meaningful_leaf(v) and key not in found:
                    found[key] = v
                elif isinstance(v, dict):
                    _collect_semantic_user_inputs(v, form_name, by_form_yaml, found)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            _collect_semantic_user_inputs(item, form_name, by_form_yaml, found)
                        elif _is_meaningful_leaf(item) and key not in found:
                            found[key] = item
                continue
            if isinstance(v, dict):
                _collect_semantic_user_inputs(v, form_name, by_form_yaml, found)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _collect_semantic_user_inputs(item, form_name, by_form_yaml, found)
                    elif key in by_form_yaml and _is_meaningful_leaf(item):
                        if key not in found:
                            found[key] = item


# Form 1040 age/blind: only emit a line when the box is checked (yes); unchecked / false omits the line.
_FORM1040_AGE_BLIND_YES_PHRASE: dict[str, str] = {
    "primary65OrOlderInd": "Taxpayer is over 65.",
    "primaryBlindInd": "Taxpayer is blind.",
    "spouse65OrOlderInd": "Spouse is over 65.",
    "spouseBlindInd": "Spouse is blind.",
}


def _coerce_age_blind_truthy(value: Any) -> Optional[bool]:
    """Interpret Form 1040 checkbox / boolean payloads for age and blind fields."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(int(value))
    if isinstance(value, str):
        t = value.strip().lower()
        if t in ("x", "yes", "true", "1", "y"):
            return True
        if t in ("no", "false", "0", "n"):
            return False
    return None


def _form1040_age_blind_sentence(yaml_name: str, value: Any) -> Optional[str]:
    phrase = _FORM1040_AGE_BLIND_YES_PHRASE.get(yaml_name)
    if not phrase:
        return None
    yn = _coerce_age_blind_truthy(value)
    if yn is True:
        return phrase
    if yn is False:
        return ""
    return None


def collect_user_input_field_values(
    documents: Iterable[dict[str, Any]],
    by_form_yaml: Optional[Dict[tuple[str, str], str]] = None,
) -> Dict[tuple[str, str], Any]:
    """
    Gather (form_name, yaml_name) -> raw value from each document's ``semanticData`` and ``entityData``.

    Intuit responses often put extracted fields under ``entityData.Form1040`` (etc.) with no ``semanticData``;
    both paths are merged so CSV direct/indirect user-input rows match real payloads.
    """
    mapping = by_form_yaml if by_form_yaml is not None else load_user_inputs_mapping()
    found: Dict[tuple[str, str], Any] = {}
    for doc in documents:
        label = doc.get("label") or "Form1040"
        default_form = document_label_to_csv_form(str(label))
        data = doc.get("data") or {}
        sem = data.get("semanticData")
        if sem:
            _collect_semantic_user_inputs(sem, default_form, mapping, found)
        _collect_from_entity_data(data, mapping, found)
    return found


_MONEY_DESC_HINT = re.compile(
    r"\b(amt|amount|wages?|income|tax|credit|payment|expense|supplies|cost|rent|benefit|withheld|loss|gain|refund|liability|deduct|dividend|interest|ira|pension|basis)\b",
    re.I,
)


def _field_looks_like_currency(description: str, yaml_name: str) -> bool:
    y = yaml_name or ""
    if y in ("taxYear", "filingYear", "year"):
        return False
    if re.search(r"(Amt|Amount)$", y):
        return True
    return bool(_MONEY_DESC_HINT.search(description or ""))


_FILING_STATUS_LABELS = {
    "FSSingle": "Single",
    "FSMarriedFilingJointly": "Married filing jointly",
    "FSMarriedFilingJoint": "Married filing jointly",
    "FSMarriedFilingSeparate": "Married filing separately",
    "FSMarriedFilingSep": "Married filing separately",
    "FSHeadOfHousehold": "Head of household",
    "FSQualifyingSurvivingSpouse": "Qualifying surviving spouse",
    "FSQualifyingWidow": "Qualifying surviving spouse",
}

# yaml_name values — emit once when string value matches (repeated on every schedule)
_GLOBAL_DEDUPE_YAML_NAMES = frozenset(
    {
        "taxYear",
        "name",
        "ssn",
        "primaryFirstName",
        "primaryLastName",
        "spouseFirstName",
        "spouseLastName",
        "streetAddress",
        "city",
        "stateAbbreviation",
        "zipCode",
    }
)


def _statement_money(n: Any) -> str:
    if isinstance(n, bool):
        return "Yes" if n else "No"
    if isinstance(n, float) and n == int(n):
        n = int(n)
    if isinstance(n, int):
        return f"${n:,}"
    if isinstance(n, float):
        return f"${n:,.2f}".rstrip("0").rstrip(".")
    return str(n)


def _clean_field_label(description: str) -> str:
    """Shorten CSV labels for sentence stems; fix common typos."""
    d = (description or "").strip()
    if re.match(r"^Tax Tear\b", d, re.I):
        d = re.sub(r"^Tax Tear\b", "Tax year", d, flags=re.I)
    return d


_NAME_LIKE_YMLS = frozenset({"name", "nameOnReturn", "primaryAndSpouseName"})


def _global_dedupe_fingerprint(yml: str, description: str, raw: Any) -> Optional[tuple[str, str]]:
    """
    Cross-form dedupe: same (bucket, value) appears once (first wins in sorted order).

    Handles repeated tax year / name headers on every schedule even when yaml_name differs
    (e.g. ``name`` vs ``nameOnReturn`` vs ``primaryAndSpouseName``).
    """
    label = _clean_field_label(description or "").strip().lower()
    y = (yml or "").strip()

    if y == "taxYear" or label == "tax year":
        return ("tax_year", str(raw).strip())

    if y in _NAME_LIKE_YMLS and label == "name":
        return ("name_on_return", str(raw).strip().lower())

    if y not in _GLOBAL_DEDUPE_YAML_NAMES:
        return None

    if isinstance(raw, (str, int, float, bool)):
        fp = str(raw).strip().lower() if isinstance(raw, str) else str(raw)
    else:
        fp = json.dumps(raw, sort_keys=True, ensure_ascii=False)
    return (y, fp)


def _is_checkbox_style_yaml(yaml_name: str) -> bool:
    """Yes/No boxes: omit negative lines in narrative (checked-only)."""
    y = (yaml_name or "").strip()
    if y.endswith("Ind"):
        return True
    if y.startswith("excessivePayments") or y.startswith("twentyPercentEP"):
        return True
    # Schedule D worksheet flags (values are yes/no, not dollar amounts)
    if y in ("qualifiedDividends", "taxWorksheet"):
        return True
    return False


def _value_falsey_for_checkbox_omit(value: Any) -> bool:
    if value is False or value is None:
        return True
    if value == 0 or value == 0.0:
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("no", "false", "0", "n", "")
    return False


def _omit_checkbox_negative_line(yaml_name: str, value: Any) -> bool:
    return _is_checkbox_style_yaml(yaml_name) and _value_falsey_for_checkbox_omit(value)


def _checkbox_string_to_sentence(description: str, s: str, yaml_name: str = "") -> str:
    t = (s or "").strip()
    low = t.lower()
    if low in ("x", "yes", "true", "1"):
        stem = _clean_field_label(description)
        return f'The return indicates "yes" for: {stem}.'
    if low in ("no", "false", "0", ""):
        if _is_checkbox_style_yaml(yaml_name):
            return ""
        stem = _clean_field_label(description)
        return f'The return indicates "no" for: {stem}.'
    return f"{_clean_field_label(description)} is {t}."


def _list_of_dicts_to_statements(description: str, rows: list[Any]) -> list[str]:
    """Turn payer/amount tables and rental columnar JSON into full sentences."""
    stem = _clean_field_label(description)
    out: list[str] = []
    n = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not any(_is_meaningful_leaf(v) for v in row.values()):
            continue
        n += 1
        if "dividendPayer" in row or "dividendAmount" in row:
            payer = (row.get("dividendPayer") or "").strip() or "an unnamed payer"
            amt = row.get("dividendAmount")
            if _is_meaningful_leaf(amt):
                out.append(f"For {stem}, payer {n} ({payer}) reported dividends of {_statement_money(amt)}.")
            else:
                out.append(f"For {stem}, payer {n} is {payer}.")
            continue
        if "interestPayer" in row or "interestAmount" in row:
            payer = (row.get("interestPayer") or "").strip() or "an unnamed payer"
            amt = row.get("interestAmount")
            if _is_meaningful_leaf(amt):
                out.append(f"For {stem}, payer {n} ({payer}) reported interest of {_statement_money(amt)}.")
            else:
                out.append(f"For {stem}, payer {n} is {payer}.")
            continue
        if set(row.keys()) <= {"address"} or (
            len(row) == 1 and "address" in row
        ):
            addr = row.get("address")
            if _is_meaningful_leaf(addr):
                out.append(f"For {stem}, location {n} has address: {addr}.")
            continue
        # Generic Schedule E–style rows: emit one sentence per non-empty row
        parts: list[str] = []
        for k in sorted(row.keys(), key=lambda x: str(x).lower()):
            v = row.get(k)
            if not _is_meaningful_leaf(v):
                continue
            if isinstance(v, (int, float)):
                parts.append(f"{k} is {_statement_money(v)}")
            elif isinstance(v, str):
                parts.append(f"{k} is {v.strip()}")
            else:
                parts.append(f"{k} is {v}")
        if parts:
            out.append(f"For {stem}, row {n}: " + "; ".join(parts) + ".")
    return out


# Schedule E: entityData often uses parallel lists (one dict per property column). Emit one bullet per
# property with all line items together instead of separate "row 1 / row 2" bullets per field type.
_SCHEDULE_E_LIST_YAML_ORDER = [
    "propertyAddress",
    "propertyType",
    "line2Boxes",
    "rentsReceivedAmt",
    "advertisingAmt",
    "autoAndTravelAmt",
    "cleaningAndMaintenanceAmt",
    "commissionsAmt",
    "insuranceAmt",
    "legalAndOtherProfFeesAmt",
    "managementFeesAmt",
    "mortgageInterestPaidAmt",
    "otherInterestPaidAmt",
    "repairsAmt",
    "suppliesAmt",
    "taxesAmt",
    "utilitiesAmt",
    "deprecExpenseOrDepletionAmt",
    "otherExpenses",
]


def _schedule_e_parallel_list_yamls(se_found: dict[tuple[str, str], Any]) -> set[str]:
    out: set[str] = set()
    for (form, yml), v in se_found.items():
        if form != "Schedule E":
            continue
        if isinstance(v, list) and v and isinstance(v[0], dict):
            out.add(yml)
    return out


def _schedule_e_row_readable_fragment(description: str, yaml_name: str, row: dict[str, Any]) -> str:
    """One clause for a single property row (address, one amount line, or multi-key row)."""
    stem = _clean_field_label(description)
    if not isinstance(row, dict) or not any(_is_meaningful_leaf(x) for x in row.values()):
        return ""
    if set(row.keys()) <= {"address"} or (len(row) == 1 and "address" in row):
        addr = row.get("address")
        if _is_meaningful_leaf(addr):
            return f"address {addr}"
        return ""
    parts: list[str] = []
    for k, v in sorted(row.items(), key=lambda kv: str(kv[0]).lower()):
        if not _is_meaningful_leaf(v):
            continue
        if isinstance(v, (int, float)):
            if yaml_name == "line2Boxes" or "day" in k.lower():
                disp = int(v) if isinstance(v, float) and v == int(v) else v
                parts.append(f"{k} {disp}")
            else:
                parts.append(f"{k} {_statement_money(v)}")
        else:
            parts.append(f"{k} {str(v).strip()}")
    if not parts:
        return ""
    return f"{stem}: " + ", ".join(parts)


def _schedule_e_property_bullets(
    se_found: dict[tuple[str, str], Any],
    by_form_yaml: dict[tuple[str, str], str],
    parallel_ymls: set[str],
) -> tuple[list[str], set[tuple[str, str]]]:
    consumed: set[tuple[str, str]] = set()
    if not parallel_ymls:
        return [], consumed
    form = "Schedule E"
    n_prop = 0
    for y in parallel_ymls:
        v = se_found.get((form, y))
        if isinstance(v, list):
            n_prop = max(n_prop, len(v))
    if n_prop == 0:
        return [], consumed
    bullets: list[str] = []
    yml_contributed: set[str] = set()
    for i in range(n_prop):
        clauses: list[str] = []
        for yml in _SCHEDULE_E_LIST_YAML_ORDER:
            if yml not in parallel_ymls:
                continue
            rows = se_found.get((form, yml))
            if not isinstance(rows, list) or i >= len(rows):
                continue
            row = rows[i]
            if not isinstance(row, dict):
                continue
            desc = by_form_yaml.get((form, yml), yml)
            frag = _schedule_e_row_readable_fragment(desc, yml, row)
            if frag:
                clauses.append(frag)
                yml_contributed.add(yml)
        if clauses:
            bullets.append(f"Rental property {i + 1}: " + "; ".join(clauses) + ".")
    for y in yml_contributed:
        consumed.add((form, y))
    return bullets, consumed


def _scalar_to_sentence(
    description: str,
    yaml_name: str,
    value: Any,
) -> str:
    desc = _clean_field_label(description)
    age_blind = _form1040_age_blind_sentence(yaml_name, value)
    if age_blind is not None:
        return age_blind
    if isinstance(value, str) and len(value) <= 3 and value.strip().upper() == "X":
        return _checkbox_string_to_sentence(description, value, yaml_name)

    if isinstance(value, str):
        s = value.strip()
        if yaml_name == "filingStatus" or "filing status" in desc.lower():
            if s in _FILING_STATUS_LABELS:
                return f"Filing status is {_FILING_STATUS_LABELS[s]}."
            return f"Filing status code on the return is {s}."
        if _omit_checkbox_negative_line(yaml_name, s):
            return ""
        return f"{desc} is {s}."

    if isinstance(value, bool):
        if _omit_checkbox_negative_line(yaml_name, value):
            return ""
        yn = "yes" if value else "no"
        return f"{desc}: {yn}."

    if isinstance(value, (int, float)):
        disp = format_user_input_display_value(value, description=description, yaml_name=yaml_name)
        return f"{desc} is {disp}."

    if isinstance(value, (list, tuple)):
        if yaml_name == "dependentDetail" and value and isinstance(value[0], dict):
            dep = _format_dependent_detail_for_text(list(value))
            return f"Dependents: {dep}."
        if value and isinstance(value[0], dict):
            lines = _list_of_dicts_to_statements(description, list(value))
            return "\n".join(lines) if lines else f"{desc} has detailed entries (see raw data)."
        return f"{desc}: {json.dumps(value, ensure_ascii=False)}."

    return f"{desc}: {value}."


def build_tax_engine_statement_text_from_documents(
    documents: list[dict[str, Any]],
    *,
    mapping_csv: Optional[Path] = None,
    preamble: Optional[str] = None,
) -> str:
    """
    Narrative optimized for an LLM tax engine: deduped facts, one or more full sentences per field,
    list structures expanded (payers, rental properties). Statements are emitted in form order as flat
    bullets only (no ``##`` section headings).
    """
    by_form_yaml = load_user_inputs_mapping(mapping_csv)
    found = collect_user_input_field_values(documents, by_form_yaml)
    if not found:
        return ""

    form_rank = {f: i for i, f in enumerate(_FORM_ORDER)}

    def sort_key(item: tuple[tuple[str, str], Any]) -> tuple[int, str, str]:
        (form, yml), _ = item
        return (form_rank.get(form, 99), form, by_form_yaml.get((form, yml), yml))

    sorted_items = sorted(found.items(), key=sort_key)
    global_seen: set[tuple[str, str]] = set()
    sections: dict[str, list[str]] = {}

    se_found = {k: v for k, v in found.items() if k[0] == "Schedule E"}
    se_parallel = _schedule_e_parallel_list_yamls(se_found)
    se_property_lines, se_consumed = _schedule_e_property_bullets(se_found, by_form_yaml, se_parallel)
    if se_property_lines:
        sections["Schedule E"] = list(se_property_lines)

    for (form, yml), raw in sorted_items:
        if (form, yml) in se_consumed:
            continue
        desc = by_form_yaml.get((form, yml), f"{form} / {yml}")
        gkey = _global_dedupe_fingerprint(yml, desc, raw)
        if gkey is not None:
            if gkey in global_seen:
                continue
            global_seen.add(gkey)

        if form not in sections:
            sections[form] = []
        if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], dict):
            if yml == "dependentDetail":
                s = _scalar_to_sentence(desc, yml, raw)
                if s.strip():
                    sections[form].append(s)
            else:
                for line in _list_of_dicts_to_statements(desc, list(raw)):
                    if line.strip():
                        sections[form].append(line)
        else:
            s = _scalar_to_sentence(desc, yml, raw)
            if s.strip():
                sections[form].append(s)

    lines_out: list[str] = []
    if preamble is not None:
        lines_out.append(preamble.strip())
        lines_out.append("")

    ordered_forms = sorted(sections.keys(), key=lambda f: (form_rank.get(f, 99), f))
    first_form = True
    for form in ordered_forms:
        if not first_form:
            lines_out.append("")
        first_form = False
        for sent in sections[form]:
            for piece in sent.split("\n"):
                p = piece.strip()
                if p:
                    lines_out.append(f"- {p}")

    return "\n".join(lines_out).strip()


def _format_dependent_detail_for_text(rows: list) -> str:
    """Readable lines for dependent rows (entityData / semantic lists)."""
    lines: list[str] = []
    n = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        bits: list[str] = []
        order = (
            "dependentFirstNm",
            "dependentLastNm",
            "dependentRelationshipCd",
            "dependentSsn",
            "childTaxCreditInd",
            "creditForOtherDependentsInd",
        )
        seen = set()
        for key in order:
            if key not in row:
                continue
            val = row.get(key)
            if not _is_meaningful_leaf(val):
                continue
            bits.append(f"{key}={format_user_input_display_value(val, yaml_name=key)}")
            seen.add(key)
        for key in sorted(row.keys(), key=lambda x: str(x).lower()):
            if key in seen:
                continue
            val = row.get(key)
            if not _is_meaningful_leaf(val):
                continue
            bits.append(f"{key}={format_user_input_display_value(val, yaml_name=key)}")
        if bits:
            n += 1
            lines.append(f"Dependent {n}: " + "; ".join(bits))
    return " | ".join(lines) if lines else json.dumps(rows, ensure_ascii=False)


def format_user_input_display_value(
    value: Any,
    *,
    description: str = "",
    yaml_name: str = "",
) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float) and value == int(value):
        value = int(value)
    if isinstance(value, int):
        if _field_looks_like_currency(description, yaml_name):
            return f"${value:,}"
        return str(value)
    if isinstance(value, float):
        if _field_looks_like_currency(description, yaml_name):
            return f"${value:,.2f}".rstrip("0").rstrip(".")
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        if yaml_name == "filingStatus" or (description and "filing status" in description.lower()):
            if s in _FILING_STATUS_LABELS:
                return f"{_FILING_STATUS_LABELS[s]} ({s})"
        return s
    if isinstance(value, (list, tuple)):
        if yaml_name == "dependentDetail" and value and isinstance(value[0], dict):
            return _format_dependent_detail_for_text(list(value))
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_user_inputs_text_from_documents(
    documents: list[dict[str, Any]],
    *,
    mapping_csv: Optional[Path] = None,
    header: Optional[str] = None,
) -> str:
    """
    Build lines like: `Materials and Supplies: $12,000` for every mapped user-input field present in extraction JSON.
    """
    by_form_yaml = load_user_inputs_mapping(mapping_csv)
    found = collect_user_input_field_values(documents, by_form_yaml)
    if not found:
        return ""

    form_rank = {f: i for i, f in enumerate(_FORM_ORDER)}

    def sort_key(item: tuple[tuple[str, str], Any]) -> tuple[int, str, str]:
        (form, yml), _ = item
        return (form_rank.get(form, 99), form, by_form_yaml.get((form, yml), yml))

    lines_out: list[str] = []
    if header is not None:
        lines_out.append(header)
        lines_out.append("")
    global_seen_lines: set[tuple[str, str]] = set()
    for (form, yml), raw in sorted(found.items(), key=sort_key):
        desc = by_form_yaml.get((form, yml), f"{form} / {yml}")
        gkey = _global_dedupe_fingerprint(yml, desc, raw)
        if gkey is not None:
            if gkey in global_seen_lines:
                continue
            global_seen_lines.add(gkey)
        if yml in _FORM1040_AGE_BLIND_YES_PHRASE and _coerce_age_blind_truthy(raw) is not True:
            continue
        if _omit_checkbox_negative_line(yml, raw):
            continue
        lines_out.append(
            f"{desc}: {format_user_input_display_value(raw, description=desc, yaml_name=yml)}"
        )
    return "\n".join(lines_out).strip()


def cookies_header_to_dict(cookie_header_value: str) -> dict[str, str]:
    """Parse a raw ``Cookie`` header string (``name=value; …``) for ``httpx`` ``cookies=``."""
    out: dict[str, str] = {}
    for part in (cookie_header_value or "").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        out[key.strip()] = value.strip()
    return out


class IAMDocumentsAPIClient:
    """Financial Document API client (IAM, cookies, or API key)."""

    def __init__(
        self,
        base_url: str,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
        cookies: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
        intuit_offering_id: str = "Intuit.incometax.prep.directtaxui",
        verbose: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.user_id = user_id
        self.cookies = cookies
        self.api_key = api_key
        self.timeout = timeout
        self.intuit_offering_id = intuit_offering_id
        self.verbose = verbose
        self.debug_http_dump_dir: Optional[Path] = None

        self.cookies_dict = None
        if cookies:
            d = cookies_header_to_dict(cookies)
            self.cookies_dict = d if d else None

    def uses_cookie_auth_only(self) -> bool:
        """True when requests use session cookies and no IAM / API-key Authorization header."""
        return bool(self.cookies_dict) and self._get_iam_auth_header() is None

    def _vlog(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def _dump_http_response_body(self, filename_stem: str, response: httpx.Response) -> Optional[Path]:
        base = self.debug_http_dump_dir
        if not base:
            return None
        base = Path(base)
        base.mkdir(parents=True, exist_ok=True)

        if not response.content:
            loc = response.headers.get("location") or ""
            meta: Dict[str, Any] = {
                "note": (
                    "Empty response body (typical for POST /v2/documents 201). "
                    "Use the Location header and GET /v2/documents/{id} for the document JSON."
                ),
                "status_code": response.status_code,
                "headers": dict(response.headers),
            }
            if "/documents/" in loc:
                meta["location"] = loc
                meta["document_id"] = loc.rstrip("/").split("/")[-1]
            out = base / f"{filename_stem}_metadata.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            return out

        try:
            data = response.json()
            out = base / f"{filename_stem}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return out
        except Exception:
            text = response.text
            if text:
                out = base / f"{filename_stem}_raw.txt"
                out.write_text(text, encoding="utf-8")
                return out
            out_bin = base / f"{filename_stem}_raw.bin"
            out_bin.write_bytes(response.content)
            return out_bin

    def _get_iam_auth_header(self) -> Optional[str]:
        if all([self.app_id, self.app_secret, self.token, self.user_id]):
            return (
                f"Intuit_IAM_Authentication "
                f"intuit_appid={self.app_id}, "
                f"intuit_app_secret={self.app_secret}, "
                f"intuit_token={self.token}, "
                f"intuit_userid={self.user_id}, "
                f"intuit_token_type=IAM-Ticket"
            )
        if self.api_key:
            return f"Intuit_APIKey intuit_apikey={self.api_key}"
        return None

    async def create_document(
        self,
        pdf_file_path: str,
        document_json_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v2/documents"
        headers = {
            "Accept": "application/json;version=3.0.0",
            "channel": "localFile",
            "intuit_offeringid": self.intuit_offering_id,
            "intuit_tid": f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-e2e",
        }
        auth_header = self._get_iam_auth_header()
        if auth_header:
            headers["Authorization"] = auth_header

        pdf_path = Path(pdf_file_path)
        if not pdf_path.exists():
            return {
                "success": False,
                "error": f"PDF file not found: {pdf_file_path}",
                "status_code": None,
            }

        pdf_content = pdf_path.read_bytes()
        self._vlog(f"[IAM] POST /v2/documents — {pdf_path.name} ({len(pdf_content):,} bytes)")

        max_attempts = _post_429_max_attempts()
        base_backoff = _post_429_base_backoff_seconds()
        last_failure: Optional[Dict[str, Any]] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                for attempt in range(max_attempts):
                    req_headers = {
                        **headers,
                        "intuit_tid": f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-e2e-{attempt}",
                    }
                    files = {
                        "document": ("blob", json.dumps(document_json_data), "application/json"),
                        "file": (pdf_path.name, pdf_content, "application/pdf"),
                    }
                    response = await client.post(
                        url,
                        files=files,
                        headers=req_headers,
                        cookies=self.cookies_dict,
                    )
                    self._dump_http_response_body(f"post_v2_documents_response_{attempt}", response)
                    self._vlog(f"[IAM] POST /v2/documents → {response.status_code} (attempt {attempt + 1}/{max_attempts})")

                    if response.status_code == 429:
                        ra_raw = response.headers.get("Retry-After")
                        wait_s = base_backoff + min(attempt * 30.0, 180.0)
                        if ra_raw:
                            try:
                                wait_s = max(wait_s, float(ra_raw))
                            except ValueError:
                                pass
                        self._vlog(
                            f"[IAM] POST rate limited (429); sleeping {wait_s:.0f}s "
                            f"(Retry-After={ra_raw!r})…",
                        )
                        await asyncio.sleep(wait_s)
                        last_failure = {
                            "success": False,
                            "error": f"HTTP 429: {response.text or 'Too Many Requests'}",
                            "status_code": 429,
                            "response_headers": dict(response.headers),
                        }
                        continue

                    if response.is_error:
                        error_detail = response.text if response.text else "No error details"
                        document_id = None
                        location = response.headers.get("location", "")
                        if location and "/documents/" in location:
                            document_id = location.split("/documents/")[-1]
                        return {
                            "success": False,
                            "error": f"HTTP {response.status_code}: {error_detail}",
                            "status_code": response.status_code,
                            "document_id": document_id,
                            "response_text": error_detail,
                            "response_headers": dict(response.headers),
                        }

                    response_data = None
                    semantic_data = None
                    content_type = response.headers.get("content-type", "")

                    if "multipart/form-data" in content_type:
                        try:
                            msg_content = f"Content-Type: {content_type}\r\n\r\n".encode() + response.content
                            msg = message_from_bytes(msg_content, policy=default)
                            for part in msg.iter_parts():
                                content_disposition = part.get("Content-Disposition", "")
                                if 'name="semanticData"' in content_disposition:
                                    semantic_data_text = part.get_content()
                                    try:
                                        semantic_data = json.loads(semantic_data_text)
                                    except json.JSONDecodeError:
                                        semantic_data = semantic_data_text
                            response_data = {"semanticData": semantic_data}
                        except Exception as e:
                            self._vlog(f"[IAM] Multipart parse warning: {e}")
                            response_data = {"raw": response.text[:1000]}
                    elif response.content:
                        try:
                            response_data = response.json()
                        except json.JSONDecodeError:
                            response_data = {"raw": response.text}

                    document_id = None
                    location = response.headers.get("location", "")
                    if location and "/documents/" in location:
                        document_id = location.split("/documents/")[-1]

                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": response_data,
                        "semantic_data": semantic_data,
                        "document_id": document_id,
                        "headers": dict(response.headers),
                        "elapsed_ms": response.elapsed.total_seconds() * 1000,
                    }

                if last_failure:
                    last_failure["error"] = (
                        f"{last_failure.get('error', 'HTTP 429')} "
                        f"(gave up after {max_attempts} POST attempts; wait and retry later)"
                    )
                    return last_failure
                return {
                    "success": False,
                    "error": "POST /v2/documents failed after retries.",
                    "status_code": 429,
                }

            except httpx.RequestError as e:
                detail = f"{type(e).__name__}: {e!s}" if str(e) else repr(e)
                return {
                    "success": False,
                    "error": f"Request error: {detail}",
                    "status_code": None,
                }

    async def get_document(
        self,
        document_id: str,
        output_basename: Optional[str] = None,
        save_response: bool = True,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        base_dir = Path(output_dir) if output_dir else Path.cwd()
        url = f"{self.base_url}/v2/documents/{document_id}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/xml",
        }
        auth_header = self._get_iam_auth_header()
        if auth_header:
            headers["Authorization"] = auth_header

        self._vlog(f"[IAM] GET /v2/documents/{document_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers, cookies=self.cookies_dict)
                self._dump_http_response_body(f"get_response_{document_id}", response)

                response_json: Any = None
                if response.content:
                    try:
                        response_json = response.json()
                    except Exception as e:
                        self._vlog(
                            f"[IAM] GET JSON parse error: {e} "
                            f"(status={response.status_code}, len={len(response.content)})"
                        )
                        if save_response:
                            response_file = base_dir / (
                                f"{output_basename}.txt" if output_basename else f"get_response_{document_id}.txt"
                            )
                            response_file.write_text(response.text, encoding="utf-8")
                        if response.is_success:
                            return {
                                "success": False,
                                "error": (
                                    f"Non-JSON GET body (HTTP {response.status_code}); "
                                    "often rate limiting or gateway — will retry with backoff."
                                ),
                                "status_code": response.status_code,
                                "transient": True,
                                "elapsed_ms": response.elapsed.total_seconds() * 1000,
                            }
                        response.raise_for_status()
                        return {
                            "success": True,
                            "status_code": response.status_code,
                            "data": None,
                            "elapsed_ms": response.elapsed.total_seconds() * 1000,
                        }

                if save_response and response_json is not None:
                    response_file = base_dir / (
                        f"{output_basename}.json" if output_basename else f"get_response_{document_id}.json"
                    )
                    with open(response_file, "w", encoding="utf-8") as f:
                        json.dump(response_json, f, indent=2, ensure_ascii=False)
                    self._vlog(f"[IAM] Saved {response_file.name}")

                if response_json and self.verbose:
                    sys_attrs = response_json.get("systemAttributes", {}) or {}
                    self._vlog(
                        f"[IAM] dataExtractionStatus={sys_attrs.get('dataExtractionStatus', 'N/A')!r}"
                    )

                response.raise_for_status()

                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response_json,
                    "elapsed_ms": response.elapsed.total_seconds() * 1000,
                }

            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                return {
                    "success": False,
                    "error": f"HTTP {code}: {e.response.text}",
                    "status_code": code,
                    "transient": code == 429,
                }
            except httpx.RequestError as e:
                detail = f"{type(e).__name__}: {e!s}" if str(e) else repr(e)
                return {
                    "success": False,
                    "error": f"Request error: {detail}",
                    "status_code": None,
                }

    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        get_url = f"{self.base_url}/v2/documents/{document_id}"
        get_headers = {"Accept": "application/json"}
        auth_header = self._get_iam_auth_header()
        if auth_header:
            get_headers["Authorization"] = auth_header

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                get_response = await client.get(get_url, headers=get_headers, cookies=self.cookies_dict)
                last_modified = get_response.headers.get("Last-Modified")
                if not last_modified:
                    from email.utils import formatdate

                    last_modified = formatdate(timeval=None, localtime=False, usegmt=True)

                delete_url = f"{self.base_url}/v2/documents/{document_id}"
                delete_headers = {
                    "Accept": "application/json",
                    "If-Unmodified-Since": last_modified,
                }
                if auth_header:
                    delete_headers["Authorization"] = auth_header

                self._vlog(f"[IAM] DELETE /v2/documents/{document_id}")
                response = await client.delete(delete_url, headers=delete_headers, cookies=self.cookies_dict)
                response.raise_for_status()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "message": f"Document {document_id} deleted successfully",
                }

            except httpx.HTTPStatusError as e:
                return {
                    "success": False,
                    "error": f"HTTP {e.response.status_code}: {e.response.text}",
                    "status_code": e.response.status_code,
                }
            except httpx.RequestError as e:
                detail = f"{type(e).__name__}: {e!s}" if str(e) else repr(e)
                return {
                    "success": False,
                    "error": f"Request error: {detail}",
                    "status_code": None,
                }


def _normalize_cookie_header_value(raw: str) -> str:
    """Strip wrapping quotes, optional ``Cookie:`` prefix, and junk newlines from pasted header values."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        s = s[1:-1].strip()
    if s.lower().startswith("cookie:"):
        s = s[7:].strip()
    s = " ".join(line.strip() for line in s.splitlines() if line.strip())
    return s.strip()


def financialdoc_session_cookie_header() -> str:
    """
    Non-empty ``Cookie`` header value: optional file, then FINANCIALDOC_SESSION_COOKIES, then SESSION_COOKIES.
    """
    for fp_key in ("FINANCIALDOC_SESSION_COOKIES_FILE", "SESSION_COOKIES_FILE"):
        fp = (os.getenv(fp_key) or "").strip()
        if not fp:
            continue
        try:
            raw = Path(fp).expanduser().read_text(encoding="utf-8")
            norm = _normalize_cookie_header_value(raw)
            if norm:
                return norm
        except OSError:
            continue
    for key in ("FINANCIALDOC_SESSION_COOKIES", "SESSION_COOKIES"):
        raw = os.getenv(key)
        if raw and str(raw).strip():
            return _normalize_cookie_header_value(str(raw))
    return ""


def _stderr_financialdoc_cookie_401_hints() -> None:
    base = os.getenv("FINANCIALDOC_BASE_URL", "https://financialdocument-e2e.platform.intuit.com")
    print(
        "\nCookie auth returned 401 (AuthenticationFailed). Typical fixes:\n"
        "  • Paste a fresh Cookie header from browser DevTools → Network → pick a request whose URL "
        f"is on the same host as your API ({base.rstrip('/')}) or from the Intuit session that owns this API.\n"
        "  • Env value must be only name=value; name2=value2 — no leading 'Cookie:' prefix, no JSON.\n"
        "  • Session cookies expire; log in again and re-copy.\n"
        "  • Toolkit parity: set FINANCIALDOC_API_KEY alongside SESSION_COOKIES (auto mode sends both).\n"
        "  • Cookie-only: EXPERT_E2E_IAM_AUTH_MODE=cookies (omits API key even if FINANCIALDOC_API_KEY is set).\n"
        "  • If your org requires both, set EXPERT_E2E_IAM_AUTH_MODE=both and restore DES IAM vars "
        "(INTUIT_APP_SECRET_FOR_DES + INTUIT_IAM_TICKET + INTUIT_AUTH_ID).\n"
        "  • Long values: FINANCIALDOC_SESSION_COOKIES_FILE=/path/to/cookies.txt (single line).\n",
        file=sys.stderr,
    )


def financialdoc_extraction_configured() -> bool:
    """True if Financial Document extraction can run (session cookies and/or DES IAM triple and/or API key)."""
    if financialdoc_session_cookie_header():
        return True
    if (os.getenv("FINANCIALDOC_API_KEY") or "").strip():
        return True
    return bool(
        (os.getenv("INTUIT_APP_SECRET_FOR_DES") or "").strip()
        and (os.getenv("INTUIT_IAM_TICKET") or "").strip()
        and (os.getenv("INTUIT_AUTH_ID") or "").strip()
    )


def _iam_env_client(verbose: bool) -> tuple[IAMDocumentsAPIClient | None, str | None]:
    base_url = os.getenv(
        "FINANCIALDOC_BASE_URL",
        "https://financialdocument-e2e.platform.intuit.com",
    )
    app_id = os.getenv("INTUIT_APP_ID_FOR_DES", "Intuit.fdp.extraction.desnextgen")
    app_secret = os.getenv("INTUIT_APP_SECRET_FOR_DES")
    token = os.getenv("INTUIT_IAM_TICKET")
    user_id = os.getenv("INTUIT_AUTH_ID")
    cookie_header = financialdoc_session_cookie_header()
    api_key = os.getenv("FINANCIALDOC_API_KEY")
    offering = os.getenv("INTUIT_OFFERING_ID", "Intuit.incometax.prep.directtaxui")
    auth_mode = (os.getenv("EXPERT_E2E_IAM_AUTH_MODE") or "auto").strip().lower()

    use_iam_creds = all(
        [
            (app_secret or "").strip(),
            (token or "").strip(),
            (user_id or "").strip(),
        ]
    )
    use_ck = bool(cookie_header)
    use_api = bool((api_key or "").strip())

    if auth_mode in ("both", "iam+cookies", "iam+session"):
        use_iam = use_iam_creds
        use_cookies = use_ck
    elif auth_mode in ("cookies", "cookie", "session"):
        use_iam = False
        use_cookies = use_ck
    elif auth_mode == "iam":
        use_iam = use_iam_creds
        use_cookies = False
    else:
        # auto: prefer cookies alone when present (matches working browser session; avoids broken IAM + cookies)
        if use_ck:
            use_iam = False
            use_cookies = True
        else:
            use_iam = use_iam_creds
            use_cookies = False

    # Match tax-advisory-toolkit test_iam_extraction.py: cookies + FINANCIALDOC_API_KEY are sent together
    # when both are set (API often requires the Intuit_APIKey header even with a browser session).
    send_api_key = bool(use_api and not use_iam)
    if auth_mode in ("cookies", "cookie", "session"):
        send_api_key = False

    if not (use_iam or use_cookies or send_api_key):
        return None, (
            "Intuit document extraction credentials missing. Set FINANCIALDOC_SESSION_COOKIES or SESSION_COOKIES, "
            "or INTUIT_APP_SECRET_FOR_DES + INTUIT_IAM_TICKET + INTUIT_AUTH_ID, "
            "or FINANCIALDOC_API_KEY. "
            "With both cookies and IAM in .env, default is cookies-only (EXPERT_E2E_IAM_AUTH_MODE=auto); "
            "set EXPERT_E2E_IAM_AUTH_MODE=both to send both."
        )

    if verbose:
        if use_cookies and use_iam:
            print(
                "[IAM] Auth: Intuit_IAM_Authentication + session cookies (EXPERT_E2E_IAM_AUTH_MODE=both).",
                flush=True,
            )
        elif use_cookies and send_api_key:
            print(
                "[IAM] Auth: SESSION_COOKIES + FINANCIALDOC_API_KEY (Intuit_APIKey), same as toolkit test_iam_extraction.py.",
                flush=True,
            )
        elif use_cookies:
            print("[IAM] Auth: session cookies only (no IAM / API-key Authorization header).", flush=True)
        elif use_iam:
            print("[IAM] Auth: Intuit_IAM_Authentication (DES app + ticket).", flush=True)
        else:
            print("[IAM] Auth: FINANCIALDOC_API_KEY.", flush=True)

    dump_dir: Optional[Path] = None
    if os.getenv("IAM_EXTRACTION_DUMP_HTTP", "").lower() in ("1", "true", "yes"):
        raw = os.getenv("IAM_EXTRACTION_DUMP_HTTP_DIR", "").strip()
        dump_dir = Path(raw) if raw else Path(tempfile.gettempdir()) / f"iam_http_{datetime.now():%Y%m%d_%H%M%S}"

    client = IAMDocumentsAPIClient(
        base_url=base_url,
        app_id=app_id if use_iam else None,
        app_secret=app_secret if use_iam else None,
        token=token if use_iam else None,
        user_id=user_id if use_iam else None,
        cookies=cookie_header if use_cookies else None,
        api_key=api_key if send_api_key else None,
        intuit_offering_id=offering,
        verbose=verbose,
    )
    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)
        client.debug_http_dump_dir = dump_dir
    return client, None


def _extraction_poll_seconds() -> float:
    try:
        return float(os.getenv("EXPERT_E2E_IAM_POLL_INTERVAL", "15"))
    except ValueError:
        return 15.0


def _extraction_max_wait_seconds() -> float:
    try:
        return float(os.getenv("EXPERT_E2E_IAM_MAX_WAIT", "600"))
    except ValueError:
        return 600.0


def _extraction_initial_wait_seconds() -> float:
    """After POST /v2/documents, wait before polling GET (legacy script used 60s; reduces 429s)."""
    try:
        return float(os.getenv("EXPERT_E2E_IAM_INITIAL_WAIT", "60"))
    except ValueError:
        return 60.0


def _post_429_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("EXPERT_E2E_IAM_POST_MAX_ATTEMPTS", "8")))
    except ValueError:
        return 8


def _post_429_base_backoff_seconds() -> float:
    try:
        return max(15.0, float(os.getenv("EXPERT_E2E_IAM_POST_429_BACKOFF", "60")))
    except ValueError:
        return 60.0


def _infer_tax_year_from_pdf_filename(pdf_path: Path) -> Optional[int]:
    """Parse TY24, TY2024, or 4-digit year from PDF file name when env tax year is not set."""
    stem = pdf_path.stem
    # Avoid trailing \b: TY24_anonymized — underscore is a word char, so \b would not follow "24".
    m = re.search(r"(?i)(?<![A-Za-z0-9])ty[\s._-]*(\d{2,4})(?![0-9])", stem)
    if m:
        y = int(m.group(1))
        if y < 100:
            y = 2000 + y if y < 70 else 1900 + y
        if 2000 <= y <= 2035:
            return y
    m = re.search(r"(?<![0-9])(20\d{2})(?![0-9])", stem)
    if m:
        y = int(m.group(1))
        if 2000 <= y <= 2035:
            return y
    return None


def _tax_year_for_upload(pdf_path: Optional[Path] = None) -> int:
    raw = os.getenv("EXPERT_E2E_IAM_TAX_YEAR", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    raw2 = (os.getenv("DEFAULT_TAX_YEAR") or "").strip()
    if raw2:
        try:
            return int(raw2)
        except ValueError:
            pass
    if pdf_path is not None:
        inferred = _infer_tax_year_from_pdf_filename(pdf_path)
        if inferred is not None:
            return inferred
    return 2024


def financialdoc_upload_tax_year(pdf_path: Optional[Path] = None) -> int:
    """Tax year for Financial Document POST ``commonAttributes`` (shared with ``test_iam_extraction.py``)."""
    return _tax_year_for_upload(pdf_path)


def _upload_common_is7216() -> bool:
    """Default True; set EXPERT_E2E_IAM_IS7216=0 to try uploads with is7216=false (environment-dependent)."""
    return (os.getenv("EXPERT_E2E_IAM_IS7216") or "1").strip().lower() not in ("0", "false", "no")


def _extraction_failure_detail_suffix(sys_attrs: Any) -> str:
    if not isinstance(sys_attrs, dict):
        return ""
    bits: list[str] = []
    for key in ("extractionErrorCode", "classificationDetails", "extractor", "documentType"):
        val = sys_attrs.get(key)
        if val is None or val == "":
            continue
        if isinstance(val, (dict, list)):
            try:
                s = json.dumps(val, ensure_ascii=False)[:400]
            except (TypeError, ValueError):
                s = str(val)[:400]
        else:
            s = str(val)[:400]
        bits.append(f"{key}={s}")
    if not bits:
        return ""
    return " | " + " | ".join(bits)


def _classifier_failure_stderr_hint() -> str:
    return (
        "\nHint: Intuit could not classify this PDF (common for heavy redaction, non-IRS layouts, or bundled forms). "
        "Try: (1) a scan closer to official IRS Form 1040 layout, (2) EXPERT_E2E_IAM_TAX_YEAR matching the return year, "
        "(3) FINANCIALDOC_SESSION_COOKIES if IAM ticket auth fails, "
        "(4) expert_advisory_e2e PDF flow — it falls back to the local pdf_to_tax_situation pipeline when extraction fails.\n"
    )


def _delete_after_extract() -> bool:
    return os.getenv("EXPERT_E2E_IAM_DELETE_AFTER", "1").lower() not in ("0", "false", "no")


async def _delete_document_relaxed(
    client: IAMDocumentsAPIClient,
    doc_id: str,
    *,
    verbose: bool,
) -> None:
    """Best-effort delete; backs off on HTTP 429 so cleanup does not fail the run."""
    for attempt in range(2):
        r = await client.delete_document(doc_id)
        if r.get("success"):
            return
        if r.get("status_code") == 429 and attempt == 0:
            if verbose:
                print("[IAM] DELETE hit 429; waiting 60s before one retry…", flush=True)
            await asyncio.sleep(60)
            continue
        if verbose:
            print(f"[IAM] DELETE {doc_id} failed (non-fatal): {r.get('error')}", flush=True)
        return


def _clear_prior_extraction_artifacts(output_dir: Path, *, verbose: bool = False) -> None:
    """Remove stale JSON artifacts from a prior run in output_dir before writing new files."""
    exact = (
        "Form1040.json",
        "Form1040_2.json",
        "other.json",
        "other_2.json",
    )
    for name in exact:
        p = output_dir / name
        if p.is_file():
            try:
                p.unlink()
                if verbose:
                    print(f"[IAM] Removed prior artifact: {p.name}", flush=True)
            except OSError:
                pass
    for p in sorted(output_dir.glob("Schedule*.json")):
        if p.is_file():
            try:
                p.unlink()
                if verbose:
                    print(f"[IAM] Removed prior artifact: {p.name}", flush=True)
            except OSError:
                pass


def _get_transient_backoff_seconds(last: Dict[str, Any]) -> float:
    if last.get("status_code") == 429:
        try:
            return max(60.0, float(os.getenv("EXPERT_E2E_IAM_429_BACKOFF", "60")))
        except ValueError:
            return 60.0
    return max(_extraction_poll_seconds(), 15.0)


async def _wait_until_parent_ready(
    client: IAMDocumentsAPIClient,
    document_id: str,
) -> Dict[str, Any]:
    interval = _extraction_poll_seconds()
    deadline = time.monotonic() + _extraction_max_wait_seconds()
    last: Dict[str, Any] = {"success": False, "error": "timeout", "data": None}

    while time.monotonic() < deadline:
        last = await client.get_document(
            document_id,
            save_response=False,
        )
        if not last.get("success"):
            if last.get("transient") or last.get("status_code") == 429:
                backoff = _get_transient_backoff_seconds(last)
                if client.verbose:
                    err_snip = (last.get("error") or "")[:160]
                    ell = "…" if len(last.get("error") or "") > 160 else ""
                    print(
                        f"[IAM] GET transient error ({err_snip}{ell}); sleeping {backoff:.0f}s before retry.",
                        flush=True,
                    )
                await asyncio.sleep(backoff)
                continue
            return last
        data = last.get("data")
        if data is None:
            if client.verbose:
                print(
                    "[IAM] GET returned no JSON document yet; backing off (extraction still running)…",
                    flush=True,
                )
            await asyncio.sleep(max(interval, 15.0))
            continue
        sys_attrs = data.get("systemAttributes") or {}
        status = sys_attrs.get("dataExtractionStatus")
        if status == "ASYNC_COMPLETED":
            for attempt in range(5):
                final = await client.get_document(
                    document_id,
                    save_response=False,
                )
                if final.get("success") and final.get("data") is not None:
                    return final
                if (
                    final.get("transient")
                    or final.get("status_code") == 429
                    or (final.get("success") and final.get("data") is None)
                ) and attempt < 4:
                    await asyncio.sleep(max(15.0, _extraction_poll_seconds()))
                    continue
                return final
        if status in ("ASYNC_FAILED", "FAILED", "ERROR"):
            err = sys_attrs.get("extractionErrorMessage") or sys_attrs.get("extractionErrorCode") or status
            detail = _extraction_failure_detail_suffix(sys_attrs)
            return {"success": False, "error": f"Extraction failed: {err}{detail}", "data": data}
        await asyncio.sleep(interval)

    return {
        "success": False,
        "error": f"Timed out after {_extraction_max_wait_seconds():.0f}s waiting for extraction (last status may be incomplete).",
        "data": last.get("data"),
    }


async def extract_1040_jsons_from_pdf(
    pdf_path: Path,
    output_dir: Optional[Path] = None,
    *,
    verbose: bool = False,
    delete_on_server: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Upload PDF, poll until composite extraction completes.

    Document JSON is returned in memory under `documents` (no disk I/O unless `output_dir` is set).

    Returns keys: success, error?, document_id?, documents (list of {label, data}), and optionally
    output_dir + saved_files when persisting.
    """
    persist = output_dir is not None
    if persist:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        _clear_prior_extraction_artifacts(output_dir, verbose=verbose)

    client, err = _iam_env_client(verbose)
    if err or client is None:
        return {
            "success": False,
            "error": err or "client init failed",
            "documents": [],
            **({"output_dir": str(output_dir), "saved_files": []} if persist else {}),
        }

    do_delete = _delete_after_extract() if delete_on_server is None else bool(delete_on_server)

    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        return {
            "success": False,
            "error": f"PDF not found: {pdf_path}",
            "documents": [],
            **({"output_dir": str(output_dir), "saved_files": []} if persist else {}),
        }

    tax_year = _tax_year_for_upload(pdf_path)
    if verbose:
        print(f"[IAM] Using taxYear={tax_year} for upload metadata.", flush=True)
    document_json = {
        "commonAttributes": {
            "name": pdf_path.name,
            "documentType": "tax::Form1040Composite",
            "taxYear": tax_year,
            "is7216": _upload_common_is7216(),
            "ttlDuration": "2d",
            "payloadVersion": "3.0.0",
            "documentChannel": "upload",
            "channelType": "localFile",
            "deviceType": "desktopWeb",
        }
    }

    upload_result = await client.create_document(str(pdf_path), document_json)
    if not upload_result.get("success"):
        if upload_result.get("status_code") == 401 and client.uses_cookie_auth_only():
            _stderr_financialdoc_cookie_401_hints()
        return {
            "success": False,
            "error": upload_result.get("error") or "Upload failed",
            "documents": [],
            **({"output_dir": str(output_dir), "saved_files": []} if persist else {}),
        }

    document_id = upload_result.get("document_id")
    if not document_id:
        return {
            "success": False,
            "error": "No document ID in upload response (check Location header / API).",
            "documents": [],
            **({"output_dir": str(output_dir), "saved_files": []} if persist else {}),
        }

    initial_wait = _extraction_initial_wait_seconds()
    if initial_wait > 0:
        if verbose:
            print(
                f"[IAM] Waiting {initial_wait:.0f}s after upload before polling "
                f"(legacy behavior; set EXPERT_E2E_IAM_INITIAL_WAIT=0 to skip).",
                flush=True,
            )
        await asyncio.sleep(initial_wait)

    get_result = await _wait_until_parent_ready(client, document_id)
    if not get_result.get("success"):
        if do_delete:
            await _delete_document_relaxed(client, document_id, verbose=verbose)
        return {
            "success": False,
            "error": get_result.get("error") or "GET parent failed",
            "documents": [],
            "document_id": document_id,
            **({"output_dir": str(output_dir), "saved_files": []} if persist else {}),
        }

    doc_data = get_result.get("data") or {}
    documents: list[dict[str, Any]] = [{"label": "Form1040", "data": doc_data}]
    saved: list[str] = []

    if persist:
        saved.append("Form1040.json")
        (output_dir / "Form1040.json").write_text(
            json.dumps(doc_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        semantic_data = doc_data.get("semanticData")
        if semantic_data:
            (output_dir / "Form1040_semantic.json").write_text(
                json.dumps(semantic_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            saved.append("Form1040_semantic.json")

    sys_attrs = doc_data.get("systemAttributes", {}) or {}
    children = sys_attrs.get("children") or []
    used_child_names: set = {"Form1040"}
    child_ids_to_delete: list[str] = []

    for i, child in enumerate(children):
        if isinstance(child, str):
            child_id = child
        else:
            child_id = (child or {}).get("id") or (child or {}).get("documentId")
        if not child_id:
            continue
        child_ids_to_delete.append(child_id)
        if i > 0:
            await asyncio.sleep(0.5)
        child_result = await client.get_document(child_id, save_response=False)
        if not child_result.get("success"):
            continue
        cdata = child_result.get("data") or {}
        child_doc_type = (cdata.get("commonAttributes") or {}).get("documentType", "unknown")
        if child_doc_type == "unknown":
            child_doc_type = (cdata.get("systemAttributes") or {}).get("documentType", "unknown")
        simple_name = document_type_to_simple_name(child_doc_type, used_child_names)
        documents.append({"label": simple_name, "data": cdata})
        if persist:
            child_file = output_dir / f"{simple_name}.json"
            child_file.write_text(json.dumps(cdata, indent=2, ensure_ascii=False), encoding="utf-8")
            saved.append(child_file.name)

    if do_delete:
        for child_id in child_ids_to_delete:
            await _delete_document_relaxed(client, child_id, verbose=verbose)
            await asyncio.sleep(0.3)
        await _delete_document_relaxed(client, document_id, verbose=verbose)

    out: Dict[str, Any] = {
        "success": True,
        "documents": documents,
        "document_id": document_id,
    }
    if persist:
        out["output_dir"] = str(output_dir)
        out["saved_files"] = saved
    return out


def extract_1040_jsons_from_pdf_sync(
    pdf_path: Path | str,
    output_dir: Optional[Path | str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    od: Optional[Path] = Path(output_dir) if output_dir is not None else None
    return asyncio.run(extract_1040_jsons_from_pdf(Path(pdf_path), od, **kwargs))


def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float) and v == int(v):
        v = int(v)
    if isinstance(v, (int, float)):
        return f"{v:,}"
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (list, tuple)):
        if len(v) > 12:
            return json.dumps(v, ensure_ascii=False)[:500] + "…"
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)[:800] + ("…" if len(json.dumps(v)) > 800 else "")
    return str(v)


def _flatten_fields(obj: Any, prefix: str = "", max_depth: int = 4) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if max_depth <= 0:
        return rows
    if isinstance(obj, dict):
        for k in sorted(obj.keys(), key=lambda x: str(x).lower()):
            p = f"{prefix}.{k}" if prefix else str(k)
            v = obj[k]
            if isinstance(v, dict) and max_depth > 1:
                rows.extend(_flatten_fields(v, p, max_depth - 1))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for idx, item in enumerate(v[:20]):
                    rows.extend(_flatten_fields(item, f"{p}[{idx}]", max_depth - 1))
                if len(v) > 20:
                    rows.append((f"{p}[…]", f"({len(v) - 20} more rows omitted)"))
            else:
                s = _format_value(v)
                if s:
                    rows.append((p, s))
    return rows


def build_tax_input_summary_from_documents(
    documents: list[dict[str, Any]],
    *,
    max_chars: int = 48_000,
) -> str:
    """Flatten Form1040 + schedule document payloads (label + full API JSON) into scenario-style text."""
    lines: list[str] = [
        "Tax input summary (from Form 1040 PDF via Intuit document extraction).",
        "Use these facts as the taxpayer situation for calculations.",
        "",
    ]
    ordered = sorted(
        documents,
        key=lambda d: (0 if (d.get("label") or "") == "Form1040" else 1, str(d.get("label") or "").lower()),
    )
    total_len = 0
    for doc in ordered:
        label = str(doc.get("label") or "document")
        data = doc.get("data")
        if not isinstance(data, dict):
            continue

        common = data.get("commonAttributes") or {}
        title_bits = [
            label,
            common.get("documentType") or "",
            str(common.get("taxYear") or "").strip(),
        ]
        header = " — ".join(b for b in title_bits if b)
        block = [f"--- {header} ---"]

        for ck, cv in _flatten_fields(common, "common", max_depth=2):
            if cv:
                block.append(f"{ck}: {cv}")

        sem = data.get("semanticData")
        if isinstance(sem, dict):
            for schema_name, schema_obj in sorted(sem.items(), key=lambda x: str(x[0]).lower()):
                if not isinstance(schema_obj, dict):
                    block.append(f"{schema_name}: {_format_value(schema_obj)}")
                    continue
                block.append(f"[{schema_name}]")
                for fk, fv in _flatten_fields(schema_obj, "", max_depth=4):
                    if fv:
                        block.append(f"  {fk}: {fv}")

        chunk = "\n".join(block) + "\n\n"
        if total_len + len(chunk) > max_chars:
            lines.append(f"(Summary truncated; omitted after {label}.)")
            break
        lines.append(chunk.strip())
        total_len += len(chunk)

    return "\n\n".join(lines).strip()


def build_tax_input_summary_from_extraction_dir(
    output_dir: Path | str,
    *,
    max_chars: int = 48_000,
) -> str:
    """Turn saved Form1040 + schedule JSON files into narrative lines for the scenario text box."""
    d = Path(output_dir)
    json_files = sorted(d.glob("*.json"))
    names = {p.name for p in json_files}
    skip_semantic = "Form1040.json" in names
    ordered_paths: list[Path] = []
    for p in json_files:
        if skip_semantic and p.name == "Form1040_semantic.json":
            continue
        ordered_paths.append(p)
    ordered_paths.sort(key=lambda p: (0 if p.name == "Form1040.json" else 1, p.name.lower()))

    documents: list[dict[str, Any]] = []
    for path in ordered_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        documents.append({"label": path.stem, "data": data})

    return build_tax_input_summary_from_documents(documents, max_chars=max_chars)


def build_scenario_text_from_documents(
    documents: list[dict[str, Any]],
    *,
    mapping_csv: Optional[Path] = None,
    scenario_style: Optional[str] = None,
    verbose: bool = False,
) -> tuple[str | None, str | None, dict[str, str]]:
    """
    Turn in-memory DES document payloads (``documents`` list from extraction) into scenario text.

    Same mapping and style rules as :func:`extract_1040_from_pdf_for_scenario`, without reading a PDF.
    Returns ``(primary_text, error_or_none, meta)`` where ``meta`` has ``summary`` and ``statements`` strings
    (for artifact/debug use).
    """
    vb = verbose
    summary = build_user_inputs_text_from_documents(
        documents,
        mapping_csv=mapping_csv,
        header=(
            "Taxpayer inputs extracted from Form 1040 PDF "
            "(fields classified as user inputs in the YAML-to-PDF mapping)."
        ),
    )
    if not summary and documents:
        flat = build_tax_input_summary_from_documents(documents)
        if flat and len(flat) > 120:
            summary = flat
            if vb:
                print(
                    "[IAM] CSV user-input mapping matched no fields; using full semantic flatten as scenario text.",
                    flush=True,
                )
    statements = ""
    if documents:
        statements = build_tax_engine_statement_text_from_documents(
            documents,
            mapping_csv=mapping_csv,
            preamble=(
                "Taxpayer-provided facts extracted from the Form 1040 PDF (user-input fields only). "
                "Each bullet is a complete statement for tax modeling."
            ),
        )
    style = (
        (scenario_style or os.getenv("EXPERT_E2E_IAM_SCENARIO_STYLE") or "lines")
        .strip()
        .lower()
    )
    primary = summary
    if style in ("statements", "sentences", "tax_engine") and statements.strip():
        primary = statements
        if vb:
            print("[IAM] Returning tax-engine statement text (EXPERT_E2E_IAM_SCENARIO_STYLE).", flush=True)
    meta = {"summary": summary or "", "statements": statements}
    if not primary:
        return (
            None,
            "Intuit extraction returned no usable semantic data for a scenario summary "
            "(empty or missing semanticData). Try EXPERT_E2E_IAM_VERBOSE=1 or EXPERT_E2E_IAM_KEEP_ARTIFACTS=1.",
            meta,
        )
    return primary, None, meta


def extract_1040_from_pdf_for_scenario(
    pdf_path: Path | str,
    *,
    verbose: bool = False,
    mapping_csv: Optional[Path] = None,
    scenario_style: Optional[str] = None,
) -> tuple[str | None, str | None]:
    """
    One-shot: extract in memory, map CSV `user inputs` fields to descriptions, return (text, error).

    Default text is ``Label: value`` lines. Set ``EXPERT_E2E_IAM_SCENARIO_STYLE=statements`` to return
    ``build_tax_engine_statement_text_from_documents`` instead (deduped sentences grouped by form).
    Pass ``scenario_style`` (``lines`` or ``statements``) to override env for this call only.

    Set EXPERT_E2E_IAM_KEEP_ARTIFACTS=1 to also persist JSON + ``user_inputs_summary.txt`` +
    ``tax_engine_statements.txt`` under a temp directory.

    Used by expert_advisory_e2e when ``financialdoc_extraction_configured()`` is true (cookies and/or API key and/or DES IAM).

    For DES JSON already in memory, use :func:`build_scenario_text_from_documents`.
    """
    import shutil

    pdf_path = Path(pdf_path)
    vb = verbose or os.getenv("EXPERT_E2E_IAM_VERBOSE", "").lower() in ("1", "true", "yes")
    keep = os.getenv("EXPERT_E2E_IAM_KEEP_ARTIFACTS", "").lower() in ("1", "true", "yes")
    artifact_dir: Optional[Path] = Path(tempfile.mkdtemp(prefix="iam-1040-")) if keep else None

    result = extract_1040_jsons_from_pdf_sync(pdf_path, artifact_dir, verbose=vb)
    if not result.get("success"):
        if artifact_dir:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        return None, (result.get("error") or "IAM extraction failed").strip()

    documents = result.get("documents") or []
    primary, scen_err, meta = build_scenario_text_from_documents(
        documents,
        mapping_csv=mapping_csv,
        scenario_style=scenario_style,
        verbose=vb,
    )
    if artifact_dir:
        (artifact_dir / "user_inputs_summary.txt").write_text(meta.get("summary", ""), encoding="utf-8")
        st = meta.get("statements", "")
        if st.strip():
            (artifact_dir / "tax_engine_statements.txt").write_text(st, encoding="utf-8")
        if vb:
            print(f"[IAM] Artifacts kept under {artifact_dir}", flush=True)

    if scen_err or not primary:
        if artifact_dir:
            shutil.rmtree(artifact_dir, ignore_errors=True)
        return None, (scen_err or "IAM extraction produced no scenario text.").strip()

    return primary, None


async def _cli_main(
    pdf_filename: str,
    delete_on_server: bool,
    output_dir: Optional[Path],
    dump_http: Optional[str],
) -> None:
    pdf_path = Path(pdf_filename).resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    out = Path(output_dir).resolve() if output_dir else None
    if out:
        out.mkdir(parents=True, exist_ok=True)

    prev_dump = os.environ.get("IAM_EXTRACTION_DUMP_HTTP")
    prev_dir = os.environ.get("IAM_EXTRACTION_DUMP_HTTP_DIR")
    if dump_http:
        os.environ["IAM_EXTRACTION_DUMP_HTTP"] = "1"
        if dump_http != "__auto__":
            os.environ["IAM_EXTRACTION_DUMP_HTTP_DIR"] = dump_http

    try:
        res = await extract_1040_jsons_from_pdf(
            pdf_path,
            out,
            verbose=True,
            delete_on_server=delete_on_server,
        )
    finally:
        if prev_dump is None:
            os.environ.pop("IAM_EXTRACTION_DUMP_HTTP", None)
        else:
            os.environ["IAM_EXTRACTION_DUMP_HTTP"] = prev_dump
        if prev_dir is None:
            os.environ.pop("IAM_EXTRACTION_DUMP_HTTP_DIR", None)
        else:
            os.environ["IAM_EXTRACTION_DUMP_HTTP_DIR"] = prev_dir

    if not res.get("success"):
        err = res.get("error") or ""
        print(err, file=sys.stderr)
        if "classifier" in err.lower() or "async_failed" in err.lower():
            print(_classifier_failure_stderr_hint(), file=sys.stderr)
        sys.exit(2)

    docs = res.get("documents") or []
    report = build_user_inputs_text_from_documents(
        docs,
        header=(
            "Taxpayer inputs extracted from Form 1040 PDF "
            "(fields classified as user inputs in the YAML-to-PDF mapping)."
        ),
    )
    print(report)
    meta = {k: v for k, v in res.items() if k != "documents"}
    print("\n--- extraction meta ---", file=sys.stderr)
    print(json.dumps(meta, indent=2), file=sys.stderr)

    if out:
        (out / "user_inputs_summary.txt").write_text(report, encoding="utf-8")
        legacy = build_tax_input_summary_from_extraction_dir(out)
        (out / "tax_input_summary.txt").write_text(legacy, encoding="utf-8")
        stmts = build_tax_engine_statement_text_from_documents(
            docs,
            preamble=(
                "Taxpayer-provided facts extracted from the Form 1040 PDF (user-input fields only). "
                "Each bullet is a complete statement for tax modeling."
            ),
        )
        if stmts.strip():
            (out / "tax_engine_statements.txt").write_text(stmts, encoding="utf-8")
        print(
            f"\nWrote JSON artifacts + user_inputs_summary.txt + tax_input_summary.txt"
            f"{' + tax_engine_statements.txt' if stmts.strip() else ''} under {out}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IAM Form 1040 PDF extraction (Financial Document API)")
    parser.add_argument("pdf_filename", help="Path to PDF")
    parser.add_argument("--no-delete", action="store_true", help="Leave documents on the server")
    parser.add_argument(
        "--output-dir",
        "--output",
        type=Path,
        default=None,
        dest="output_dir",
        help="If set, write JSON files, user_inputs_summary.txt, and tax_input_summary.txt here.",
    )
    parser.add_argument(
        "--dump-http-bodies",
        nargs="?",
        const="__auto__",
        default=None,
        metavar="DIR",
        help="Dump HTTP bodies (sets IAM_EXTRACTION_DUMP_HTTP)",
    )
    args = parser.parse_args()
    asyncio.run(
        _cli_main(
            args.pdf_filename,
            delete_on_server=not args.no_delete,
            output_dir=args.output_dir,
            dump_http=args.dump_http_bodies,
        )
    )
