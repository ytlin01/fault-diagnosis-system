# V2-TASK001_route_a_shared_gold_eval_framework - Notes

## Status

Static-coverage framework is implemented and locally validated. An old-TP-DX snapshot adapter, frozen normalized snapshot, versioned coverage targets, and a static-coverage execution have not started; no domain-correctness or release claim follows from this work.

### Evaluation boundary 闂?old TP-DX KG

The old topology-diagnostic (TP-DX) KG diagnostic layer is not reviewed. V2-TASK001 may nevertheless implement and execute the evaluation framework against a frozen old-KG snapshot for pipeline correctness, structural/static coverage, ranking fidelity against explicitly provisional labels, abstention/safety behavior, scorer calibration, and mutation testing.

Those runs must be reported as `unreviewed` or `provisional` evidence. They must not be described as independently reviewed domain correctness, diagnostic truth, release readiness, or a reviewed old/new KG comparison. Reviewed domain-correctness claims require independently sourced, domain-reviewed or adjudicated gold labels under the V2-TASK001 annotation workflow.
For framework execution, the old TP-DX baseline is designated `assumed-label / provisional`. This designation permits the full static-coverage, ranking, chain, bridge, abstention, safety, calibration, mutation, and blind-partition evaluation workflow, while preserving the restrictions above on reviewed-truth and release claims.

## Plan

1. Inventory existing Route A evaluation artifacts and freeze semantic ownership for each.
2. Draft the shared case schema, annotation guide, scenario registry, and maturity states.
3. Review the schema and acceptance gates before producing labels or code.
4. Build the normalized result contract and old-KG adapter.
5. Calibrate and mutation-test the scorer, then freeze the old-KG baseline.
6. After V2-TASK003, implement the new-KG adapter and run paired development/validation comparisons.
7. Freeze both candidates, audit leakage, and execute the blind comparison.

## Changed Files

- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/brief.md`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/acceptance.md`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/notes.md`

### Implemented 闂?static coverage framework

- `contracts/evaluation/route_a_static_coverage_input_v1.schema.json`
- `services/evaluation/route_a_static_coverage.py`
- `scripts/eval/eval_route_a.py`
- `tests/unit/test_route_a_static_coverage.py`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/static_coverage.md`

The evaluator is adapter- and graph-independent: it scores explicit entity, relation, topology/diagnostic/bridge path, provenance, and integrity coverage from a frozen normalized snapshot. It preserves `assumed_label_provisional` maturity and does not create domain-correctness claims.

## Validation

- Confirmed TASK-018A is executor/graph-specific and does not provide an independent shared domain gold.
- Confirmed TASK-029A covers fixture-based structural behavior and explicitly deferred reviewed-KG faithfulness/domain evaluation.
- Confirmed TASK-034 is a Route B troubleshooting evidence benchmark and is outside this scope.
- V2-TASK001 remains the current evaluation task identifier; TASK-043 was removed from this data-engineering branch because it belongs to runtime/assembly work.

No implementation tests were run because this change defines the task boundary only.

### Validated 闂?static coverage framework

- `python -m unittest tests.unit.test_route_a_static_coverage` 闂?4 tests passed.
- `python -m json.tool contracts/evaluation/route_a_static_coverage_input_v1.schema.json` 闂?passed.
- `python -m py_compile services/evaluation/route_a_static_coverage.py scripts/eval/eval_route_a.py` 闂?passed.
- `python scripts/eval/eval_route_a.py --help` 闂?passed; `eval_route_a.py` is the sole Route A evaluation CLI.
- A temporary synthetic snapshot run through `--static-coverage-input` / `--static-coverage-output` with `--skip-scenarios --skip-audit` 闂?passed.
- No data artifact, Neo4j query, old-TP-DX snapshot, or blind case was read or executed during validation.

## Risks

- The current Route A eval scripts are uncommitted user work and must not be overwritten or reclassified without review.
- Independent domain labels require reviewer availability and trustworthy source anchors.
- Old and new KG capabilities may differ; applicability rules must be frozen before score comparison.
- A blind partition is only blind for its first controlled use.

## Next Step

For static coverage: the pipeline/KG owner supplies a frozen old-TP-DX adapter-normalized snapshot and a config-digested, versioned coverage-target artifact. The quality reviewer then runs the static mode, verifies blockers and maturity labels, and records the provisional result. This does not authorize a domain-correctness or release claim.

### Implemented 闂?generic expert-ranking evaluator

- `contracts/evaluation/route_a_expert_ranking_input_v1.schema.json`
- `services/evaluation/route_a_expert_ranking.py`
- `scripts/eval/eval_route_a_expert_ranking.py`
- `tests/unit/test_route_a_expert_ranking.py`

The evaluator is source- and graph-independent. It accepts a future separately governed gold set and candidate rankings, then reports cause and cause/action-pair recall, MRR, nDCG, and abstention. It contains no source-derived gold labels, source-specific adapters, graph snapshots, or mapping artifacts.

### Validated 闂?generic expert-ranking evaluator

- `python -m unittest tests.unit.test_route_a_expert_ranking` 闂?3 tests passed.
- Python compilation and CLI-help checks passed.
### Implemented 闂?C1STN masked blind-validation execution boundary

The C1STN troubleshooting workbook is governed as `masked_validation_only`.
The 35-case blind query bank is query-only and is neither serving-eligible nor
KG-ingestion-eligible. It is executed from the existing Route A evaluator using
the full Route A graph plus local Ollama path; deterministic blind execution is
not exposed. The expected cause/action material is generated only into a local
human-review key from the authorized masked workbook and is never passed to the
KG, retrieval, prompt, or tuning path.

Changed files:

- `data/eval/route_a/c1stn_blind_queries_v1.json`
- `services/evaluation/route_a_blind.py`
- `scripts/eval/eval_route_a.py`
- `contracts/evaluation/route_a_blind_validation_input_v1.schema.json`

The query-bank loader enforces the same governed query-only contract at runtime; the JSON Schema is the versioned interchange contract.

Run artifacts are intentionally ignored under `data/eval/route_a/`; the query
bank is the only versioned blind artifact. No blind run has been executed and
no domain-correctness, reviewed-truth, or release claim is made.

### Validated 闂?C1STN blind-validation tooling

- `python -m py_compile scripts/eval/eval_route_a.py services/evaluation/route_a_blind.py` passed.
- `python scripts/eval/eval_route_a.py --help` exposes the blind query-bank,
  Ollama execution, and separate local human-review-key arguments.

### Reviewed / Released

- Not reviewed by a domain expert.
- Not released; not eligible for a reviewed domain-correctness or release-readiness claim.

### Planned — error-code seed to expert-ranking golden pilot

Use the independently sourced `raw__C1STN_error_data__C1STN Error code` dataset
(reported as 225 rows and not ingested into either v4.0 KG) as a seed for a
small expert-ranking pilot. It is an input to annotation, not an accepted
golden answer key.

1. Record the source's governed path, owner/version, masking status, and
   old/new-KG non-ingestion evidence.
2. Add a deterministic mapping adapter that pre-fills phenomenon candidates,
   error/alarm-code aliases, category context, and source-suggested repair
   actions for the existing annotation CLI.
3. Have a domain expert confirm or revise the phenomenon, add ranked causes,
   rank actions for each accepted cause, or select abstention when evidence is
   insufficient.
4. Pilot 10–15 cases before producing the full annotation queue; preserve
   source lineage, reviewer decision, confidence, and rationale for every
   resulting golden case.
5. Freeze development/validation/blind allocation before broad annotation;
   later run the same approved cases against old and new KG adapters.

