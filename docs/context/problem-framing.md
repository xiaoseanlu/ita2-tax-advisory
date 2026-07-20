# ITA 2.0 — Problem Framing

This document captures the full problem space behind ITA 2.0. It goes deeper than the overview and is intended for use in working sessions where understanding the "why" matters as much as the "what."

---

## The Client Profile Pyramid

Tax advisory is not a single market. The complexity of a client's tax situation — and therefore the depth of advisory needed — varies by orders of magnitude.

```
                        ┌──────────────────────────────┐
                        │  Pro Firm Top 10%            │
                        │  Thousands of data points    │
                        │  Multi-entity, K-1s, QSBS    │
                        │  (PTG top clients)           │
                        └──────────────────────────────┘
                   ┌──────────────────────────────────────────┐
                   │  Expert-Led: QBL / ITA                   │
                   │  200–600 inputs                          │
                   │  Self-employed, rental, small business   │
                   └──────────────────────────────────────────┘
              ┌──────────────────────────────────────────────────────┐
              │  DIY Mid                                             │
              │  Itemized deductions, some investment income         │
              └──────────────────────────────────────────────────────┘
         ┌──────────────────────────────────────────────────────────────────┐
         │  DIY Low                                                         │
         │  TurboTax, TaxCaster — under 30 inputs                          │
         │  W-2 filers, simple returns                                     │
         └──────────────────────────────────────────────────────────────────┘
```

ITA 1.0 is positioned in the Expert-Led / ITA tier but fails both down and up:
- 415 inputs is far more than what a mid-market client can provide
- 415 inputs is far less than what a top PTG firm needs for a complex client

A rigid input model is wrong for a heterogeneous market. The LLM approach — natural language input, reason over what's present, flag what's missing — is the only architectural answer that works across the pyramid.

---

## Failure Mode 1: Inputs Are Wrong Before Computation Starts

### The 75% stat
75% of ITA 1.0 Voice of Customer complaints involve input problems. Not calculation problems — input problems. This is the most important signal in the VOC data.

### The 415-input problem
The Planning Summary Box (PSB) contains 415 input fields. This is more than any other Intuit advisory product. Yet it is still insufficient for PTG top clients.

The problems with 415 fields:
- **Missing data**: fields the client hasn't provided, fields the advisor doesn't know, fields pulled from prior-year returns that are now stale
- **Stale data**: pre-populated from ProConnect data, but the client's situation has changed
- **Bundled fields**: single inputs that aggregate values that should be separate (e.g., "total business income" when gross revenue, expenses, and owner draws matter separately)
- **Non-overridable values**: inputs locked to ProConnect values the advisor can't override for planning scenarios

### The LLM alternative
With a natural language input model, the advisor describes the client's situation conversationally. The LLM extracts structured facts where they exist, estimates or flags uncertainty where they don't, and prompts for clarification on what it needs. This is how an expert tax advisor actually works with a client — not by filling in 415 form fields.

---

## Failure Mode 2: Strategy Interaction Effects Are Invisible

### How ITA 1.0 works
Each strategy is evaluated independently against the baseline return. The output is: "This strategy saves you $X." That $X is calculated holding all other strategies constant.

### Why this is wrong
Tax strategies interact. A Roth conversion increases AGI in the conversion year — which can trigger IRMAA surcharges, phase out credits, reduce QBI deductions, and affect SALT. None of these interaction effects are visible when each strategy is evaluated in isolation.

Interaction effects go both ways:
- **Amplifying interactions**: S-Corp election reduces SE tax, which increases net income, which increases Solo 401(k) contribution capacity, which further reduces taxable income
- **Canceling interactions**: Bonus depreciation and Roth conversion in the same year: depreciation reduces income (good for the conversion) but may push the client into a loss year where the conversion's benefit is diminished

### The real-world cost
A known case from ITA 1.0 production: a $20K excess advance tax payment was recommended to a real client. The error was caused by incorrect AMT triggering in the isolated strategy evaluation. The actual net saving is only visible when you recompute the full return with all strategies applied simultaneously. ITA 1.0 cannot do this.

### What ITA 2.0 does differently
The LLM engine computes the full return with all strategies applied. Strategy interactions are not modeled separately — they emerge from the integrated computation. This is not an optimization; it is a prerequisite for accurate advisory.

