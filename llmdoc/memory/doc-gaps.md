# Documentation Gaps

- `update-llmdoc.yml` assumes an existing llmdoc tree and is not called by local `ci.yml`; its
  bootstrap and scheduled external-caller story is still not documented.
- README's external caller listens to Issue `opened,labeled`, while local `ci.yml` intentionally listens only to `opened`.
- `design.md` contains legacy tool-specific system instructions; executable workflows and current Skills supersede them.
- Fork-PR behavior for secret-backed review is not defined.
- No automated integration fixture exercises a private cross-repository submodule or a legacy
  consumer without the latest template files; the local contract harness verifies static credential
  and fallback invariants but cannot prove cross-repository GitHub access.
- The immutable PR-review policy SHA is advanced manually; there is no release/rotation check that
  detects policy authoring changes which have not yet been pinned by the reusable workflow.
- Local independent closure environments do not currently provide `actionlint`. The tracked contract
  harness parses YAML and syntax-checks embedded shell, but does not replace actionlint's expression
  and GitHub Actions semantic checks.
