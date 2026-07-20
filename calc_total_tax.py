"""
Compute total federal income tax using deduction and ordinary_income_tax tools.
Provides get_total_federal_tax() for any scenario; main() runs the 2024 MFJ example.
get_tax_reference_text() returns IRS rates/deductions for a given year/status for LLM prompts.
"""

from deduction import calculate_comprehensive_deduction
from ordinary_income_tax import (
    get_ordinary_income_tax,
    get_ltcg_tax,
    get_brackets,
    get_ltcg_thresholds,
)

# NIIT MAGI thresholds by filing status (2024–2026)
_NIIT_THRESHOLD = {"Single": 200_000, "MFJ": 250_000, "QSS": 250_000, "MFS": 125_000, "HOH": 200_000}

# Child Tax Credit: phaseout uses MAGI; threshold above which credit is reduced (2024–2026)
# Reduction: $50 for each $1,000 (or fraction) of MAGI above threshold → effective rate 5% of excess
_CTC_PHASEOUT_THRESHOLD = {
    2024: {"Single": 200_000, "HOH": 200_000, "MFS": 200_000, "MFJ": 400_000, "QSS": 400_000},
    2025: {"Single": 200_000, "HOH": 200_000, "MFS": 200_000, "MFJ": 400_000, "QSS": 400_000},
    2026: {"Single": 200_000, "HOH": 200_000, "MFS": 200_000, "MFJ": 400_000, "QSS": 400_000},
}
_CTC_MAX_PER_CHILD = {2024: 2_000, 2025: 2_200, 2026: 2_000}  # 2025 increased per TCJA/IRS
_CTC_PHASEOUT_RATE = 0.05  # $50 per $1,000 = 5% of MAGI above threshold


def _fs_key_from_status(filing_status: str) -> str:
    """Map filing_status string to deduction key (MFJ, Single, MFS, HOH, QSS)."""
    status_upper = filing_status.strip().upper()
    status_map = {
        "single": "Single", "mfj": "MFJ", "mfs": "MFS", "hoh": "HOH", "qss": "QSS",
        "married filing jointly": "MFJ", "married filing separately": "MFS",
        "head of household": "HOH", "qualifying surviving spouse": "QSS",
    }
    return status_map.get(filing_status.strip().lower()) or (
        "Single" if status_upper == "SINGLE" else "MFS" if status_upper == "MFS"
        else "MFJ" if status_upper in ("MFJ", "QSS") else "HOH"
    )


def get_child_tax_credit(
    magi: float,
    filing_status: str,
    num_qualifying_children: int,
    year: int = 2024,
    *,
    tax_before_credits: float | None = None,
) -> dict:
    """
    Child Tax Credit (CTC) with phaseout. Phaseout is based on MAGI (not taxable income).

    What is checked for phaseouts:
    - MAGI (Modified AGI) is compared to the threshold for your filing status.
    - 2024 thresholds: Single / HOH / MFS = $200,000; MFJ / QSS = $400,000.
    - For each $1,000 of MAGI above the threshold, the total credit is reduced by $50
      (effective rate 5% of excess MAGI). So: reduction = (MAGI - threshold) * 0.05.
    - Tentative CTC = max(0, num_children * max_per_child - reduction).
    - Nonrefundable CTC = min(tentative CTC, tax liability before credits) if
      tax_before_credits is provided; otherwise returns tentative (full) amount.

    Returns dict with: tentative_ctc, nonrefundable_ctc, phaseout_threshold, phaseout_reduction.
    """
    fs_key = _fs_key_from_status(filing_status)
    thresholds = _CTC_PHASEOUT_THRESHOLD.get(year, _CTC_PHASEOUT_THRESHOLD[2024])
    threshold = thresholds.get(fs_key, 200_000)
    max_per = _CTC_MAX_PER_CHILD.get(year, 2_000)
    max_credit = num_qualifying_children * max_per
    excess = max(0.0, magi - threshold)
    reduction = excess * _CTC_PHASEOUT_RATE
    tentative_ctc = max(0.0, max_credit - reduction)
    nonrefundable_ctc = (
        min(tentative_ctc, tax_before_credits) if tax_before_credits is not None
        else tentative_ctc
    )
    return {
        "tentative_ctc": round(tentative_ctc, 2),
        "nonrefundable_ctc": round(nonrefundable_ctc, 2),
        "phaseout_threshold": threshold,
        "phaseout_reduction": round(reduction, 2),
        "max_per_child": max_per,
    }


