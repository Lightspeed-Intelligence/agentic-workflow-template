# Workflow Orchestration

## Purpose

Separate event routing from reusable task execution so consumers can adopt the template without
copying Agent logic.

## Core Components

- `.github/workflows/ci.yml` (`jobs`): local caller that routes Issue, Issue-comment and PR events.
- `.github/workflows/issue-dispatch.yml`: classifies new Issues without modifying code, then publishes an Issue response.
- `.github/workflows/implement.yml`: produces and validates a local candidate commit before an isolated publisher creates or updates a PR.
- `.github/workflows/question.yml`: answers explicit question commands through an isolated publisher.
- `.github/workflows/pr-review.yml`: isolated Codex-primary/Claude-fallback review and publication.
- `.github/workflows/update-llmdoc.yml`: produces and validates an llmdoc-only candidate commit before an isolated publisher creates or updates a PR.
- `.claude/skills/`: task-specific behavior and output contracts.

## Flow

1. A caller repository owns the event trigger and grants the maximum authority any called workflow may use.
2. The reusable workflow narrows authority per job and applies its keyword/draft gate.
3. A prepare job freezes event data and the consumer source SHA. The relevant Skill and shared runner
   come from an immutable template commit; consumers do not distribute template policy.
4. Codex runs first without GitHub write credentials. Process, schema or structured soft failure starts
   Claude Code from the same fixed input in a fresh runner.
5. Pure-answer workflows transfer validated JSON. Code-writing workflows transfer a single-parent Git
   bundle which a separate read-only job validates before publication.
6. Only the terminal `answer`, `dispatch`, `implement`, `update` or `review` job may publish. Stable
   terminal names are part of the downstream ruleset contract.
7. Optional Feishu notification reports the result but is never the source of workflow truth.

## Invariants

- Called-workflow permissions cannot exceed caller permissions; every sensitive job still declares its own minimum.
- Every Agent process is separated from GitHub write authority. Code-writing Agents may edit their
  disposable local checkout, but only a deterministic publisher may push, create PRs or comment.
- `issue-dispatch` is analysis-only. `auto_fix_eligible` may recommend a later `implement` run but never
  authorizes an automatic fix in the dispatch workflow.
- `NO_CHANGES` and genuine `BLOCKED` results are valid domain outcomes; they do not trigger fallback.
- Workflow YAML, action YAML and tracked Skills are executable contracts; README/design/llmdoc must follow them.
- Submodules are optional consumer topology even though checkouts and helper scripts support them.
- A GitHub Actions rerun retains the reusable-workflow revision resolved by the original run. A
  newly merged template fix at a moving ref requires a fresh caller event/run for validation.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/workflow-contracts.md`
