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
  per field to the corresponding `ANTHROPIC_*` secret. Every Claude fallback uses `claude-opus-5`
  and receives only `ANTHROPIC_*`.
- `PAT_TOKEN` is for private-submodule checkout and, in code-writing workflows, the isolated publisher.
  Checkouts disable credential persistence and Agent processes never receive PAT or GitHub tokens.

## Shared Result and Publication Semantics

- `question` Agent output has exactly `description`, `result_status` and `comment_body` before the
  normalizer adds reviewer/model identity. `issue-dispatch` additionally requires exactly
  `issue_type`, `severity`, `cost` and boolean `auto_fix_eligible`; enum/type/extra-field failures occur
  in the Agent job and trigger fallback.
- Pure-answer Agent artifacts require `result_status=COMPLETE`; `INCOMPLETE` triggers the fresh Claude fallback.
- Code-writing results are `READY`, `NO_CHANGES`, `BLOCKED` or `INCOMPLETE`. Only technical/schema/
  validation failure or `INCOMPLETE` triggers fallback; valid `NO_CHANGES` and `BLOCKED` are published as-is.
- `NO_CHANGES` requires a clean root worktree, no untracked files and clean recursive submodule
  worktrees. Dirty state is a candidate failure, not a successful empty artifact.
- `READY` transfers a one-commit Git bundle tied to the frozen base SHA. A no-write validator checks
  checksum, ancestry, paths and an optional base-pinned consumer validator before re-uploading it.
- Any gitlink add/change/delete or dirty submodule worktree becomes `BLOCKED`; the workflow never
  publishes a bundle that silently omits cross-repository work. `update-llmdoc` additionally rejects
  every changed path outside `llmdoc/`.
- Publishers receive validated artifacts but no model key. They do not execute consumer code and use
  stable markers/branches to create or update one comment/PR idempotently.
- Existing Issue comments are updated only when their marker belongs to `github-actions[bot]` acting
  through the `github-actions` App. The publisher alone owns branch names, marker text, `Closes`, push,
  PR creation/editing and Issue comments.
- Final job names remain `answer`, `dispatch`, `implement`, `update` and `review` for downstream rulesets.

## Shared Runtime Pin

`question`, `issue-dispatch`, `implement` and `update-llmdoc` obtain their runner, scripts, Skills and
publisher from one immutable template commit. Consumers do not copy these files. Runtime authoring
changes land first; a following commit advances all workflow refs. The agentic contract test requires
one 40-character ref and byte-for-byte equality between every pinned runtime path and the current tree.

## Submodules

Recursive checkout and `scripts/init.sh`, `scripts/status.sh`, `scripts/update-all.sh` support optional
consumer submodules. Every Agent/validator checkout that needs consumer context uses recursive
submodules with `persist-credentials: false`. This template currently has no tracked `.gitmodules`.

PR-review private cross-repository submodules require `PAT_TOKEN` with read access. The token is used
only by PR-head `actions/checkout`, with credential persistence disabled, and is absent from Agents.
The other four workflows likewise restrict PAT use to consumer checkout and, for code-writing tasks,
the isolated publisher; template-runtime checkout continues to use the job token.

## Sources of Truth

- `.github/workflows/ci.yml`: local triggers and forwarded inputs/secrets.
- Each reusable workflow's `on.workflow_call` and job permissions: callable interface and authority.
- `README.md`: consumer examples; reconcile it when executable contracts change.
