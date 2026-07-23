# Project Basics

- This repository is a reusable GitHub Actions automation template, not an application runtime.
- `.github/workflows/ci.yml` routes repository events into reusable workflows.
- `.github/workflows/*.yml`, `.github/actions/` and `.claude/skills/` are product code and contracts.
- Consumer repositories own their events, secrets, source checkout and project-specific context.
- Prefer executable YAML/Skill/action behavior over explanatory README or design prose when they disagree.
