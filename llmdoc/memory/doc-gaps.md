# Documentation Gaps

- `update-llmdoc.yml` assumes an existing llmdoc tree and is not called by `ci.yml`; its
  bootstrap and scheduled external-caller story is still not documented.
- `design.md` is kept as a historical first draft. Its legacy tool-specific prompt block was removed;
  the remaining notes on branch names, automatic bug fixes and review range are outdated.
- Template cleanup's fork exclusion has no live verification; only the template, created-from-template,
  multi-commit and manual-confirmation paths were exercised on GitHub.
- `feishu-notify` does not skip when `FEISHU_WEBHOOK_TOKEN` is empty: it retries four times and logs an
  error, while `pr-review.yml` skips with a notice. A repository created from the template without that
  secret sees this on every non-review run. Fixing it changes pinned runtime and needs a pin advance.
- Whether organization-level secrets reach a newly created public repository is unverified; the live
  check used a private repository.
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
- `setup_script` does not reach the `validate_codex`/`validate_claude` jobs, which execute a consumer's
  optional base-pinned `.github/agentic/validate.sh`. For the exact scenario that motivated the hook — a
  project needing a specific JDK or an internal Python package — that validator still cannot run. Extending
  the hook there means preparing an environment inside a job whose purpose is to gate an unreviewed
  candidate commit, so it is a deliberate omission rather than an oversight, but the public docs now
  advertise the capability without naming this boundary.
- No offline fixture exercises submodule dirtiness for the setup hook's clean-worktree assertion. The
  contract harnesses would catch a change to `run-setup-hook.sh` that did not advance the runtime pin,
  but not a reverted submodule-dirty definition committed together with a pin advance. Building such a
  fixture needs a nested-submodule scratch repository; until then the alignment with
  `package-change-result.sh` rests on review rather than automation.
- Local independent closure environments do not currently provide `actionlint`. The tracked contract
  harness parses YAML and syntax-checks embedded shell, but does not replace actionlint's expression
  and GitHub Actions semantic checks.
