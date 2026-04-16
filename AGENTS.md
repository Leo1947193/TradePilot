<!-- ==================== GENERAL (do not edit per project) ==================== -->

## Core Principles

- **Clarity first**: If requirements are unclear or ambiguous, ask before writing any code. Never guess intent.
- **Simplicity first**: Always choose the simplest viable solution. Complexity requires explicit justification.
- **Readability**: Code must be immediately understandable by both humans and AI. Prefer clarity over cleverness.
- **DRY**: Do not repeat yourself. Before writing new code, search for existing implementations.
- **No unnecessary dependencies**: Do not introduce new libraries or frameworks unless explicitly requested or clearly justified.
- **Follow conventions**: Adhere to established language and framework conventions for the current stack.

## Behavior Boundaries

**Always do:**
- Add or update tests for every change, even if not asked.
- Use meaningful names that reflect domain concepts, not technical implementation details.
- Keep changes small and focused. One logical change per task.
- After completing a task, briefly summarize what was changed and why.

**Ask first:**
- Before refactoring code that wasn't part of the original request.
- Before adding new dependencies.
- Before making changes across more than 3 files.
- Before changing any interface, API contract, or database schema.

**Never do:**
- Hard-code secrets, API keys, credentials, or environment-specific values.
- Delete or disable failing tests instead of fixing them.
- Modify files in vendor/, dist/, or build/ directories.
- Make changes outside the scope of the current task without flagging it.

## Code Style

- Prefer explicit over implicit.
- Write comments that explain *why*, not *what*. Avoid comments that just paraphrase the code.
- Keep functions small and single-purpose.
- Prefer returning early over deep nesting.

## Change Discipline

- Before starting, briefly confirm your understanding of the task.
- Make the smallest change that solves the problem.
- If you notice an unrelated issue while working, flag it rather than silently fixing it.
- Do not silently regenerate or reorganize existing working code.

## Security

- Never commit secrets or credentials in any form.
- Sanitize all user inputs. Never trust external data.
- When in doubt about security implications, flag it and ask.

## Git

- Write clear, descriptive commit messages. Preferred format: `<type>: <short summary>` (e.g. `fix: handle null case in user lookup`).
- Each commit should represent one logical change.

<!-- ==================== PROJECT-SPECIFIC RULES (TradePilot) ==================== -->

## Project-Specific Rules

- Treat `docs/zh/api/openapi.yaml` as the public API source of truth.
- Before changing architecture or runtime behavior, also check `docs/zh/design/system-architecture.md`, `docs/zh/implementation/implementation-stack.md`, `docs/zh/implementation/runtime-contract.md`, and `docs/zh/implementation/data-sources.md`.
- This project is V1 of a backend-only US stock analysis service. Do not add frontend pages, admin panels, or trading execution flows.
- The product is a decision-support tool, not an auto-trading system.
- Optimize for deterministic, explainable JSON output for a holding window of `1 week` to `3 months`.

- Fixed stack for V1:
  - `Python 3.11`
  - `FastAPI` + `Uvicorn`
  - `Pydantic v2`
  - `LangGraph`
  - `PostgreSQL` + `psycopg v3` + `psycopg_pool`
  - `httpx`
  - `pytest` + `pytest-asyncio`
  - `uv` for dependency and virtualenv management
- Do not introduce `ORM`, `Redis`, `Celery`, `WebSocket`, `SSE`, `Poetry`, or `pipenv` unless explicitly approved.

- V1 exposes exactly one business endpoint: `POST /api/v1/analyses`.
- The request is synchronous and must return the full JSON result in one response.
- Do not add `job_id`, polling endpoints, background jobs, streaming responses, or public module-level debug endpoints without approval.
- The external API accepts only the documented contract; do not add extra request fields casually.
- Public API enums should remain lowercase. Time values must use `UTC` and `ISO 8601`.

- Required module flow: `validate_request -> prepare_context -> parallel analysis modules -> synthesize_decision -> generate_trade_plan -> assemble_response -> persist_analysis`.
- The four core analysis modules are `technical`, `fundamental`, `sentiment`, and `event`.
- Cross-module weighting and conflict resolution are only allowed in the decision synthesis layer.
- Trading-plan generation must consume system-level outputs; it must not recompute overall bias.

- Keep layer boundaries strict:
  - `app/api`: HTTP transport, validation, and error mapping only
  - `app/graph`: orchestration only, no business scoring rules
  - `app/analysis`: deterministic analysis and scoring rules
  - `app/services/providers`: fetch and normalize external data only, never make trading decisions
  - `app/repositories`: persistence only, never analysis logic
- Do not expose LangGraph state, checkpoint IDs, internal runtime IDs, or node internals in public responses.

- Provider integrations must be behind explicit interfaces before concrete implementations are added.
- Default V1 providers are `yfinance` for market/financial/company-event basics, a news REST provider such as `Finnhub`, and a repository-managed static macro calendar provider.
- Provider outputs must be normalized into internal DTOs; analysis modules must not consume raw third-party payloads directly.
- If a provider is missing or fails, follow the documented degrade/fail rules instead of guessing values.

- Only the four analysis modules may degrade. `validate_request`, `prepare_context`, `assemble_response`, and `persist_analysis` must fail the request if they fail.
- A successful `200` response requires both a valid top-level response and successful PostgreSQL persistence.
- External fetches may retry once with short backoff; database writes and internal rule errors must not be retried automatically.
