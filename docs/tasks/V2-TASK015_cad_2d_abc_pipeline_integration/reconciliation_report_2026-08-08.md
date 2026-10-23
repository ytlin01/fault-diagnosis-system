# V2-TASK015 reconciliation report - 2026-08-08

## Decision

Task 015 remains `planned`. The completed 54-record human review is valid JSON
and its PDF references are intact. Phase 1 governance was restored and
validated during this reconciliation, but the live review contract does not
yet admit the two reviewed `exclude` decisions. No A/B/C output is approved for
promotion.

## Permission boundary used for this reconciliation

The continuation handoff records explicit local read/write permission for:

- `data/governance/`
- `data/processed/`
- `reference_work/AAA*`

All content under `data/raw/` remains explicitly denied and was not opened,
parsed, hashed, sampled, copied, or indirectly processed. No local drawing
content or protected identifier was sent to an external service.

## Live-state and recovery audit

- Branch: `feature/v2-data-pipeline`
- Startup HEAD: `724b332`. During reconciliation, unrelated user commits
  advanced the current local HEAD through `7a0fd61` to `cc07048`; neither
  touches Task 015 or canonical governance paths and both were preserved.
- Pre-existing untracked paths at startup:
  `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/CONTINUATION_HANDOFF_2026-08-08.md`
  and `reference_work/`
- The current Task 015 config, service, CLI, and unit-test write paths are
  absent from the live branch.
- The local reflog contains no Task 015 implementation entry. Four unreachable
  commits exist; none provides a safe standalone Task 015 implementation
  commit.
- A recovery candidate exists at local and remote ref `kg_pipeline` /
  `origin/kg_pipeline`, commit `ee3316a`. It contains the Task 015 config, six
  service modules, five CLI scripts, and five unit-test modules. That commit
  also contains broad unrelated repository deletions, so it is not a safe
  cherry-pick target.
- Candidate files may be restored only selectively after governance and
  contract gates. They have not been copied into the current branch and have
  not been accepted as the current-v2 implementation.

## Source accounting

| Component | Cleaned AAA snapshot | `feature/material-layer` comparison | `kg_pipeline` recovery candidate | Current decision |
|---|---|---|---|---|
| A01 classification merge | Output present | Modular implementation present | Stage and tests present | Retain behavior; change review contract before use |
| A02 field extraction | Output present | Modular implementation present | Stage and tests present | Retain controlled-profile behavior; preserve missingness |
| A03 drawing index | Output present | Modular implementation present | Stage and tests present | Retain classification-left join and audit behavior |
| B01 ASM BOM | Output present | Modular implementation present | Stage and tests present | Retain only for reviewed ASM inputs |
| B02 audit | Output and historical record present | Absent from drawing subset | Stage, blockers, and tests present | Recover selectively; recompute all findings |
| C01 relationships | Edge and combined outputs present | Absent from drawing subset | Stage, blocking gate, overrides, and tests present | Recover selectively after B02 and contract review |
| C02 governed final candidate | Historical final output present | Absent from drawing subset | Stage and tests present | Recover selectively; no consumer/release approval implied |
| T00/T01 diagnostics | Historical evidence only | Probe tooling present | Redaction/inspection helpers present | Local diagnostic use only under approved-sample gates |
| Manual classification | 54-record derived package present | No `exclude` contract | Builder allows only `asm`, `prt`, `unresolved` | Preserve original review; extend governed contract |
| Redaction evidence | Not the source of serving approval | No whole-document safety proof | Redaction code and tests present | Keep 507 PDFs non-serving and KG-ineligible |

The historical branch remains comparison input only. `Faultdx_ref/` was not
accessed or used.

## Canonical governance state and hashes

The canonical governance store currently contains no Task 015 registration or
event:

| Canonical file | Records | Task 015 matches | SHA-256 before Phase 1 writes |
|---|---:|---:|---|
| `source_inventory.csv` | 161 | 0 | `a973baa8f178624511d56583fcca2aec68200776967161f0f7f9fec4370c376c` |
| `masking_log.jsonl` | 4 | 0 | `31788458636bf67ddc2865727380ec08bc6ec7f9353a8ed6fbfa42e73b8429d0` |
| `annotation_log.jsonl` | 1 | 0 | `ac6137a6b8f0ec19d0766100486c1395b88c557b8c0c865cbb72a3ec3e000097` |
| `index_registry.jsonl` | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `eval_run_log.jsonl` | 3 | 0 | `8a8b88a7b29c6447835eb09ece48921f383e5e2c5bab0c8f3801899fa2775b00` |

Phase 1 then added four source registrations, one masking-evidence
registration, and two annotation/governance events. Post-write validation and
hashes are:

