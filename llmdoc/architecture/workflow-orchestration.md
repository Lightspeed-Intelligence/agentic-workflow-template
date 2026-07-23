# Workflow Orchestration

## Purpose

Separate event routing from reusable task execution so consumers can adopt the template without
copying Agent logic.

## Core Components

- `.github/workflows/ci.yml` (`jobs`): local caller that routes Issue, Issue-comment and PR events.
- `.github/workflows/issue-dispatch.yml`: classifies new Issues and publishes an Issue response.
- `.github/workflows/implement.yml`: implements approved Issue work and creates a PR.
- `.github/workflows/question.yml`: answers explicit question commands.
- `.github/workflows/pr-review.yml`: isolated Codex-primary/Claude-fallback review and publication.
- `.github/workflows/update-llmdoc.yml`: write-capable reusable llmdoc update workflow for an existing llmdoc tree.
- `.claude/skills/`: task-specific behavior and output contracts.

## Flow

1. A caller repository owns the event trigger and grants the maximum authority any called workflow may use.
2. The reusable workflow narrows authority per job and applies its keyword/draft gate.
3. The Agent reads the caller checkout plus the relevant Skill and returns structured output.
4. Each workflow either publishes directly (write-oriented Issue/implementation tasks) or delegates publication to a deterministic job (PR review).
5. Optional Feishu notification reports the result but is never the source of workflow truth.

## Invariants

- Called-workflow permissions cannot exceed caller permissions; every sensitive job still declares its own minimum.
- PR review has a stricter write boundary than Issue-oriented workflows; do not generalize one policy to all tasks.
- Workflow YAML, action YAML and tracked Skills are executable contracts; README/design/llmdoc must follow them.
- Submodules are optional consumer topology even though checkouts and helper scripts support them.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/workflow-contracts.md`
