# Change and Validate Workflows

## 1. Establish Scope

1. Read startup docs, then the relevant architecture/reference docs and prior reflections.
2. Read the reusable workflow, its caller, invoked Skills, action code and public README/design claims.
3. Freeze base/head/status, authorized paths and intended permission/secret changes before mutation.
4. Treat local execution, job permissions, credential injection and external side effects as separate dimensions.
5. Classify ownership before editing: template-owned policy/runtime, consumer-owned event/source tree,
   and consumer-base trusted compatibility inputs are different trust and release boundaries.
6. Once a PR has a stable reviewed boundary, do not repeatedly chase a moving default branch. Integrate
   again only for a real conflict, a required dependency, or an explicit release decision.

## 2. Keep Contracts Synchronized

- Update workflow behavior, Skill/SOP/output format, schema/validators and public docs together.
- Move untrusted PR/Agent text through environment variables and encode with `jq --arg`; never interpolate it into shell source.
- Pin CLIs, install them without lifecycle scripts or model secrets, and verify the exact executable used.
- Release shared Agent runtime in two commits: commit the runtime/Skill/script bytes first, then pin
  every reusable workflow to that immutable commit. Never pin a workflow to bytes that exist only in
  the same uncommitted or not-yet-addressable tree.
- Pin template-owned reviewer policy to an immutable template revision. Use the consumer base SHA only
  for consumer-owned trusted inputs such as history preparation; never require a consumer to copy the
  template's reviewer policy file.
- If a consumer base lacks an optional trusted preparation script, generate full-review inputs with
  deterministic workflow commands. Never execute a PR-head copy as a bootstrap fallback.
- A private-submodule PAT may be used by `actions/checkout` with `persist-credentials: false`; never
  inject it into an Agent process or reuse it for public/template policy checkout.
- Resolve optional provider credentials per field: Codex `OPENAI_*` values may independently fall
  back to `ANTHROPIC_*`, while Claude continues to receive only `ANTHROPIC_*`.
- Keep artifact paths non-hidden and upload/download names stable across rerun-failed-jobs behavior.
- Do not dynamically fetch mutable code in a high-permission publisher.
- Preserve terminal job names that downstream rulesets may require. Internal prepare/Agent/validator
  jobs may change, but `answer`, `dispatch`, `implement`, `update` and `review` are compatibility APIs.

## 3. Validate Locally

Baseline:

```bash
git diff --check
bash -n scripts/init.sh scripts/status.sh scripts/update-all.sh
actionlint .github/workflows/*.yml
python3 scripts/test-pr-review-contract.py
python3 scripts/test-agentic-workflow-contract.py
```

If the repository-wide command exposes a pre-existing baseline warning, prove that the changed
workflows are clean, confirm the warned paths are unchanged from the frozen base, and record the
baseline in `memory/doc-gaps.md`. Do not hide it, but do not silently expand an unrelated task.

Also:

- parse every workflow and composite action as YAML;
- replace GitHub expression placeholders and run `bash -n` on every embedded `run:` body;
- verify exact pinned CLI versions/help from local cache without downloads;
- test permission/token, model/fallback, schema/count, artifact and trusted-checkout invariants;
- reject malformed complete results before the fallback decision, including missing, mistyped and
  extra task-specific fields;
- exercise clean and dirty `NO_CHANGES` for tracked, untracked and recursive-submodule state;
- exercise gitlink add/change/delete, dirty submodule worktrees and update-llmdoc recursive checkout;
- assert that every shared-runtime pin resolves locally and its tracked bytes equal the authoring tree;
- assert stable terminal job names independently of display names;
- assert policy provenance and credential scope: PR-head checkout alone may use the PAT fallback,
  while consumer-base and template-policy checkouts use the read-only job token;
- exercise `review_status` COMPLETE/INCOMPLETE soft-failure fixtures and `extra_allowed_tools` valid/write/traversal/injection fixtures;
- exercise history-state fixtures for trusted/untrusted author, malformed marker, stale/current/non-ancestor SHA,
  0/1/3/4 suggestions and any critical/important count; all invalid cases must select full review;
