<!-- ==================== GENERAL (do not edit per project) ==================== -->

# AGENTS.md

Behavior guidelines for coding agents working in this repository.
This file defines how to reason, edit, verify, and communicate.

## 1. Core Principles

- Clarity over speed: do not guess on important ambiguity.
- Simplicity over cleverness: choose the simplest solution that fully solves the task.
- Minimal surface area: change as little as necessary.
- Verification over confidence: prove changes work instead of assuming.

## 2. Understand the Task First

Before coding:

- Restate the task in concrete engineering terms.
- State assumptions explicitly.
- If multiple reasonable interpretations exist, present them.
- Ask for clarification when ambiguity affects behavior, APIs, data flow, architecture, or user-visible outcomes.
- For low-risk details, make the smallest reasonable assumption and state it.

## 3. Read Before You Write

Before editing:

- Read the relevant files and nearby code paths.
- Look for existing helpers, utilities, and patterns before creating new ones.
- Check whether tests already cover the behavior being changed.
- Match the local style and conventions.

Do not invent a new pattern when an adequate existing one already exists.

## 4. Keep It Simple

Prefer:

- direct implementations
- local changes
- existing utilities
- explicit code over premature abstraction

Avoid:

- speculative generalization
- single-use abstractions unless they clearly improve readability
- new configuration that was not requested
- over-engineering for hypothetical future needs

## 5. Make Surgical Changes

Only change code directly relevant to the task.

Do:

- keep diffs focused
- preserve existing architecture unless the task requires otherwise
- remove imports or code made unused by your own changes

Do not:

- refactor adjacent code without being asked
- rename symbols for style only
- reformat unrelated code
- fix unrelated bugs in the same change
- delete pre-existing dead code unless asked

Every changed line should trace directly to the request.

## 6. Know When to Ask

Ask before proceeding if the task would require:

- non-obvious changes to public behavior or APIs
- data model or persistent format changes
- a new dependency
- architectural or cross-cutting refactors
- high-risk or irreversible changes
- acting on unclear product intent

Do not ask about trivial details that can be resolved from context and local conventions.

## 7. Verify the Result

Turn the request into a checkable outcome.

Examples:

- fix a bug -> reproduce it, change the code, verify it is gone
- add validation -> add or update tests, then make them pass
- refactor -> preserve behavior and verify equivalence where possible

Do not claim success without verification.
If verification is incomplete or impossible, say so clearly.

## 8. Plan for Non-Trivial Work

For multi-step tasks, provide a brief plan:

1. [step]
   - verify: [check]
2. [step]
   - verify: [check]

Keep plans short and practical.

## 9. Communicate Clearly

When reporting work:

- state assumptions
- describe exactly what changed
- mention important tradeoffs
- separate facts from guesses
- say what was verified and what was not

Do not hide uncertainty or imply checks that did not happen.

## 10. Default Output Structure

For coding tasks, use this order when helpful:

- Understanding
- Plan
- Changes
- Verification
- Open Questions / Risks

## 11. Good Agent Behavior

A good agent:

- asks before making meaningful assumptions
- avoids unnecessary complexity
- keeps changes narrow and relevant
- follows existing patterns
- verifies outcomes instead of guessing
- communicates clearly about assumptions, changes, and risks
<!-- ==================== PROJECT-SPECIFIC RULES (TradePilot) ==================== -->

## 12. TradePilot Project Rules

- This project is a contract-first backend for structured US stock analysis.
- Keep the existing stack and layering stable: `FastAPI` + `Pydantic v2` + `LangGraph` + provider adapters + `PostgreSQL`.
- Prefer reading `docs/zh/design/*` and `docs/zh/implementation/*` before changing behavior that is already documented.

### 12.1 Contract Sources of Truth

- Treat `app/schemas/api.py` as the public API contract source of truth.
- Treat `app/schemas/graph_state.py:TradePilotState` as the semantic runtime state source of truth.
- Treat `app/graph/builder.py` as the execution source of truth for node order and reducer behavior.
- If code, docs, and tests disagree, do not guess. Read the matching implementation doc and the nearest tests, then align the smallest possible surface.

### 12.2 Fixed Runtime Shape

- Keep the main request flow fixed unless the task explicitly requires changing runtime architecture:
  `validate_request -> prepare_context -> run_technical/run_fundamental/run_sentiment/run_event -> synthesize_decision -> generate_trade_plan -> assemble_response -> persist_analysis`.
- Do not add hidden side paths, background jobs, or implicit state passing.
- `persist_analysis` is part of the main request path, not a best-effort async task.
- Do not add new business endpoints, loosen the request shape, or expand `AnalyzeRequest` beyond `ticker` unless explicitly requested.

### 12.3 Layer Responsibilities

- Put deterministic business rules in `app/analysis/`.
- Put orchestration and state wiring in `app/graph/` and `app/graph/nodes/`.
- Put external API adaptation, DTO mapping, timeout, and provider-specific parsing in `app/services/providers/`.
- Put persistence mapping in `app/repositories/` and SQL/migrations in `app/db/`.
- Do not move scoring, conflict resolution, or trade-plan branching into providers, repositories, or the API layer.

### 12.4 Analysis and Synthesis Boundaries

- The four analysis modules are peers. They must not depend on each other's conclusions as inputs.
- Cross-module weighting, conflict handling, and blocking logic belong only in `synthesize_decision`.
- `generate_trade_plan` must consume `decision_synthesis`; it must not recompute overall direction.
- Preserve fixed module ordering where relevant: `technical`, `fundamental`, `sentiment`, `event`.

### 12.5 Degrade Instead of Smearing Failures

- For provider-backed module failures or missing upstream data, prefer module `degraded`/`excluded` behavior over ad hoc API changes.
- Do not silently degrade validation, context preparation, response assembly, or persistence nodes.
- Preserve diagnostics updates (`degraded_modules`, `excluded_modules`, `warnings`, `errors`) and avoid duplicate markers.
- Keep source aggregation deterministic: deduplicate and preserve the builder-defined ordering.

### 12.6 Editing and Verification Rules for This Repo

- Match the existing implementation style: small synchronous node functions, explicit Pydantic validation, and narrow helper functions.
- Reuse existing DTOs, enums, and module result models before introducing new shapes.
- Do not add dependencies, new config knobs, or schema fields unless the task requires them.
- Use `uv` for local commands and `pytest` for verification.
- When changing:
  - analysis rules: update focused rule or node tests
  - public schemas or response shape: update schema/API tests
  - graph flow or node contracts: update graph/node tests
  - persistence or migrations: update repository/DB tests
- Prefer deterministic tests with local fixtures and no network access.
