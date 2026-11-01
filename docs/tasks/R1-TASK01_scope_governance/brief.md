# R1-TASK01: scope_governance

## Identity

- Owner: data_workflow_lead
- Reviewer: workflow lead and contract/domain reviewers as applicable; quality acceptance independent of implementation
- State: planned
- Dependencies: None
- Historical predecessors: 001,012,014,024, under docs/task_archive/2026-10-31/
- Candidate version: not yet frozen

## Goal and scope

Accept C1STN Route A scope and freeze source authority. Acceptance gates bound the outcome. Product scope remains docs/releases/c1stn_route_a_release_scope_v1.md.

## Inputs and reading order

Read AGENTS.md, docs/agents/data_engineering_workflow.md, owning role guide, brief.md, acceptance.md, notes.md, then frozen contracts/schema/ and contracts/package/ and predecessor evidence. Resolve historical task paths through ../../task_archive/2026-10-31/README.md.

## Write boundary

Planning writes: this package only. Before implementation record exact code/config/test paths, governed input/output paths and one explicit owner here. Existing implementation is preserved. Independent reviewers cannot repair candidates while scoring. Canonical governance and integration-manifest writes require lead ownership and exact paths.

## Constraints and handoff

Obtain explicit bounded permission before direct or indirect data/ reads; this package grants none. Preserve Phenomenon, MappingRecord, reviewed pairing and co-source provenance. Exclude Route B/C promotion, default GraphRAG, unsupported material edges, reference-code copying, incidental contract changes and runtime activation. System implementation needs separate authorization. Keep task packages and harnesses local-only.

Hand off exact versions/hashes, commands/results, failures, queues, exclusions, risks, independent decision and next owner. Historical results do not establish current readiness.