- verify documentation examples satisfy the same executable truth table.
- reserve `review_status=INCOMPLETE` for inaccessible core diff/worktree/context or inability to
  perform meaningful analysis; an unavailable individual project test is disclosed but not alone fatal.

`scripts/test-pr-review-contract.py` is the maintained offline truth table. It exercises the actual
base-pinned history-preparation script plus the workflow's schemas, publisher gate, fallback/artifact
conditions and extra-tool allowlist; `.github/workflows/ci.yml` runs it for pull requests.

### External consumer verification

Local fixtures cannot reproduce every consumer topology. Before releasing checkout, trust-source or
credential changes, exercise or explicitly account for:

1. a repository without submodules;
2. a private cross-repository submodule using checkout-only PAT access;
3. an older consumer without the latest history-preparation script and without any copied reviewer policy.

After changing a reusable workflow referenced through a moving ref such as `@main`, trigger a fresh
consumer event/run. GitHub reruns keep the reusable-workflow commit resolved for the original run, so
repeatedly clicking **Re-run jobs** cannot validate the newly merged workflow.

## 4. Commit with Temporal Evidence

1. Before staging: freeze HEAD/tree/status, authorized paths and unstaged patch digest.
2. Stage only authorized paths.
3. Before commit: freeze staged binary patch digest/name-status and separate unstaged/untracked state.
4. Immediately after commit: record commit/parent/tree/status and prove committed patch digest equals staged digest.

## 5. Close Review with a Bound

- Run one fresh no-parent blind review in an object-independent fixed-commit offline clone.
- Batch all implementation findings into one fix commit when possible, then run one incremental re-review.
- Run one final full-range review only if the tree changed after the first range review.
- Run one terminal evidence audit. Permit at most one targeted evidence repair; never rerun blind code review on an unchanged tree merely to improve paperwork.
- Classify failures as implementation, review integrity or evidence completeness. At the retry cap, stop and report choices rather than expanding scope.
- Require every blind report itself—not only its manifest—to record run ID, canonical reviewer task,
  fixed snapshot/head/tree/range, `fork_turns`, `inherited_turns`, and allowed/forbidden inputs.

## 6. Clean Up After Merge

1. Switch to the default branch, prune remote refs, and fast-forward only to the current remote tip.
2. Delete local and remote branches whose PRs are merged and whose work is present in the default branch.
3. Check GitHub PR state as well as Git ancestry: squash/rebase merges may leave redundant branches
   that `git branch --merged` cannot identify.
4. Preserve open-PR and genuinely unmerged branches. Remove pre-rebase backups only after their
   replacement has merged and the user has authorized cleanup.

## Common Failure Points

- Treating `permissions:` alone as proof that the Agent cannot access persisted credentials.
- Removing a credential from Agent processes and accidentally removing it from the earlier checkout
  phase that legitimately needs private-submodule read access.
- Treating consumer base layout as template policy distribution, or using PR-head code to bootstrap
  a missing trusted script.
- Passing raw historical comments to the Agent as trusted state, or selecting incremental mode
  without exact App identity, publisher marker, schema/count and ancestry validation.
- Inferring completion from schema-valid prose instead of requiring structured `review_status=COMPLETE`.
- Marking a meaningful review `INCOMPLETE` solely because one project-specific test runtime is absent.
- Passing a broad `Bash(git -C repo:*)` pattern that includes write subcommands.
- Letting docs or human output formats contradict structured count/conclusion validators.
- Treating a schema-valid common subset as sufficient when the selected workflow has additional
  required fields, causing a publisher failure instead of primary fallback.
- Accepting `NO_CHANGES` before proving that root, untracked and recursive-submodule state is clean.
- Advancing only some immutable runtime refs or pinning them before the runtime commit exists.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/pr-review-contract.md`
- `llmdoc/memory/reflections/bounded-independent-review.md`
- `llmdoc/memory/reflections/reusable-pr-review-integration-regressions.md`
