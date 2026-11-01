# First-release backlog

Start with **R1-TASK01**. C1STN Route A only. All tasks are planned; notes own later status. Local task materials must not be staged, committed or uploaded.

| Task | Outcome | Dependencies |
|---|---|---|
| [R1-TASK01](R1-TASK01_scope_governance/brief.md) | Accept C1STN Route A scope and freeze source authority. | None |
| [R1-TASK02](R1-TASK02_cad_material_refreeze/brief.md) | Produce reproducible CAD and material candidates. | R1-TASK01 |
| [R1-TASK03](R1-TASK03_independent_component_review/brief.md) | Independently review CAD and material. | R1-TASK01,R1-TASK02 |
| [R1-TASK04](R1-TASK04_error_code_producer/brief.md) | Implement the Error Code-only Schema 4.2 diagnostic producer. | R1-TASK01 |
| [R1-TASK05](R1-TASK05_release_package/brief.md) | Assemble accepted components into a frozen release package. | R1-TASK03,R1-TASK04 |
| [R1-TASK06](R1-TASK06_shadow_import_rollback/brief.md) | Implement isolated Schema 4.2 import and executable rollback. | R1-TASK05 |
| [R1-TASK07](R1-TASK07_schema42_query_adapter/brief.md) | Implement safe code and governed-description queries. | R1-TASK01 for design; R1-TASK06 for graph validation |
| [R1-TASK08](R1-TASK08_independent_data_rc/brief.md) | Independently evaluate the frozen release candidate. | R1-TASK03,R1-TASK04,R1-TASK05,R1-TASK06,R1-TASK07 |
| [R1-TASK09](R1-TASK09_system_release_handoff/brief.md) | Prepare Data RC handoff and system-release acceptance checklist. | R1-TASK08 |

## Reset record

Plan: replace active backlog with first-release gaps while preserving evidence. Changed files: 23 folders archived unchanged; nine three-file packages and two indexes added. TASK_TEMPLATE.md unchanged. Validation: archived hashes match originals; new packages contain required files. No code tests or data reads performed.

Risks: historical documents and provenance strings retain old paths; resolve using [archive mapping](../task_archive/2026-10-31/README.md). IDs 001-024 remain reserved, including local-only 018. Release scope remains the product boundary; its old task table is historical routing. No code, governance authority or release approval changed.

R1-TASK01 gates real-data work. R1-TASK02 and R1-TASK04 may progress independently with serialized writes; R1-TASK03 independently reviews components. Packaging, import, query validation, Data RC and handoff follow in order. Query contract design can begin after R1-TASK01. System implementation remains separately authorized.



Release-1 numbering starts at R1-TASK01; historical V2 IDs are preserved. Entry documents, task template and workflow guard are synchronized with this naming decision.

