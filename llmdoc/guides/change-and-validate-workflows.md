# Change and Validate Workflows

## 1. Establish Scope

1. Read startup docs, then the relevant architecture/reference docs and prior reflections.
2. Read the reusable workflow, its caller, invoked Skills, action code and public README/design claims.
3. Freeze base/head/status, authorized paths and intended permission/secret changes before mutation.
4. Treat local execution, job permissions, credential injection and external side effects as separate dimensions.

## 2. Keep Contracts Synchronized

- Update workflow behavior, Skill/SOP/output format, schema/validators and public docs together.
- Move untrusted PR/Agent text through environment variables and encode with `jq --arg`; never interpolate it into shell source.
- Pin CLIs, install them without lifecycle scripts or model secrets, and verify the exact executable used.
- Pin trusted reviewer policy to the base SHA, sanitize nested checkout paths, and keep reviewer credentials ephemeral.
- Keep artifact paths non-hidden and upload/download names stable across rerun-failed-jobs behavior.
- Do not dynamically fetch mutable code in a high-permission publisher.

## 3. Validate Locally

Baseline:

```bash
git diff --check
bash -n scripts/init.sh scripts/status.sh scripts/update-all.sh
actionlint .github/workflows/*.yml
```

If the repository-wide command exposes a pre-existing baseline warning, prove that the changed
workflows are clean, confirm the warned paths are unchanged from the frozen base, and record the
baseline in `memory/doc-gaps.md`. Do not hide it, but do not silently expand an unrelated task.

Also:

- parse every workflow and composite action as YAML;
- replace GitHub expression placeholders and run `bash -n` on every embedded `run:` body;
- verify exact pinned CLI versions/help from local cache without downloads;
- test permission/token, model/fallback, schema/count, artifact and trusted-checkout invariants;
- exercise `review_status` COMPLETE/INCOMPLETE soft-failure fixtures and `extra_allowed_tools` valid/write/traversal/injection fixtures;
- exercise history-state fixtures for trusted/untrusted author, malformed marker, stale/current/non-ancestor SHA,
  0/1/3/4 suggestions and any critical/important count; all invalid cases must select full review;
- verify documentation examples satisfy the same executable truth table.

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

## Common Failure Points

- Treating `permissions:` alone as proof that the Agent cannot access persisted credentials.
- Passing raw historical comments to the Agent as trusted state, or selecting incremental mode
  without exact App identity, publisher marker, schema/count and ancestry validation.
- Inferring completion from schema-valid prose instead of requiring structured `review_status=COMPLETE`.
- Passing a broad `Bash(git -C repo:*)` pattern that includes write subcommands.
- Letting docs or human output formats contradict structured count/conclusion validators.

## Related Docs

- `llmdoc/architecture/pr-review-trust-boundary.md`
- `llmdoc/reference/pr-review-contract.md`
- `llmdoc/memory/reflections/bounded-independent-review.md`
