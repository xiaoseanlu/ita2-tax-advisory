# Tax situation and Form 1040 schema (simplified)

## Purpose

- **Source:** Stripped down from `tax-model-input-schema-annotated.json`. All tax-engine / `INPUT_CODE` / `products` / `nativeAddress` removed.
- **Intent:** A single, clean data model that:
  1. **Tax situation** — can be **populated by the LLM** from the raw scenario text we give it.
  2. **Form 1040 calculated lines** — can be filled from the LLM’s calculation output (or later from a calculator) and used to **drive a UI** that shows the tax situation and 1040 lines.

No code or prompt changes are made yet; this is schema-only.

## What’s in the schema

- **`tax_situation`** — Inputs from the scenario: `tax_year`, `filing_status`, `primary_taxpayer`, `spouse`, **`dependents` (array)**, **`income`** (including `depreciable_assets`, `wash_sale_disallowed`), **`itemized_deductions`** (including `state_and_local_taxes_paid`), **`credits_mentioned` (array)**, **`payments`**.
- **`form_1040_calculated_lines`** — Outputs: AGI, MAGI, schedule_c_net_profit_or_loss, deduction used, taxable income, ordinary/preferential portions, net_investment_income, tax on ordinary/preferential, NIIT, credits, other taxes, total tax, payments, amount owed or refund.

Arrays are kept where they matter: **`dependents`**, **`credits_mentioned`**.

## Variable names

- Human-readable, LLM-friendly snake_case (e.g. `schedule_c_material_participation`, `qualifying_child_under_17`, `tax_before_credits`).
- No internal codes or product IDs.

## Filling the model from the LLM

Possible approaches (for later):

1. **Structured output:** Ask the LLM to return JSON that conforms to this schema (if the API supports structured output).
2. **Grep/parse:** Ask the LLM to write a short “data block” (e.g. key: value or JSON snippet) in its response, then parse it with regex or a small parser to populate the schema.
3. **Two-step:** One prompt to extract `tax_situation` from raw text; another (or same) to fill `form_1040_calculated_lines` from the calculation narrative.

No implementation of these is done here; the schema is ready to be passed to the LLM or to a parser once you choose an approach.
