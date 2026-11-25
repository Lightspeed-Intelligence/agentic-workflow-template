# Project Overview

## Identity

Agentic Workflow Template centralizes reusable GitHub Actions and Markdown Skills for Issue
classification, implementation, technical Q&A, PR review and llmdoc maintenance.

## Boundaries

- This repository owns reusable orchestration, shared actions, prompts, Skills and their public contracts.
- A consuming repository owns the caller workflow, GitHub event payload, code, secrets, branch policy and project-specific llmdoc.
- Local Agent filesystem/shell privilege is distinct from GitHub repository authority and from external model/notification credentials.

## Major Areas

- `.github/workflows/ci.yml`: the consumer caller, byte-for-byte what a consumer repository uses.
- `.github/workflows/template-ci.yml`: this repository's event router, calling local workflow copies.
- `.github/workflows/template-cleanup.yml` and `.github/template/`: one-shot cleanup that reduces a
  repository created from the template to the caller, ignore rules and a README skeleton.
- `.github/workflows/`: reusable task workflows.
- `.github/actions/feishu-notify/`: reusable Feishu notification action for non-review workflows.
- `.claude/skills/`: task behavior, trust and output contracts.
- `docs/code-review-design.md`: detailed audience-facing PR-review explanation.
- `scripts/`: optional submodule helpers for consumer repositories.

## Source Hierarchy

1. Executable workflow/action YAML and tracked Skill files.
2. Event-pinned Git objects and prepared runtime inputs.
3. llmdoc architecture/reference contracts.
4. README and design explanations.
