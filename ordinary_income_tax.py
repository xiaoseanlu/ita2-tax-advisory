"""
Federal ordinary income tax calculation using IRS bracket data for 2024–2026.
Uses the same filing status conventions as deduction.py.
Sources: IRS Revenue Procedures (e.g. Rev. Proc. 2023-34 for 2024, 2024-40 for 2025, 2025-32 for 2026).
"""

# Bracket ceilings (top of each bracket) and rate for 10%, 12%, 22%, 24%, 32%, 35%. 37% applies above last ceiling.
# Each row: (ceiling_10, ceiling_12, ceiling_22, ceiling_24, ceiling_32, ceiling_35)
# Rates: 10%, 12%, 22%, 24%, 32%, 35%, 37%

_BRACKETS = {
    2024: {
        "Single": (11600, 47150, 100525, 191950, 243725, 609350),
        "MFJ": (23200, 94300, 201050, 383900, 487450, 731200),
        "MFS": (11600, 47150, 100525, 191950, 243725, 365600),
        "HOH": (16550, 63100, 100500, 191950, 243700, 609350),  # Tax Foundation 2024
        "QSS": (23200, 94300, 201050, 383900, 487450, 731200),
    },
    2025: {
        "Single": (11925, 48475, 103350, 197300, 250525, 626350),
        "MFJ": (23850, 96950, 206700, 394600, 501050, 751600),
        "MFS": (11925, 48475, 103350, 197300, 250525, 375800),
        "HOH": (17000, 64850, 103350, 197300, 250500, 626350),
        "QSS": (23850, 96950, 206700, 394600, 501050, 751600),
    },
    2026: {
        "Single": (12400, 50400, 105700, 201775, 256225, 640600),
        "MFJ": (24800, 100800, 211400, 403550, 512450, 768700),
        "MFS": (12400, 50400, 105700, 201775, 256225, 640600),
        "HOH": (17700, 67450, 105700, 201775, 256200, 640600),
        "QSS": (24800, 100800, 211400, 403550, 512450, 768700),
    },
}

_RATES = (0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37)

# LTCG/qualified dividends: (taxable_income at which 15% starts, at which 20% starts)
# Stack: ordinary_portion filled first, then preferential; 0% below 15% start, 15% to 20% start, 20% above.
_LTCG_THRESHOLDS = {
    2024: {
        "Single": (47_025, 518_900),
        "MFJ": (94_050, 553_850),
        "MFS": (47_025, 518_900),
        "HOH": (63_000, 551_350),
        "QSS": (94_050, 553_850),
    },
    2025: {
        "Single": (48_475, 533_400),
        "MFJ": (96_950, 600_050),
        "MFS": (48_475, 533_400),
        "HOH": (64_850, 566_700),
        "QSS": (96_950, 600_050),
    },
    2026: {
        "Single": (50_400, 545_500),
        "MFJ": (100_800, 613_700),
        "MFS": (50_400, 545_500),
        "HOH": (67_450, 579_600),
        "QSS": (100_800, 613_700),
    },
}

_STATUS_MAP = {
    "single": "Single",
    "married filing jointly": "MFJ",
    "mfj": "MFJ",
    "married filing separately": "MFS",
    "mfs": "MFS",
    "head of household": "HOH",
    "hoh": "HOH",
    "qualifying surviving spouse": "QSS",
    "qss": "QSS",
}


def _normalize_filing_status(filing_status: str) -> str:
    clean = _STATUS_MAP.get(filing_status.strip().lower())
    if not clean:
        raise ValueError(
            f"Invalid filing status: {filing_status!r}. "
            "Use one of: Single, MFJ, MFS, HOH, QSS (or long forms)."
        )
    return clean


def get_ordinary_income_tax(
    ordinary_income: float,
    year: int,
    filing_status: str,
) -> float:
    """
    Compute federal tax on ordinary (non-preferential) taxable income using
    the correct brackets for the given year and filing status.

    Args:
        ordinary_income: Amount of taxable income to be taxed at ordinary rates
                         (e.g. taxable income minus net capital gain / qualified dividends).
        year: Tax year (2024, 2025, or 2026).
        filing_status: One of 'Single', 'MFJ', 'MFS', 'HOH', 'QSS' or long forms
                       (e.g. 'married filing jointly').

    Returns:
        Federal tax on that ordinary income (rounded to 2 decimals).
        Returns 0 if ordinary_income <= 0.

    Raises:
        ValueError: If year or filing_status is invalid.
    """
    if year not in _BRACKETS:
        raise ValueError(
            f"Tax year {year} not available. Supported years: {sorted(_BRACKETS.keys())}."
        )
    status = _normalize_filing_status(filing_status)
    ceilings = _BRACKETS[year][status]

    if ordinary_income <= 0:
        return 0.0

    tax = 0.0
    prev = 0
    for i, ceiling in enumerate(ceilings):
        if ordinary_income <= prev:
            break
        amount_in_bracket = min(ordinary_income, ceiling) - prev
        tax += amount_in_bracket * _RATES[i]
        prev = ceiling
    if ordinary_income > prev:
        tax += (ordinary_income - prev) * _RATES[6]  # 37%

    return round(tax, 2)


def get_ltcg_tax(
    ordinary_portion: float,
    preferential_income: float,
    year: int,
    filing_status: str,
) -> float:
    """
    Tax on qualified dividends + long-term capital gains (stacked on top of ordinary).

    Args:
        ordinary_portion: Taxable income already allocated to ordinary (fills brackets first).
        preferential_income: Qualified dividends + net long-term capital gain.
        year: 2024, 2025, or 2026.
        filing_status: Single, MFJ, MFS, HOH, QSS (or long forms).

    Returns:
        Tax at 0% / 15% / 20% on preferential_income (rounded to 2 decimals).
    """
    if year not in _LTCG_THRESHOLDS:
        raise ValueError(
            f"Tax year {year} not available. Supported years: {sorted(_LTCG_THRESHOLDS.keys())}."
        )
    status = _normalize_filing_status(filing_status)
    start_15, start_20 = _LTCG_THRESHOLDS[year][status]

    if preferential_income <= 0:
        return 0.0

    in_0 = max(0.0, min(preferential_income, start_15 - ordinary_portion))
    in_15 = max(0.0, min(preferential_income - in_0, start_20 - ordinary_portion - in_0))
    in_20 = preferential_income - in_0 - in_15

    return round(0.15 * in_15 + 0.20 * in_20, 2)


def get_brackets(year: int, filing_status: str) -> list[tuple[float, float]]:
    """
    Return the bracket structure for the given year and filing status.
    Each element is (ceiling, rate) for 10%, 12%, 22%, 24%, 32%, 35%.
    Income above the last ceiling is taxed at 37%.
    """
    if year not in _BRACKETS:
        raise ValueError(
            f"Tax year {year} not available. Supported years: {sorted(_BRACKETS.keys())}."
        )
    status = _normalize_filing_status(filing_status)
    ceilings = _BRACKETS[year][status]
    return list(zip(ceilings, _RATES[:6], strict=True))


def get_ltcg_thresholds(year: int, filing_status: str) -> tuple[float, float]:
    """
    Return (taxable_income_at_15_pct, taxable_income_at_20_pct) for LTCG/qualified dividends.
    """
    if year not in _LTCG_THRESHOLDS:
        raise ValueError(
            f"Tax year {year} not available. Supported years: {sorted(_LTCG_THRESHOLDS.keys())}."
        )
    status = _normalize_filing_status(filing_status)
    return _LTCG_THRESHOLDS[year][status]
