# Bounded Independent Review Reflection

## Task

Rework PR review so Agents have broad local execution but no GitHub write authority, then close
the change with independent local review.

## Expected vs Actual

- Expected: one implementation review, one fix review if needed, one terminal audit.
- Actual: evidence defects were initially treated like code defects, causing repeated blind reviews
  of an unchanged tree and delaying delivery after the implementation was already stable.

## What Went Wrong

- Review integrity, code findings and evidence completeness were not classified early enough.
- Missing temporal commit evidence was discovered only at terminal audit.
- “Review until zero” had no explicit retry cap, so paperwork defects triggered more reviewers.

## Root Cause

The process correctly valued reviewer independence but failed to separate independent scrutiny from
unbounded repetition. It also deferred closure-readiness checks until too late.

## Missing Docs or Signals

- A standard pre-commit evidence checklist.
- A closure-readiness check before final full-range review.
- A numeric retry cap and explicit stop rule for evidence-only terminal failures.

## Promotion Candidates

- `llmdoc/guides/change-and-validate-workflows.md`: bounded review closure and temporal evidence.
- `llmdoc/must/working-agreement.md`: classify review failures and cap retries.

## Follow-up

Use one fresh full-range blind review after the final committed tree, batch all findings, and allow
at most one targeted evidence repair after terminal audit. Never rerun code review on an unchanged
tree solely to improve manifests or receipts.
