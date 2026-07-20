# ITA 2.0 — Technical Architecture

This document covers the four-layer architecture of ITA 2.0 in detail. Audience: engineers and senior PMs.

For the high-level summary, see [`ita2-overview.md`](./ita2-overview.md). For the position paper narrative, see `llm-tax-engine-case.html`.

---

## The Four Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 4: Lacerte MCP Integration                               │
│  Multi-year projections · State returns · Entity modeling       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Strategy Skill Files + Guardrails                     │
│  Per-strategy output constraints · Human-gated updates          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: RAG                                                   │
│  Rates, limits, thresholds by tax year · Retrieval at inference │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: LLM Tax Engine                                        │
│  Natural language input · 1040 Federal · Dollar-exact output    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — LLM Tax Engine

### Purpose
Produce dollar-exact 1040 Federal tax output from a canonical Tax Plan schema and natural language context input. This replaces the DSL-based computation engine in ITA 1.0.

### Input / Output contract
- **Input**: Tax Plan schema (structured) + natural language facts about the client situation
- **Output**: Structured tax output — line-level 1040 figures, strategy impacts, scenario deltas

The schema design deliberately separates the structured data model from the natural language intake. The LLM does not require every field to be populated; it reasons over what is present and flags what is missing.

### Shadow Mode

ITA 2.0 does not hard-cut over from ITA 1.0. It runs in Shadow Mode first:

1. Both engines receive the same input and compute independently
2. Outputs are compared against each other and against actual filed returns (the ATE — Actual Tax Engine benchmark)
3. Delta is logged for every comparison
4. When the LLM engine reaches ≥95% accuracy vs. ATE, it graduates to primary

Shadow Mode serves two functions: (a) it builds the accuracy track record needed for launch confidence, and (b) it generates the training signal for the validation loop.

### Validation Loop

The validation feedback loop is the mechanism by which the LLM engine improves after deployment:

```
Filed return (PTO ground truth)
        ↓
Delta computation vs. LLM output
        ↓
Candidate skill file update generated
        ↓
Human approval gate (PM or tax expert reviewer)
        ↓
Approved update deployed to skill file store
        ↓
LLM engine re-evaluated against benchmark suite
```

The human approval gate is non-negotiable for any update that affects production computation. SLA and reviewer definition are open questions (see [`context/open-questions.md`](./context/open-questions.md)).

### Benchmark Suite

A curated set of 1040 profiles covering:
- All filing statuses (Single, MFJ, MFS, HoH, QW)
- Income types: W-2, self-employment, rental, capital gains, K-1 pass-throughs, Social Security, pension/annuity
- Common strategy scenarios: Roth conversions, S-Corp elections, depreciation elections, charitable giving
- Edge cases: IRMAA cliffs, AMT exposure, NOL carryforwards, QSBS exclusions

Benchmark profiles are compared against actual ProConnect Tax filed returns. Ownership and legal/privacy review of test profiles is an open question.

---

## Layer 2 — RAG (Retrieval-Augmented Generation)

### Purpose
Decouple the LLM from static knowledge of tax rates, limits, and thresholds. Tax law changes annually; baking these into model weights creates a model that is out of date the moment it is trained.

### What lives in the retrieval store
- Standard deduction amounts by filing status and year
- Tax bracket thresholds and rates by year
- Contribution limits: 401(k), IRA, HSA, SEP-IRA, SIMPLE, Solo 401(k)
- Phase-out ranges: Roth IRA, child tax credit, education credits, SALT cap
- IRMAA brackets (Medicare premium surcharges)
- AMT exemption amounts and phase-outs
- QBI deduction thresholds
- Depreciation bonus percentages by year

### Retrieval mechanism
At inference time, the LLM identifies what rate/limit facts it needs for the client's tax year and issues retrieval queries. The retrieved facts are injected into context. The LLM does not need to memorize these values; it reads them at query time.

### Why not fine-tuning
Fine-tuning on tax facts would require retraining after every tax year. The retrieval architecture means a tax year update is a data update, not a model update.

---

## Layer 3 — Strategy Skill Files + Guardrails

