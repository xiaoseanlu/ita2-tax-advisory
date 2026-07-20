# Tax calculation flow – what the code actually does

This document shows how the LLM and the programmatic calculator are used, and where confusion or mixing can happen.

---

## Two ways to get the scenario (description) input

| Path | Where it lives | When it’s used |
|------|----------------|----------------|
| **Manual** | User types or pastes the tax situation in the UI, or uses “Copy from Baseline”. | Current flow. Scenario text goes straight into the prompt. |
| **PDF import** | Folder **`pdf_to_tax_situation/`**: PDF → extract/process → **description of the tax situation** (text). | Separate pipeline. When that pipeline is done, its output can be pushed into the same scenario text area or as a new scenario. Integration only after PDF → description is ready. |

The main app (web UI, `tax_cli.py`, `genai_tax_core`) does not depend on the PDF path. See `pdf_to_tax_situation/README.md` and the Chrome plugin in `~/Documents/GitHub/tax-advisory-toolkit/tools/1040-ita-mapping/`.

---

## High-level: who does the math?

| What | Who does it |
|------|-------------|
| **Reference thresholds** (brackets, standard deduction base, LTCG, NIIT, CTC by year and status) | **Our code** (get_tax_reference_text_all). We inject a **full table** for all years (2024–2026) and all filing statuses. **We do not parse** the scenario to pick one row. |
| **Which row to use** | **The LLM**. It is told to use the tax year and filing status from the scenario and to apply only the thresholds that match. |
| **SE tax, AGI, QBI, itemized vs standard, taxable income, tax amounts, NIIT, credits, amount due** | **The LLM**. It does all of this inside the prompt. We do not run Python to compute these for the scenario. |

So: we **give the LLM a reference table** (no parsing, no assumptions). The LLM is told to use the **right tax year and filing status** from the scenario and the **corresponding thresholds**, then to do the full tax calculation.

---

## Single-prompt path (default: `python tax_cli.py`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  build_tax_prompt(raw_prompt=DEFAULT_TAX_PROMPT, include_reference=True)     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  REFERENCE BLOCK (from calc_total_tax.get_tax_reference_text_all)           │
│  • Instruction: use tax year and filing status from the scenario; use       │
│    only the thresholds that correspond to that year and status.             │
│  • For 2024, 2025, 2026: each filing status (Single, HOH, MFJ, MFS, QSS)     │
│    with standard deduction base, brackets, LTCG, NIIT, CTC phaseout.        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │  "---"
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SCENARIO + INSTRUCTIONS (DEFAULT_TAX_PROMPT)                                │
│  • Scenario: John Anderson, MFJ 2024, $200k wages, $64k business,           │
│    SALT/mortgage/RE tax, no dividends/pensions/cap gains                    │
│  • Instructions: 1–8 (SE tax, AGI, QBI, deduction choice, stack, NIIT, …)   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ask_llm(prompt)  →  ONE LLM CALL                                            │
│  The model reads the reference + scenario + instructions and returns        │
│  a full tax write-up (it does ALL calculations in the response).             │
│  Print answer and stop.                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Two-step path (`python tax_cli.py --two-step`)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Get AGI                                                             │
│  get_agi_from_scenario(DEFAULT_TAX_PROMPT)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Prompt = AGI_EXTRACTION_PROMPT + "---" + scenario text                      │
│  ask_llm(prompt)  →  FIRST LLM CALL                                          │
│  Model returns e.g. "AGI: $258247" (for John Anderson scenario)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  parse_agi_from_response(response)  →  agi, magi                             │
│  We prepend "Use AGI = $X" to the step-2 prompt; reference is universal.      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Full tax                                                            │
│  Optional line: "Use AGI = $X from the prior AGI determination."             │
│  + REFERENCE BLOCK (universal: all years and filing statuses)                 │
│  + "---"                                                                     │
│  + SCENARIO + INSTRUCTIONS (same DEFAULT_TAX_PROMPT)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ask_llm(prompt)  →  SECOND LLM CALL                                          │
│  Again, the model does the ENTIRE tax calculation in the response.           │
└─────────────────────────────────────────────────────────────────────────────┘
```

So even in two-step mode, **only AGI is extracted after step 1**. All other math (SE tax, QBI, deduction choice, taxable income, tax, NIIT, credits) is still done by the LLM in step 2.

---

## Where “mixing up” can come from

1. **All logic in one place (the LLM)**  
   We only inject reference numbers. The model must:
   - Apply the scenario (which taxpayer, which income).
   - Choose standard vs itemized and use that consistently.
   - Do SE tax, AGI, QBI, taxable income, brackets, LTCG, NIIT, credits, payments.  
   Any mistake (wrong number, wrong step, mixing scenarios) is in the model’s response.

2. **Reference vs scenario**  
   The reference block is built from our tools (and, in two-step, from the AGI we parsed). The scenario is free text (e.g. DEFAULT_TAX_PROMPT). If the model confuses “use the reference standard deduction” with “use standard deduction for this taxpayer” even when itemized is higher, it will mix things up.

---

## Summary diagram

```
                    ┌─────────────────────────────────────┐
                    │  Our code (Python)                   │
                    │  • deduction.py                     │
                    │  • ordinary_income_tax.py           │
                    │  • calc_total_tax.get_tax_reference │
                    └─────────────────────────────────────┘
                                      │
                                      │ builds REFERENCE (numbers only)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROMPT = [REFERENCE] + "---" + [SCENARIO + INSTRUCTIONS]                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LLM (GenOS)                                                                 │
│  Does ALL tax calculation for the scenario: SE, AGI, QBI, deduction choice, │
│  taxable income, tax, NIIT, credits, amount due.                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Printed: LLM response (full narrative + numbers)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```
