# PR Review Trust Boundary

## Purpose

Allow deep local code analysis while preventing model-driven processes from writing to GitHub.

## Runtime Flow

```text
pull_request event
  -> deterministic preparation: authenticate structured Bot history, select full/incremental range
  -> codex_review: read-only token, full local execution, gpt-5.6-sol
  -> on process/schema/soft failure: independent claude_review, read-only token, claude-opus-4-8
  -> one-day structured artifact
  -> publish: deterministic validation, pull-requests: write, gh pr comment
  -> optional Feishu notification
```

## Trust Classes

- Trusted reviewer policy: immutable template-repository revision checkout of `pr-review/SKILL.md`,
  `review-sop.md`, `output-format.md` and `github-comment/SKILL.md` into sanitized `.trusted-policy`.
- Consumer repositories do not need to copy the split reviewer policy files. Their exact base-SHA
  checkout in `.trusted-base` supplies only the optional history-preparation script.
- History-preparation code comes only from the consumer base-SHA checkout. If the script is absent from
  base, no PR-head preparation code runs; deterministic workflow commands select a complete
  `base...head` review without historical state.
- Reviewed/untrusted data: PR metadata, commits, full head checkout, docs, selected diff and historical comment body.
- Trusted control data: publisher-generated state marker from the latest `github-actions` App comment,
  accepted only after schema, count, SHA and ancestry validation by the deterministic preparation step.
- Cross-boundary message: schema-conforming reviewer artifact; it is data, not executable shell.
- Write authority: only the non-Agent publisher job.

## Credential Invariants

- `codex_review` and `claude_review`: only `contents: read` and `pull-requests: read`.
- Reviewer PR-head checkouts may use optional `PAT_TOKEN` to read cross-repository private
  submodules and use `persist-credentials: false`; trusted-policy checkout and preparation use the
  read-only job token. Agent processes receive model credentials but no GitHub/PAT token.
- Codex prefers optional `OPENAI_API_KEY` and `OPENAI_BASE_URL`; each missing value independently
  falls back to its `ANTHROPIC_*` counterpart. Claude receives only the `ANTHROPIC_*` pair.
- `PAT_TOKEN` is forwarded by callers only for checkout, with `github.token` as the fallback.
- Only PR-head checkout may use that PAT fallback. Consumer-base history and immutable template-policy
  checkouts use `github.token`; all checkout credentials are removed before Agent execution.
- `publish`: receives GitHub PR-write authority and optional Feishu webhook, but no model key and no PR-head checkout.

## Local Privilege

Both reviewers intentionally have broad local shell/filesystem/test access on disposable runners.
Codex bypasses approvals and its local sandbox because hosted-runner bubblewrap can fail while
configuring loopback before review starts. Claude runs `--bare` from a temporary root and bypasses
permission prompts. These flags are not the GitHub boundary; job/token/process isolation is.

`extra_allowed_tools` accepts only normalized repository-relative `git -C` patterns for read-only
subcommands. It is a Claude CLI tool hint for monorepos/submodules, not enforcement: Claude already
has full local access and the input cannot grant GitHub credentials.

## Review and Artifact Invariants

- Default to the complete event-pinned `base.sha...head.sha` diff. Use `cutoff..head` only when the
  prior authenticated state has zero critical/important and 1–3 suggestion findings, and cutoff is
  a strict ancestor of head; otherwise fail closed to full review.
- Publisher appends the machine-readable state marker after model prose; the Agent cannot choose it.
- Codex success requires process success, schema/count validation and structured `review_status=COMPLETE`; `INCOMPLETE` is an exit-zero soft-failure signal.
- `INCOMPLETE` is reserved for inaccessible core review inputs or inability to perform meaningful
  code analysis. An unavailable project-specific test/tool is recorded but is not sufficient alone.
- Claude runs only when the whole Codex job is non-success and uses a fresh runner.
- The artifact includes `comment_body`; public `structured_output` removes it but retains reviewer/model identity.
- Publisher revalidates `review_status=COMPLETE`, type, length, count/conclusion semantics and the reviewer/model pair before commenting.

## Residual Risks

- Full local execution plus model credentials and network egress is not a general sandbox.
- Fork PRs may not receive required model secrets and therefore can fail before review.
- Publisher validates Markdown size/structure fields, not the semantic truth of prose, mentions or links.
- The `github-actions` App identity is shared by trusted repository workflows; the marker is a
  repository control-plane convention, not cryptographic provenance. Strict marker/schema/ancestry
  validation and full-review fallback limit this residual risk.
- Schema and validation logic are duplicated across reviewer/publisher blocks and must be changed together.
- The immutable policy SHA is manually advanced. Policy source edits do not affect runtime until the
  reusable workflow deliberately pins a revision containing them.

## Sources of Truth

- `.github/workflows/pr-review.yml`: executable ordering, permissions, credentials and validation.
- `.github/scripts/pr-review/prepare-review-history.sh`: base-pinned history authentication and range selection.
- `scripts/test-pr-review-contract.py`: tracked offline truth-table fixtures run by CI.
- `.github/workflows/ci.yml`: local trigger and secret forwarding.
- `.claude/skills/pr-review/`: policy authoring source; runtime uses the exact revision pinned by the workflow.