Boundaries: KG retrieval results must not be shown as label authority; the
source repair action remains `source_suggested` until an expert accepts or
replaces it. This source supports an error-code/alarm-code scenario family and
does not by itself establish all free-text, multi-fault, or cause-evidence
coverage.

Status: planned only. No source content was opened in this planning update, no
adapter or annotation queue was created, and no golden labels were promoted.

### Implemented — golden annotation governance validation

The data-free annotation boundary now rejects:

- query types and difficulty values outside the golden-case contract;
- variants of one `scenario_id` assigned to different partitions;
- cause/action pairs whose cause is not selected;
- `adjudicated` maturity set by anyone other than an adjudicator;
- provisional blind labels; and
- reviewed/adjudicated labels whose anchors are not independently reviewed and
  eligible for evaluation.

Changed files:

- `services/evaluation/route_a_golden_annotation.py`
- `tests/unit/test_route_a_golden_annotation.py`

### Validated — contract and annotation boundary

- `contracts/evaluation/route_a_expert_ranking_input_v1.schema.json` parses as
  JSON and contains both `rank.maximum = 5` and
  `ranked_results.maxItems = 5`.
- No `schemas/evaluation/route_a_expert_ranking_input_v1.schema.json` exists in
  the live worktree. Repository references use the contract path, so no mirror
  was synchronized.
- `python -m unittest tests.unit.test_route_a_golden_annotation` — 10 tests
  passed.
- Python compilation for the annotation service and CLI passed.
- No file contents under `data/` were read by these checks.

### Open verification issue — expert-ranking implementation

The live worktree does not contain the evaluator files named by the earlier
implementation note:

- `services/evaluation/route_a_expert_ranking.py`
- `scripts/eval/eval_route_a_expert_ranking.py`
- `tests/unit/test_route_a_expert_ranking.py`

Therefore the earlier three-test expert-ranking validation claim has not been
reproduced in the current worktree. The frozen schema policy is present, but
downstream evaluator compatibility remains open.

### Implemented — C1STN seed-source governance paths

With explicit permission limited to
`data/governance/source_inventory.csv`, the inventory was updated without
opening any workbook or any file under `data/raw/`:

- `raw__C1STN_error_data__C1STN Error code`
  - current path: `data/raw/C1STN_error_data/C1STN Error code.xlsx`
  - raw, masking pending, review pending, not serving-safe, and not route
    eligible before masking/review;
- `raw__C1STN_error_data__CG Link  Trouble shooting`
  - current path:
    `data/raw/C1STN_error_data/CG Link  Trouble shooting.xlsx`
  - raw lineage source, unmasked, review pending, not serving-safe, and not
    directly eligible for evaluation or KG ingestion;
- `processed__masked__C1STN Trouble shooting-C1STN`
  - current path:
    `data/processed/masked/C1STN Trouble shooting-C1STN.xlsx`
  - masked-validation-only, assumed-label provisional, not serving-safe, and
    prohibited from development/validation tuning, KG ingestion, or promotion
    to Route A truth.

No masking-log event was fabricated or backfilled. The masked derivative's
workbook content, masking audit, rule version, run timestamp, and lineage
evidence were not inspected in this update.

### Planned — C1STN error-code seed masking subtask

Created:

- `subtasks/c1stn_error_code_seed_masking/brief.md`
- `subtasks/c1stn_error_code_seed_masking/acceptance.md`
- `subtasks/c1stn_error_code_seed_masking/notes.md`

The subtask adopts N's `phase1_v1` structured CSV/XLSX workflow and adds a
dedicated-source gate because the current `C1STN Error code.xlsx` filename is
not matched by an existing masking source. Under the current permission
boundary, the data owner runs header inspection, dry-run, and formal masking;
the agent may review only sanitized non-row reports unless separately
authorized.

The data-owner header report showed six direct Level C diagnostic columns,
zero unmatched columns, and zero unused rules. A dedicated
`v2_task001_c1stn_error_code_seed` masking source is now configured. Its three
free-text columns are review-flagged; because Level C values pass through, a
local content review remains mandatory before the output can advance beyond a
masked candidate.

### Validated — inventory update

- Inventory row count remained 151.
- The three updated source IDs are unique.
- The former
  `processed__review_pending__C1STN Trouble shooting-C1STN` identifier is no
  longer present.
- One unrelated pre-existing duplicate source ID remains for two
  `raw__C1STN_system_arch` paths; it was not modified.

## Next Step

After explicit permission to inspect the bounded C1STN/CGSF source and its
governance record, create a deterministic 10–15-case error-code annotation
pilot. Treat source actions as `source_suggested`, preserve source lineage, and
promote only independently reviewed/adjudicated labels. The C1STN blind-query
workflow remains a separate sealed evaluation path.

### Implemented — data-free golden annotation governance hardening

- `services/evaluation/route_a_golden_annotation.py`
- `tests/unit/test_route_a_golden_annotation.py`
- `tests/unit/test_route_a_expert_ranking_contract.py`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/golden_annotation_cli.md`

The annotation queue now enforces scenario-level partition integrity, the
contract coverage vocabularies, adjudicator-only `adjudicated` maturity,
reviewed/evaluation-eligible source anchors for reviewed gold, cause/action
referential integrity, and reviewed/adjudicated maturity for blind labels.

The expert-ranking contract is the only metric-policy artifact. Its frozen
policy constants and top-five constraints are verified directly from
`contracts/evaluation/route_a_expert_ranking_input_v1.schema.json`. There is no
`schemas/evaluation/route_a_expert_ranking_input_v1.schema.json` mirror in the
current worktree and no repository reference indicating that one is generated.

### Validated — data-free golden annotation governance

- `python -m unittest tests.unit.test_route_a_golden_annotation` — 10 tests
  passed.
- `python -m unittest tests.unit.test_route_a_expert_ranking_contract` — metric
  policy and top-five contract checks passed.
- `python -m json.tool
  contracts/evaluation/route_a_expert_ranking_input_v1.schema.json` — passed.
- Python compilation of the annotation service and CLI — passed.
- No file contents under `data/` were opened or processed.

### Open — real golden-set pilot

The user did not authorize inspection of the proposed C1STN/CGSF source or its
governance record. No source adapter, annotation queue, golden case, or label
was created. Further work remains limited to data-free contracts, synthetic
tests, and procedure design unless a future explicit bounded permission is
granted.

### Implemented and validated - C1STN provisional annotation seed

With explicit bounded permission, the corrected masked C1STN serving candidate
and its evidence were reviewed. The corrected formal run has 224 input,
canonical, and serving rows across six columns; manifest
`v2_task001_c1stn_error_code_seed_manifest_20260723T195218.json`, masking-log
event `mask_20260723T115218Z_c9f59e08`, and the post-mask audit are clean. No
raw workbook was opened.

Added a deterministic 15-case, development-only annotation queue at
`data/processed/review_pending/route_a/v2_task001_c1stn_error_code_annotation_seed_v1.json`,
implemented by `services/evaluation/route_a_golden_seed.py`,
`scripts/eval/build_route_a_annotation_seed.py`, and
`tests/unit/test_route_a_golden_seed.py`. The queue uses
`source_suggested_only` context, has no accepted labels, and is registered as
a masked, pending, non-serving annotation seed in
`data/governance/source_inventory.csv`. It must not be treated as KG truth, a
serving source, or a gold evaluation set.

Validation: `python -m unittest tests.unit.test_route_a_golden_seed
tests.unit.test_route_a_golden_annotation tests.unit.test_name_mapping` passed
22 tests; deterministic rebuild, seed validation, Python compilation, and
`git diff --check` passed.

### Next gate - controlled vocabulary, then independent expert review

The seed is ready for expert annotation only after the controlled cause and
repair-action ID vocabulary is supplied or a governed proposal workflow is
approved. Independent review and later adjudication may produce candidate gold
labels; evaluation remains blocked until those separate gates complete.

### Implemented - external-vendor vocabulary-reference masking boundary

Registered `raw__C1STN_error_data__Repair SOP_C1STN` as an unmasked raw SOP
with `route_eligibility=n_a`, `serving_safe=no`, and `reviewed_status=pending`.
It is authorized only as a locally masked controlled-vocabulary design
reference. It is prohibited as diagnosis data, KG input, serving evidence,
CGSF/C1STN truth, or gold-label authority. Diagnosis-source selection remains
outside this work and awaits the separately owned design decision.

Added the dedicated masking source
`v2_task001_vendor_repair_sop_vocab_reference`. It preserves the existing
Repair SOP field semantics while isolating this workbook from `repair_sop_v2`
through separate governed input, canonical, and serving source IDs. Machine,
station, and vendor fields are generalized in the serving candidate; Item,
Root Cause, Repair Action, and detailed repair text remain review-flagged.

The data owner reported a local inspection and five-row dry-run with 588 input,
post-filter, and post-deduplication rows, zero missing columns, no embedded
sensitive content, and no actual unnamed business column. The agent did not
open the raw `.xls`, its local `.xlsx` conversion, or any generated derivative.

Changed files:

- `configs/masking_rules.yaml`
- `data/governance/source_inventory.csv`
- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/notes.md`

