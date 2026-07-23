# Documentation Gaps

- `update-llmdoc.yml` assumes an existing llmdoc tree and a `update-llmdoc` Skill supplied outside this repository; its bootstrap/caller story is not documented.
- README's external caller listens to Issue `opened,labeled`, while local `ci.yml` intentionally listens only to `opened`.
- README says all workflows expose structured output, but only PR review declares a caller-visible `workflow_call.outputs` contract.
- `design.md` contains legacy tool-specific system instructions; executable workflows and current Skills supersede them.
- Fork-PR behavior for secret-backed review is not defined.
- Repository-wide actionlint currently reports untrusted Issue-title interpolation in
  `implement.yml`, `issue-dispatch.yml` and `question.yml`; these paths predate and are outside the
  PR-review isolation change, but need a dedicated hardening task.
