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
