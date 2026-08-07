# Consumer-Owned Extension Points

Lessons from adding an optional environment-preparation script to all five workflows.

## The extension point belongs where the blast radius is smallest

The request started as a `pr-review` concern: reviewers could not run Java or Python compile checks
because the runner lacked the required JDK and internal packages. Extending it to every workflow was
correct for contract consistency, but the flows are not equally safe.

`pr-review` produces no persistent artifact — it reads, reports and exits. `implement` and
`update-llmdoc` package the worktree into a candidate commit through `package-change-result.sh`, which
runs `git add -A`. The same hook that is harmless in a reviewer can silently commit a regenerated
lockfile in a code writer.

Check what the flow does with the worktree before reusing a step across flows. Symmetry in the YAML
does not imply symmetry in consequences.

## Freeze the inputs before running consumer code

The original proposal placed the hook right after checkout. But `prepare-review-history.sh` derives the
review range from the live worktree with `git diff` and `git log`. A hook that runs first can perturb
that derivation, so the hook would influence *what gets reviewed*, not just *what tools are available*.

Ordering the hook after input freezing and before CLI installation keeps the useful capability
(`GITHUB_PATH` still reaches the Agent) and removes the dangerous one.

## A pinned script is not a pinned input

Reading the hook from the base SHA prevents the current change from editing the hook. It does not
prevent the current change from driving it: `pip install -r requirements.txt` executes a dependency's
`setup.py`, and `mvn` executes the head `pom.xml`. Both manifests are PR-editable.

The honest claim is "removes one direct injection path and matches how the repository already handles
trusted scripts", not "prevents PR-driven code execution". The initial issue and its automated review
both overstated this; the documentation deliberately does not.

## Separate configuration errors from environment conditions

Two failures look similar and need opposite handling.

A malformed `setup_script` path or a hook that dirties a bundling worktree is a configuration mistake.
Fail the job loudly — the alternative is a silently degraded run or build output committed to a user's
PR.

A hook that fails because a dependency download timed out is an environment condition. Failing the job
there is actively worse than continuing: the primary job goes non-success, the fallback starts on a
fresh runner, runs the same script, fails the same way, and the PR ends up with no review at all plus a
wasted model call. Disclose the exit code to the Agent and let it report the limitation instead.

## Credentials cannot be scoped into a step that writes GITHUB_ENV

Supporting authenticated private indexes would require giving the hook a token. Because the hook is a
distinct step, it can write `GITHUB_ENV`, and later steps holding the model key inherit it. That turns
"Agent processes structurally cannot receive a PAT" into "the hook author must remember not to leak
it". The capability was deliberately deferred rather than weakened; `llmdoc/memory/doc-gaps.md`
records the undesigned credential interface.

## Fixture hazards found while writing the harness

- Temporary git repositories inherit the author's `commit.gpgsign`/`gpg.format`. With SSH signing,
  `git commit` blocks on an interactive key prompt and the test hangs rather than failing. The existing
  `make_repo` already set `commit.gpgsign=false`; new fixtures must reuse that initialization.
- A fixture that writes its hook script immediately before asserting on worktree cleanliness dirties
  the very state it checks. Commit all fixture scripts first, then vary which one runs.
- Verify a new assertion actually bites by breaking the contract on purpose — injecting a secret into
  the hook step and flipping the mode argument both had to fail before the tests were trustworthy.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/architecture/workflow-orchestration.md`
- `llmdoc/guides/change-and-validate-workflows.md`
- `llmdoc/memory/reflections/codex-first-agentic-workflows.md`