### Purpose
Prevent the LLM from returning outputs that are internally inconsistent with how a strategy mechanically works — without constraining the LLM's reasoning about whether a strategy applies or what it saves.

### What a skill file contains
Each of the 13 PTG strategies has a skill file that defines:
- **Return signature**: which 1040 fields are affected by this strategy
- **Expected output shape**: what a valid response looks like (delta on which lines, in which direction)
- **Guardrail assertions**: conditions that must hold in the output (e.g., Roth conversion increases AGI in year of conversion; S-Corp election reduces SE tax)
- **Known failure modes**: outputs that would indicate a computation error

### What skill files do NOT do
Skill files do not constrain whether the LLM recommends a strategy. They do not limit reasoning. They validate that if the LLM says "this strategy saves $X," the computed output is mechanically consistent with that claim.

### Governance
Skill files are human-reviewed before deployment. They are not automatically updated by the validation loop — the loop generates candidates, and a human (PM or tax expert) approves each update. This is a deliberate safety decision: skill files are the primary defense against systematic LLM errors in production.

### Update cadence
Skill files are expected to update in two scenarios:
1. Tax law changes that affect strategy mechanics (e.g., bonus depreciation phase-down)
2. Validation loop identifying a systematic output pattern that requires a new guardrail assertion

---

## Layer 4 — Lacerte MCP Integration

### Purpose
Surface Lacerte's existing computation capabilities — multi-year projections, state return modeling, S-corp/C-corp entity modeling — inside the ITA 2.0 advisory context. ITA 2.0 does not build these; it integrates them.

### Scope
- **Multi-year projections**: Lacerte already computes multi-year tax paths. MCP integration exposes this to the ITA 2.0 LLM context so strategies can be evaluated over a 3–5 year horizon.
- **State returns**: State conformity is Lacerte's domain. ITA 2.0 delegates state computation to Lacerte via MCP rather than attempting to duplicate state tax engines.
- **Entity modeling**: S-corp vs. C-corp vs. partnership comparisons require entity-level return computation. Lacerte handles this; MCP surfaces the results.

### What is out of scope for ITA 2.0 (delegated to Lacerte MCP)
- State conformity rules
- Multi-state allocation and apportionment
- Partnership and LLC entity returns (1065)
- C-corporation returns (1120)

### MCP API surface
The MCP contract with Lacerte is not yet fully defined. This is an open question. See [`context/open-questions.md`](./context/open-questions.md).

---

## Cross-Cutting Concerns

### Accuracy definition
"Dollar-exact" means the LLM engine's computed tax liability matches the ProConnect Tax output within a defined tolerance (to be specified — likely $0 for federal liability, with documented acceptable delta for intermediate line items). The 95% Shadow Mode graduation threshold is measured against actual filed returns (ATE), not against the DSL engine.

### Hallucination prevention
The primary hallucination risk is fabricated dollar amounts. Three defenses:
1. RAG: rates and limits are retrieved, not generated
2. Skill file guardrails: output shape validation catches mechanically impossible results
3. Validation loop: production outputs are compared against ground truth on an ongoing basis

### State and entity complexity
States and entities (S-corps, partnerships) are the hardest part of the LLM accuracy problem. States have non-uniform conformity to federal rules; entity returns require different computation paths. The architecture's answer is: don't solve this in Layer 1. Delegate to Lacerte MCP. ITA 2.0's 1040 Federal scope is deliberate — it is the scope where LLM accuracy is achievable at launch.

---

## Architecture Decisions Summary

| Decision | Choice | Rationale |
|---|---|---|
| Cutover strategy | Shadow Mode → gradual | Accuracy must be proven before primary; hard cutover is too risky |
| Tax knowledge | RAG, not baked-in | Annual law changes require data updates, not model updates |
| Output validation | Skill files + guardrails | Catches mechanically inconsistent outputs without constraining reasoning |
| State/entity computation | Delegate to Lacerte MCP | Lacerte already has this; rebuilding it is unnecessary duplication |
| Accuracy signal | Validation loop vs. filed returns | Filed returns are ground truth; DSL engine is not ground truth |

For the rationale behind each decision, see [`context/design-decisions.md`](./context/design-decisions.md).