| Canonical file | Records | Task 015 matches | SHA-256 after Phase 1 writes |
|---|---:|---:|---|
| `source_inventory.csv` | 165 | 4 | `376df3d4529de72b56cef8fbc0a02929243d5cdc3317c4ab136b3df8dd0810f5` |
| `masking_log.jsonl` | 5 | 1 | `95f8c5d0da3cf77bd7dd8fafd68758f0e89fa00ebdc2c79afdc54393f6ce70ed` |
| `annotation_log.jsonl` | 3 | 2 | `7c2e1504a073710c8785d6264f1c6f46afb62706e9998c2aa86392659e51cf9d` |
| `index_registry.jsonl` | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `eval_run_log.jsonl` | 3 | 0 | `8a8b88a7b29c6447835eb09ece48921f383e5e2c5bab0c8f3801899fa2775b00` |

CSV uniqueness, JSONL parsing, non-serving/KG-ineligible invariants, and the
absence of new `data/raw/` references all passed. No index or evaluation event
was fabricated.

Existing local evidence hashes used for reconciliation:

- cleaned handoff governance registration:
  `178f7266b22cf927341a88f1078792a070cf7d9aeb4aedec111452c468e1bda7`
- redaction candidate status:
  `9869b6dd4486e96a5db583a242638cff1119ff29489e0b784096d0ea68e80dc5`
- current redaction run manifest:
  `7b7dfabc44658cdcc1eae0a58dbff876365dd678fbda161dfdf5192468f55704`
- completed manual review file:
  `997e28ef1252a967c6433c3c41064ce0bfab5613a4be332282f844c60e6c98a1`
- manual review package manifest file:
  `871d65a60f15ce50d10e2eac67b8f11d53154102419ba85d517bcddc97c4b7f2`

The manual-review manifest's recorded canonical manifest digest remains
`4c2a4d5d0b45c488d960dbcf7b33fde4c21a59b4e274b2fc3696229d421cf4c1`.
The completed review changed the review-file digest; Phase 1 must record the
new reviewed artifact without regenerating or overwriting it.

## Completed human-review validation

- JSON syntax: valid
- Schema label: `cad_2d_manual_classification_review_v1`
- Records: 54; sequences are unique and cover 1 through 54
- Decisions: 8 `asm`, 44 `prt`, 2 `exclude`
- Confidence: 50 `high`, 2 `medium`, and 2 intentionally empty on excluded
  records
- Reviewer, review timestamp, and decision: present on all 54 records
- Exclusion reason: present on both excluded records as human text
  `empty drawing`
- Review PDFs: 54 present; all 54 recorded PDF SHA-256 values match
- Unique source identifiers and PDF digests: 54 each
- Package state remains non-serving and KG-ineligible

The source review artifact still declares `review_state` as
`pending_human_decisions` and its `allowed_decisions` omit `exclude`. These are
contract-state mismatches, not missing human work. Preserve this completed
artifact as immutable review evidence and apply decisions through a derived,
governed projection.

## Approved `exclude` contract change

The user's reviewed domain decision authorizes `exclude` as a classification
decision for records that must remain in lineage/audit but must not enter
A01/A03/BOM/KG promotion. The reviewed proposal must add:

- decision enum value `exclude`;
- required `exclusion_reason_code` when decision is `exclude`;
- reason code `empty_drawing` for the two reviewed human-text reasons
  `empty drawing`;
- optional/empty confidence for excluded records;
- retained source evidence, digest, reviewer, review timestamp, and human
  rationale;
- a derived review state indicating decisions are complete without mutating the
  original 54-record review file.

This approval is scoped to the reviewed records and does not authorize global
filename, suffix, title, or page-count heuristics.

## Next serialized owner and write set

Phase 1 owner `data_workflow_lead` completed the bounded inventory/governance
writes. The user directly approved the Phase 2 classification and identity
rules, then requested removal of the stale standalone contract/schema. The
approved rules are recorded in Task015 notes and remain enforced by behavioral
tests. Next owner: `data_pipeline_kg_engineer`, for selective recovery and
Phase 3 implementation.

Exact write set:

- `configs/pipelines/cad_2d_pipeline_v2.yaml`
- `services/ingestion/cad_2d_pipeline_v2/`
- `scripts/pipelines/cad_2d_v2/`
- `tests/unit/cad_2d_v2/`
- `docs/tasks/V2-TASK015_cad_2d_abc_pipeline_integration/`

The pipeline owner may selectively restore candidate blobs from `ee3316a` but
must not cherry-pick that commit. It must implement the immutable v1-to-v2
projection, adapt A01/A03/B01 and downstream audits to `exclude`, retain the
identity and missingness rules, and rerun all tests. C01/C02 remain blocked on
fresh B02 results.

## Phase 3 candidate result

The pipeline owner selectively restored only Task 015 blobs from `ee3316a`,
adapted them to the reviewed v2 projection, and produced exclusive-write local
candidates:

- v2 projection: 54 decisions; 8 `asm`, 44 `prt`, 2 `exclude`, zero
  `unresolved`; canonical JSON SHA-256
  `390f01ea46c3c999127ab5306c88d2bd59b12de6bdf8108a8828c43c6a77c3d9`;
