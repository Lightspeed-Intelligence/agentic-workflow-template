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
- Use immutable template-revision-pinned reviewer rules and full event-pinned diffs by default.
  Consumer-base code may prepare authenticated history but cannot supply template policy. Permit a
  narrow incremental exception only from publisher-generated, preparation-validated Bot state for
  fixes to 1–3 small findings.

## Consequences

- A failed primary cannot contaminate fallback or publisher runners.
- Most reviews repeat the full diff. Small-finding fix rounds may use less model time, while the
  deterministic preparation step—not the Agent—authenticates state and fails closed to full review.
- Model credentials and general network egress remain exposed to the locally unrestricted reviewer; this is an acknowledged, separate risk.
- Schema, Skill and publisher validation must evolve together.