Validation:

- Config-only rule resolution passed for all 12 governed columns.
- `scripts/ingest/run_mask_structured.py --list-sources` lists the dedicated
  source and exact converted-workbook pattern.
- The new raw inventory source ID occurs exactly once and the CSV retains its
  ten-column contract.
- `git diff --check` passed for the config and inventory changes; the existing
  CRLF-to-LF Git warning for the inventory remains visible.

Remaining gate: the data owner runs formal masking and a post-mask audit. The
generated derivatives must not be registered or used for vocabulary extraction
until manifest counts, lineage, governance IDs, review flags, and audit results
are reviewed. Even after that review, extracted vocabulary remains `proposed`
until CGSF canonicalization approval.

### Validated - external-vendor vocabulary-reference masking run

With explicit permission for the bounded run evidence and masked serving
candidate, run `maskrun_20260724T044210Z_fb72ad9d` was independently reviewed.
The manifest, lineage, and canonical masking-log event join on the same run ID.
The manifest and masking-log event carry the same governed input, canonical,
and serving source IDs and portable output/evidence paths.

The manifest reconciles 588 input, canonical, and serving rows across 12
columns, with no filtered or deduplicated rows, unmatched headers, or unused
rules. The 14,112 lineage records equal `588 rows * 12 columns * 2 views`.
All canonical fields pass through; the serving view has 5,292 C-level
passthrough records and 1,764 B-level generalizations. `Item`, `Root Cause`,
`Repair Action`, and `詳細維修動作描述` are review-flagged. The serving
candidate contains 588 rows and 12 fields, and `機種`, `工站名稱`, and
`廠商 Vendor` are each reduced to `[TO_TYPE]`. The data owner's post-mask
audit was reported clean.

Registered the canonical and serving derivatives in
`data/governance/source_inventory.csv` with `route_eligibility=n_a`,
`serving_safe=no`, `masking_status=masked`, and `reviewed_status=pending`.
Registration does not approve serving, KG ingestion, diagnosis use, or gold
authority.

### Analyzed - reference-derived Cause/RA vocabulary shape

The masked reference contains 129 distinct source Cause strings and 140
distinct source Repair Action strings before canonicalization. A heuristic
inventory found strong production-line clusters around sensors, pneumatic and
vacuum systems, material flow, motion/robotics, safety interlocks,
parameters/software, communication, vision/scanning, mechanical tooling, and
insufficient-evidence/no-fault states. Source spelling, Traditional/Simplified
variants, whitespace, symptom/cause mixing, and device-specific codes require
canonicalization; the 129/140 raw strings must not be copied directly into the
controlled vocabulary.

Recommended proposal shape: stable bilingual Cause families plus
mechanism-focused Cause IDs, and verb-object Repair Action IDs separated into
inspect/verify, measure/test, adjust/configure, reconnect/reseat,
reset/recover, clean/remove, replace, evidence collection, and escalation.
Vendor repair-action codes and device-specific image references remain source
aliases/evidence only. All extracted entries remain `reference-derived /
proposed` pending CGSF domain and canonicalization review.

### Implemented - domain-expert review workbook

Created the local review artifact
`docs/outputs/v2_task001_c1stn_domain_review_20260723/V2-TASK001_C1STN_Domain_Expert_Review.xlsx`
from the approved masked seed with
`scripts/eval/build_v2_task001_c1stn_domain_review_workbook.py`.

The workbook is a human-facing review aid, not an annotation log or gold-set
artifact. It contains a 15-case review queue, clear source-suggestion-only
context, editable proposed cause/action fields, decision/confidence/status
controls, and a blank pending-canonicalization vocabulary-proposal register.
No canonical IDs, accepted labels, or source-derived diagnostic truth were
created. The sealed blind-query set was not opened or used.

Validation confirmed four expected sheets, 15 queue rows, 20 queue columns,
three editable categorical controls, blank proposed-ID cells, and a blank
proposal register. Python compilation and `git diff --check` passed. Local
visual rendering was unavailable because no supported headless renderer is
installed; the workbook should be opened once in Excel before distribution to
confirm local viewer layout.

### Implemented and validated - regenerated proposed-vocabulary expert workbook

After the previous local workbook and seed were accidentally deleted, the data
owner explicitly authorized the exact C1STN raw workbook for regeneration. The
existing governed `v2_task001_c1stn_error_code_seed` masking pipeline produced
run `maskrun_20260724T073414Z_73fd54ad` and masking-log event
`mask_20260724T073414Z_41fc5acd`. The run reconciles 224 input, canonical, and
serving rows across six matched columns. A bounded residual-pattern audit of
the regenerated serving candidate found zero email, CN-phone, or employee-ID
matches.

The deterministic builder recreated the 15-case development-only seed at
`data/processed/review_pending/route_a/v2_task001_c1stn_error_code_annotation_seed_v1.json`.
It generated no accepted Cause or Cause/RA labels. The regenerated canonical,
serving, and seed artifacts are registered as masked, pending, non-serving,
and non-route-eligible in `data/governance/source_inventory.csv`.

Created the local workbook:

- `docs/outputs/v2_task001_vocab_pilot/V2-TASK001_C1STN_Expert_Review_Proposed_Vocab_v1.xlsx`

The workbook contains seven sheets: instructions, a 21-entry proposed Cause
catalog, a 16-entry proposed Repair Action catalog, 49 initial proposed allowed
pairs, the 15-case review queue, ID proposal guidance, and a blank vocabulary
proposal register. Review Queue dropdowns reference the catalogs; Cause and RA
names are formula-derived; Pair Check marks listed pairs `Allowed` and all
other combinations `Review pair`. All catalog entries and pairs remain
`reference-derived / proposed` pending CGSF domain and canonicalization review.

Validation:

- Post-export import confirmed seven expected sheets, 15 cases, 21 Causes, 16
  Repair Actions, and 49 proposed pairs.
- Formula inspection confirmed 45 lookup/pair formulas across the 15 queue
  rows, with bounded quoted cross-sheet references.
