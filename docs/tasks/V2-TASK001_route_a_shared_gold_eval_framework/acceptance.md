# V2-TASK001_route_a_shared_gold_eval_framework - Acceptance Criteria

## A. Gold Independence and Governance

- [ ] One golden-case contract is used for both old and new KG domain evaluation.
- [ ] Domain labels cite independent reviewed evidence and annotation status.
- [ ] Neither KG's returned candidates are automatically accepted as correct labels.
- [ ] Graph-specific identifiers are isolated in adapter mapping artifacts.
- [ ] Reviewer disagreement and adjudication are recorded.
- [ ] Provisional cases cannot be reported as reviewed domain correctness.

## B. Coverage and Split Integrity

- [ ] Scenario registry covers EC, phenomenon, asset, ambiguous, partial-chain, multiple-valid-answer, and no-hit/abstention cases.
- [ ] Coverage is reported by equipment scope, query type, difficulty, language, and review maturity.
- [ ] Development, validation, and blind partitions are split by underlying scenario.
- [ ] Leakage and duplicate-scenario checks pass.
- [ ] Blind labels are inaccessible to graph construction, retrieval, and prompt tuning paths.

## C. Reusable Framework

- [ ] One normalized Route A evaluation-result contract is documented and validated.
- [ ] Old and new KG adapters conform to the same contract.
- [ ] The shared scorer has no graph-specific Cypher, node labels, or physical IDs.
- [ ] Entity, ranking, chain, abstention, provenance, faithfulness, safety, and operational metrics are reported separately.
- [ ] A primary comparison metric and non-negotiable safety gates are frozen before blind execution.

## D. Old-KG Calibration

- [ ] Old KG dataset, adapter, query preprocessing, and configuration versions are frozen in the run manifest.
- [ ] At least 10 representative cases have hand-calculated expected metric results.
- [ ] Controlled mutations cover missing answer, lowered rank, wrong cause/action pairing, missing provenance, unsupported claim, and failed abstention.
- [ ] Each mutation changes the intended metric or gate.
- [ ] Repeated execution against the same snapshot produces equivalent results.

## E. New-KG Reuse and Paired Comparison

- [ ] New KG is connected by an adapter without changing shared gold labels.
- [ ] Identical cases and scorer configuration are used for old and new KGs.
- [ ] Report includes old-pass/new-fail, old-fail/new-pass, both-fail, and applicability-excluded cases.
- [ ] Capability exclusions are explicit and are not silently counted as passes.
- [ ] Blind comparison runs only after both graph configurations are frozen.

## F. Documentation and Safety

- [ ] No raw or sensitive data is committed or sent to an unapproved external endpoint.
- [ ] Existing evaluation scripts are inventoried and reused, superseded, or kept separate with documented reasons.
- [ ] `notes.md` records changed files, commands, results, risks, and next steps.
- [ ] Failed checks and known weak scenarios remain visible in the final report.