---

## Failure Mode 3: Architectural Debt That Cannot Be Patched

### The DSL problem
ITA 1.0 is written in a proprietary domain-specific language (DSL). This is not a standard programming language — it is a custom language built for tax rule expression.

Current state:
- Only 2 engineers at Intuit understand the DSL
- Vendor support for the DSL has ended — no external help is available
- The AMT calculation is known to be incorrect; fixing it requires DSL expertise that is scarce

### What this forecloses
The DSL architecture cannot support:
- **Multi-year projections**: the engine is single-year by design
- **State returns**: state conformity rules were never built into the DSL
- **Entity modeling**: S-corp, C-corp, and partnership returns require different computation paths
- **MCP integration**: the DSL engine cannot be exposed as an API surface for Lacerte MCP
- **Modern maintainability**: new engineers cannot contribute; every change is high-risk

### Why this cannot be patched
The failure is not a bug in the DSL code. It is the DSL itself. Patching individual errors (like the AMT calculation) does not change the underlying architecture — it just delays the inevitable migration while the knowledge transfer problem compounds.

The only path forward is a full replacement. ITA 2.0 is that replacement.

---

## LLM Risk Areas: Where Accuracy Is Hard

The LLM approach solves the three failure modes above. It introduces new risks that must be managed.

### States
State tax law does not conform uniformly to federal law. Each state has its own:
- Conformity decisions (rolling conformity vs. fixed-date conformity vs. selective conformity)
- State-specific deductions, credits, and exemptions
- Addition/subtraction modifications to federal AGI

Getting state tax computation right requires maintaining a separate rule set for each state. This is not a problem the LLM can solve through general reasoning — it requires structured knowledge of each state's conformity rules.

**Architecture answer**: Delegate state computation to Lacerte MCP. Lacerte already has this. ITA 2.0's initial scope is 1040 Federal only.

### S-corps and partnerships
S-corp, C-corp, and partnership returns (1120S, 1065) require entity-level computation that feeds into the individual 1040 via K-1. The entity-level computation is not a simple pass-through — it has its own rules for reasonable compensation, basis tracking, at-risk limitations, passive activity rules, and QBI treatment.

**Architecture answer**: Entity comparison use cases (UC-1, UC-9) use Lacerte MCP for entity-level computation. The LLM engine handles the 1040 impact.

### Hallucinated dollar amounts
The most dangerous LLM failure mode in a tax advisory context is a confidently stated but fabricated dollar figure. A client making a financial decision based on a hallucinated tax savings estimate is a serious product failure.

**Architecture answer**: Three-layer defense:
1. RAG: rates and limits are retrieved from ground truth, not generated
2. Skill file guardrails: output validation catches mechanically impossible results
3. Validation loop: production outputs compared against filed returns on an ongoing basis

### AMT
AMT is one of the most complex calculations in the federal tax code. The alternative minimum tax has its own income definition, its own exemption phase-out, its own rate structure, and its own credit carry mechanism. ITA 1.0's AMT calculation is known to be incorrect.

**Architecture answer**: AMT is a first-class test case in the benchmark suite. The LLM engine's AMT output is validated against ProConnect filed returns before Shadow Mode graduation. This is one area where the validation loop must demonstrate accuracy before launch.

---

## Why Rules-Based Cannot Be Patched

It is worth stating this directly, because "why not just fix ITA 1.0" is a question that will be asked.

| Problem | Patch | Why the patch doesn't work |
|---|---|---|
| 415-input model | Add more fields, reduce required fields | More fields don't fix missing/stale data; the input model is wrong by design |
| Strategy isolation | Add interaction tables | Interaction effects are combinatorially complex; explicit tables don't generalize |
| AMT error | Fix the AMT DSL code | Requires DSL expertise that is scarce; fixing one error doesn't fix the architecture |
| Multi-year | Build multi-year DSL rules | The single-year architecture is foundational; multi-year is a rewrite |
| State returns | Build state DSL rules | Would require rebuilding 50 state tax codes in a language no one knows |
| Maintainability | Document the DSL | Documentation doesn't restore vendor support or grow the knowledge base |

Each individual problem has a theoretical patch. None of the patches address the underlying issue: the DSL is a dead-end architecture. The cost of patching individual problems while the knowledge base erodes is higher than the cost of replacement.
