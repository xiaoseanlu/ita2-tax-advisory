# Context Folder — Purpose and Index

This folder contains the raw thinking, problem framing, and design reasoning behind ITA 2.0 / Project AIR.

It serves two audiences:

1. **AI-assisted working sessions** — When resuming a Claude Code session on this project, load files from this folder to restore full context without re-explaining everything from scratch. Start with `problem-framing.md`, then `design-decisions.md`.

2. **New team members and stakeholders** — These files explain not just what we decided, but why. The product binder and PRD capture the output; these files capture the thinking.

---

## Files in This Folder

| File | What it covers |
|---|---|
| [`problem-framing.md`](./problem-framing.md) | The detailed problem space: client profile pyramid, the three failure modes in full, LLM risk areas, why rules-based cannot be patched |
| [`design-decisions.md`](./design-decisions.md) | Key design decisions with rationale: Shadow Mode, skill files, RAG, Lacerte MCP delegation, validation loop |
| [`open-questions.md`](./open-questions.md) | Open questions from the PRD with context on why they remain unresolved |

---

## How to Use These Files in an AI Session

When starting a new Claude Code session on this project, reference this folder explicitly:

> "Load context from `/docs/context/` — read `problem-framing.md`, `design-decisions.md`, and `open-questions.md` before we begin."

This gives the session the full reasoning context, not just the surface-level product description.

For the full product artifact context, also reference:
- `llm-tax-engine-case.html` — the position paper
- `ita2.0-prd.html` — the full PRD
- `ita2.0-product-binder.html` — the product blueprint

---

## Maintenance Note

These files should be updated when:
- A major design decision is made or reversed
- A new open question is identified
- An open question is resolved
- The problem framing changes (new data, new constraints, new stakeholder input)

These are living documents, not snapshots.