- An in-memory allowed-pair test returned the expected Cause/RA display names
  and `Allowed`; a non-listed pair returned `Review pair`.
- Formula-error scans found no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or
  `#N/A` cells.
- All seven sheets were rendered and visually checked. Titles, catalog tables,
  source/reference coloring, reviewer-input coloring, formulas, and proposal
  rows are legible; the intentionally wide queue remains horizontally
  scrollable with two frozen identifier columns.

Reviewed / released:

- Not reviewed by a CGSF domain expert or canonicalization owner.
- Not released. The workbook is a local proposal/review aid and is prohibited
  from diagnosis, KG, serving, or reviewed-gold use.

### Historical delivery record - provisional seed-to-golden workbook

The regenerated review workbook was previously reported at:

- `docs/output/V2-TASK001_C1STN_Seed_to_Golden_Review_Provisional.xlsx`

That file is absent from the current worktree and is not part of the
consolidated output package. The retained workbook is the proposed-vocabulary
review aid listed above. Do not use this historical delivery record as evidence
that the separately named provisional workbook is currently published.

The historical validation record reported that workbook as preserving the
seven-sheet structure, 15 masked review cases, 21 proposed Causes, 16 proposed
Repair Actions, and 49 proposed allowed pairs. Its Start Here sheet marked the
artifact `NOT GOLDEN YET` and required CGSF vocabulary review, independent
expert decisions, evidence anchors, and adjudication before any
reviewed/adjudicated export.

Recorded historical validation (not reproduced against the absent file):

- Post-export import confirmed all seven sheets and preserved lookup and pair
  check formulas.
- Formula-error scans found zero matching error cells.
- All seven sheets rendered successfully; the Start Here and Review Queue
  renders were visually checked and found legible and structurally intact.

Reviewed / released:

- Not independently reviewed or adjudicated.
- Not released as golden data and not eligible for diagnosis, KG, or serving.

### Implemented and validated - VS Code-readable CSV review bundle

Because the VS Code Office previewer could not display the valid OpenXML
workbook, exported its seven logical sheets as UTF-8 CSV files under
`docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Seed_to_Golden_Review_Provisional_csv/`.
The exports remove workbook-only title/merged rows and retain clean table
headers. The primary `05_Review_Queue.csv` contains one header plus all 15
masked cases; the Cause, Repair Action, and allowed-pair catalogs contain 21,
16, and 49 records respectively. Chinese text was verified after export.

The CSV bundle is a compatibility/review representation only. It does not
preserve dropdowns, formulas, formatting, or workbook validation and does not
change the provisional, non-golden maturity state.

### Consolidated - Task001 review outputs

The useful Task001 review artifacts now live under `docs/outputs/`: the
proposed-vocabulary XLSX and the seven-sheet CSV compatibility bundle. The
root `outputs/` inspection NDJSON and rendered PNG previews were removed as
regenerable QA snapshots after the workbook was retained. No golden, serving,
KG, reviewed-truth, or release claim follows from this consolidation.

### Validated - cleanup handoff review

- Four evaluation JSON contracts parsed successfully.
- `python -m unittest tests.unit.test_route_a_static_coverage
  tests.unit.test_route_a_golden_annotation
  tests.unit.test_route_a_expert_ranking_contract
  tests.unit.test_route_a_golden_seed` passed 19 tests.
- The blind query bank remains a 35-case query-only,
  `masked_validation_only`, non-serving, non-KG-ingestion artifact with
  `assumed_label_provisional` maturity.
- The retained XLSX is useful as a proposed-vocabulary review aid; the CSVs are
  compatibility exports. The removed inspection NDJSON and PNGs were derived
  QA snapshots.

Independent quality review remains `NOT_READY`: no frozen old/new adapters or
normalized snapshots, calibrated baseline, mutation evidence, paired
comparison, or independently reviewed/adjudicated gold labels exist. The
blind-review-key paired-argument check also occurs after blind execution in the
current CLI; malformed blind-key arguments must not be used until that ordering
is corrected. No blind or Ollama execution was performed during cleanup.

### Prepared - governance repair

The canonical inventory was rebuilt from the clean committed inventory plus
the verified Task001 source changes after a corrupted worktree copy was found.
The resulting inventory has 161 unique source IDs, no replacement characters,
and no duplicate IDs. The annotation event now references `V2-TASK001` and the
registered masked blind source. All declared masking source and derivative IDs
resolve exactly once.

Two risks remain visible: one superseded 2026-07-23 masking event retains an
unregistered historical canonical-output path, and three provisional eval-log
records reference an unregistered local static-audit report without a frozen
snapshot/config/maturity manifest. Neither is release-quality evidence.

### Implemented and validated - Chinese expert-review package v1

Generated the requested review-ready deliverables under the consolidated
Task001 review-output directory:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v1.xlsx`
- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_SOP_zh-CN_v1.docx`

The XLSX preserves the seven-sheet review workflow and replaces the brief
Start Here page with a complete Chinese SOP covering Cause, Repair Action,
Allowed Pair, Review Queue, rationale, confidence, pre-submission checks, and
adjudication. It retains 21 proposed Causes, 16 proposed Repair Actions, 49
proposed pairs, 15 masked review cases, dropdown-based reviewer inputs, and 45
lookup/pair-check formulas. It explicitly states `NOT GOLDEN YET` and keeps
diagnosis, KG, and serving out of scope.

Validation:

- Post-export XLSX import confirmed all seven sheets and the complete SOP
  range; formula-error scanning returned zero matches.
- All seven XLSX sheets rendered successfully and were visually inspected;
  Chinese text, tables, inputs, catalogs, formulas, and proposal rows were
  legible and structurally intact.
- DOCX structural validation confirmed required Chinese content, one Letter
  section with 1-inch margins, the selected compact-reference typography
  tokens, ten fixed-DXA tables, consistent cell widths, and no placeholder or
  replacement-character leakage.
- DOCX PNG rendering could not run because LibreOffice/soffice is absent on
  the host. Per the document workflow's permitted fallback, structural QA was
  completed, but the DOCX does not claim rendered visual verification.

Reviewed / released:

- The package is ready for independent expert review, not yet independently
  reviewed or adjudicated.
- It is not reviewed Golden data and is not released for diagnosis, KG, or
  serving.

### Implemented and validated - production-language review columns v2

Created the versioned expert-review workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v2.xlsx`

The Cause Catalog and RA Catalog each add two expert-input columns:

- `是否符合产线用户习惯？` with a controlled `是 / 否` dropdown;
- `若否：修正后贴合用户习惯的描述方式` for the expert's preferred
  production-language wording.

Both sheets explain that the correction is required when `否` is selected.
Conditional formatting highlights `是`, `否`, an empty required correction,
and a completed correction. The Start Here SOP was updated to direct experts
to these fields and to include them in the submission completeness check.

Validation:

- Post-export inspection confirmed 21 Cause rows and 16 RA rows with both new
  headers and blank expert-input cells.
- Exported worksheet XML retains the `是 / 否` data validations and the
  `否`-with-empty-correction conditional-format rules on both catalogs.
- Formula-error scanning returned zero matches; all 45 Review Queue lookup and
  pair-check formulas were preserved.
- All seven sheets rendered and passed visual inspection with no detected
  layout regression.

Reviewed / released:

- The added columns are ready for expert input but contain no review decisions.
- Workbook v2 remains provisional, non-Golden, and unreleased for diagnosis,
  KG, or serving.

### Implemented and validated - grouped expert-review fields v3

Created the versioned expert-review workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v3.xlsx`