- A01: 453 historical classifications plus 54 governed review additions = 507;
  result SHA-256
  `fd7b42c3feb617f3f324a55913e40b00a4aeaa57894c0eb0cad640b7ead682a7`;
- A03: 507 classification-left records, zero missing fields, zero field-only
  identifiers; result SHA-256
  `a9aa3cc8af2461a108e7696581643ae97f9d406b5949e838fff309b1980a2f70`;
- B01: 40 reviewed ASM definitions, 32 governed historical structured BOM
  candidates reused, and 8 newly reviewed ASM sources explicitly unavailable;
  result SHA-256
  `c875325955629dd6f9854f8abe120c18e128c0bb8792566e9361bea66d03baef`;
- B02: 36 blocking findings: 25 `SUSPICIOUS_IDENTIFIER`, 9
  `CLASSIFICATION_OR_EMPTY_BOM`, and 2 `BLANK_PART_NUMBER`; result SHA-256
  `24114e697c431b6513e55fad2c98c72f8bf7b6faad4661e47846e47ed9f58bdf`.

C01 was previewed and failed closed with all 36 blockers. C02 was not run. No
risk acceptance or override was fabricated. The candidate is not frozen and
cannot be handed to Task 016 yet.

## Validation and risks

Validation performed:

- branch, HEAD, worktree, Git history, reflog, unreachable commits, and branch
  trees inspected;
- authorized governance and processed artifacts parsed locally;
- all 54 review records and PDF digests checked without reporting protected
  identifiers;
- the governed v2 projection passed semantic tests and an in-memory projection
  of all 54 decisions;
- no external API or model call used.

Open risks:

- the current manual-review source schema is stale relative to the completed
  decisions and therefore remains immutable evidence rather than pipeline
  input without projection;
- the 507-PDF package has not passed independent whole-document visual/security
  review and remains non-serving;
- recovered code requires selective restoration, contract adaptation, and
  fresh tests; historical pass claims are not current evidence;
- C01/C02, 2D-to-3D reconciliation, graph activation, and Data RC remain out of
  scope at this gate.

## PDF-assisted B01 refinement

Using the repository virtual environment and the recorded bounded permission,
the pipeline locally verified and extracted word geometry from all eight
reviewed ASM PDFs. Seven configured pages contain readable BOM tables. The
reviewed three-page assembly contains fabrication/detail views but no BOM table
on any page; it therefore remains a governed source/reliable-header blocker and
no BOM was invented.

The refined B01 combines 32 governed historical structured parents with seven
fresh PDF-derived parents, for 39 of 40 reviewed ASM. It retains 219 extraction
findings and records explicit source provenance. Result SHA-256:
`232bb19c0e404f50ae398ab7d2057c0654040b825db9e392644c3ecb7953c7c1`.

B02 now consumes both the 39 candidate parents and B01 exclusions. It reports
266 findings, 261 blocking: 201 invalid extracted quantities, 17 blank extracted
part numbers, 38 suspicious identifiers, two blank part numbers, two
classification/empty-BOM findings, one reliable-header finding, and five
non-blocking item-sequence warnings. Result SHA-256:
`1729d868490816cd87222eaaaf13ee0380eb461002617a80b827638456533f37`.
C01 recomputed the same inputs and failed closed with 261 unresolved blockers;
C02 was not run. This refines, but does not erase, the earlier 36-finding
historical-only candidate result.

The final B00 boundary pins the immutable review file, v2 projection file, and
canonical B00 bundle digests in governed pipeline config. B00 revalidates exact
record decisions and PDF evidence against the immutable review; combined B01
rejects any bundle or manifest that differs from those pins. An independent
adversarial re-review replayed a forged-bundle attack and confirmed rejection,
with no remaining high/blocking code findings. This is code-review readiness
only; the 261 unresolved B02 blockers still prevent C01/C02 and release.

## Phase 3 safe-parser refinement

Subsequent PDF layout QA and adversarial review replaced broad below-header
parsing with strict same-row, center-owned BOM column assignment. Ambiguous
headers and unattached part-column continuation lines now produce explicit
findings instead of silently contaminating child identifiers.

The latest safe B01 contains 38 parents (32 historical and six fresh), leaves
two reviewed ASM unresolved, and reports 17 extraction findings. B02 reports 62
findings, 60 blocking. C01 recomputed the exact inputs and failed closed with
all 60 blockers; C02 did not run. These latest counts supersede the earlier
261-blocker candidate for current status while preserving it as historical
evidence.

Independent adversarial review found no remaining high/blocking parser defect,
and independent quality review reproduced the stored B01/B02 results and
validated their provenance and manifests. The implementation is code-review
ready and its safety evidence is acceptable; the data candidate remains
`NOT_READY` for promotion or release pending governed resolution of all 60
blocking findings.
