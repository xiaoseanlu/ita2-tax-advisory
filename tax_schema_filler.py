"""
Second LLM call: given the raw calculation blob and the original tax situation text,
ask the LLM to fill the tax data model schema (tax-situation-and-1040-schema.json).
Returns a dict that conforms to the schema (or as close as the LLM produces).

Uses genai_tax_core.ask_llm for the call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from genai_tax_core import ask_llm

_ROOT = Path(__file__).resolve().parent
_DEFAULT_SCHEMA_PATH = _ROOT / "tax-situation-and-1040-schema.json"

FILL_SCHEMA_SYSTEM = """You are a precise assistant. Your task is to fill a JSON data model from two inputs:
1) The original tax situation (scenario text).
2) The tax calculation output (narrative with numbers: AGI, taxable income, tax amounts, credits, etc.).

Output only valid JSON that matches the provided schema. Use the schema's property names exactly.
- For tax_situation: use the schema's five groups only (do not put facts at the root of tax_situation):
  • personal — tax_year, filing_status, primary_taxpayer, spouse, dependents.
  • income — wages, Schedule C fields, dividends, interest, pensions, capital gains/losses, rental, other_income, depreciable_assets, wash_sale_disallowed, QBI flags. No withholding here.
  • itemized_deductions — SALT (paid and deductible), mortgage_interest, charitable, medical, etc.
  • credits — array `credits` with {credit_name, amount} for every credit named in the scenario.
  • payments — total_withholding, wages_withholding, dividend_withholding, estimated_tax_payments, other_payments.
  Include depreciable_assets when assets placed in service; wash_sale_disallowed when wash sale is mentioned.
- For form_1040_calculated_lines: extract from the calculation output (AGI, magi, schedule_c_net_profit_or_loss, taxable income,
  ordinary_income_portion, preferential_income_portion, net_investment_income, tax before/after credits, total tax, amount owed or refund, etc.).
- For form_1040_output_lines: REQUIRED array of {line, amount} objects in this exact order — line must be exactly:
  1a, 1z, 2b, 3b, 4b, 5b, 6b, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 21, 22, 23, 24, 25d, 26, 32, 33, 34.
  Map scenario and calculation to Form 1040 lines (wages→1a/1z, interest→2b, ordinary dividends→3b, IRA taxable→4b, pension taxable→5b,
  taxable SS→6b, capital gain/loss→7, other income→8, subtotals 9–15, tax/credits 16–24, withholding 25d, estimated 26, payments 32–33, refund/owed 34).
  Line 34: always set when the calculation states refund or balance due — use schema convention: positive = amount owed, negative = refund (overpayment).
  amount is a number or null. Use null only when the line truly does not apply.
Omit other fields you cannot determine; use null for unknown. For numbers use digits only (no commas). Do not wrap the JSON in markdown code blocks."""


def load_schema(path: Path | str | None = None) -> dict[str, Any]:
    """Load the JSON schema from path."""
    p = Path(path) if path is not None else _DEFAULT_SCHEMA_PATH
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def fill_tax_data_model(
    llm_calculation_blob: str,
    original_tax_situation_text: str,
    *,
    schema_path: Path | str | None = None,
    model: str | None = None,
    print_prompt: bool = False,
) -> dict[str, Any]:
    """
    Call the LLM with the calculation blob + original scenario and ask it to fill
    the tax data model schema. Returns a dict (tax_situation + form_1040_calculated_lines).

    schema_path: Path to tax-situation-and-1040-schema.json; default is same dir as this module.
    """
    schema = load_schema(schema_path)
    schema_str = json.dumps(schema, indent=2) if schema else "{}"

    user_content = f"""Fill the following JSON schema using the two inputs below.

Schema (use these exact property names):
{schema_str}

---
Original tax situation (input):
{original_tax_situation_text}

---
Tax calculation output (use this for form_1040_calculated_lines, form_1040_output_lines, and to cross-check tax_situation):
{llm_calculation_blob}

---
Output only valid JSON, no other text. Include form_1040_output_lines with all line codes listed in the system instructions, in order."""

    response = ask_llm(
        user_content,
        system_prompt=FILL_SCHEMA_SYSTEM,
        model=model,
        print_prompt=print_prompt,
    )

    return _parse_json_from_response(response)


def _parse_json_from_response(response: str) -> dict[str, Any]:
    """Extract JSON from LLM response; strip markdown code fences if present."""
    text = response.strip()
    # Remove optional markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the response
        start = text.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
        return {"_raw": response, "_parse_error": True}
