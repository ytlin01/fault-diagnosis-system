# V2-TASK001 subtask — C1STN error-code seed masking

## Goal

Create a governed masked derivative of
`data/raw/C1STN_error_data/C1STN Error code.xlsx` for a small V2-TASK001
expert-annotation seed. The derivative is annotation input, not a golden answer
key, reviewed Route A truth, a KG-ingestion source, or a serving release.

This subtask adopts the Phase 1 structured CSV/XLSX masking method inherited
from N. Current implementation and governance ownership remain on the A/data
line:

`inventory -> rules -> inspect -> dry-run -> formal masking -> manifest/lineage -> audit -> annotation-seed gate`

## Parent and ownership

- Parent: `V2-TASK001_route_a_shared_gold_eval_framework`
- Masking implementation owner: Data Pipeline and KG Engineer
- Governance owner: Data Workflow Lead
- Independent masked-candidate review: Data Quality Reviewer
- Later label review: domain reviewer and adjudicator

Only one write owner may change the masking source rule or generated masking
artifacts at a time.

## Governed source

- Source ID: `raw__C1STN_error_data__C1STN Error code`
- Path identifier:
  `data/raw/C1STN_error_data/C1STN Error code.xlsx`
- Current state: raw, masking pending, review pending, not serving-safe, and
  not route eligible
- Reported scope: 225 error-code rows; the pipeline must record the observed
  row count and explain any blank-row filtering or deduplication

The current user restriction prohibits the agent from opening, parsing,
previewing, hashing, or otherwise inspecting this workbook or any file under
`data/raw/`. Commands that read the workbook are data-owner-run commands unless
the user later grants new, path-specific permission.

## Phase 1 method checked

The method was verified against `origin/phase1_v1`:

- `configs/masking_rules.yaml`
- `services/ingestion/masking_engine.py`
- `services/ingestion/structured_masking.py`
- `scripts/ingest/preview_masking.py`
- `scripts/ingest/run_structured_masking.ps1`
- `docs/data/structured_masking_runbook.md`
- TASK-002 through TASK-004 masking records

The current branch retains the Phase 1 three-view workflow and adds stricter
header inspection, alias reporting, required-pattern checks, automatic header
detection, and explicit rejection of legacy `.xls` inputs.

## Configuration decision

Do not formally run either existing source:

- `error_codes_raw` expects `C1STN Error code.xlsx`;
- `error_code_catalog_v2` expects three differently named files and requires
  all three.

After the header-only inspection is reviewed, add a dedicated source named:

`v2_task001_c1stn_error_code_seed`

Its configuration must:

- match only `C1STN_error_data/C1STN Error code.xlsx`;
- select the reviewed sheet and header row explicitly;
- allowlist every retained column;
- classify all discovered columns as A, B, or C;
- tokenize/drop discovered A-level identifiers;
- retain B-level context internally and generalize or drop it in the serving
  candidate;
- review-flag free-text descriptions, cause text, and repair/action text;
- keep all source causes/actions as `source_suggested` candidates;
- deduplicate deterministically while reporting excluded rows; and
- use a unique source name so it cannot overwrite another source's outputs.

## Outputs

Expected outputs use the current branch's governed zone topology:

- canonical:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/v2_task001_c1stn_error_code_seed_canonical.json`
- serving candidate:
  `data/processed/serving/structured/v2_task001_c1stn_error_code_seed_serving.json`
- manifest under:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_manifests/`
- row-level lineage under:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_lineage/`
- governance summary under:
  `data/processed/canonical/structured/v2_task001_c1stn_error_code_seed/_governance/`
- a masking-log record created by the successful pipeline run

These paths are planned names. Generated contents remain local/governed and
must not be committed merely because masking completed.

The artifacts have distinct authority:

- the masking run manifest is immutable technical evidence for one run;
- row/field lineage is the detailed transformation audit for that run;
- the `_governance/` sibling is a run-local filtering/deduplication summary,
  not the canonical governance store;
- `data/governance/` is the canonical cross-zone inventory and operational
  event registry; and
- a future Data RC integration manifest is a reviewed delivery selection, not
  a masking run manifest.

One `run_id` must join the run manifest, lineage records, and canonical
masking-log event. The masking-log event must use governed inventory source IDs
and portable evidence paths.

## Boundaries

- Raw input remains immutable.
- No raw row or dry-run preview may be pasted into chat, task notes, Git, or an
  external service.
- A masked artifact is not automatically serving-safe.
- Masking success does not review or confirm a cause/action.
- The annotation seed is built only after masking audit and governance review.
- Only a 10–15-case development pilot is created initially.
- The 225-row source covers an error-code scenario family; it does not satisfy
  all V2-TASK001 scenario types.
