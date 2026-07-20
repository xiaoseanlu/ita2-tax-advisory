# ITA 2.0 / Project AIR — Overview

**ITA** = Intuit Tax Advisor, a product inside ProConnect Tax and Lacerte for professional tax advisors.

ITA 2.0 (codename: Project AIR) is a full replatforming of ITA 1.0 from a rules-based DSL calculator to an LLM-powered tax engine. The north star is dollar-exact accuracy on 1040 Federal returns, with natural language input and no rigid data model requirement.

This document is a 5-minute orientation. For the full position paper, open `llm-tax-engine-case.html`. For the PRD, open `ita2.0-prd.html`.

---

## Why ITA 2.0 Exists

ITA 1.0 has three structural failure modes that cannot be patched.

### Failure 1 — The inputs are wrong before the calculation starts

ITA 1.0 has 415 inputs in its Planning Summary Box (PSB). 75% of ITA 1.0 Voice of Customer complaints involve input problems: missing data, stale data, bundled fields, non-overridable values.

The number of inputs is simultaneously too many and not enough:
- TurboTax TaxCaster manages with under 30 inputs for DIY filers
- PTG's top 10% clients (multi-entity, K-1s, QSBS) need thousands of data points that 415 fields cannot capture

No amount of UI work fixes this. The input model is wrong at the architectural level.

### Failure 2 — The engine evaluates strategies in isolation

ITA 1.0's rules-based engine evaluates each strategy independently. It cannot see interaction effects — strategies that amplify each other or strategies that cancel each other out.

A known real-world consequence: a $20K excess advance tax payment was recommended to a client due to incorrect AMT triggering. The error only becomes visible when you recompute the full return with all strategies applied simultaneously. ITA 1.0 cannot do that.

### Failure 3 — The architecture cannot be maintained and forecloses the market

ITA 1.0 is written in a proprietary domain-specific language (DSL). Only two engineers at Intuit currently understand it, and vendor support for the DSL has ended. Known bugs (including an incorrect AMT calculation) cannot be fixed without risk. The architecture forecloses:
- Multi-year projections
- State return modeling
- S-corp / C-corp entity comparisons
- MCP-based integration with Lacerte and ProConnect

ITA 2.0 must replace this engine entirely. There is no incremental upgrade path.

---

## What ITA 2.0 Is: Four Layers

ITA 2.0 is not a single AI feature. It is a four-layer platform.

### Layer 1 — LLM Tax Engine

The core computation layer. Takes natural language input and a canonical Tax Plan schema, produces a structured tax output. Runs first in Shadow Mode alongside the current deterministic engine, taking over as primary when it reaches ≥95% accuracy on the benchmark suite vs. actual filed returns.

### Layer 2 — RAG (Retrieval-Augmented Generation)

Tax rules change every year. Rather than baking rates, limits, and thresholds into the model (which degrades the moment tax law changes), ITA 2.0 stores this data in a retrieval store. The LLM retrieves what it needs at inference time. This converts a memorization problem into a retrieval problem.

### Layer 3 — Strategy Skill Files + Guardrails

Per-strategy constraint files that define what fields change and what the output shape must look like for each strategy (S-Corp election, Roth conversion, etc.). These prevent the LLM from returning internally inconsistent outputs. Skill files are human-reviewed before deployment. They constrain output consistency — they do not constrain the LLM's reasoning.

### Layer 4 — Lacerte MCP Integration

Lacerte already handles multi-year projections, state returns, and S-corp/C-corp entity modeling. ITA 2.0 does not need to rebuild that — it needs to stop duplicating it. MCP integration surfaces Lacerte's existing computation in the ITA 2.0 advisory context.

---

## Use Cases

**PTG (ProConnect Tax / Lacerte) — 13 use cases**
S-Corp election, retirement account selection, Roth conversion ladder, depreciation strategy, home office deduction, backdoor Roth, IRMAA cliff avoidance, passive activity loss harvesting, entity comparison, NOL carryforward, charitable giving, QSBS exclusion, 1031 exchange/OZ comparison.

**QBL (QuickBooks Live / TurboTax Live) — 5 use cases**
Natural language tax intake, context mutation, client summary generation, session save/retrieve, PDF intake and pre-population.

See [`usecases/README.md`](./usecases/README.md) for the full list with IDs.

---

## Key Metrics

| Metric | Value / Target |
|---|---|
| North Star | Dollar-exact parity with ProConnect on 1040 Federal |
| Shadow Mode graduation threshold | ≥95% accuracy vs. actual filed return |
| Current advisory penetration (PTG) | ~3% of eligible clients |
| PTG firms actively using ITA | ~2.7% |
| Prospect willingness to pay | $538 vs. $155 for existing customers (MaxDiff) |
| Guardrail | Zero hallucinated dollar amounts in production |
| Q3 2026 milestone | Learning plan complete |
| 2027 milestone | 1040 Shadow Mode live |
| 2028 milestone | Full platform |

---

## How to Navigate This Repo

| If you want to... | Go to |
|---|---|
| Understand the full argument for rebuilding | `llm-tax-engine-case.html` |
| See the full PRD | `ita2.0-prd.html` |
| Explore the product blueprint (A/B/C sections) | `ita2.0-product-binder.html` |
| Read the technical architecture | [`docs/architecture.md`](./architecture.md) |
| Understand the personas | [`docs/personas.md`](./personas.md) |
| Resume an AI-assisted working session | [`docs/context/README.md`](./context/README.md) |
| Dig into the problem space | [`docs/context/problem-framing.md`](./context/problem-framing.md) |
| See design decisions and rationale | [`docs/context/design-decisions.md`](./context/design-decisions.md) |
| Track open questions | [`docs/context/open-questions.md`](./context/open-questions.md) |
