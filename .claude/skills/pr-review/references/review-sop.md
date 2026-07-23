# PR Review SOP

This SOP adapts the adversarial-review workflow from `codex-adversarial-review` for GitHub Actions. In CI, Codex is already the reviewer, so do not start another external Codex process.

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

Missing observability on a core production path is a real finding, usually **MAJOR**.

Logs:

- Exceptional branches should log explicit errors instead of silently swallowing failures.
- Logs should be short and include a distinctive single-token CamelCase keyword, such as `GiftBatchDeductFail`.
- Generic words like `error`, `failed`, `exception`, or multi-word phrases are not enough for tokenized log systems.

Metrics / analytics:

- Core flows should expose a funnel: entry, key branches, success, and distinct failure reasons.
- Use the project's existing metrics, logging, or analytics idiom. Do not force a new library.
- Performance-motivated changes need duration measurement for the optimized path. Without it, the improvement is not verifiable after deploy and may be **BLOCKER**.

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
- broad rewrites when a narrow fix addresses the risk.

When in doubt, downgrade to an open question or omit it.
