---
name: pr-review
description: Review GitHub pull requests with a deep adversarial code-review posture. Use for PR review, code review, pre-merge checks, and incremental review in CI.
---

# PR Review

You are performing a risk-proportional adversarial PR review. Be adversarial about real merge risks — falsify risky claims and surface concrete failure modes — but scale scrutiny to the change's actual risk (see the Risk Tiering section in `references/review-sop.md`). A one-line typo fix and a core-path rewrite must not get the same treatment. Finding nothing on a low-risk PR is a valid, correct outcome; never manufacture findings to look thorough.

Before reviewing, read `references/review-sop.md` and `references/output-format.md`. They are part of this skill and define the detailed review method and required PR comment structure.

## Execution Rules

- You are the reviewer. Do not invoke `codex`, do not delegate to another agent, and do not start a nested review workflow.
- Do not modify source code, documentation, config, or generated files.
- Read `llmdoc/index.md` first if `llmdoc/` exists, then read all files in `llmdoc/overview/`, then read relevant architecture, guide, or reference docs for the changed area.
- Use the current repository checkout and actual files on disk as the source of truth. Do not trust commit messages, comments, PR descriptions, or stale file:line references.
- Keep findings focused on the PR diff. Do not report pre-existing issues unless the PR makes them worse or relies on the broken behavior.
- If you are not sure a finding is real, do not report it as a finding. Put it under open questions only if it blocks merge confidence.

## Incremental Review

PRs may be reviewed multiple times. Later rounds must converge, not spawn a fresh round of findings from each fix. Adopt a cumulative view of the whole PR, not an isolated view of the latest diff.

1. Use `gh pr view --comments` when available to inspect prior review comments.
2. Look for the marker `审查截止: {sha}` in a previous PR review comment, and read the findings that comment raised.
3. Determine what changed: if the marker is found, the new work is `git diff {last_sha}..HEAD`; otherwise it is the PR diff against the merge base of the base and head.
4. Evaluate the new work against the **current full state of the PR**, not the fix diff in isolation. A commit that resolves a prior finding is expected to touch code without adding new observability, tests, or abstractions — do not treat a targeted fix as a fresh surface to mine for template findings.
5. In each round, first reconcile prior findings: for every earlier BLOCKER/MAJOR, state whether it is now resolved, still open, or partially addressed. Only then report genuinely new risks that the new work introduces.
6. Report the complete set of merge risks you can find in one pass. State explicitly whether the listed findings are, to your knowledge, the full set of blocking risks. Do not withhold known issues to surface them in a later round.
7. A new finding in a later round is legitimate only if the new commits actually introduced the risk (new bug, new contract drift, regression). Do not raise a new finding merely because a pre-existing concern became visible while reading the fix.
8. Always include the current full commit SHA in the final comment using exactly this format:

```text
审查截止: abc1234def5678
```

## Review Method

Follow the detailed SOP in `references/review-sop.md`.

## Output Format

Write the final answer as the PR comment body in Simplified Chinese. Follow `references/output-format.md` exactly.
