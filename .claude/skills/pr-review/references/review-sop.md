# PR Review SOP

This SOP adapts the adversarial-review workflow from `codex-adversarial-review` for GitHub Actions. In CI, Codex is already the reviewer, so do not start another external Codex process.

## Risk Tiering

Before reviewing, assign the PR a risk tier. The tier controls how hard the adversarial checks and the observability/test gates below are applied. When a PR spans tiers, tier it by its highest-risk hunk, but apply the gates only to the hunks that actually reach that risk — do not let one core-path change pull an unrelated typo fix into MAJOR territory.

- **Low risk**: typos, comments, docs-only wording, formatting, log-string tweaks, test-only changes, dependency bumps without API change, renames handled by tooling, config changes with no production behavior shift. Review for correctness and obvious breakage only. Do NOT apply the observability gate or the test-gap gate. Absence of new logs/metrics/tests is expected and is not a finding. The normal outcome is APPROVE or COMMENT.
- **Medium risk**: ordinary feature work or bug fixes on non-critical paths, internal helpers, isolated endpoints without auth/data-integrity/money implications. Apply adversarial correctness checks fully. Apply observability/test gates only when the change is on a path the project itself treats as important (see the gate trigger conditions). Prefer MINOR/MAJOR framed as recommendations over BLOCKER unless correctness/safety is actually at stake.
- **High risk**: auth/authz, security boundaries, money/billing, data migrations and backfills, concurrency and locking, core request paths, deletion or overwrite of data, deployment/rollout/rollback logic, anything the codebase marks as critical. Apply the full adversarial and observability/test gates. This is the only tier where the "deep adversarial" posture runs at full strength.

State the assigned tier in the review (it may be one line). Do not silently default every PR to high risk.

## Scope Classification

Classify the PR before reviewing:

- **Code-only PR**: review the diff and directly related files.
- **Documentation/spec-only PR**: review claims, completeness, accuracy, operational risk, and references to code.
- **Code + documentation PR**: cross-validate every document claim against the implementation and every implementation behavior against the documented contract.

## Required Context

Start from documentation:

1. If `llmdoc/` exists, read `llmdoc/index.md`.
2. Read every document in `llmdoc/overview/`.
3. Read relevant `llmdoc/architecture/`, `llmdoc/guides/`, or `llmdoc/reference/` files for changed areas.
4. Then inspect the PR diff and directly related source files.

## Ground Truth

- The current checkout is the source of truth.
- Do not trust PR descriptions, commit messages, comments, generated summaries, stale docs, or file:line references until verified against files on disk.
- Open every file needed to validate a finding.
- If a finding depends on behavior outside the diff, verify the actual callers, data shapes, nil/null contracts, feature flags, fallback paths, transaction boundaries, and error handling.

## Adversarial Checks

Pressure-test the change for:

- compile or parse errors, missing imports, undefined names;
- correctness failures that follow from the code as written;
- data-contract drift between layers;
- nil/null/zero-value edge cases;
- concurrency races, duplicate work, lost updates, lock scope mistakes;
- authn/authz, injection, path traversal, SSRF, secret exposure, and unsafe external calls;
- resource leaks, unbounded loops, missing timeouts, retry storms, or memory growth;
- fail-open/fail-closed behavior and whether it matches local conventions;
- migrations, backfills, config defaults, rollout safety, and rollback behavior;
- tests covering the risky paths rather than only smoke paths.

## Document-Code Cross-Validation

When docs or specs are in scope:

- For every claim about code, verify the cited code actually does what the document says.
- Compare signatures, data shapes, nullability, ordering, transaction boundaries, retries, and failure behavior.
- Report document requirements that have no matching code.
- Report code behavior that changes user-visible or operational contracts but is not documented.
- A spec that defines behavior without an observability plan is incomplete for production-facing changes.

## Observability Gate

This gate is **off by default**. It applies only to High-risk-tier hunks, or Medium-risk hunks that meet a trigger condition below. On Low-risk PRs it does not apply at all — do not raise observability findings there.