def get_standard_deduction_tool_result(
    year: int,
    filing_status: str,
    magi: float = 0,
    *,
    filer_65: bool = False,
    filer_blind: bool = False,
    spouse_65: bool = False,
    spouse_blind: bool = False,
) -> tuple[dict, str]:
    """
    Call the standard deduction calculation tool (calculate_comprehensive_deduction) and return
    the result dict plus a short text block for use in LLM prompts. Use this so the LLM is told
    to use the tool output rather than computing deduction itself.

    magi is only used for 2025+ senior bonus phase-out; for 2024 it has no effect.

    Returns:
        (deduction_dict, prompt_text)
    """
    fs_key = _fs_key_from_status(filing_status)
    ded = calculate_comprehensive_deduction(
        year, fs_key, magi,
        filer_65=filer_65, filer_blind=filer_blind,
        spouse_65=spouse_65, spouse_blind=spouse_blind,
    )
    total = ded["Total Deduction"]
    base = ded["Base"]
    addon = ded["Age/Blindness Add-on"]
    bonus = ded["Senior Bonus"]
    text = (
        f"Standard deduction (from get_standard_deduction tool): "
        f"Total ${total:,.0f}. Breakdown: Base ${base:,}, Age/Blindness add-on ${addon:,}, Senior bonus ${bonus:,.0f}. "
        "Use this amount when standard is chosen (after comparing to itemized)."
    )
    return ded, text


def get_tax_reference_text(
    year: int,
    filing_status: str,
    *,
    magi: float = 0,
    filer_65: bool = False,
    filer_blind: bool = False,
    spouse_65: bool = False,
    spouse_blind: bool = False,
) -> str:
    """
    Build reference text with IRS rates and deduction data from our tools (same as used in
    get_total_federal_tax). Standard deduction is from get_standard_deduction_tool_result
    (i.e. calculate_comprehensive_deduction). Use this to prepend to an LLM prompt so the agent
    uses the tool output for the deduction.
    """
    fs_key = _fs_key_from_status(filing_status)
    _, ded_tool_text = get_standard_deduction_tool_result(
        year, filing_status, magi,
        filer_65=filer_65, filer_blind=filer_blind,
        spouse_65=spouse_65, spouse_blind=spouse_blind,
    )
    ded = calculate_comprehensive_deduction(
        year, fs_key, magi,
        filer_65=filer_65, filer_blind=filer_blind,
        spouse_65=spouse_65, spouse_blind=spouse_blind,
    )
    brackets = get_brackets(year, filing_status)
    start_15, start_20 = get_ltcg_thresholds(year, filing_status)
    niit = _NIIT_THRESHOLD.get(fs_key, 250_000)
    lines = [
        f"## Reference: {year} federal tax data (from IRS; use these numbers)",
        "",
        f"Filing status: {filing_status}.",
        "",
        "Standard deduction (from get_standard_deduction tool):",
        f"  {ded_tool_text}",
        "  Compare to itemized; use the higher for taxable income. If you choose itemized, use the itemized amount only (not the standard amount above) for all steps.",
        "",
        "Ordinary income tax brackets (ceiling, rate):",
    ]
    for ceiling, rate in brackets:
        lines.append(f"  Up to ${ceiling:,.0f}: {rate*100:.0f}%")
    lines.append("  Above last ceiling: 37%")
    lines.append("")
    lines.append("LTCG / qualified dividends (stack on top of ordinary):")
    lines.append(f"  0% below taxable income ${start_15:,.0f}; 15% from ${start_15:,.0f} to ${start_20:,.0f}; 20% above ${start_20:,.0f}.")
    lines.append("")
    lines.append("NIIT (3.8% on net investment income above MAGI threshold):")
    lines.append(f"  MAGI threshold: ${niit:,}.")
    lines.append("")
    # Child Tax Credit phaseout (uses MAGI; $50 per $1,000 above threshold)
    ctc_thresholds = _CTC_PHASEOUT_THRESHOLD.get(year, _CTC_PHASEOUT_THRESHOLD[2024])
    ctc_thresh = ctc_thresholds.get(fs_key, 200_000)
    ctc_max = _CTC_MAX_PER_CHILD.get(year, 2_000)
    lines.append("Child Tax Credit (CTC) phaseout — use MAGI (not taxable income):")
    lines.append(f"  Max ${ctc_max:,} per qualifying child under 17. Phaseout: MAGI above ${ctc_thresh:,} reduces credit by $50 per $1,000 of MAGI over threshold (5% of excess). Single/HOH/MFS: $200,000; MFJ/QSS: $400,000 (2024).")
    lines.append("")
    return "\n".join(lines)


