# ITA SPE-Fidelity Tests

Tests that confirm each Python strategy tool under
`skills/income_tax/assisted/*/tools/` faithfully reproduces **every condition,
rule, threshold, and clamp** from its SPE source of truth in
`tax-strategy-content/IndUS/strategies/`.

Each tool has two jobs — **applicability** and **savings estimate** — and the
tests cover both, plus validation clamps and projection mutations.

## Running

Stdlib `unittest` only (no pytest dependency; works on the system Python 3.9):

```bash
cd ita-rules/tests
python3 -m unittest discover -v          # all strategies
python3 -m unittest test_401k_employee   # one strategy
```

## Conventions

- Every assertion cites the exact SPE file + line it pins (see comments).
- Expectations are derived from the SPE formulas, not copied from tool output,
  so a test failing means the tool drifted from the SPE — not the reverse.
- SPE `test_suite` anchors are reused where they exist (e.g. 401k-EE
  `22500 @ 33% -> 7425 / 15075`).

## Reviewed strategies

All 11 implemented retirement/entity tools reviewed against their SPE source.
**Total: 394 tests, all passing.** No regressions in
`scripts/test_retirement_spe_tools.py` (9/9).

| Strategy | Tool | Test file | Tests | Verdict |
|----------|------|-----------|-------|---------|
| 401(k) Employee | `401k-employee/tools/ee_401k.py` | `test_401k_employee.py` | 44 | ✅ faithful (year/age fix) |
| 401(k) Employer | `401k-employer/tools/er_401k.py` | `test_401k_employer.py` | 42 | ✅ faithful (year/age fix) |
| 403(b) Employee | `403b-employee/tools/ee_403b.py` | `test_403b_employee.py` | 43 | ✅ faithful (year/age fix) |
| 403(b) Employer | `403b-employer/tools/er_403b.py` | `test_403b_employer.py` | 42 | ✅ faithful (year/age fix) |
| Solo 401(k) | `solo-401k/tools/solo_401k.py` | `test_solo_401k.py` | 45 | ✅ faithful |
| SEP-IRA | `sep-ira/tools/sep_ira.py` | `test_sep_ira.py` | 29 | ✅ faithful |
| Traditional IRA | `traditional-ira/tools/traditional_ira.py` | `test_traditional_ira.py` | 29 | ✅ faithful |
| Backdoor Roth IRA | `backdoor-roth-ira/tools/backdoor_roth.py` | `test_backdoor_roth_ira.py` | 26 | ✅ faithful |
| Mega Backdoor Roth | `mega-backdoor-roth/tools/mega_backdoor.py` | `test_mega_backdoor_roth.py` | 24 | ✅ faithful |
| Roth IRA Conversion | `roth-ira-conversion/tools/roth_conversion.py` | `test_roth_ira_conversion.py` | 28 | ✅ faithful |
| S-Corp Conversion | `scorp-conversion/tools/scorp_conversion.py` | `test_scorp_conversion.py` | 42 | ✅ faithful |

### Fidelity fixes made during review

- **Combined §415(c) limit by tax year + age-50 catch-up** (401k EE/ER, 403b
  EE/ER) — the SPE (`common/shared401KLimit_GlobalScope.spe` lines 39-83)
  computes the combined limit per year (2022=61k, 2023=66k, 2024=69k) with a
  $6,500/$7,500 age-50 catch-up. These four tools hardcoded `69_000`. Now
  surfaced as `resolve_combined_401k_limit(tax_year, age, engine_value=...)`
  driven by `tax_year`/`age` inputs on `RetirementBaseline`. An explicit engine
  value still wins. **The year table must be extended each year the IRS updates
  §415(c); keep prior years for multi-year support.**
- **State non-conformity is strategy-specific** — pinned per tool via
  `NON_CONFORMING_STATES`: 401k EE = PA-only; 401k ER = none; 403b EE = PA+NJ;
  403b ER = NJ; SEP = MA/NJ/PA; Traditional IRA = MA/NH/NJ/PA; Roth conversion =
  PA (full) + NJ (partial pension-exclusion). These lists differ by SPE and are
  NOT interchangeable — do not copy one to another.
- **SEP spouse applicability precedence** — refined to SPE
  `(married && SE income) || wages_paid_by_scorp` so an unmarried spouse with
  S-Corp wages is still applicable.

### Documented (NOT fixed — flagged for owner review)

- **403(b) Employer `validation_max`** — SPE validation
  (`employer-403b-contribution.spe` L155-157) uses the absorption-inclusive
  headroom with no wages cap; the tool uses the no-absorption formula capped by
  wages. No SPE test distinguishes the two, and the current form matches the
  exemplar convention. Left as-is to avoid an un-anchored hub-UI regression.
- **Traditional IRA / SEP unclamped default** — SPE `strategyChange` default is
  unclamped; the tool clamps the *default* to ≥0. Benign: the recommend gate and
  validation range already exclude the negative case. Explicitly supplied
  strategy_change passes through unclamped, matching the SPE.

### Notes on intentional per-variant differences (verified faithful)

- **Employer headroom** (401k/403b ER) uses the combined-limit formula with **no
  baseline subtraction**; CASH_OUTLAY is always 0; mutations write combined
  absorption only (no wage/deferral writes).
- **403(b) recommend** keys **on** `wages403bContribution > 0` (opposite of the
  401k 403b/457b blocker); **403(b) applicable** uses `headroom > 0`, not
  `contribution <= headroom`.
- **Backdoor / Mega Backdoor** are intentionally ungated on MAGI for
  applicability; savings are ~0 (after-tax dollars). Mega reads the combined
  limit directly from the engine — no year-table gap.
- **Roth conversion** has two modes: `tax_cost` (negative savings) and `growth`
  (future-value); mutation targets `pensTxblAmt` / `ConvertedAmount`.
