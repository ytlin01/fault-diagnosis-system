# V2-TASK017 acceptance

## Contract and ownership

- [x] `data_pipeline_kg_engineer` is the single implementation write owner.
- [x] The user confirmed material-schema compatibility review is complete.
- [x] The authoritative compatibility artifact, decision, and approved material
  node/relationship surface are named in the task package.
- [x] Historical Schema v4.0 assumptions are mapped, rejected, or migrated
  explicitly; no parallel active contract is created.

## Parser behavior

- [ ] Approved BOM03 and BOM04 inputs are supported independently. (Stale
  wording: BOM03 was removed by brief decision 5; reword at next revision.)
- [ ] Canonicalization, salted identity, lineage, collision handling, and output
  order are deterministic and versioned.
- [x] Only approved node labels and relationships are emitted. (Real run
  `material_cef539710b861b7d`: node-only, JSON schema + semantic passed.)
- [x] Ambiguous or unresolved joins become review candidates, not graph edges.
  (53 station-usage review entries, zero edges.)
- [ ] Missing values remain missing and unsupported semantics are not inferred.
- [x] Supplier, price, equipment, internal-code, unapproved station, and other
  forbidden values fail leakage validation. (23 forbidden values checked,
  leak_count 0; fail-closed path covered by synthetic tests.)

## Reproducibility and evidence

- [ ] Equivalent input/config/code/contract versions produce byte-equivalent
  canonical candidate and manifest artifacts.
- [x] The manifest fingerprints inputs, config, code, active contracts, outputs,
  exclusions, candidate queues, and validation results. (Run
  `material_cef539710b861b7d`.)
- [x] Synthetic positive, negative, layout-drift, collision, leakage, and
  determinism tests pass. (19 tests + 4 subtests, 2026-08-27.)
- [x] Exact commands, observed results, exclusions, and risks are recorded.
  (Notes entry 2026-09-01.)
- [x] A frozen candidate is handed to `V2-TASK016` without being modified by
  the independent reviewer. (Run `material_cef539710b861b7d` frozen 2026-09-01;
  handoff document `material_candidate_handoff_task016.md` declares
  immutability and assigns digest verification to the reviewer.)

## Masked derivative (subtask)

- [x] Masking of the governed BOM04 input is tracked under
  `subtasks/c1stn_replacement_list_masking/` with its own brief,
  acceptance, and notes.
- [x] Formal masking, post-mask audit, masking-log evidence, and derivative
  registration complete per the subtask acceptance before any downstream use
  of the masked derivatives. (Completed 2026-09-01, run
  `maskrun_20260901T034134Z_865c656a`; independent review remains open in the
  subtask.)

## Data-content permission

- [x] Task creation did not inspect any real BOM, base-triple, alias, salt, or
  generated-output content.
- [x] Exact paths and explicit user permission are recorded before any direct or
  indirect real-data read. (Real-data runs are data-owner executed; agent
  reads are bounded and recorded in the subtask notes; the raw workbook
  remains unopened by the agent.)
