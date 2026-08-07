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

## A step-level timeout cannot be caught by the step's own script

The first implementation bounded the hook with `timeout-minutes: 15` and relied on the script's
`hook_status=$?` branch to degrade gracefully. That combination does not work: when a step-level
timeout fires, the runner kills the whole process tree and marks the step failed, so the degradation
branch never executes. Four separate documents and the script's own comment asserted the opposite.

The failure mode it produced was precisely the one the non-fatal design existed to prevent — and it
would have triggered on exactly the slow toolchains that motivate the hook. The fix is for the script
to bound itself with `timeout`, turning expiry into an ordinary non-zero exit (GNU `timeout` uses 124)
that reuses the disclosure path, while `timeout-minutes` remains a wider backstop.

Lesson: when a mechanism promises graceful degradation, verify that the failure it degrades from is
actually observable by the code doing the degrading. Writing the promise in four documents does not
make the control flow real.

## Keep a derived value in one place

`llmdoc/reference/pr-review-contract.md` duplicated the policy SHA as a literal. Merging the pins
updated all 20 workflow references but left that literal stale, and the same change had replaced the
one test that hardcoded it with a regex extraction — removing the only thing that would have caught
the drift. The document now points at the workflow as the source of truth, and a contract assertion
rejects any 40-character SHA literal in `README.md`/`docs/` or a non-current one anywhere in `llmdoc/`.

Lesson: when you relax an assertion from an exact literal to a pattern, check what that literal was
incidentally protecting elsewhere.

## Assert on every flow a document claims to cover

The public docs stated that `implement` **and** `update-llmdoc` steer the Agent toward `BLOCKED` when
preparation failed, but only `implement` had the prompt text — and the contract test asserted on
`implement` alone, so CI agreed with the code rather than the contract. A documented claim that spans
N flows needs an assertion that loops over all N.

## Match sibling checks exactly or explain the divergence

The hook's clean-worktree assertion used plain `git status --porcelain --untracked-files=all` while the
sibling `package-change-result.sh` used `--ignore-submodules=none` plus a recursive `submodule foreach`.
The two diverge once a consumer sets `submodule.<name>.ignore = all`; the user would then see a
misleading "cross-repository changes unsupported" `BLOCKED` instead of "your setup script dirtied the
worktree". No safety invariant broke, but the diagnostic was wrong. Two checks guarding the same
invariant should share one definition of dirty.

## An ordering assertion can be structurally incapable of failing

The step-ordering checks for this hook were vacuous in two independent ways, and both passed review
until a mutation test proved otherwise.

First, positions were located with `str.index()` over the entire workflow file. Every workflow here has
a Codex job and a Claude fallback job with identically named steps, so the search always returned the
primary job's match and the fallback's ordering was never examined. Fix: slice the job block first.

The positions were also derived from one another: `block.index(needle, contract_at)` starts searching at
`contract_at`, so the result can only be after it. Within a single job block the hook appears once, so a
moved hook makes this raise `ValueError` rather than pass — a loud failure, which is why per-job slicing
alone already closed the gap. The current code still locates each position independently and compares
absolute offsets, because relying on an exception to enforce an ordering is fragile: it depends on the
needle being unique inside the block, and a second occurrence would silently restore the blind spot.

A third variant of the same mistake outlived both fixes: the assertions checked that each argument
literal *appeared somewhere* in the step, not that the arguments were in the right order. Swapping the
source directory and the repository directory left both literals present while making the hook read its
script from the PR head worktree instead of the trusted base checkout — destroying the exact property
the trust boundary rests on — and both harnesses passed. Appending characters to a path, or pointing the
prompt file at a path nobody reads, passed too. Asserting the whole five-argument sequence as one regex
closes all of them.

Lesson: verify an ordering assertion by breaking it in every direction it should catch, and confirm the
failure is the one you expect. "Contains the right strings" is not "calls it the right way": when
argument position carries meaning, assert the sequence, not the membership. The mutation surface here is 20 cases — five workflows carry the hook,
each with a primary and a fallback job, and each job's hook can move to either side of its neighbours —
not the 4 I first checked. A fix that "looks correct" is not evidence; my own first attempt appeared to
pass a mutation that had in fact failed to apply, and I initially misattributed that to the derived
search start.

Corollary: "the harness compares pinned files byte-for-byte, so a stale pin fails CI" was true, but
nothing compared the five workflows' pins *to each other* — repinning one workflow alone to a different
real commit passed. A claim about a cross-file invariant needs a check that actually reads across those
files.

## The template cannot test a consumer-only configuration

Issue #31: after this extension point shipped, any consumer declaring `setup_script` in `pr-review.yml`
failed on both the primary and the fallback chain, with the error blaming the consumer's setup script for
dirtying the worktree. The real cause was that `pr-review` checks out `.trusted-base` and
`.trusted-policy` **inside** `$GITHUB_WORKSPACE` and then passes that same directory as the hook's
`repo_dir`, so `git status` was always going to list them as untracked. The timing made it unavoidable:
those directories exist before the hook runs, and the assertion runs after.

Nine local blind rounds, two automated PR reviews and a terminal audit all missed it. The reason is
structural, not carelessness: **this repository never declares `setup_script` on itself.** The code path
that fails is only reachable from a consumer configuration, so every green run — including the PR that
introduced the bug reviewing itself — exercised the empty-input no-op branch instead. Reviewers verified
the clean-worktree assertion against synthetic fixtures where `repo_dir` contained nothing but the fixture
repository, which is precisely the condition that hides the defect.

Two lessons:

- When adding an opt-in extension point that this repository will not itself opt into, the offline fixture
  must reproduce the **caller's** directory layout, not just the script's contract. Passing `repo_dir` a
  bare fixture repo tests an arrangement no real caller uses. The regression test now plants
  `.trusted-base`/`.trusted-policy` inside the fixture before running the hook.
- A shared script should not encode its callers' path conventions. The fix compares worktree status against
  a baseline captured before the hook runs and reports only additions, so `run-setup-hook.sh` needs to know
  nothing about `pr-review`'s layout. Excluding the two paths by name would have worked too, but it would
  also have silently exempted a consumer that genuinely tracks files under those names — the issue reporter
  flagged that risk explicitly. Keying on status entries rather than path names keeps that case failing.

Also worth noting: the error text said "your setup script's artifacts must be gitignored" while pointing at
a workflow-owned directory. A hardcoded diagnosis that names a cause it has not established sends every
reader down the wrong path. The message is now only produced for state the hook actually introduced.

### A baseline must be captured no earlier than the action it measures

The first fix put the baseline capture at the top of the script, before the `setup_script`-is-empty
short-circuit. That made every workflow run `git status` and `submodule foreach` even when the feature was
switched off — and a repository with an unusable gitlink (a `.gitmodules` entry missing for a checked-out
submodule path) then exited 128. A repository not using the feature at all would have started failing.

Lesson: a "before" measurement belongs immediately before the thing it measures, past every early return.
Placing it at the top of the script looks harmless because the value is only consumed later, but the
*collection* has side effects and failure modes of its own.

### A reset in a shared fixture helper can silently disarm later cases

The regression fixture planted the workflow-owned directories once, then ran each case through a helper that
ended with `git clean -qfd`. That deleted the planted directories, so only the very first case saw them —
and the `review` branch, the actual victim of the bug, was never guarded. Mutating the implementation to
skip the baseline in `review` mode passed both harnesses.

Lesson: when a fixture helper resets state between cases, anything the test *depends on* must be re-planted
inside the helper, not set up once outside it. Verify by mutating the specific branch each case claims to
cover, not just the first one.

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
