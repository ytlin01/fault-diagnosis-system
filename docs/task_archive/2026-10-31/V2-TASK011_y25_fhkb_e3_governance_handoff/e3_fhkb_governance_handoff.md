# E3 Y25 FHKB governance handoff

## Purpose

Perform a standalone, read-only discovery of the missing Phase 1 Y25
downtime/FHKB artifacts on E3. Do not run VLM, DEKG production, or graph
migration in the same governance session. This handoff does not grant
permission to read Y25 content.

## Before the E3 visit

- Assign an E3 custodian and the `data_workflow_lead` as discovery recorder.
- Carry this checklist and the frozen `fhkb_case_v1` and
  `fhkb_validation_policy_v1` versions.
- Do not pre-register a guessed Y25 source ID, version, checksum, or path.
- Do not copy raw or unmasked payloads into Git, chat, external services, or
  any VLM/DEKG working directory.

## Stage 1: metadata-only discovery

Locate by filename and filesystem metadata only:

| Historical lead | Intended role | Discovery result to capture |
|---|---|---|
| raw workbook matching `C1STN DT*.xlsx` or older `Val CG DT*.xlsx` naming | immutable Y25 downtime source | exact path, filename(s), size, modified time, custodian, storage zone |
| `data/processed/y25_downtime_canonical.json` | Phase 1 canonical derivative | exact path, size, modified time, associated sidecars |
| `data/processed/_governance/y25_downtime_governance.json` | historical governance sidecar | exact path, size, modified time |
| `data/processed/aggregates/rag_fp_case_candidates_v1.json` | Phase 1 Route C candidate artifact | exact path, size, modified time, named consumer binding |
| `data/processed/aggregates/structured_fp_join_v1_baseline.json` | review-only baseline | exact path, size, modified time; never mark as serving input |
| manifest, lineage, checksum, masking, or serving sidecars with the same source family | governance evidence | exact paths and relationship claims |
| Phase 1/E3 handoff bundle | custody evidence | bundle root, transfer record, source machine, receiving custodian |

If more than one candidate matches, stop at metadata and record every conflict.
Do not select the newest file as authoritative without provenance review.

## Stage 2: permission checkpoint

After Stage 1, request explicit permission naming the exact bounded files whose
contents must be inspected. Permission for the Vision SOP, DEKG/VLM run, or the
current repository's `data/governance/` does not cover these E3 files.

## Stage 3: approved governance evidence capture

For the raw source, establish:

- authoritative owner/custodian and allowed use;
- stable source ID proposal, source version/snapshot, exact checksum, and
  immutable governed location;
- sensitivity and field classification, including free text and personal,
  customer, vendor, equipment, and time fields;
- workbook/sheet scope, record count, deduplication rule, and source-record
  identity rule;
- raw-to-canonical lineage and whether the raw source was ever modified.

For each derivative, establish:

- schema and artifact version;
- input source/version and exact derivation configuration;
- manifest/config digest and checksum;
- record counts before filtering, after deduplication, accepted, review-held,
  rejected, and excluded, with reasons;
- masking run ID/rules version and residual-sensitive-content audit;
- record-level `source_refs` and collision behavior;
- serving-safe decision and reviewer evidence;
- producer marker `rag_case_pool`, candidate-only publication, and absence of
  diagnosis or `MappingRecord` promotion claims.

## Required disposition

Assign one of these evidence states to every located item:

| State | Meaning |
|---|---|
| `located_unread` | metadata exists; content permission not yet granted |
| `identity_review` | content inspected with permission; identity/version or custody is unresolved |
| `governance_review` | identity is adequate; masking, lineage, projection, or serving evidence is incomplete |
| `producer_input_candidate` | source evidence is adequate for an offline producer proposal; not yet accepted |
| `rejected_source` | unsafe, ambiguous, corrupted, unregistered, or unsupported source |
| `missing` | historical lead is absent from the inspected E3/bundle scope |

Do not use `accepted_candidate`, `serving_safe`, `reviewed`, or `released` as a
discovery result.

## Return handoff and serialized writes

1. The workflow lead records the E3 evidence and prepares a source-specific
   governance dry run.
2. The contract engineer reviews source identity/version, projection,
   record-level provenance, missingness, and collision rules.
3. One governance write owner updates only approved source/derivative rows and
   required masking or classification events, then performs exact read-back.
4. The pipeline/KG engineer receives the approved named input and produces the
   deterministic FHKB package; broad aggregate-directory scanning is forbidden.
5. The quality reviewer independently reviews the package and offline evidence.
6. N performs consumer validation. Index registration, evaluation logging,
   Data RC, and runtime activation occur only at their respective gates.

## Stop conditions

Stop and return `NOT_READY` for producer handoff if any of the following holds:

- no authoritative raw/canonical source can be identified;
- source version, checksum, custody, or owner is missing or conflicting;
- raw/unmasked content is found in a serving or candidate artifact;
- no record-level source identity or `source_refs` can be reconstructed safely;
- filtering/deduplication silently loses records or lacks disposition counts;
- an artifact claims reviewed diagnosis, confirmed cause, or in-place
  `MappingRecord` promotion;
- only the review baseline exists, while the named candidate artifact is
  missing;
- a tool requires scanning the aggregate directory rather than a named input;
- the E3 evidence cannot be brought back without violating data-security or
  custody rules.
