# Gate 1 - local SOP governance baseline

## Permission and read boundary

On 2026-07-27 the user explicitly authorized reading only
`data/governance/source_inventory.csv` to reconcile the E3 SOP inventory.
No referenced raw, processed, serving, evaluation, graph, or index artifact was
opened by this audit.

## Snapshot identity

- Canonical inventory rows: 161
- Inventory SHA-256:
  `c4d168e47b86a50ad508c18a1bda58843bd521f36241588698fbb572f2b70a21`
- Rows with exact `source_type=sop`: 17
- Canonical SOP-row-set SHA-256:
  `b1a4b81fef2bf020152dbd747bcad283807c7143e4b80277fa88c75f6f38c31a`

These hashes identify the reviewed local baseline only. They are not E3 source,
package, graph, or release hashes.

## Inventory summary

| Zone | SOP rows | Governance interpretation |
|---|---:|---|
| raw | 11 | Mother/source candidates; no raw row is serving-safe |
| processed | 4 | Historical Vision SOP residual registrations; all pending and absent from this worktree per their notes |
| serving | 2 | Two reviewed, masked, serving-safe registrations for the same apparent legacy `C1STN-_SOPV1.2_8aff482b6083` document family |

The 11 raw SOP registrations divide as follows:

| Route state | Count | Masking/review state |
|---|---:|---|
| `route_b` | 9 | all `masking=pending`, `reviewed=pending` |
| `route_a|route_b` | 1 | Vision SOP: `masking=pending`, `reviewed=reviewed` |
| `n_a` | 1 | repair vocabulary reference: `unmasked`, `reviewed=pending`; notes forbid KG ingestion |

## Reconciliation findings to test on E3

### G1 - legacy SOP serving lineage is incomplete

The inventory has two reviewed serving-safe SOP registrations:

- `serving__masked__C1STN-_SOPV1.2_8aff482b6083_vlm_masked_serving`
- `serving__unstructured__C1STN-_SOPV1.2_8aff482b6083_canonical_vlm_serving`

They appear to be parallel/stale-layout derivatives of one `doc_id` family,
but the inventory carries no explicit mother `source_id`, derivation/run ID,
supersession rule, or content checksum. E3 must show which artifact was loaded
and whether the two registrations represent one logical document or duplicate
graph input.

Historical documentation records a legacy graph with three
`RouteBDocument:DocumentAsset` documents, 4,941 Route B nodes, and 12,276 Route
B edges; one named document was `C1STN-_SOPV1.2_8aff482b6083`. That was a local
historical validation, not proof of current E3 state.

### G2 - nine raw Route B SOPs are not production-approved in inventory

Nine raw SOP mother/source candidates are Route B eligible but remain both
masking-pending and review-pending. No serving-safe SOP registration in the
inventory establishes their approved derivative lineage. If any is deployed on
E3, it requires an explicit source, masking, serving, review, and release
explanation; graph presence alone cannot close those gates.

### G3 - Vision SOP is not yet an approved DEKG production candidate

The Vision SOP mother registration is source-reviewed and governed for
`evidence_residual`, but remains non-serving with masking pending. Its four
historical residual rows remain pending, and `V2-TASK008` states that no real
candidate has been generated. If Vision SOP evidence is present on E3, treat it
as a governance exception pending exact lineage and producer evidence, not as
an approved release.

### G4 - reference-only repair SOP must not appear in DEKG

`raw__C1STN_error_data__Repair SOP_C1STN` is `route_eligibility=n_a` and its
notes explicitly prohibit serving or KG ingestion. Any matching E3 graph/index
record is a critical route-governance failure.

### G5 - the canonical inventory cannot prove deployment

The canonical columns are limited to source ID, path, zone, source type, route
eligibility, serving-safe state, masking state, reviewed state, date, and
notes. They contain no E3 database, deployment/run, graph/index, contract,
`evidence_id`, `doc_id`, block/chunk count, model/config, or release identity.
Therefore:

- the local inventory is the expected governance comparison set;
- the E3 graph plus its run manifest is the deployed evidence set;
- neither may substitute for the other;
- the intersection and differences must be reported explicitly.

## Provisional comparison classes

Each E3 SOP will be assigned exactly one initial class:

1. `registered_and_serving_approved`;
2. `registered_but_not_serving_approved`;
3. `registered_but_ambiguous_lineage`;
4. `registered_and_forbidden`;
5. `unregistered_on_e3`;
6. `inventory_expected_but_absent_on_e3`.

These are audit classifications, not release decisions. Independent review
still issues `READY`, `READY_WITH_EXCLUSIONS`, or `NOT_READY`.

## Remaining blocker

No E3/gx10 SSH or Neo4j endpoint is configured in this workspace. Complete
Gate 1 requires read-only E3 access or N's approved metadata-only export as
defined in `brief.md`.
