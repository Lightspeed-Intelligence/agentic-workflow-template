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

All five workflows obtain their runner, scripts, Skills, reviewer policy and publisher from one
immutable template commit. Consumers do not copy these files. Runtime authoring changes land first; a
following commit advances all workflow refs. Both contract tests require one 40-character ref per
workflow and byte-for-byte equality between every pinned runtime path and the current tree.

## Environment Setup Hook

Every workflow accepts optional `setup_script`, a normalized repository-relative path of
`[A-Za-z0-9._/-]` characters. Empty is a no-op; a missing declared file warns and continues; an
existing file runs bounded by the script's own 13-minute `timeout` (step-level `timeout-minutes: 15` is
a wider backstop) with no secret in its environment.

`pr-review` reads it from the PR base SHA through `.trusted-base`; the other four read it from the
event-pinned consumer checkout. Runtime failure appends the exit code and truncated log tail to the
prompt as untrusted data and does not fail the job or change `INCOMPLETE`/`READY` validation.
Path-validation failure fails the job. Every workflow rejects dirty state the hook itself introduced, so
setup artifacts must be gitignored. The check diffs `git status` porcelain lines against a baseline taken
just before the hook runs, so a calling workflow's own directories inside `repo_dir` (`pr-review`'s
`.trusted-base`/`.trusted-policy`) are not blamed on the hook. Exemption is by status line, not by path
name: a modification to a consumer-**tracked** file under those same paths still fails.

The baseline is captured only after the hook is known to exist, so a repository that leaves `setup_script`
empty runs no `git` command at all — otherwise an unrelated unusable gitlink would fail a job that does not
use the feature.

Known limits, all bounded by the same trust model as the rest of the hook — owner-maintained configuration,
not a security boundary.

Inherent to `git status` porcelain:

- A directory containing a nested `.git` is reported as a single folded entry (`?? .trusted-policy/`).
  Anything the hook adds, deletes or rewrites **inside** such a directory produces no new porcelain line and
  is therefore undetected. This is the live case in `pr-review`, because `actions/checkout` with `path:`
  creates that nested `.git`. Folding stops if the directory also holds index entries.
- A porcelain line does not encode content, so rewriting a file that was already listed — untracked
  individually, or tracked but already modified — yields the same line and is undetected.

Inherent to the baseline comparison itself:

- Only *added* status entries are reported, so a hook that **deletes** an entry present in the baseline is
  not reported. In a fresh checkout the only such entries are the calling workflow's own directories.
  Deleting a consumer-**tracked** file still produces a new ` D` line and fails.

What remains guarded: any change that produces a *new* status entry, including modification of a
consumer-tracked file anywhere in the tree (exemption keys on status lines, not path names).

`implement` and `update-llmdoc` additionally steer the Agent toward `BLOCKED` when preparation prevented
verification.

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