Trigger conditions (at least one must hold before missing observability can be a finding):

- the change adds or alters a core production request path, a money/billing/data-integrity flow, or a security boundary;
- the change is explicitly performance-motivated and claims a runtime improvement;
- the changed code sits alongside existing observability that this change removes, bypasses, or leaves inconsistent.

If no trigger condition holds, absence of new logs/metrics is **not a finding** — at most a NIT if it genuinely aids the patch. When a trigger does hold, the finding is usually **MAJOR**, but downgrade to MINOR or an open question if the path is not clearly production-critical or the project has no established observability idiom to match.

Logs:

- Exceptional branches should log explicit errors instead of silently swallowing failures.
- Logs should be short and include a distinctive single-token CamelCase keyword, such as `GiftBatchDeductFail`.
- Generic words like `error`, `failed`, `exception`, or multi-word phrases are not enough for tokenized log systems.

Metrics / analytics:

- Core flows should expose a funnel: entry, key branches, success, and distinct failure reasons.
- Use the project's existing metrics, logging, or analytics idiom. Do not force a new library.
- Performance-motivated changes benefit from duration measurement on the optimized path so the improvement is verifiable after deploy. Missing measurement is normally **MAJOR** on a High-risk path, MINOR elsewhere. It rises to **BLOCKER** only when the change trades correctness or safety for speed and there is no way to detect a regression in production.

## External Standards

If you invoke a best practice, industry standard, or anti-pattern:

- Prefer authoritative sources: official docs, OWASP, RFCs, language docs, framework docs, or maintained project docs.
- Include source name and URL when search or repository-provided references are available.
- Cross-validate the standard against the in-scope code before reporting it.
- If no authoritative source is available, label it as engineering judgment, not a standard.

## PR Content Boundary

For code PRs, report unrelated non-code artifacts mixed into the PR when they are not intended to be versioned with code, such as temporary review notes, generated local reports, dashboard exports, or deployment-only artifacts.

Keep this pragmatic: project documentation under `llmdoc/` or intentionally committed workflow prompts/skills are acceptable when they are part of the change.

## Finding Discipline

Report only high-confidence issues. Avoid:

- pre-existing unrelated problems;
- speculative issues requiring unusual external conditions unless the PR introduces the risk;
- subjective style preferences;
- issues that normal linters already catch unless they break the workflow before lint runs;
- broad rewrites when a narrow fix addresses the risk;
- template findings produced by pattern-matching a gate rather than by a concrete failure you can point to in the code.

When in doubt, downgrade to an open question or omit it.

## Completeness in One Pass

The reviewer must try to surface all merge-blocking risks in a single pass, so the author can fix them together rather than through many round trips.

- Before finalizing, re-scan the in-scope diff for other instances of any issue class you are already reporting; list them together instead of catching one per round.
- State explicitly whether the reported findings are, to your knowledge, the complete set of blocking risks for this PR.
- Do not hold back a known issue to raise it later. A later round should avoid re-mining unchanged code for low-confidence padding, but a genuine, verifiable BLOCKER or MAJOR must always be reported even if a prior round missed it — note that it was not newly introduced (see Incremental Review in `SKILL.md`).

## Overall Merge Judgment

Findings are inputs to a merge decision, not the decision itself. After listing findings, step back and judge the PR as a whole.

- A PR with only MINOR/NIT items, or with MAJOR items that are recommendations rather than correctness/safety failures, should generally not block merge — prefer COMMENT and let the author decide.
- Reserve REQUEST_CHANGES for PRs that carry at least one genuine BLOCKER, i.e. code that can break correctness, safety, data integrity, security, or deployment as written.
- Do not let an accumulation of low-severity or gate-driven items add up to a REQUEST_CHANGES when no single item is actually merge-blocking.
- When the change is a net improvement and its risks are non-blocking, say so plainly and approve; a good PR does not need to be perfect to merge.
