# FaultDx v2 Data Integration Policy

## Purpose

This document defines the stable integration boundary between
`r1-data` (A/data line) and
`r1-system` (N/system line).

It specifies what a future Data RC delivery must prove, what requires joint
reconciliation, and what remains branch-local. It is not a live status ledger,
a task tracker, or a replacement for the N-owned system/release handoff.

Operational delivery state and open decisions belong in the owning task package
and the Data RC integration manifest.

## Integration ownership

- A owns governed data contracts and proposals, reproducible pipelines, KG
  candidates, serving-safe fixtures, provenance, and data/KG evaluation evidence.
- N owns system architecture, router/runtime safeguards, consumer adapters, UI,
  providers, deployment, and the system/release handoff.
- Consumer-facing contract freeze and cross-branch compatibility require joint
  A/N review.
- The independent data quality reviewer makes the Data RC readiness
  recommendation; implementation existence alone is not acceptance.

## Integration method

- Prefer reviewed cherry-pick, a scoped delivery commit, or path-scoped
  migration.
- A full-branch merge is exceptional and requires Git-history and data-security
  review.
- The `r1-integration` scaffold may exist before Data RC. Data activation still
  requires the applicable Data Contract Freeze and Data RC gates.
- Do not propagate branch-local workflow files or retired role definitions as
  default data payload.
- Historical task documents may move only with the references required to
  interpret them, and only after review.

## Eligible delivery groups

A Data RC manifest may propose:

- reviewed contracts and schemas with consumer compatibility evidence;
- deterministic pipeline/KG implementation and governed configuration;
- reproducible manifests, lineage, masking records, and review queues;
- serving-safe fixtures and approved evaluation artifacts;
- independent validation and release-readiness evidence.

Presence on this branch does not make an item eligible. Every proposed item must
be explicitly named and pass its task acceptance and release gates.

## Default exclusions

Unless an approved manifest explicitly says otherwise, exclude:

- raw, private, unmasked, or unapproved generated data;
- local runtime output, caches, experiments, and machine-specific paths;
- branch-local workflow files, executable-agent definitions, and task templates;
- retired role definitions and unrelated historical task material;
- deferred or unreviewed candidates;
- system-owned runtime, router, UI, provider, deployment, and release files.

## Required Data RC manifest

The manifest must record:

- delivery task and candidate/source versions;
- accepted commits and exact file groups;
- explicit exclusions and their reasons;
- approved contract/schema version and consumer compatibility result;
- governance, masking, review, serving, and promotion states;
- reproducibility commands and observed validation results;
- migration, rename, replacement, and rollback steps;
- A owner, N consumer, independent reviewer, and required approvals;
- unresolved risks, bounded exceptions, and next owner.

The manifest, not this policy, records operational state.

## Data-content permission

Before inspecting the contents of any file under `data/` for integration review,
ask the user for explicit permission for the intended path or bounded scope.
This includes indirect reads through validation, comparison, or packaging tools.
File names and metadata may be inspected only to scope the request safely.

## Reconciliation rules

- Shared contracts must name which version and commit the consumer adopted.
- Rename or replacement behavior must be explicit; do not rely on full-branch
  merge semantics.
- Governance exports are not automatically canonical mutation sources.
- Route A/B/C meaning and co-source provenance must survive integration.
- Workflow reconciliation is a separate governance decision, not part of the
  normal data payload.
- Runtime validation may be claimed only by the owner of the runtime evidence.

## Where decisions live

- Task progress, blockers, approvals, and follow-ups:
  `docs/tasks/V2-TASK###_<name>/`.
- Historical task evidence: read-only packages under `legacy/tasks/`.
- Contract and schema decisions: the governed contract/plan plus task evidence.
- Data RC delivery status: the reviewed integration manifest.
- System/runtime decisions: the N-owned system task and handoff.

## Public workflow documentation

Reusable agent guides and sanitized handoffs are separately versioned project
documentation, not data-package payload. Keep branch-specific authority intact.
See HANDOFF.md for the public documentation change and its validation limits.
