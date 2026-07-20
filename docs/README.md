# Project AIR — Documentation Index

This folder contains the reference documentation for ITA 2.0 / Project AIR. It is the canonical written record of what we're building and why.

---

## Live Product Artifacts (GitHub Pages)

The main HTML product artifacts are published at:
**https://github.intuit.com/pages/rraman2/project-air/**

| File | Description |
|---|---|
| `ita2.0-product-binder.html` | Main product binder — Overview, Use Cases, and Product Blueprint (Sections A, B, C) |
| `llm-tax-engine-case.html` | Position paper: "The Case for a Tax Engine" — three failures, four-layer solution |
| `ita2.0-prd.html` | Full PRD — seven tabs: Overview, Personas, Features, Architecture, Goals & Metrics, Scope, Milestones |

---

## Docs in This Folder

### Overview & Architecture

| File | What it covers |
|---|---|
| [`ita2-overview.md`](./ita2-overview.md) | What ITA 2.0 is, why it exists, the three failure modes, and the four-layer architecture. Start here. |
| [`architecture.md`](./architecture.md) | Technical deep-dive into all four layers: LLM engine, RAG, skill files, Lacerte MCP, Shadow Mode, and the validation loop. |
| [`personas.md`](./personas.md) | The five personas, what they need from ITA 2.0, and which use cases map to each. |

### Context Files (for AI-assisted sessions and PM reference)

| File | What it covers |
|---|---|
| [`context/README.md`](./context/README.md) | Index and purpose of the context/ folder |
| [`context/problem-framing.md`](./context/problem-framing.md) | Full problem framing: client profile pyramid, failure modes in depth, LLM risk areas |
| [`context/design-decisions.md`](./context/design-decisions.md) | Key design decisions and the reasoning behind each |
| [`context/open-questions.md`](./context/open-questions.md) | Open questions and decisions from the PRD, with context on why they remain open |

### Use Cases

| File | What it covers |
|---|---|
| [`usecases/README.md`](./usecases/README.md) | Index of PTG and QBL use cases |

---

## Quick Orientation

- **New to the project?** Read [`ita2-overview.md`](./ita2-overview.md) first, then open `llm-tax-engine-case.html`.
- **Engineer?** Go to [`architecture.md`](./architecture.md) and Section C of the product binder.
- **PM working on personas or use cases?** See [`personas.md`](./personas.md) and `ita2.0-prd.html` (Personas tab).
- **Resuming an AI-assisted session?** Start with [`context/README.md`](./context/README.md).
