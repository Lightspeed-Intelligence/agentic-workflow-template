# Workflow Contracts

## Reusable Workflows

| Workflow | Local routing | GitHub authority | Agent behavior |
|---|---|---|---|
| `issue-dispatch.yml` | Issue opened | contents/issues/PR write | Classifies and directly comments; optional PAT |
| `implement.yml` | Issue comment matches implementation keyword | contents/issues/PR write | Changes code, comments and creates PR; optional PAT |
| `question.yml` | Issue comment starts question keyword | contents read, issues write | Answers and directly comments |
| `pr-review.yml` | Non-draft PR opened/synchronized/reopened | reviewers read-only; publisher PR write | Codex primary, isolated Claude fallback, artifact publication |
| `update-llmdoc.yml` | External reusable caller only | contents/PR write | Updates an existing llmdoc tree and may create a PR |

## Local Caller

`.github/workflows/ci.yml` listens to Issue `opened`, Issue-comment `created`, and PR
`opened/synchronize/reopened`. It does not currently call `update-llmdoc.yml`.

## Secrets

- Required model credential: `ANTHROPIC_API_KEY`.
- Optional: `ANTHROPIC_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `FEISHU_WEBHOOK_TOKEN`.
- The optional `OPENAI_*` pair applies to PR-review Codex only and falls back per value to the
  corresponding `ANTHROPIC_*` secret; other workflows and Claude continue using `ANTHROPIC_*`.
- `PAT_TOKEN` is for write-capable/private-submodule workflows. PR review declares it only for caller compatibility and must never reference or forward it.

## Submodules

Recursive checkout and `scripts/init.sh`, `scripts/status.sh`, `scripts/update-all.sh` support optional
consumer submodules. This template currently has no tracked `.gitmodules`.

## Sources of Truth

- `.github/workflows/ci.yml`: local triggers and forwarded inputs/secrets.
- Each reusable workflow's `on.workflow_call` and job permissions: callable interface and authority.
- `README.md`: consumer examples; reconcile it when executable contracts change.
