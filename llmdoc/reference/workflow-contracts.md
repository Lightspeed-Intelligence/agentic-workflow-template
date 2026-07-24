# Workflow Contracts

## Reusable Workflows

| Workflow | Local routing | GitHub authority | Agent behavior |
|---|---|---|---|
| `issue-dispatch.yml` | Issue opened | Agents contents read; `dispatch` issues write | Codex primary/Claude fallback analyzes only; authenticated publisher comments |
| `implement.yml` | Issue comment matches implementation keyword | candidates/validators contents read; `implement` contents/issues/PR write | Agent produces a local commit bundle; validator gates deterministic push/PR/comment |
| `question.yml` | Issue comment starts question keyword | Agents contents read; `answer` issues write | Codex primary/Claude fallback returns JSON; authenticated publisher comments |
| `pr-review.yml` | Non-draft PR opened/synchronized/reopened | reviewers read-only; publisher PR write | Codex primary, isolated Claude fallback, artifact publication |
| `update-llmdoc.yml` | External reusable caller only | candidates/validators contents read; `update` contents/PR write | Agent produces an llmdoc-only bundle; validator gates deterministic PR publication |

## Local Caller

`.github/workflows/ci.yml` listens to Issue `opened`, Issue-comment `created`, and PR
`opened/synchronize/reopened`. It does not currently call `update-llmdoc.yml`.

Reusable workflow refs are resolved when a caller run is created. A rerun retains that resolved
revision; after updating a moving ref, use a fresh matching event/run to consume the new revision.

## Secrets

- Required model credential: `ANTHROPIC_API_KEY`.
- Optional: `ANTHROPIC_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `FEISHU_WEBHOOK_TOKEN`.
- Every Codex job resolves optional `OPENAI_API_KEY` and `OPENAI_BASE_URL` independently, falling back
  per field to the corresponding `ANTHROPIC_*` secret. Claude receives only `ANTHROPIC_*`.
- `PAT_TOKEN` is for private-submodule checkout and, in code-writing workflows, the isolated publisher.
  Checkouts disable credential persistence and Agent processes never receive PAT or GitHub tokens.

## Shared Result and Publication Semantics

- Pure-answer Agent artifacts require `result_status=COMPLETE`; `INCOMPLETE` triggers the fresh Claude fallback.
- Code-writing results are `READY`, `NO_CHANGES`, `BLOCKED` or `INCOMPLETE`. Only technical/schema/
  validation failure or `INCOMPLETE` triggers fallback; valid `NO_CHANGES` and `BLOCKED` are published as-is.
- `READY` transfers a one-commit Git bundle tied to the frozen base SHA. A no-write validator checks
  checksum, ancestry, paths and an optional base-pinned consumer validator before re-uploading it.
- Publishers receive validated artifacts but no model key. They do not execute consumer code and use
  stable markers/branches to create or update one comment/PR idempotently.
- Final job names remain `answer`, `dispatch`, `implement`, `update` and `review` for downstream rulesets.

## Submodules

Recursive checkout and `scripts/init.sh`, `scripts/status.sh`, `scripts/update-all.sh` support optional
consumer submodules. This template currently has no tracked `.gitmodules`.

PR-review private cross-repository submodules require `PAT_TOKEN` with read access. The token is used
only by PR-head `actions/checkout`, with credential persistence disabled, and is absent from Agents.

## Sources of Truth

- `.github/workflows/ci.yml`: local triggers and forwarded inputs/secrets.
- Each reusable workflow's `on.workflow_call` and job permissions: callable interface and authority.
- `README.md`: consumer examples; reconcile it when executable contracts change.
