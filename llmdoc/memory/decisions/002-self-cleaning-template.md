# Decision 002: The Template Cleans Itself in Repositories Created from It

## Status

Accepted.

## Context

README told users to create a repository from this template and then to add a caller workflow that
references the reusable workflows remotely. Creation copied the whole repository: reusable workflows
frozen at creation time, this repository's llmdoc, Skills, contract tests and design notes. None of it is
used by a consumer, and the copied llmdoc misleads Agents that are told to read the consumer's llmdoc.

The maintainer wants one command to produce a ready repository and does not want a second, thin
template repository to maintain.

## Decision

- Keep this repository as the template. Ship `ci.yml` in its final consumer form and add a cleanup
  workflow that reduces a newly created repository to that caller, the ignore rules and a README skeleton.
- Move this repository's own routing and contract tests to `template-ci.yml`, selected by
  `github.event.repository.is_template`.
- Limit automatic cleanup to a non-template, non-fork repository whose default branch has exactly one
  commit; otherwise require manual dispatch with a typed confirmation.

## Alternatives Rejected

- Documentation only, dropping the template flag: cheapest, but removes one-command creation.
- A separate thin template repository: a second repository whose caller must track this one's interface.
- Hosting the runtime on a non-default branch so the default branch can be thin: every existing consumer
  references `@main` and would have to migrate.

## Consequences

- A consumer's `ci.yml` carries an `is_template` condition that is always true there.
- Every caller change must be made in both `ci.yml` and `template-ci.yml`; a contract test enforces it.
- New files are deleted from created repositories unless `cleanup.sh` keeps them.
- Cleanup depends on Actions being enabled and on the job token being allowed to write contents. When it
  does not run, the repository stays a full copy until someone dispatches cleanup manually.

## Evidence

Verified on GitHub on 2026-11-25 with two private scratch repositories in the organization:

- In a repository flagged as a template, the push run of cleanup was skipped, `ci.yml` was skipped for an
  Issue event and `template-ci.yml` started its local `issue-dispatch` call.
- A repository created from it was reduced to four files by a `github-actions[bot]` commit about a minute
  after creation. The job token deleted seven workflow files, and no further run was triggered.
- With two commits on the branch the automatic path left all files in place and printed a notice. Manual
  dispatch was skipped for a wrong confirmation and cleaned the repository for `cleanup`.
- In the created repository, an Issue was analysed through `ci.yml` using organization-level secrets,
  without any repository secret.
