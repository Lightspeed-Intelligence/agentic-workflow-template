# PR Review Contract

## Fixed Runtime

- Primary: `@openai/codex@0.145.0`, model `gpt-5.6-sol`.
- Fallback: `@anthropic-ai/claude-code@2.1.148` package wrapper, model `fable-5`.
- Reviewer timeouts: 45 minutes each; publisher runs only after reviewer jobs settle.

## Inputs and Secrets

- `use_feishu_notify` boolean, default `true`.
- `extra_allowed_tools` comma-separated Claude tool patterns; only normalized repository-relative
  `git -C` plus `diff`, `log`, `show`, `status`, `rev-parse`, `merge-base` or `ls-files`.
- `ANTHROPIC_API_KEY` required; `ANTHROPIC_BASE_URL` optional.
- `OPENAI_API_KEY` and `OPENAI_BASE_URL` optional. Codex resolves each independently as
  `OPENAI_*` first, then the corresponding `ANTHROPIC_*` value; Claude always uses `ANTHROPIC_*`.
- Feishu webhook optional.
- `PAT_TOKEN` optional for PR-head checkout of cross-repository private submodules. Both reviewer
  checkouts resolve `PAT_TOKEN || github.token`, disable credential persistence, and never inject
  PAT into an Agent process.

## Artifact Schema

```text
description        non-empty single line, <= 500 characters
review_status      COMPLETE | INCOMPLETE
conclusion         APPROVE | REQUEST_CHANGES | COMMENT
critical_count     non-negative integer
important_count    non-negative integer
suggestion_count   non-negative integer
comment_body       non-empty Markdown, <= 60000 characters
reviewer/model     codex/gpt-5.6-sol | claude/fable-5
```

`APPROVE` requires all counts zero. `REQUEST_CHANGES` requires critical or important nonzero.
`COMMENT` requires critical and important zero; suggestions may be zero for an open question.
Only `COMPLETE` is publishable. `INCOMPLETE` is a structured soft failure even when the Agent process exits zero.

## Review Range and History

- Reviewer Skill/SOP/output policy comes from immutable template revision
  `dbf05344dfc582d63a18442f81a370926a445700`, not from the consumer repository. Consumer bases may
  therefore use older/no split policy layout without breaking review.
- History preparation uses only the base-SHA script. When base has no copy, deterministic workflow
  commands generate full `base...head` inputs with reason `trusted_preparation_unavailable`; PR-head
  preparation code is never executed.
- Publisher appends `<!-- pr-review-state:v1:<base64-json> -->` after the model comment, containing
  head SHA, conclusion, counts, reviewer and model.
- Preparation accepts only the latest marker from a `github-actions[bot]` comment whose GitHub App
  slug is `github-actions`, validates marker schema/counts and requires cutoff to be a strict ancestor.
- Incremental mode requires prior `critical_count=0`, `important_count=0` and
  `1 <= suggestion_count <= 3`; it reviews `cutoff..head` and reconciles every prior finding.
- Missing, malformed, stale, current-head, non-ancestor, zero-finding, important-finding or more-than-three-small-finding state selects full `base...head` review.
- The historical body remains untrusted data. The Agent receives `review-history.json`, never the GitHub token.

## Reusable Workflow Resolution

- A new caller run that references `@main` resolves the then-current template commit.
- Re-running an existing Actions run reuses the template commit resolved by its original attempt;
  it does not pick up later changes to `main`.
- Validate a merged template fix with a fresh PR event/new run, not with **Re-run jobs** on the old run.

## Artifacts and Output

- Reviewer artifacts: `review-result-codex` or `review-result-claude`, path `review-output/review.json`, overwrite enabled, one-day retention.
- Public reusable output deletes `comment_body` and preserves review status, description, conclusion, counts, reviewer and model.
- Publication uses a body file; model/PR text is not interpolated into shell commands.

## Failure Semantics

- Any Codex job non-success, including structured `review_status=INCOMPLETE`, triggers Claude.
- `INCOMPLETE` means core diff/worktree/context is inaccessible or meaningful code review cannot be
  performed. A project-specific test unavailable because of runner tooling is disclosed, not alone fatal.
- Findings are successful review results; `REQUEST_CHANGES` does not trigger fallback.
- If neither reviewer succeeds, notification may run but the publisher job ultimately fails.
- Feishu is best effort and cannot turn a failed review into success or a successful review into failure.

## Sources of Truth

- `.github/workflows/pr-review.yml`
- `.github/scripts/pr-review/prepare-review-history.sh`
- `scripts/test-pr-review-contract.py`
- `.claude/skills/pr-review/SKILL.md`
- `.claude/skills/pr-review/references/review-sop.md`
- `.claude/skills/pr-review/references/output-format.md`