def get_tax_reference_text_all() -> str:
    """
    Build reference text with thresholds for all years (2024–2026) and all filing statuses.
    No parsing or assumptions: the LLM is told to use the tax year and filing status from
    the scenario and to apply only the thresholds that match.
    """
    lines = [
        "## Tax reference — use the tax year and filing status from the scenario",
        "",
        "**CRITICAL — match the scenario exactly:**",
        "1. Read the scenario and identify the **tax year** (2024, 2025, or 2026) and **filing status** (e.g. Head of Household, Single, Married Filing Jointly).",
        "2. Use **only** the rows under the heading for that tax year. If the scenario says **2026**, use ONLY the rows under \"TAX YEAR 2026\"; do not use 2024 or 2025 brackets, deduction, or thresholds. If the scenario says **2024**, use ONLY the rows under \"TAX YEAR 2024\".",
        "3. **Head of Household is not the same as Single.** If the scenario says Head of Household, use the **Head of Household** row for that year (different brackets and standard deduction than Single).",
        "4. At the start of your calculation, state: \"Filing status: [exact status]. Tax year: [year]. Using the [year] [Filing status] row from the reference.\"",
        "",
    ]
    status_labels = [
        ("Single", "Single"),
        ("Head of Household", "HOH"),
        ("Married Filing Jointly", "MFJ"),
        ("Married Filing Separately", "MFS"),
        ("Qualifying Surviving Spouse", "QSS"),
    ]
    for year in (2024, 2025, 2026):
        lines.append(f"### TAX YEAR {year} — use these rows only when the scenario says {year}")
        for label, fs_key in status_labels:
            ded = calculate_comprehensive_deduction(
                year, fs_key, 0.0,
                filer_65=False, filer_blind=False, spouse_65=False, spouse_blind=False,
            )
            base = ded["Base"]
            brackets = get_brackets(year, fs_key)
            start_15, start_20 = get_ltcg_thresholds(year, fs_key)
            niit = _NIIT_THRESHOLD.get(fs_key, 250_000)
            ctc_thresh = _CTC_PHASEOUT_THRESHOLD.get(year, _CTC_PHASEOUT_THRESHOLD[2024]).get(fs_key, 200_000)
            ctc_max = _CTC_MAX_PER_CHILD.get(year, 2_000)
            bracket_str = ", ".join(f"${c:,.0f} @ {r*100:.0f}%" for c, r in brackets)
            lines.append(f"**{label}:** Standard deduction (base): ${base:,}. Ordinary brackets (ceiling, rate): {bracket_str}; above last: 37%. LTCG/qualified dividends: 0% below taxable income ${start_15:,.0f}, 15% to ${start_20:,.0f}, 20% above. NIIT MAGI threshold: ${niit:,}. CTC: ${ctc_max:,}/child; phaseout above MAGI ${ctc_thresh:,} ($50 per $1,000 over threshold).")
        lines.append("")
    lines.append(
        "**Standard deduction — age 65+ and blind (applies to 2024, 2025, and 2026):** The *base* amounts in each row above do **not** include the extra standard deduction for the taxpayer or spouse being age 65 or older or blind. "
        "Use `calculate_comprehensive_deduction` / the get_standard_deduction tool logic: for **2024** Married Filing Jointly, add **$1,550 per condition** (each of: taxpayer 65+, taxpayer blind, spouse 65+, spouse blind — up to four add-ons). "
        "**Example — 2024 MFJ, both spouses age 65+, neither blind:** $29,200 base + ($1,550 × 2) = **$32,300** total standard deduction (before comparing to itemized). "
        "If the scenario or PDF narrative states **both** spouses are over 65, you must include **two** age add-ons for MFJ (not one). **2025+** also adds the OBBBA senior bonus per rules in code (phase-out with income)."
    )
    lines.append("Compare standard (base + add-ons + any senior bonus for the year) to itemized; use the higher for taxable income.")
    lines.append("")
    lines.append("**Reminder — tax year:** If the scenario says 2026, your brackets, standard deduction, LTCG thresholds, NIIT threshold, and CTC threshold must all come from the TAX YEAR 2026 section above. Using 2024 data for a 2026 scenario is wrong.")
    lines.append("**Reminder — filing status:** Head of Household and Single have different brackets (e.g. 2024 HOH: 10% up to $16,550; Single: 10% up to $11,600). Use the row that matches the scenario's filing status.")
    lines.append("")
    return "\n".join(lines)


