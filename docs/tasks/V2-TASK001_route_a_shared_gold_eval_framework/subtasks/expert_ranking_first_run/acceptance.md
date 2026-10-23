# Expert-ranking first run — acceptance

## Pairing and abstention decisions

- [x] Every mapped case (12) has accepted cause/action pairs with per-pair
      evidence, or an explicit no-pair reason.
- [x] Every unmapped case (3) has an accepted abstention encoding
      (`required` / `allowed`) or a recorded exclusion reason.
- [x] Decisions are recorded in the annotation log with the data owner's
      evidence basis.

## Candidate supply

- [x] Candidate rankings arrive from a frozen adapter output with
      `candidate_id`, `graph_version`, `snapshot_id`, `data_maturity`, and
      `config_digest`.
- [x] Unidentified, unfrozen, or graph-derived-label candidates are rejected
      and recorded as blockers.
- [x] Candidate output was not used to choose or tune pairs, abstention
      encodings, or cutoffs.

## Input and execution

- [x] The assembled input carries the frozen metric policy verbatim and
      passes `validate_expert_ranking_input`.
- [x] The evaluator run is deterministic and reproducible from the recorded
      input digest.
- [x] `reviewed`/`adjudicated` and provisional maturities are reported
      separately; no domain-correctness claim is made from provisional cases.
- [x] Abstention-gate failures are listed explicitly, never averaged away.
- [x] The report contains no composite score.

## Governance

- [x] The pairing/abstention artifacts, input, and report are registered in
      `source_inventory.csv` with correct eligibility flags.
- [x] Annotation-log events record decisions, digests, and rationale.
- [x] The sealed blind bank is untouched; no blind execution occurred.
- [x] `notes.md` records plan, changed files, validation, risks, and state.
