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
4. After task inputs are frozen, an optional consumer-declared `setup_script` may prepare language
   runtimes and dependencies. Codex runs first without GitHub write credentials. Process, schema or
   structured soft failure starts Claude Code with `claude-opus-5` from the same fixed input in a
   fresh runner.
5. Pure-answer workflows transfer validated JSON. Code-writing workflows transfer a single-parent Git
   bundle which a separate read-only job validates before publication.
6. Only the terminal `answer`, `dispatch`, `implement`, `update` or `review` job may publish. Stable
   terminal names are part of the downstream ruleset contract.
7. Optional Feishu notification reports the result but is never the source of workflow truth.

## Result Flows

### Pure answers

`question` and `issue-dispatch` normalize the primary result against their complete task-specific
schema before upload. A missing field, wrong type, extra field or structured `INCOMPLETE` result
makes the primary job fail and starts Claude from the original fixed input. The publisher accepts
only `COMPLETE` JSON, authenticates an existing marker comment by Bot and App identity, and removes
the comment body from caller-visible output.

### Code-writing tasks

`implement` and `update-llmdoc` package a `READY` worktree as exactly one child commit of the frozen
base and transfer it in a Git bundle. A separate read-only job verifies checksum, ancestry, changed
paths, gitlink policy and an optional base-pinned consumer validator. The publisher receives only the
validated artifact, operates in a bare repository, and does not execute consumer code.

`NO_CHANGES` is accepted only when the root and recursive submodule worktrees are clean. `BLOCKED`
may describe a deliberate inability to publish, including any submodule change; neither outcome
contains a candidate bundle or triggers fallback.

## Immutable Runtime Release

All five workflows use one full template commit SHA for their shared runner, scripts, Skills, reviewer
policy, publisher and notification action. Runtime changes use two commits: first commit the runtime
bytes, then advance every workflow pin to that commit. `scripts/test-agentic-workflow-contract.py` and
`scripts/test-pr-review-contract.py` compare each pinned runtime file with the authoring tree so a
stale or split pin cannot pass CI.

## Environment Setup Hook

Every workflow accepts an optional `setup_script` path. Empty means no-op; a declared path missing from
the trusted source warns and continues; an existing file runs bounded by the script's own 13-minute
`timeout`, with a step-level `timeout-minutes: 15` as a wider backstop. The script bounds itself because
a step-level timeout kills the process tree and would bypass the non-fatal degradation branch.

The script is read from a trusted source — PR base SHA for `pr-review`, the event-pinned consumer
checkout for the others — so the current change cannot edit the script itself. It still reads
worktree data, so dependency manifests remain an execution path; the pinned source is not a boundary.
The step receives no secret because it can export `GITHUB_ENV` to later steps holding the model key.

Runtime failure is non-fatal: exit code and truncated log tail are appended to the prompt as untrusted
data and the Agent discloses which verification it could not perform. Path-validation failure and, for
code-writing flows, a dirty worktree are configuration errors that fail the job.

## Invariants

- Called-workflow permissions cannot exceed caller permissions; every sensitive job still declares its own minimum.
- Every Agent process is separated from GitHub write authority. Code-writing Agents may edit their
  disposable local checkout, but only a deterministic publisher may push, create PRs or comment.
- `issue-dispatch` is analysis-only. `auto_fix_eligible` may recommend a later `implement` run but never
  authorizes an automatic fix in the dispatch workflow.
- `NO_CHANGES` and genuine `BLOCKED` results are valid domain outcomes; they do not trigger fallback.
- Complete task-specific schema and worktree checks happen before a primary Agent job is considered
  successful; publisher-only rejection must not suppress fallback.
- Gitlink add/change/delete and dirty recursive submodule worktrees are never silently truncated into
  a publishable root-repository bundle.
- Setup-hook artifacts never enter a candidate bundle. `implement` and `update-llmdoc` assert a clean
  worktree right after the hook, before the Agent runs, because `package-change-result.sh` would
  otherwise `git add -A` a tracked lockfile change or an unignored artifact into the candidate commit.
- Publisher-owned comments are matched only when both `github-actions[bot]` and the `github-actions`
  App identity agree with the stable marker.
- Workflow YAML, action YAML and tracked Skills are executable contracts; README/design/llmdoc must follow them.
- Submodules are optional consumer topology even though checkouts and helper scripts support them.
- A GitHub Actions rerun retains the reusable-workflow revision resolved by the original run. A
  newly merged template fix at a moving ref requires a fresh caller event/run for validation.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/workflow-contracts.md`
