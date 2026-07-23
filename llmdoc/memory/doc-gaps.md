# Documentation Gaps

- `update-llmdoc.yml` assumes an existing llmdoc tree and a `update-llmdoc` Skill supplied outside this repository; its bootstrap/caller story is not documented.
- README's external caller listens to Issue `opened,labeled`, while local `ci.yml` intentionally listens only to `opened`.
- README says all workflows expose structured output, but only PR review declares a caller-visible `workflow_call.outputs` contract.
- `design.md` contains legacy tool-specific system instructions; executable workflows and current Skills supersede them.
- Fork-PR behavior for secret-backed review is not defined.
- No automated integration fixture exercises a private cross-repository submodule or a legacy
  consumer without the latest template files; the local contract harness verifies static credential
  and fallback invariants but cannot prove cross-repository GitHub access.
- The immutable PR-review policy SHA is advanced manually; there is no release/rotation check that
  detects policy authoring changes which have not yet been pinned by the reusable workflow.
- Repository-wide actionlint currently reports untrusted Issue-title interpolation in
  `implement.yml`, `issue-dispatch.yml` and `question.yml`; these paths predate and are outside the
  PR-review isolation change, but need a dedicated hardening task.
