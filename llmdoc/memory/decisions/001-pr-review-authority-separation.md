# Decision 001: Separate Reviewer Local Power from GitHub Write Authority

## Status

Accepted.

## Context

Code review benefits from unrestricted local tests and analysis, but PR content is untrusted and
must not be able to drive repository writes or obtain PAT/GitHub write credentials.

## Decision

- Run Codex and Claude in separate disposable, locally unrestricted reviewer jobs with read-only GitHub permissions.
- Do not inject GitHub/PAT credentials into Agent processes and do not persist checkout credentials.
- Transfer only validated structured artifacts to a separate non-Agent publisher with PR-write authority.
- Use full event-pinned diffs and base-pinned reviewer rules rather than comment-derived incremental state.

## Consequences

- A failed primary cannot contaminate fallback or publisher runners.
- Review repeats the full diff and uses more model time, but does not depend on unauthenticated comment state.
- Model credentials and general network egress remain exposed to the locally unrestricted reviewer; this is an acknowledged, separate risk.
- Schema, Skill and publisher validation must evolve together.