def get_total_federal_tax(
    *,
    year: int,
    filing_status: str,
    wages: float = 0,
    ordinary_dividends: float = 0,
    qualified_dividends: float = 0,
    taxable_interest: float = 0,
    taxable_pensions: float = 0,
    st_capital_gain: float = 0,
    lt_capital_gains: float = 0,
    rental_income: float = 0,
    other_ordinary_income: float = 0,
    filer_65: bool = False,
    filer_blind: bool = False,
    spouse_65: bool = False,
    spouse_blind: bool = False,
    nonrefundable_credits: float = 0,
    withholding: float = 0,
) -> dict:
    """
    Total federal tax using deduction + ordinary tax + LTCG + NIIT.

    Long-term gains and qualified dividends are preferential; everything else is ordinary.
    Returns a dict with AGI, taxable_income, tax_ordinary, tax_ltcg, regular_tax, niit,
    tax_before_credits, tax_after_credits, amount_owed, and the deduction breakdown.
    """
    status_upper = filing_status.strip().upper()
    if status_upper not in ("SINGLE", "MFJ", "MFS", "HOH", "QSS"):
        status_map = {
            "single": "Single", "mfj": "MFJ", "mfs": "MFS",
            "hoh": "HOH", "qss": "QSS",
            "married filing jointly": "MFJ", "married filing separately": "MFS",
            "head of household": "HOH", "qualifying surviving spouse": "QSS",
        }
        status_upper = status_map.get(filing_status.strip().lower(), filing_status)
    if status_upper in ("SINGLE", "MFS"):
        fs_key = "Single" if status_upper == "SINGLE" else "MFS"
    else:
        fs_key = "MFJ" if status_upper in ("MFJ", "QSS") else "HOH"

    preferential = qualified_dividends + lt_capital_gains
    agi = (
        wages + ordinary_dividends + taxable_interest + taxable_pensions
        + st_capital_gain + lt_capital_gains + rental_income + other_ordinary_income
    )

    ded = calculate_comprehensive_deduction(
        year, fs_key, agi,
        filer_65=filer_65, filer_blind=filer_blind,
        spouse_65=spouse_65, spouse_blind=spouse_blind,
    )
    standard_deduction = ded["Total Deduction"]
    taxable_income = max(0, agi - standard_deduction)
    ordinary_portion = max(0, taxable_income - preferential)

    tax_ordinary = get_ordinary_income_tax(ordinary_portion, year, fs_key)
    tax_ltcg = get_ltcg_tax(ordinary_portion, preferential, year, fs_key)
    regular_tax = tax_ordinary + tax_ltcg

    niit_threshold = _NIIT_THRESHOLD.get(fs_key, 250_000)
    nii = taxable_interest + ordinary_dividends + st_capital_gain + lt_capital_gains + rental_income
    niit_base = min(nii, max(0, agi - niit_threshold))
    niit = round(0.038 * niit_base, 2)

    tax_before_credits = regular_tax + niit
    tax_after_credits = max(0, tax_before_credits - nonrefundable_credits)
    amount_owed = tax_after_credits - withholding

    return {
        "agi": agi,
        "standard_deduction": standard_deduction,
        "deduction_breakdown": ded,
        "taxable_income": taxable_income,
        "ordinary_portion": ordinary_portion,
        "preferential_income": preferential,
        "tax_ordinary": tax_ordinary,
        "tax_ltcg": tax_ltcg,
        "regular_tax": round(regular_tax, 2),
        "niit": niit,
        "tax_before_credits": round(tax_before_credits, 2),
        "nonrefundable_credits": nonrefundable_credits,
        "tax_after_credits": round(tax_after_credits, 2),
        "withholding": withholding,
        "amount_owed": round(amount_owed, 2),
    }


