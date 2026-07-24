# Codex-First Agentic Workflow Refactor

## Task

Refactor `question`, `issue-dispatch`, `implement`, and `update-llmdoc` so Codex is primary and a
fresh Claude Code job is the fallback. Separate model execution from GitHub write authority, remove
automatic repair from Issue dispatch, preserve terminal job names used by downstream rulesets, and
keep existing consumers working without copying template runtime files.

## Expected vs Actual

- Expected: introduce a shared Agent runner, put Codex before Claude, and retain the existing
  publisher behavior.
- Actual: pure answers and code-writing tasks required different cross-job contracts. The former can
  transfer exact-schema JSON; the latter need a single-parent Git bundle, a separate validator, and a
  deterministic publisher that never executes consumer code.
- Expected: immutable template runtime checkout would be a straightforward pin.
- Actual: a workflow cannot pin runtime changes contained in its own uncommitted tree. Runtime fixes
  and pin advancement therefore require two commits, with a tracked test comparing pinned bytes to
  the authoring tree.

## What Went Wrong

### Fallback decisions were initially too shallow

- A generic answer normalizer checked only common fields, so an incomplete Issue-dispatch result
  could make the Codex job succeed and prevent Claude fallback, then fail only in the publisher.
- `NO_CHANGES` was initially accepted before checking the actual worktree, allowing an Agent to leave
  tracked, untracked, or submodule changes that were silently discarded.
- The correction is to validate the complete task-specific schema and worktree semantics before the
  primary job is considered successful.

### Submodule behavior must be end-to-end

- Checking only staged gitlink changes missed dirty submodule worktrees.
- Checking only one raw-diff mode missed gitlink deletion.
- `update-llmdoc` initially omitted recursive submodule checkout in five consumer-context jobs even
  though its contract promised submodule awareness.
- Checkout, packaging, validation, publication, tests, and documentation must describe the same
  submodule topology. This workflow intentionally blocks submodule changes rather than publishing a
  partial cross-repository result.

### Publisher identity and ownership need deterministic rules

- Stable comment markers are insufficient unless existing comments are also restricted to
  `github-actions[bot]` acting through the `github-actions` App.
- The Agent and publisher initially both owned the `Closes` sentence, which could duplicate it.
- A deterministic publisher must own marker selection, idempotency, branch naming, closing syntax,
  push and PR/comment side effects. Agent prose remains untrusted data.

### Compatibility includes names and release timing

- Downstream rulesets can bind the terminal job names, so descriptive renames are breaking changes.
  The terminal jobs remain `answer`, `dispatch`, `implement`, `update`, and `review` even when they
  now perform deterministic publication rather than model work.
- Existing consumers may have no template-owned Skill or helper files. Those files must come from an
  immutable template checkout; consumer-base files are used only for explicitly consumer-owned
  compatibility hooks.
- A GitHub Actions rerun retains the old reusable-workflow revision. A merged fix needs a fresh caller
  event before it can prove the new moving ref works.

### Review evidence needs its own schema

- The code converged to zero findings, but two early blind reports omitted canonical reviewer task
  and explicit fork/inherited-turn fields even though their manifests and preflights recorded them.
- The terminal audit correctly classified this as evidence completeness rather than a code defect.
  The original reviewers added explicitly retrospective attestations without rewriting frozen
  reports, and one bounded terminal re-audit accepted the combined evidence.
- Every future reviewer packet should require run ID, canonical task path, fixed snapshot/range,
  `fork_turns`, `inherited_turns`, and allowed/forbidden inputs in the report itself from the start.

## What Worked

- Separating model credentials/local execution from GitHub write authority made both primary and
  fallback replaceable without giving either Agent a repository write token.
- Exact structured soft-failure states let genuine `BLOCKED` and `NO_CHANGES` outcomes publish while
  technical/schema/validation failures trigger a fresh fallback.
- A tracked offline contract harness caught runtime-pin drift, permission drift, malformed results,
  dirty worktrees, gitlink edge cases, duplicate publisher ownership, and stable terminal job names.
- Batching findings, reviewing only changed increments, and allowing one terminal evidence repair
  avoided repeating full code review on an unchanged tree.

## Promotion Candidates

- `llmdoc/architecture/workflow-orchestration.md`: distinguish JSON and Git-bundle flows and document
  the two-commit immutable-runtime release boundary.
- `llmdoc/reference/workflow-contracts.md`: record exact schema/worktree/submodule/publisher contracts.
- `llmdoc/guides/change-and-validate-workflows.md`: add the agentic contract harness, runtime repin
  sequence, stable-job-name check, and required reviewer metadata.
- `llmdoc/memory/doc-gaps.md`: remove assumptions invalidated by the tracked update-llmdoc Skill and
  caller-visible outputs while keeping the unresolved bootstrap/integration gaps explicit.