The Cause Catalog and RA Catalog now place the four fields needed for the
production-language decision next to one another:

- column C: Chinese name;
- column D: Definition / Boundary;
- column E: whether the Chinese name fits production-line user language;
- column F: corrected production-line wording when the answer is no.

Family / Action Type, Status, and Source move to columns G-I. Catalog IDs and
Chinese-name lookup positions remain compatible with the Review Queue
formulas. The Start Here instructions were updated to describe the C-F review
sequence.

Validation:

- Post-export inspection confirmed 21 Cause rows and 16 RA rows in the new
  column order.
- Exported worksheet XML retains the yes/no data validations on column E and
  the required-correction conditional-format rules on column F for both
  catalogs.
- Formula-error scanning returned zero matches; all 45 Review Queue lookup and
  pair-check formulas were preserved.
- All seven sheets rendered and passed visual inspection with no detected
  layout regression.

Reviewed / released:

- Workbook v3 is ready for expert input but contains no review decisions.
- It remains provisional, non-Golden, and unreleased for diagnosis, KG, or
  serving.

### Implemented and validated - merged-review Chinese query v6

Created the versioned expert-review workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v6.xlsx`

Version 6 uses the merged Cause + Repair Review workbook v4 as its baseline.
The only content changes are the Review Queue header `I5` and the 15 Review
Query cells `I6:I20`, which were rewritten as Chinese expert questions. No
other workbook values or formulas changed.

Validation:

- A cell-by-cell comparison against v4 confirmed exactly 16 changed values,
  all in `Review Queue!I5:I20`, and zero formula changes.
- Formula-error scanning returned zero matches; all 30 Review Queue lookup
  formulas were preserved.
- Exported worksheet XML retains the combined Cause/Repair review validations
  and all Review Queue input validations.
- All five sheets rendered and passed visual inspection, including the merged
  Cause + Repair Review sheet.

Reviewed / released:

- Workbook v6 is ready for expert input but contains no review decisions.
- It remains provisional, non-Golden, and unreleased for diagnosis, KG, or
  serving.

### Implemented and validated - Chinese Review Query v5

Created the versioned expert-review workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v5.xlsx`

The Review Queue title, legend, and Review Query header are now Chinese. All
15 Review Query cells were rewritten as Chinese expert instructions based on
the alarm code and Chinese alarm description. The English source description
remains in its original evidence column for traceability and is explicitly
marked as not required for expert judgment. The Start Here instructions were
updated accordingly.

Validation:

- Post-export inspection confirmed the Chinese Review Query header and 15
  populated Chinese questions.
- Formula-error scanning returned zero matches; all 45 Review Queue lookup and
  pair-check formulas were preserved.
- Cause, Repair Action, and Review Queue data validations remain present in
  the exported worksheet XML.
- All seven sheets rendered and passed visual inspection with no detected
  layout regression.

Reviewed / released:

- Workbook v5 is ready for expert input but contains no review decisions.
- It remains provisional, non-Golden, and unreleased for diagnosis, KG, or
  serving.

### Implemented and validated - combined expert vocabulary review v4

Created a clean expert-facing workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v4.xlsx`

Cause and Repair Action vocabulary review now occurs on one worksheet. The
Cause catalog is shown on the left and the Repair Action catalog on the right,
with independent name, definition/boundary, production-language decision, and
correction fields. The workbook explicitly states that items on the same row
are not paired.

The expert-facing Cause-Repair Action pairing worksheet and Pair Check column
were removed. Review Queue retains separate Cause and Repair Action selection
and automatic name lookup, but no longer asks reviewers to interpret or
maintain compatibility rules. The workbook contains only five reviewer-useful
sheets: Start Here, Cause + Repair Review, Review Queue, Vocabulary Proposals,
and ID Proposal Guide.

Validation:

- Exported workbook inspection confirmed exactly five sheets, 21 Cause rows,
  16 Repair Action rows, and 15 masked review cases.
- Cause and Repair Action language decisions retain yes/no dropdowns and
  conditional correction prompts.
- Review Queue retains 30 Cause/Repair Action name-lookup formulas and the
  required dropdowns for Cause, Repair Action, Decision, Confidence, and
  Review Status.
- Formula-error scanning returned zero matches; exported worksheet XML
  contains no Allowed Pairs sheet name or Pair Check label.
- All five sheets rendered and passed visual inspection.

Reviewed / released:

- Workbook v4 is ready for expert input but contains no review decisions.
- It remains provisional, non-Golden, and unreleased for diagnosis, KG, or
  serving.

### Implemented and validated - two-sheet expert review v7

Created the streamlined expert-review workbook:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v7.xlsx`

The workbook now contains only the two worksheets that require expert input:

- `Cause + Repair Review`
- `Review Queue`

`Start Here`, `Vocabulary Proposals`, and `ID Proposal Guide` were removed.
The two retained worksheets preserve the v6 values, formulas, Chinese Review
Query content, formatting, data validations, and conditional formatting.

Validation:

- Post-export inspection and worksheet XML confirmed exactly two sheets.
- Cell-by-cell value comparison against v6 passed for both retained sheets.
- All 30 Review Queue lookup formulas were preserved with zero formula
  changes and zero formula-error matches.
- Cause/Repair review and Review Queue data validations remain present.
- Both sheets rendered and passed visual inspection.

Reviewed / released:

- Workbook v7 is ready for expert input but contains no review decisions.
- It remains provisional, non-Golden, and unreleased for diagnosis, KG, or
  serving.

### Recorded - user-reported domain expert pass, verbal evidence only

On 2026-08-18 the user reported that the validation material sent for domain
expert review has returned and passed. Stated scope, confirmed by the user in
this session:

- the proposed Cause and Repair Action vocabulary catalogs;
- the 15-case C1STN review queue;
- the 35-case blind query bank; and
- the expert-ranking input set.

Evidence basis and limits:

- The only evidence is the user's verbal confirmation. No completed workbook,
  reviewer identity, per-case decision, confidence, rationale, signature, or
  returned review artifact was provided or placed in the repository.
- The v1-v7 expert-review workbooks are not present on this branch. Workbook
  v7 exists only on the `kg_pipeline` branch (commit `ee3316a`) and was never
  committed to `feature/v2-data-pipeline`; only the CSV compatibility bundle
  and the v1 vocab-pilot workbook exist here. The reviewed artifact therefore
  cannot be fingerprinted on this branch.
- The golden-case contract requires per-case reviewer decision, confidence,
  and rationale, and `adjudicated` maturity requires an adjudicator. A verbal
  pass cannot by itself populate `reviewed` or `adjudicated` labels in the
  annotation queue or produce a reviewed expert-ranking export.
- The blind query bank remains sealed and query-only with
  `assumed_label_provisional` maturity. This report does not unseal it,
  execute it, or satisfy blind-label maturity requirements.
- The open verification issue on the missing expert-ranking evaluator
  implementation files is unchanged by this outcome.
- No file under `data/` was opened, parsed, or validated while recording this
  entry.

What this records and what it does not unlock:

- Recorded: a user-reported domain-review pass over the listed material as of
  2026-08-18.
- Not unlocked: reviewed/adjudicated gold labels, a reviewed expert-ranking
  run, blind execution, serving or KG eligibility, diagnosis use, or any
  release claim. Independent quality review standing remains unchanged.

Next gate:

- If a completed review artifact with per-case decisions exists, place it at
  a governed path. The independent quality reviewer then verifies it and, with
  explicit bounded `data/` permission, imports the decisions into the
  annotation seed. Only reviewed/adjudicated labels may be exported to a
  reviewed expert-ranking run.

