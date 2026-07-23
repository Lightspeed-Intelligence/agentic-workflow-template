# llmdoc Index

## Purpose

- This is the global map for durable project knowledge.
- Start every task with `llmdoc/startup.md` and its MUST reading order.
- Runtime YAML, tracked Skills, and actions remain executable sources of truth; llmdoc explains how they fit together.

## Categories

- `must/`: recurring invariants and working agreements.
- `overview/`: project identity and boundaries.
- `architecture/`: runtime flows, ownership and trust boundaries.
- `guides/`: repeatable change workflows.
- `reference/`: stable contracts and lookup facts.
- `memory/`: decisions, reflections and documentation gaps.

## Key Documents

- `llmdoc/startup.md`: required startup reading order.
- `llmdoc/overview/project-overview.md`: project identity and major areas.
- `llmdoc/architecture/workflow-orchestration.md`: caller/reusable workflow ownership and flow.
- `llmdoc/architecture/pr-review-trust-boundary.md`: reviewer/publisher permissions, credentials and artifacts.
- `llmdoc/guides/change-and-validate-workflows.md`: contract-consistent edits, validation and bounded closure.
- `llmdoc/reference/workflow-contracts.md`: trigger, authority and secret lookup facts.
- `llmdoc/reference/pr-review-contract.md`: exact PR-review inputs, models, schema and failure semantics.
- `llmdoc/memory/decisions/001-pr-review-authority-separation.md`: durable authority-separation decision.
- `llmdoc/memory/reflections/bounded-independent-review.md`: lesson from an unbounded review/evidence loop.
- `llmdoc/memory/reflections/reusable-pr-review-integration-regressions.md`: lessons from trust bootstrap,
  private submodules, legacy consumers, provider routing and reusable-workflow reruns.
- `llmdoc/memory/doc-gaps.md`: unresolved documentation and automation gaps.

## Routing Rules

- Read `must/` on every task.
- Read `architecture/` and `reference/` before changing a workflow or permission boundary.
- Read the matching `guides/` before implementation and validation.
- Read related `memory/reflections/` before repeating a previously difficult workflow.
