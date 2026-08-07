# Documentation Gaps

- `update-llmdoc.yml` assumes an existing llmdoc tree and is not called by local `ci.yml`; its
  bootstrap and scheduled external-caller story is still not documented.
- README's external caller listens to Issue `opened,labeled`, while local `ci.yml` intentionally listens only to `opened`.
- `design.md` contains legacy tool-specific system instructions; executable workflows and current Skills supersede them.
- Fork-PR behavior for secret-backed review is not defined.
- No automated integration fixture exercises a private cross-repository submodule or a legacy
  consumer without the latest template files; the local contract harness verifies static credential
  and fallback invariants but cannot prove cross-repository GitHub access.
- Resolved: the PR-review policy SHA is now the same single runtime pin as the four agentic workflows,
  and both contract harnesses compare every pinned path byte-for-byte with the working tree. Advancing
  the pin is still manual, but an unpinned policy edit now fails CI instead of passing silently.
- `setup_script` cannot install packages from an index that requires authentication. Passing a
  credential to the hook step would let it export that credential through `GITHUB_ENV` to later steps
  holding the model key, breaking the invariant that Agent processes receive no GitHub/PAT token. A
  scoped credential interface for private dependencies is still undesigned.
- Setup-hook caching is undefined. Codex and Claude run on separate runners, so a consumer with a slow
  toolchain pays the preparation cost twice within the 45-minute reviewer budget.
- Local independent closure environments do not currently provide `actionlint`. The tracked contract
  harness parses YAML and syntax-checks embedded shell, but does not replace actionlint's expression
  and GitHub Actions semantic checks.