### Recorded - acceptance decision: originals accepted as proposed

On 2026-08-18, in the same session as the verbal report above, the data owner
decided to accept the original as-sent review material as passed: approved as
proposed, with no modifications. This section supersedes the artifact-availability
limits recorded above; the evidence-basis limits below still stand.

Decision scope, confirmed by the user:

- The proposed Cause and Repair Action vocabulary catalogs (21 Causes, 16
  Repair Actions, including production-language wording) are domain-reviewed
  as proposed.
- The 15-case review queue's source-suggested cause/action pairings are
  promoted to `reviewed` labels by bulk data-owner attestation.
- The 35-case blind query bank is accepted as-is; it remains sealed,
  query-only, `assumed_label_provisional`, and unchanged by this decision.
- The gold labels for a pilot expert-ranking run may be assembled from the 15
  attested cases and the reviewed vocabulary.

Accepted artifact:

- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v7.xlsx`
  restored to this branch from `kg_pipeline` commit `ee3316a` (the file was
  never committed on `feature/v2-data-pipeline`).
- SHA-256:
  `ad0e18cb171c7418bf142f05933c4bb5deeb49585022b42ec9bd28db2962b205`.
- The restored file is untracked and unstaged; committing it is a separately
  authorized decision.

Evidence basis and surviving limits:

- Evidence remains the data owner's attestation of an unnamed domain expert
  review. Per-case reviewer decisions, confidence, and rationale were not
  individually captured; the provenance of all 15 reviewed labels is the bulk
  attestation recorded here.
- `adjudicated` maturity is not claimed; no adjudicator was involved.
- The missing expert-ranking evaluator implementation files remain an open
  issue; no expert-ranking run has been performed or authorized by this entry.
- No annotation-seed, governance-log, or other `data/` content was read or
  modified. Importing the attested labels into the annotation seed under
  `data/processed/review_pending/route_a/` still requires explicit bounded
  permission and independent quality-reviewer verification.
- No serving, KG-ingestion, diagnosis eligibility, or release claim follows.
- The independent quality review standing of this task is otherwise unchanged.

Changed files for this entry:

- `docs/tasks/V2-TASK001_route_a_shared_gold_eval_framework/notes.md`
- `docs/outputs/v2_task001_seed_to_golden_review/V2-TASK001_C1STN_Vocab_Golden_Review_Workbook_v7.xlsx`
  (restored)

Validation:

- SHA-256 recorded above; file restored byte-identical from commit `ee3316a`.
- `git status` shows the workbook as untracked only; nothing was staged.
- `python scripts/check_workflow_guard.py` passed; no protected workflow
  files changed.

### Implemented and validated - attestation-reviewed gold set and scenario registry under data/eval

With explicit bounded permission granted in-session for
`data/processed/review_pending/route_a/v2_task001_c1stn_error_code_annotation_seed_v1.json`,
`data/governance/source_inventory.csv`, `data/governance/annotation_log.jsonl`,
and new writes under `data/eval/route_a/`, the acceptance decision was
materialized as deterministic evaluation artifacts.

Added:

- `services/evaluation/route_a_reviewed_gold.py` - builder for the reviewed
  gold queue and scenario registry; validates both through the annotation
  governance service.
- `scripts/eval/build_route_a_reviewed_gold_v1.py` - deterministic CLI that
  extracts the accepted vocabulary from workbook v7 (fails closed unless
  exactly 21 causes and 16 repair actions are found) and joins it with the
  seed.
- `tests/unit/test_route_a_reviewed_gold.py` - 4 unit tests.
- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v1.json`
  (SHA-256 `300fa701aca16c475e18b68f700ec092710f6f01c180605f6dfccbd98cb1644b`) -
  15-case gold queue, `queue_state=reviewed_by_attestation`; per-case
  `review` blocks record `accept`/`reviewed`/`bulk_data_owner_attestation`
  with the accepted source-suggested material and
  `mapping_state=not_mapped`; 21-entry cause catalog and 16-entry
  repair-action catalog carried from workbook v7 as
  `reviewed_by_attestation`; empty pair catalog (v7 proposed none).
- `data/eval/route_a/route_a_scenario_registry_v1.json`
  (SHA-256 `f94fe671dfc060f86ea5f6c29c8b41ff700e8570f652bf69831c7b1d48967453`) -
  42 planned `RA-GOLD` scenario rows (4 development / 1 validation / 1 blind
  per type) per coverage plan v1, plus the 15 C1STN EC seed scenarios bound
  to the gold queue as `reviewed_by_attestation`.
- `data/governance/source_inventory.csv` - two new registration rows
  (`eval__route_a__v2_task001_c1stn_error_code_reviewed_gold_v1`,
  `eval__route_a__route_a_scenario_registry_v1`).
- `data/governance/annotation_log.jsonl` - one
  `route_a_annotation_bulk_attestation` event with both artifact digests, the
  workbook digest, decision `accepted_as_proposed`, and the verbal-evidence
  rationale.

Boundary decisions:

- Canonical cause/action selections were never recorded by any reviewer
  (workbook v7 queue rows carry no proposed IDs), so no per-case canonical
  mapping was invented; `mapping_state=not_mapped` is explicit on every case
  and bound scenario.
- The seed file, blind query bank, and task044 legacy seed were not modified.
- The gold queue remains not serving-safe and not KG truth; the blind
  partition is unaffected.

Validation:

- `python -m unittest tests.unit.test_route_a_reviewed_gold
  tests.unit.test_route_a_golden_annotation tests.unit.test_route_a_golden_seed
  tests.unit.test_route_a_expert_ranking_contract
  tests.unit.test_route_a_static_coverage` - 23 tests passed.
- Python compilation of the new service and CLI passed.
- Deterministic rebuild reproduced both artifact SHA-256 values exactly.
- Inventory recheck: 169 data rows, 10 columns, unique source IDs;
  annotation log reparse: 7 valid events.
- `python scripts/check_workflow_guard.py` and `git diff --check` passed.

Next gate:

- Canonical cause/action mapping per case remains the open path to a
  reviewed expert-ranking input; it requires either per-case expert
  selections or a governed mapping proposal, then independent quality
  review. The missing expert-ranking evaluator implementation files remain a
  separate blocker for any run.

### Implemented and validated - canonical mapping proposal v1

Added a deterministic alias-table proposal that bridges the accepted
source-suggested free text to the reviewed cause/action vocabulary:

- `services/evaluation/route_a_canonical_mapping.py` - fixed alias table
  (`c1stn_canonical_alias_v1`) with per-alias basis (`catalog_token` vs
  `interpretive_alias`) and substring matching over the case's Chinese and
  English descriptions, suggestion, and query.
- `scripts/eval/build_route_a_canonical_mapping_proposal_v1.py` - CLI.
- `tests/unit/test_route_a_canonical_mapping.py` - 7 unit tests covering
  evidence recording, interpretive flagging, out-of-catalog suppression,
  empty-suggestion and unmatched handling, and empty-gold rejection.
- `data/eval/route_a/v2_task001_c1stn_canonical_mapping_proposal_v1.json`
  (SHA-256 `bcb91698f8c035f699346da1d7b9c10288623c618a4dc400e7656f03bb74eadb`) -
  15 cases; 12 with proposed causes, 5 with proposed actions.
- Governance: one inventory row (reviewed_status=`pending`) and one
  `canonical_mapping_proposal_created` annotation event.

Honest gaps preserved as explicit unmapped entries:

