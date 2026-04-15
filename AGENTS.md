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
