# PR Review Contract

## Fixed Runtime

- Primary: `@openai/codex@0.145.0`, model `gpt-5.6-sol`.
- Fallback: `@anthropic-ai/claude-code@2.1.148` package wrapper, model `fable-5`.
- Reviewer timeouts: 45 minutes each; publisher runs only after reviewer jobs settle.

## Inputs and Secrets

- `use_feishu_notify` boolean, default `true`.
- `extra_allowed_tools` comma-separated Claude tool patterns; only normalized repository-relative
  `git -C` plus `diff`, `log`, `show`, `status`, `rev-parse`, `merge-base` or `ls-files`.
- `ANTHROPIC_API_KEY` required; base URL and Feishu webhook optional.
- `PAT_TOKEN` optional declaration for compatibility, with zero workflow references.

## Artifact Schema

```text
description        non-empty single line, <= 500 characters
conclusion         APPROVE | REQUEST_CHANGES | COMMENT
critical_count     non-negative integer
important_count    non-negative integer
suggestion_count   non-negative integer
comment_body       non-empty Markdown, <= 60000 characters
reviewer/model     codex/gpt-5.6-sol | claude/fable-5
```

`APPROVE` requires all counts zero. `REQUEST_CHANGES` requires critical or important nonzero.
`COMMENT` requires critical and important zero; suggestions may be zero for an open question.

## Artifacts and Output

- Reviewer artifacts: `review-result-codex` or `review-result-claude`, path `review-output/review.json`, overwrite enabled, one-day retention.
- Public reusable output deletes `comment_body` and preserves description, conclusion, counts, reviewer and model.
- Publication uses a body file; model/PR text is not interpolated into shell commands.

## Failure Semantics

- Any Codex job non-success, including explicit environment soft-failure prose, triggers Claude.
- Findings are successful review results; `REQUEST_CHANGES` does not trigger fallback.
- If neither reviewer succeeds, notification may run but the publisher job ultimately fails.
- Feishu is best effort and cannot turn a failed review into success or a successful review into failure.

## Sources of Truth

- `.github/workflows/pr-review.yml`
- `.claude/skills/pr-review/SKILL.md`
- `.claude/skills/pr-review/references/review-sop.md`
- `.claude/skills/pr-review/references/output-format.md`
