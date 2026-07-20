#!/usr/bin/env python3
"""
Presentation runner for the SPE-fidelity test suite.

Runs every strategy's tests and prints a narrated, grouped summary so a viewer
can SEE what is being proven — not just a bare "OK". The assertions are the same
ones in test_*.py; this only changes how results are displayed.

Usage:
    cd ita-rules/tests
    python3 run_demo.py            # narrated summary (best for a screen grab)
    python3 -m unittest discover   # plain runner, unchanged

Exit code is non-zero if any test fails.
"""
from __future__ import annotations

import io
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Strategy files in a sensible presentation order, with a one-line "what this
# strategy is" so the audience has context as each block scrolls by.
STRATEGIES = [
    ("test_401k_employee", "401(k) Employee", "Elective deferral from W-2 wages"),
    ("test_401k_employer", "401(k) Employer", "Employer match within combined limit"),
    ("test_403b_employee", "403(b) Employee", "Non-profit elective deferral"),
    ("test_403b_employer", "403(b) Employer", "Employer contribution"),
    ("test_solo_401k", "Solo 401(k)", "Self-employed owner-only plan"),
    ("test_sep_ira", "SEP-IRA", "Self-employed % of net earnings"),
    ("test_traditional_ira", "Traditional IRA", "Deductible IRA w/ MAGI phase-out"),
    ("test_backdoor_roth_ira", "Backdoor Roth IRA", "Non-deductible IRA -> Roth"),
    ("test_mega_backdoor_roth", "Mega Backdoor Roth", "After-tax 401(k) -> Roth"),
    ("test_roth_ira_conversion", "Roth IRA Conversion", "Pre-tax -> Roth (tax cost / growth)"),
    ("test_scorp_conversion", "S-Corp Conversion", "Reasonable wage cuts SE tax"),
]

# Human-readable names for the rule categories the test classes cover, so the
# per-strategy line can say WHAT was checked, not just how many.
CATEGORY_LABELS = {
    "HeadroomFormula": "contribution headroom",
    "EmployerHeadroomFormula": "employer headroom",
    "EmployerMatch": "employer match",
    "CombinedLimitByYearAge": "§415(c) limit by year + age-50 catch-up",
    "ApplicabilityPool": "applicability pool",
    "ApplicabilityGate": "applicability gate",
    "ApplicabilitySEFilter": "self-employment income filter",
    "ApplicableGate": "applicable gate",
    "SpouseApplicability": "spouse applicability",
    "SpouseApplicableNoMarriedGate": "spouse applicability",
    "SpouseGate": "spouse gate",
    "SpouseMarriedRecommendGate": "spouse recommend gate",
    "BizWagesAndOppositeEIN": "business wages / opposite-EIN",
    "RecommendGate": "recommend gate",
    "StrategyChangeDefault": "default contribution amount",
    "RoomFormula": "after-tax room formula",
    "SavingsMath": "savings & cash-outlay math",
    "TaxCostMode": "tax-cost mode (negative savings)",
    "GrowthMode": "future-value growth mode",
    "SETaxComputation": "self-employment tax brackets/caps",
    "NetEarningsFactor": "92.35% net-earnings factor",
    "WagesFICA": "FICA on W-2 wages",
    "ReasonableWageSplit": "reasonable-wage income split",
    "HalfSEDeductionFederalOnly": "½ SE-tax deduction (federal only)",
    "NegativeOrdinaryTax": "negative ordinary-tax case",
    "ProjectedSavingsRollup": "projected savings roll-up",
    "NonConformingStates": "state conformity (e.g. PA/NJ/MA)",
    "StateConformity": "state conformity (e.g. PA/NJ/MA)",
    "PANonConforming": "Pennsylvania non-conformity",
    "NJPartialConformity": "New Jersey partial conformity",
    "NYCRate": "NYC marginal rate",
    "RateDefaults": "marginal-rate defaults",
    "PhaseOutFields": "MAGI phase-out fields",
    "ValidationClamp": "validation clamp / 'Exceeds' limit",
    "ValidationRange": "validation range",
    "ValidationErrors": "validation errors",
    "Mutations": "projection writes (apply)",
    "NotApplicablePath": "not-applicable guard",
    "NotApplicableSavings": "not-applicable guard",
    "EstimateGuards": "estimate guards",
    "OwnerSelection": "taxpayer/spouse selection",
    "ProjectedBaseline": "projected vs baseline amounts",
    "JSONEntrypoints": "JSON entry points",
}

BAR = "─" * 72


def _categories_for(suite) -> list[str]:
    """Collect distinct, human-labeled rule categories from a strategy's suite."""
    seen: list[str] = []
    for test in _iter_tests(suite):
        cls = type(test).__name__  # e.g. TestSavingsMath
        key = cls[4:] if cls.startswith("Test") else cls
        label = CATEGORY_LABELS.get(key)
        if label and label not in seen:
            seen.append(label)
    return seen


def _iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def main() -> int:
    loader = unittest.TestLoader()
    # Send unittest's own "Ran N tests / OK" chatter to a throwaway buffer so
    # only our narrated summary shows on screen.
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)

    print()
    print(BAR)
    print("  ITA STRATEGY TOOLS  —  SPE ↔ Python fidelity tests")
    print("  Proving each Python tool reproduces the original SPE rules exactly")
    print(BAR)

    grand_total = 0
    grand_fail = 0
    t0 = time.perf_counter()

    for module, title, blurb in STRATEGIES:
        try:
            suite = loader.loadTestsFromName(module)
        except Exception as exc:  # pragma: no cover - import guard
            print(f"\n✗  {title}: could not load {module}: {exc}")
            grand_fail += 1
            continue

        count = suite.countTestCases()
        cats = _categories_for(suite)

        # Run this strategy's suite quietly; we render our own summary.
        result = runner.run(suite)
        failed = len(result.failures) + len(result.errors)
        passed = count - failed
        grand_total += count
        grand_fail += failed

        mark = "✓" if failed == 0 else "✗"
        print(f"\n{mark}  {title:<20} {blurb}")
        print(f"    {passed}/{count} checks pass")
        # Show the rules that were verified, wrapped to keep it readable.
        line = "    rules verified: "
        indent = " " * len(line)
        buf = line
        for i, c in enumerate(cats):
            piece = c + ("" if i == len(cats) - 1 else ", ")
            if len(buf) + len(piece) > 72:
                print(buf)
                buf = indent + piece
            else:
                buf += piece
        print(buf)
        if failed:
            for case, _ in result.failures + result.errors:
                print(f"      FAILED: {case}")

    elapsed = time.perf_counter() - t0
    grand_pass = grand_total - grand_fail

    print()
    print(BAR)
    strategies_ok = sum(1 for _ in STRATEGIES)
    if grand_fail == 0:
        print(f"  RESULT:  {grand_pass}/{grand_total} checks pass across "
              f"{strategies_ok} strategies   ({elapsed:.2f}s)")
        print("  Every applicability rule, threshold, limit, state-conformity")
        print("  rule and savings formula matches the original ITA SPE source.")
    else:
        print(f"  RESULT:  {grand_fail} FAILED of {grand_total} "
              f"({grand_pass} passed)   ({elapsed:.2f}s)")
    print(BAR)
    print()
    return 0 if grand_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
