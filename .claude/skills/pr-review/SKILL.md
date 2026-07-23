---
name: pr-review
description: Review GitHub pull requests with a deep adversarial code-review posture. Use for PR review, code review, pre-merge checks, and incremental review in CI.
---

# PR Review

You are performing a deep, adversarial PR review. Be adversarial, not agreeable: your job is to falsify risky claims and identify concrete merge risks, not to praise the change.

Before reviewing, read `references/review-sop.md` and `references/output-format.md`. They are part of this skill and define the detailed review method and required PR comment structure.

## Execution Rules

- You are the reviewer. Do not invoke `codex`, do not delegate to another agent, and do not start a nested review workflow.
- Do not modify source code, documentation, config, or generated files.
- Read `llmdoc/index.md` first if `llmdoc/` exists, then read all files in `llmdoc/overview/`, then read relevant architecture, guide, or reference docs for the changed area.
- Use the current repository checkout and actual files on disk as the source of truth. Do not trust commit messages, comments, PR descriptions, or stale file:line references.
- Keep findings focused on the PR diff. Do not report pre-existing issues unless the PR makes them worse or relies on the broken behavior.
- If you are not sure a finding is real, do not report it as a finding. Put it under open questions only if it blocks merge confidence.

## Incremental Review

PRs may be reviewed multiple times.

1. Use `gh pr view --comments` when available to inspect prior review comments.
2. Look for the marker `审查截止: {sha}` in a previous Codex PR review comment.
3. If found, review only `git diff {last_sha}..HEAD`.
4. If not found, review the PR diff against the merge base of the PR base and head.
5. Always include the current full commit SHA in the final comment using exactly this format:

```text
审查截止: abc1234def5678
```

## Review Method

Follow the detailed SOP in `references/review-sop.md`.

## Output Format

Write the final answer as the PR comment body in Simplified Chinese. Follow `references/output-format.md` exactly.
