# Project Basics

- This repository is a reusable GitHub Actions automation template, not an application runtime.
- `.github/workflows/ci.yml` is the consumer caller the template ships: it routes repository events into
  the reusable workflows by remote `@main` reference and is skipped in a repository flagged as a template.
- `.github/workflows/template-ci.yml` is this repository's own CI: it calls the local reusable workflows
  and runs the contract tests. `.github/workflows/template-cleanup.yml` turns a repository created from
  the template into a consumer repository.
- `.github/workflows/*.yml`, `.github/actions/` and `.claude/skills/` are product code and contracts.
- Consumer repositories own their events, secrets, source checkout and project-specific context.
- Prefer executable YAML/Skill/action behavior over explanatory README or design prose when they disagree.
