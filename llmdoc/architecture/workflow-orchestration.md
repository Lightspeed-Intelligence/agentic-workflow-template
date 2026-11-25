# Workflow Orchestration

## Purpose

Separate event routing from reusable task execution so consumers can adopt the template without
copying Agent logic.

## Core Components

- `.github/workflows/ci.yml` (`jobs`): consumer caller that routes Issue, Issue-comment and PR events
  to this repository's reusable workflows at `@main`. Every job is skipped when the repository is a template.
- `.github/workflows/template-ci.yml`: the same routing with local `uses: ./...` calls plus the contract
  tests, run only in a template repository, so workflow changes are exercised by their own PR.
- `.github/workflows/template-cleanup.yml` with `.github/template/cleanup.sh`: template bootstrap, see below.
- `.github/workflows/issue-dispatch.yml`: classifies new Issues without modifying code, then publishes an Issue response.
- `.github/workflows/implement.yml`: produces and validates a local candidate commit before an isolated publisher creates or updates a PR.
- `.github/workflows/question.yml`: answers explicit question commands through an isolated publisher.
- `.github/workflows/pr-review.yml`: isolated Claude-primary/Codex-fallback review and publication.
- `.github/workflows/update-llmdoc.yml`: produces and validates an llmdoc-only candidate commit before an isolated publisher creates or updates a PR.
- `.claude/skills/`: task-specific behavior and output contracts.

## Flow

1. A caller repository owns the event trigger and grants the maximum authority any called workflow may use.
2. The reusable workflow narrows authority per job and applies its keyword/draft gate.
3. A prepare job freezes event data and the consumer source SHA. The relevant Skill and shared runner
   come from an immutable template commit; consumers do not distribute template policy.
4. After task inputs are frozen, an optional consumer-declared `setup_script` may prepare language
   runtimes and dependencies. Claude Code with `claude-opus-5-5` runs first without GitHub write
   credentials. Process, schema or structured soft failure starts Codex with `gpt-6.1-sol` from the same
   fixed input in a fresh runner.
5. Pure-answer workflows transfer validated JSON. Code-writing workflows transfer a single-parent Git
   bundle which a separate read-only job validates before publication.
6. Only the terminal `answer`, `dispatch`, `implement`, `update` or `review` job may publish. Stable
   terminal names are part of the downstream ruleset contract.
7. Optional Feishu notification reports the result but is never the source of workflow truth.

## Result Flows

### Pure answers

`question` and `issue-dispatch` normalize the primary result against their complete task-specific
schema before upload. A missing field, wrong type, extra field or structured `INCOMPLETE` result
makes the primary job fail and starts Codex from the original fixed input. The publisher accepts
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
data and the Agent discloses which verification it could not perform. Path-validation failure and any dirty
state the hook itself introduced are configuration errors that fail the job, in every workflow. The check
compares against a baseline captured before the hook runs, so state that already existed — including
directories the calling workflow created inside `repo_dir` — is not attributed to the hook.

## Template Bootstrap

GitHub copies every file on the default branch when a repository is created from a template and offers
no exclude list. The template therefore cleans itself in the new repository instead of asking users to
copy a caller by hand or maintaining a second, thin template repository.

1. The creation commit raises a `push` event in the new repository. `template-cleanup.yml` runs when
   the repository is neither a template nor a fork and the ref is the default branch.
2. On `push` it proceeds only when the branch has exactly one commit — the shape template creation
   produces. A mirror or a repository that already gained commits is left untouched; cleanup can then be
   started with `workflow_dispatch` and the literal confirmation `cleanup`.
3. `cleanup.sh` refuses a dirty worktree or an incomplete template copy, removes every tracked file
   outside its keep list, and writes the README skeleton. The workflow commits and pushes with the job
   token; pushes made with that token do not start further workflow runs.

The job token may delete workflow files but may not create or update them. `ci.yml` must therefore
already be the final consumer file inside the template, and the template's own routing has to live in a
separate file that cleanup deletes. `github.event.repository.is_template` keeps the two mutually
exclusive: `ci.yml` jobs require it false, `template-ci.yml` jobs require it true.

## Invariants

- `ci.yml` and `template-ci.yml` job bodies are identical except for the call target and the
  `is_template` condition; `scripts/test-agentic-workflow-contract.py` compares them line by line.
- A file added to this repository is template-only unless `cleanup.sh` lists it in `keep`.
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
- Setup-hook artifacts that produce a new `git status` entry never reach an Agent. Every workflow compares
  worktree state before and after the hook, right before the Agent runs, and fails on anything the hook
  added. This is not an absolute guarantee: `llmdoc/reference/workflow-contracts.md` enumerates the cases
  that escape detection, notably writes inside a folded nested-`.git` directory. Those are bounded by the
  hook's trust model — owner-maintained configuration, not a security boundary — and the Agent does receive
  the workspace, so a determined owner-authored hook can still influence it.
  What the check does prevent: in `implement`/`update-llmdoc` residue would otherwise be `git add -A`'d into
  the candidate commit; in `issue-dispatch` a post-Agent cleanliness assertion would fail both the primary
  and the fallback at the same point, yielding no answer at all; in `question`/`pr-review` the Agent would
  analyse a checkout that has drifted from the pinned SHA.
- Publisher-owned comments are matched only when both `github-actions[bot]` and the `github-actions`
  App identity agree with the stable marker.
- Workflow YAML, action YAML and tracked Skills are executable contracts; README/design/llmdoc must follow them.
- Submodules are optional consumer topology even though checkouts and helper scripts support them.
- A GitHub Actions rerun retains the reusable-workflow revision resolved by the original run. A
  newly merged template fix at a moving ref requires a fresh caller event/run for validation.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/workflow-contracts.md`