# --- Example scenario: 2024 MFJ, both 65+, neither blind ---
YEAR = 2024
FILING_STATUS = "MFJ"
FILER_65 = True
SPOUSE_65 = True
FILER_BLIND = False
SPOUSE_BLIND = False
WAGES = 180_000
ORDINARY_DIVIDENDS = 56_000
QUALIFIED_DIVIDENDS = 48_600
TAXABLE_INTEREST = 16_300
TAXABLE_PENSIONS = 280_000
ST_CAPITAL_GAIN = 12_000
LT_DISTRIBUTIONS = 18_000
LT_PASSTHROUGH_GAIN = 55_000
RENTAL_INCOME = 14_276
RESIDENTIAL_ENERGY_CREDIT = 1_350
TOTAL_WITHHOLDING = 82_000


def main():
    result = get_total_federal_tax(
        year=YEAR,
        filing_status=FILING_STATUS,
        wages=WAGES,
        ordinary_dividends=ORDINARY_DIVIDENDS,
        qualified_dividends=QUALIFIED_DIVIDENDS,
        taxable_interest=TAXABLE_INTEREST,
        taxable_pensions=TAXABLE_PENSIONS,
        st_capital_gain=ST_CAPITAL_GAIN,
        lt_capital_gains=LT_DISTRIBUTIONS + LT_PASSTHROUGH_GAIN,
        rental_income=RENTAL_INCOME,
        filer_65=FILER_65,
        filer_blind=FILER_BLIND,
        spouse_65=SPOUSE_65,
        spouse_blind=SPOUSE_BLIND,
        nonrefundable_credits=RESIDENTIAL_ENERGY_CREDIT,
        withholding=TOTAL_WITHHOLDING,
    )

    print("=== Using deduction + ordinary_income_tax tools ===\n")
    print("AGI:", result["agi"])
    print("Standard deduction (from tool):", result["standard_deduction"])
    print("Taxable income:", result["taxable_income"])
    print("Ordinary portion (for rate):", result["ordinary_portion"])
    print("Preferential (LTCG + qual. div):", result["preferential_income"])
    print()
    print("Tax on ordinary income (from tool):", result["tax_ordinary"])
    print("Tax on preferential (from get_ltcg_tax):", result["tax_ltcg"])
    print("Regular income tax:", result["regular_tax"])
    print("NIIT:", result["niit"])
    print()
    print("Federal tax before credits:", result["tax_before_credits"])
    print("Credits (nonrefundable):", -result["nonrefundable_credits"])
    print("Federal tax after credits:", result["tax_after_credits"])
    print("Withholding:", -result["withholding"])
    print("Amount owed:", result["amount_owed"])


if __name__ == "__main__":
    main()
