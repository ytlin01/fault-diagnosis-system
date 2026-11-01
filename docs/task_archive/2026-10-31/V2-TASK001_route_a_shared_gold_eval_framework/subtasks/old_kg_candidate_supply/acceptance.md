# Old-KG candidate supply — acceptance

## Graph verification and export

- [x] Live old-KG counts verified read-only against the 2026-05-18 audit
      (116/116/236/218/376/11); divergence recorded or explained.
- [x] Chain rows exported deterministically (sorted, compact) with the
      snapshot digest recorded; re-export from the same DB state
      reproduces the digest.
- [x] No mutating query ran against the graph.

## Canonical mapping

- [x] Mapping uses exact normalized text matches only (NFKC presentation
      forms + casefold); no fuzzy or semantic matching.
- [x] The mapping proposal is registered and reviewed before any scored
      use; the data owner's accept/edit/reject decisions are recorded in
      the annotation log with the evidence basis.
- [x] Graph element IDs appear only inside the mapping artifact, never in
      the expert-ranking input.
- [x] Unmatched graph texts are counted and reported, not hidden.

## Candidate supply

- [x] Candidate identity carries `candidate_id`, `graph_version`
      (`neo4j_cad_kg_v3_2`), `snapshot_id`, `data_maturity`
      (`assumed_label_provisional`), and `config_digest` (sha256 of the
      frozen config file).
- [x] Rankings follow the frozen rule: executor order, dedup by normalized
      cause text preserving first-seen actions, top 5, unmapped causes keep
      their rank slot as `unmapped:<digest8>` pseudo-ids, no scores.
- [x] Abstention is observed, not tuned; over-answering on
      required-abstention cases is recorded as-is.
- [x] Candidate output was not used to choose, edit, or tune gold labels,
      pairs, abstention encodings, or cutoffs.

## Governance

- [x] New artifacts and governance appends happen only under explicit
      bounded permission; `data/raw` untouched.
- [x] Inventory rows and annotation events record decisions, digests, and
      rationale; the eval run is registered in `eval_run_log.jsonl`.
- [x] `notes.md` records plan, changed files, validation, risks, and state.