- EC-002 (drawer seating) matches nothing in the vocabulary;
- EC-005/006 (no-content `无` suggestions) map nothing;
- EC-014/015 map `material.missing_or_removed` for cause but no action
  (manual loading has no catalog action);
- several cause mappings rely on interpretive bridges (cylinder
  not-in-position -> cylinder_stuck; not-enabled -> axis_drive_fault;
  vision-positioning -> camera_alignment_offset) that domain review must
  confirm or reject per case.

Validation:

- `python -m unittest tests.unit.test_route_a_canonical_mapping` - 7 tests
  passed; full TASK001 suite re-run green.
- Deterministic rebuild reproduces the proposal SHA-256 exactly.
- `python scripts/check_workflow_guard.py` and `git diff --check` passed.

Next gate:

- Domain review of the interpretive bridges and unmapped entries. On
  acceptance, regenerate the gold set with canonical labels
  (`mapping_state=mapped`) to produce the reviewed expert-ranking input.
  The missing expert-ranking evaluator files remain a separate blocker.

### Accepted - canonical mapping proposal v1

On 2026-08-18 the data owner reviewed the four interpretive bridges in
session and confirmed each as-is:

- cylinder not-in-position -> `cause.pneumatic.cylinder_stuck` (EC-001/003/007);
- axis not-enabled -> `cause.motion.axis_drive_fault` (EC-004/008);
- negative-pressure check -> `action.pneumatic.verify_air_supply`
  (EC-009/012);
- vision positioning -> `cause.vision.camera_alignment_offset` +
  `action.vision.verify_image_and_alignment` (EC-012/013).

The unmapped entries were also confirmed to stay unmapped: EC-002 (drawer
seating), EC-005/006 (no-content suggestions), and the missing actions for
EC-014/015 (manual loading has no catalog action). Evidence is the data
owner's session answers; no written review artifact exists.

### Implemented and validated - gold v2 with accepted canonical labels

- `services/evaluation/route_a_reviewed_gold.py` - added `build_gold_v2`
  (validates gold v1, requires every case in the proposal, rejects
  out-of-catalog IDs).
