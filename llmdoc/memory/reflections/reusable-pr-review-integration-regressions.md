# Reusable PR Review Integration Regressions

## Task

Replace the PR reviewer with isolated Codex-primary and Claude-fallback jobs, add authenticated
incremental review history, preserve external consumer compatibility, and restore production
consumers after the template was merged.

## Expected vs Actual

- Expected: merge one reviewed workflow change, then let consumer repositories continue using
  `@main` without local migrations.
- Actual: repeated review/evidence cycles delayed delivery; after merge, private-submodule and
  legacy-consumer assumptions failed in real repositories, and rerunning an old Actions run kept
  executing the old reusable-workflow revision.

## What Went Wrong

### Delivery and validation

- Independent review was initially treated as an unbounded loop. Evidence defects and unchanged
  code triggered more review passes instead of a bounded closure.
- Moving `origin/main` was repeatedly chased before the PR boundary was stable, increasing rework
  without improving the already-reviewed tree.
- A security-critical truth table initially existed only in transient evidence. The repository did
  not have a tracked regression harness until a reviewer reported the gap as MAJOR.

### Trust and bootstrap assumptions

- The first attempt to bootstrap `prepare-review-history.sh` executed the PR-head copy while the
  step held a read-only GitHub token. Read-only authority still exposes private source and control
  inputs; untrusted code must not run merely because the token cannot write.
- The safe correction was to execute only the consumer base-SHA script and fall back to deterministic
  full-review input generation when it is absent.
- Reviewer Skill/SOP/output files were then incorrectly sourced from the consumer base. Existing
  consumers had older layouts without the split reference files, so both reviewers returned
  `INCOMPLETE`. Template-owned behavior must travel with the reusable workflow, not require an
  undocumented consumer migration.

### Credential and consumer topology assumptions

- Removing `PAT_TOKEN` from every PR-review reference preserved Agent isolation but also removed the
  credential needed by `actions/checkout` for a private cross-repository submodule. The correct
  boundary is checkout-only PAT use with `persist-credentials: false`, never Agent-process injection.
- The template repository itself has no private submodule, so local contract tests could not expose
  the consumer topology regression.
- Codex and Claude legitimately use different provider credentials in some consumers. Optional
  `OPENAI_*` values therefore need independent per-field fallback to the required `ANTHROPIC_*`
  values rather than an all-or-nothing provider switch.

### Runtime and rerun semantics

- GitHub Actions reruns reuse the reusable-workflow commit resolved for the original run. Attempt 4
  of tipsy-iOS run `30009614359` still used template commit `8950cbb` after the fix had merged.
  A fresh PR event/new run is required to resolve an updated moving ref such as `@main`.
- `INCOMPLETE` was worded too broadly. A missing project-specific runtime such as JDK 25 caused an
  otherwise meaningful review to fail. It must be reserved for inaccessible core diff/worktree/context
  or inability to perform meaningful analysis; unavailable individual tests are disclosed evidence.

## What Worked

- Separating unrestricted local Agent execution from GitHub write authority kept publication
  deterministic and prevented model processes from receiving GitHub/PAT credentials.
- Publisher-generated state markers plus deterministic App/schema/count/SHA/ancestry validation
  made the narrow 1–3-small-finding incremental path auditable and fail-closed.
- The tracked `scripts/test-pr-review-contract.py` harness turned the security truth table into a
  fast CI contract and caught later credential-routing drift.
- Reviewer risk grading, prohibition on invented findings, and listing all same-class findings in
  one pass reduced review churn without weakening high-risk checks.

## Promotion Candidates

- `llmdoc/guides/change-and-validate-workflows.md`: add an external-consumer compatibility matrix,
  rerun semantics, checkout-only credential guidance, and a fresh-run integration check.
- `llmdoc/architecture/pr-review-trust-boundary.md`: keep template-owned immutable policy separate
  from consumer-base history preparation and PR-head reviewed data.
- `llmdoc/reference/pr-review-contract.md`: record provider fallback, PAT scope, policy revision,
  history fail-closed behavior, and precise `INCOMPLETE` semantics.
- `llmdoc/must/working-agreement.md`: require bounded validation and distinguish fresh runs from reruns
  when validating reusable-workflow changes.

## Follow-up

- Before changing reusable workflow checkout/policy behavior again, exercise three consumers:
  no submodules, private cross-repository submodule with PAT, and an older repository without the
  latest template policy/history files.
- After a template fix at a moving ref, create a fresh consumer run; do not use rerun as proof that
  the new workflow revision works.
- After merge, delete merged PR branches by GitHub PR state as well as ancestry: squash/rebased
  branches may be redundant even when `git branch --merged` does not list them.