- `scripts/eval/build_route_a_reviewed_gold_v2.py` - CLI.
- `tests/unit/test_route_a_reviewed_gold.py` - 3 new tests (7 total).
- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v2.json`
  (SHA-256 `b92a4cc3e9db2c6065b5a0ab578da7e3861d0e404f8d99113a3f60c139e6c6d7`) -
  15 cases: 12 `mapping_state=mapped` with canonical cause/action IDs, 3
  explicitly unmapped with recorded reasons;
  `queue_state=reviewed_by_attestation_mapping_confirmed`;
  `pairing_state=not_asserted` (cause/action pairing is a separate decision).
- Governance: proposal inventory row flipped to `reviewed`, gold v2
  registered as `reviewed`, and one
  `canonical_mapping_proposal_accepted` annotation event.

Validation:

- `python -m unittest tests.unit.test_route_a_reviewed_gold` - 7 tests
  passed; full TASK001 suite green.
- Deterministic rebuild reproduces the gold v2 SHA-256 exactly.
- Inventory recheck (171 rows, unique IDs) and annotation-log reparse
  (9 events) passed; `python scripts/check_workflow_guard.py` and
  `git diff --check` passed.

Next gate:

- The gold side of the expert-ranking input is complete. Remaining blocker:
  rebuild the missing expert-ranking evaluator
  (`services/evaluation/route_a_expert_ranking.py`, its CLI, and tests)
  against the frozen
  `contracts/evaluation/route_a_expert_ranking_input_v1.schema.json`, then
  decide cause/action pairing and candidate-ranking supply (old/new KG
  adapters) for the first run.

### Implemented and validated - expert-ranking evaluator rebuild

Closes the earlier open verification issue: the evaluator files were never
committed on any branch (verified against `git log --all`), so they were
rebuilt from the frozen contract, not restored.

Added:

- `services/evaluation/route_a_expert_ranking.py` - dependency-free
  structural validation of the input contract (frozen metric policy equality,
  rank bounds and uniqueness, top-five limits, pair/action uniqueness,
  candidate identity) plus evaluation under
  `route_a_expert_ranking_metrics_v1`: cause and pair recall at 1/3/5, MRR@5,
  the abstention safety gate, domain-correctness aggregates restricted to
  `reviewed`/`adjudicated` labels, explicit failure and exclusion lists, and
  `composite_score: prohibited`.
- `scripts/eval/eval_route_a_expert_ranking.py` - CLI
  (`--input` / `--output`, exit code 2 on contract rejection).
- `tests/unit/test_route_a_expert_ranking.py` - 11 tests covering perfect
  and partial ranking arithmetic, the three abstention-gate branches,
  provisional-maturity exclusion, pair-less case handling, and contract
  rejections (unfrozen policy, six results, duplicate rank, rank zero).

Scope note: the historical implementation claim mentioned nDCG, but the
frozen contract's metric policy contains no nDCG term; the rebuild
implements exactly the frozen policy. Adding nDCG would require a new
contract version.

Validation:

- `python -m unittest tests.unit.test_route_a_expert_ranking` - 11 tests
  passed; full TASK001 suite re-run green; `--help` smoke passed.
- `python scripts/check_workflow_guard.py` and `git diff --check` passed.

Next gate:

- Decide cause/action pairing for the 12 mapped cases and the abstention
  encoding for the three unmapped ones, then supply candidate rankings via
  old/new KG adapters to execute the first reviewed ranking run.

### Planned - expert-ranking first-run subtask

Created:

- `subtasks/expert_ranking_first_run/brief.md`
- `subtasks/expert_ranking_first_run/acceptance.md`
- `subtasks/expert_ranking_first_run/notes.md`

The subtask owns pairing, abstention encoding, input assembly, and the
first frozen-policy evaluator run. Static-coverage execution and blind
execution remain separately gated: both wait on frozen adapter/snapshot
supply, and the blind run additionally requires the CLI argument-ordering
fix and reviewed/adjudicated blind labels.

## 2026-08-19 - expert-ranking first-run subtask: pairing and abstention decided

Work performed under the `expert_ranking_first_run` subtask with explicit
bounded in-session permissions (gold-v2 and mapping-proposal reads; proposal
and gold-v3 writes under `data/eval/route_a/`; governance appends; `data/raw`
excluded by the owner's instruction and untouched).

### Implemented and validated - pairing and abstention proposal v1

- `services/evaluation/route_a_pairing_proposal.py` - deterministic
  proposal builder over gold v2's accepted canonical labels: pairs are the
  case-level cross product of accepted causes x accepted actions, each with
  basis `shared_alias_evidence` (cause and action cite the same alias
  pattern in the accepted mapping proposal) or `case_level_cross_product`
  (binding needs domain confirmation); unmapped cases are proposed
  `abstention=required` with their recorded unmapped reasons. Fails closed
  on wrong queue/proposal ids, missing cases, or canonical-label drift.
- `scripts/eval/build_route_a_pairing_proposal_v1.py` - CLI.
- `tests/unit/test_route_a_pairing_proposal.py` - 9 unit tests.
- `data/eval/route_a/v2_task001_c1stn_pairing_abstention_proposal_v1.json`
  (SHA-256 `af90688f4c92db3c517beb97ae8a66b821212c1299211052c30711362a6f6d3c`) -
  15 cases: 11 proposed pairs across 5 cases (6 shared-evidence, 5
  cross-product flagged), 7 mapped cases with no reviewed action to pair,
  3 unmapped proposed abstention=required.
- Governance: inventory row (initially `pending`) and
  `pairing_abstention_proposal_created` annotation event.

### Accepted - pairing and abstention proposal v1

Data owner reviewed in session on 2026-08-19 and accepted as proposed:
all 11 pair bindings including the 5 case-level cross-product pairs
(acceptable pairs are case-level); the 7 action-less mapped cases stay
pair-less; abstention `required` for EC-002/005/006. Evidence is the data
owner's session answers; no written review artifact exists. Recorded as
`pairing_abstention_proposal_accepted`; inventory row flipped to `reviewed`.

### Implemented and validated - gold v3 with asserted pairing

- `services/evaluation/route_a_reviewed_gold.py` - added `build_gold_v3`.
- `scripts/eval/build_route_a_reviewed_gold_v3.py` - CLI.
- `tests/unit/test_route_a_reviewed_gold.py` - 5 new tests (12 total).
- `data/eval/route_a/v2_task001_c1stn_error_code_reviewed_gold_v3.json`
  (SHA-256 `471004a59a018d451f33d2a515d948b3b2c52ab426f9f0052e1c896e2d642e90`) -
  15 cases, `pairing_state=asserted`: 5 cases with 11 asserted
  `acceptable_action_pairs`, 7 `no_reviewed_action_to_pair`, 3
  `unmapped_abstention_required`; abstention 12 `not_expected` / 3
  `required`.
- Governance: gold v3 registered `reviewed`; `route_a_gold_v3_created`
  annotation event with digests.

### Validation

- Full TASK001 unittest run - 58 tests passed.
- Deterministic rebuilds reproduced both new artifact SHA-256 values.
- Inventory recheck: 173 data rows, unique source IDs; annotation-log
  reparse: 12 valid events.
- `python scripts/check_workflow_guard.py` and `git diff --check` passed.

### Risks and next gate

- Pair acceptance is case-level; a stricter per-pair binding requires a new
  reviewed decision and a gold v4, never an in-place edit.
- 7 pair-less mapped cases cannot contribute to the frozen primary metric
  `cause_action_pair_recall_at_3` (they still score cause recall/MRR);
  attaching actions there is an open domain decision, deliberately not
  taken.
- The gold side of the expert-ranking input is complete. Remaining blocker
  for the first run: frozen candidate rankings with full candidate identity
  from the KG adapter owner (`data_pipeline_kg_engineer`), then input
  assembly, evaluator execution, and report registration per the subtask
  acceptance criteria.

## 2026-08-20 - planned - old-KG candidate supply subtask

Created:

- `subtasks/old_kg_candidate_supply/brief.md`
- `subtasks/old_kg_candidate_supply/acceptance.md`
- `subtasks/old_kg_candidate_supply/notes.md`

The subtask owns the old-KG adapter work that the first-run subtask's
non-goals exclude: live graph verification against the 2026-05-18 audit,
frozen chain-row export with snapshot digest, the exact-normalized-text
canonical mapping (proposed -> data-owner approval), the frozen adapter
config and ranking rule, and per-case candidate supply through the real
retrieval path. Exploration confirmed the old KG is the local Neo4j
instance (`neo4j_cad_kg_v3_2`, started by the user), a prior adapter was
deleted and survives only as bytecode (design recovered: NFKC+casefold
exact matching, sha256 snapshot digest over sorted compact JSON,
proposed/approved gate), and nothing live currently emits `ranked_results`
in the contract shape. The old KG has no ranking scorer, so the ranking
rule (executor order, cause-dedup preserving first-seen actions, top 5,
`unmapped:<digest8>` pseudo-ids for unmapped causes) is frozen explicitly
in `configs/route_a_expert_ranking_old_kg_v1.json` and hashed into
`config_digest`.

## 2026-08-21 - old-KG adapter built; first frozen-policy run executed (zero-coverage baseline)

Executed under the `old_kg_candidate_supply` subtask with explicit bounded
permissions (read-only live Neo4j; gold v3 read; new
`data/eval/route_a/` artifacts; governance appends including
`eval_run_log.jsonl`).

### Implemented and validated

- `services/evaluation/old_tpdx_expert_ranking_mapping.py` - exact
  normalized-text mapping service (NFKC + casefold, never fuzzy) with the
  proposed/approved gate and sha256 snapshot digest; 10 unit tests.
- `services/evaluation/route_a_candidate_ranking.py` - frozen ranking rule
  (executor order, cause dedup with first-seen action union, top 5,
  `unmapped:<digest8>` pseudo-ids, no scores) and input assembly through
  the frozen contract validator; 17 unit tests.
- `scripts/eval/export_old_tpdx_chain_rows.py`,
  `scripts/eval/build_old_tpdx_canonical_mapping_v1.py`,
  `scripts/eval/build_route_a_expert_ranking_input_v1.py`;
  `configs/route_a_expert_ranking_old_kg_v1.json` (frozen adapter config).
- Artifacts under `data/eval/route_a/`: chain-row export (236 rows,
  snapshot `sha256:bd3d0981...`), mapping proposal + approved mapping,
  assembled input (15 cases, contract-valid), and the first
  expert-ranking report.
- Governance: 5 inventory rows, 3 annotation events, eval run
  `eval_20260821T043050Z_8480f9a6`.

### Verification findings (all registered as evidence)

- Diagnostic-layer counts match the 2026-05-18 audit (116/116/236/218/376);
  TRIGGERS 7-vs-11 divergence explained (audit-named orphan DR_ nodes
  removed post-audit, verified absent; not traversed by the gold queries).
- **Coverage gap**: 0/13 gold error codes exist in the old KG; the graph's
  116-code universe is disjoint from the gold seed sample. All 15 cases
  abstained via error_code not-found.
- **Vocabulary gap**: graph texts are raw field narratives; exact-text
  mapping matches 0/97 causes and 0/90 actions. Data owner accepted the
  zero-match mapping as-is after in-session elaboration.
- First run result: primary `cause_action_pair_recall_at_3=0.0`,
  abstention gate 12 failures / 3 passes, explicit failure list, no
  composite score. Deterministic rebuilds verified for input and report.

### Validation

- 49 tests across the touched modules green; CLI smoke passed;
  workflow guard and `git diff --check` clean; governance reparse clean
  (178 inventory rows unique, 15 annotation events, 4 eval runs).

### Risks and next gate

- The baseline is a coverage measurement, not ranking quality; it must
  not be quoted as old-KG diagnostic quality.
- **Resolved 2026-08-21 (data owner, in session)**: bounded seed read
  computed the overlap — 3 of 215 distinct seed codes (1.4%), all N03
  family, each carrying divergent fault content vs the current seed and
  placeholder `pending` causes in the graph (verified read-only). The old
  KG additionally contains V/W code families absent from the current seed
  table; the two EC universes are different vintages/scopes. Decision:
  `old_kg_baseline_concluded_not_signal_bearing`, registered as
  `old_kg_seed_overlap_analyzed` (annotation log).
- Old-KG baseline deliverable conclusion: the frozen-policy framework is
  proven end-to-end (adapter, contract, evaluator, registration), and the
  accurate measured result is that the old KG covers 1.4% of the current
  C1STN error-code space with divergent semantics on the overlap — it
  cannot serve as a calibrated baseline against current gold. This is the
  evidence for the new-KG path, not a failure of the evaluation.
- Requirement carried to V2-TASK003: new-KG ingestion must normalize to
  the reviewed cause/action vocabulary or ship a reviewed crosswalk, else
  the same comparison gap recurs. Signal-bearing ranking evaluation
  proceeds there; the shared gold (v3), evaluator, and adapter config
  conventions are ready for reuse.
