# V2-TASK016 notes

## 2026-09-01 - blocker 2 scaffold: reviewer fill-in label file + validator (no domain labels authored)

### Plan

- Unblock domain-label authoring without touching any candidate: generate a
  fill-in JSONL scaffold (one record per source row plus the merge pair) with
  mechanical fields pre-filled and judgment fields marked `REPLACE_ME`, and a
  per-line validator implementing the guide's fill-workflow step 2. The agent
  authors no domain truth: no `expected` value, `decision`, or independence
  attestation is filled.

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/review_labels.jsonl`
  (created): 54 scaffold records — 53 source-row records
  (`MAT-node-id-001..053`, anchors `…#工作表1!r4..r56` copied verbatim from
  frozen run1 lineage) plus `MAT-merge-001` anchored on the r44+r49 pair
  (identified from lineage: the two rows sharing target
  `RP_63c1753c…c1f3`, i.e. the single exact name+spec merge).
- `docs/tasks/V2-TASK016_material_cad_independent_validation/validate_review_labels.py`
  (created): schema + publish-rule validator (placeholder/pending detection,
  material anchor shape, duplicate id/anchor checks, leakage-status and
  maturity gating, sensitive-column-name heuristic, overlap reminders).
- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`
  (this entry).

### Validation

- Data reads confined to the recorded grant (read `data/processed/…/run1/`;
  raw not permitted); user re-confirmed this session. `lineage.jsonl` read:
  53 records, anchors byte-verified as proper UTF-8 `工作表1` (an apparent
  mojibake was console display only; hex probe confirmed `E5 B7 A5 E4 BD 9C
  E8 A1 A8`).
- Validator on the scaffold: 54/54 pending, 0 invalid, 0 warnings (expected:
  all records carry placeholders).
- Self-test on a synthetic substituted temp copy (deleted after): 54/54
  publishable, 0 invalid; warnings limited to the advisory overlap
  confirmation and the expected merge-vs-member row overlap. Scaffold shape
  proven schema-valid end to end.
- Anchors are source-row references, salt-invariant: the scaffold remains
  valid across the TASK017 re-freeze.

### Risks

- Every `REPLACE_ME` field (expected, decision, labels_source, source_basis)
  plus `label_maturity` (default `provisional` = calibration-only),
  `leakage.status` (default `unchecked` = not publishable), and `overlap`
  (default `false`) must be consciously set by the domain reviewer; pending
  or default states never reach scoring.
- The validator's leakage scan is a column-name heuristic; the value-level
  check against the 13 sensitive columns remains the domain reviewer's
  responsibility.
- Filename `review_labels.jsonl` implements the guide's "JSONL file named by
  this task"; renaming requires updating the validator default.

### State

- Blocker 2: scaffold ready, awaiting domain-reviewer labels (user);
  decision state unchanged: `planned`.

## 2026-09-01 - decision: re-freeze (path A); bounce-back issued to V2-TASK017

### Plan

- Record the data owner's decision — path A: re-freeze under a retained salt;
  the path-B acceptance re-scope is rejected — and issue the bounce-back
  request with findings and remediation requirements for the TASK017 owner.

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/re_freeze_request_task017.md`
  (created): findings F1-F4, four remediation requirements, the TASK016
  re-verification checklist, and reviewer constraints.
- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`
  (this entry)

### Validation

- No candidate, config, or code modification (reviewer write boundary held);
  no new data reads beyond the already-granted scope.

### Risks

- The re-freeze depends on TASK017-owner and data-owner execution (salt
  generation and retention, manifest salt-fingerprint change, run3/run4, new
  handoff). Until then the determinism acceptance line stays open and the
  material candidate under review remains the superseded run1.

### State

- Determinism acceptance: open, pending TASK017 re-freeze and TASK016
  re-verification. Blocker 2 (domain labels): scaffolded, awaiting domain
  input; unaffected by the re-freeze.
- Salt parameter (2026-09-01, same session): data owner chose the **shared**
  salt — one `FAULTDX_MASKING_SALT` for masking tokenization and parser
  identity; recorded in bounce-back requirement 1.
- Salt v2 minted 2026-09-01 at the data owner's request: `secrets.token_urlsafe(48)`
  (64 chars, ~384 bits), written directly to a file under the owner's temp
  directory; the value never entered the conversation transcript. Durable home
  is the owner's password manager; the temp file is a convenience buffer to be
  deleted after run3/run4 verify. sha256 fingerprint (public by design, and
  the value requirement 2 requires in the new manifests):
  `4faf694203f82c7c9acb0a627ca7488bc940a493b7ab1aab80c2a3e05cae6cbf`.
  run3/run4 manifests must reproduce this fingerprint exactly; a mismatch
  means the wrong salt was set.

## 2026-09-01 - determinism rerun: run1 salt confirmed lost — remediation decision

### Update

- Data owner confirmed the run1 `FAULTDX_MASKING_SALT` was removed. F4 is
  therefore confirmed: `material_cef539710b861b7d` is not reproducible as
  written — salted identity reproduces only with the exact run1 salt, which no
  longer exists (sha256 is one-way; the salt cannot be derived from the frozen
  artifacts).

### Recommendation (reviewer, for workflow-lead / governance decision)

- Preferred: re-freeze. TASK017 re-runs the candidate under a newly retained
  salt (governed pepper held by the data owner), issues a new handoff with a
  new run_id, and TASK016 re-verifies a fresh run reproduces it. This restores
  byte-equivalent determinism and also fixes reproducibility of the masking
  derivatives, which are tokenized with the same `FAULTDX_MASKING_SALT`.
- Alternative: re-scope the determinism acceptance to "same input + same salt
  -> same output" (structural determinism), already demonstrated by run2
  (identical names/specs/counts/anchors; only salted ids differ). Requires
  explicit workflow-lead approval because it weakens the stated acceptance.
- Not acceptable: treating run2 (different run_id) as a pass, or marking the
  determinism acceptance as satisfied.
- If re-freeze is chosen, the reviewer recommends TASK017 also:
  - record a non-reversible salt fingerprint (e.g. sha256 of the salt value) in
    the run manifest. The current manifest records only the env-var *name*,
    which is why the mismatch surfaced only as a changed run_id; a fingerprint
    makes future salt mismatches detectable without exposing the secret;
  - ship run1' and run2' both executed under the retained salt, with both
    manifests in the new handoff, so determinism evidence travels with the
    freeze instead of remaining an open item;
  - rerun into a fresh output directory (`run2/` holds the salt-mismatch
    evidence and the builder refuses overwrite);
  - record the salt-retention requirement (set, run, clear from env, retain the
    value in the owner's secret store) in the runbook and the masking subtask
    notes — the same `FAULTDX_MASKING_SALT` tokenizes the masking derivatives,
    so pre-existing masked artifacts predate the new salt and must be annotated
    as such (co-source, non-promoting; not a violation, but divergent salt
    provenance).

### State

- Determinism acceptance line stays unchecked; decision pending on re-freeze vs
  re-scope. Domain labels (blocker 2) still pending.

## 2026-09-01 - determinism rerun (run2): NOT reproduced — salt mismatch

### Plan

- Verify a fresh-dir run2 against the frozen run1 to close the determinism
  acceptance ("run2 must reproduce `material_cef539710b861b7d`").

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`
  (this entry)

### Validation

- run2 completed as `complete_candidate` (exit 0) with six artifacts under
  `run2/`.
- run2 manifest: `run_id material_d2cb8e547f07252a` (target was
  `material_cef539710b861b7d`); input/config/schema/code digests identical to
  run1; counts identical (52 nodes / 53 rows / 0 exclusions / leak_count 0).
- Byte-equivalence vs run1:
  - `exclusions.json` and `leak_report.json` are byte-identical (non-salted).
  - `candidate.json`, `lineage.jsonl`, and `audit.json` differ.
- Structural diff of the differing artifacts, ignoring salted ids:
  - candidate node keys (label, canonical_name, specification, aliases,
    replacement_policy, identity_rule_version) identical across all 52 nodes;
  - lineage (target_type, source, extracted_from) identical across 53 records;
  - merge_audit and review_queue keys identical; counts equal;
  - only the salted `RP_` ids differ — 0 of 52 node ids in common — and the
    run_id derived from them.

### Finding

- F4 (determinism): run2 reproduced every non-salted aspect of run1
  byte-for-byte but did not reproduce `material_cef539710b861b7d`. Root cause:
  run2 executed with a different `FAULTDX_MASKING_SALT` than run1. The identity
  rule is `RP_ + sha256(salt + name|spec)`, and the run_id embeds the salted
  result, so a different salt changes every node id and the run_id while
  leaving names/specs/counts/anchors unchanged.
- Consequence: the "reproduce material_cef539710b861b7d" acceptance line is not
  closed. It reproduces only with the exact run1 salt. If the run1 salt is a
  retained secret, re-run run2 with it; if it was a one-shot cleared secret,
  the acceptance as written is unsatisfiable and must be re-scoped (structural
  determinism "same input+salt -> same output", or a re-freeze pair under a
  newly retained salt with a new handoff).

### State

- Review decision state: `planned`; run1 gates verified, determinism rerun
  failed to reproduce the target run_id (salt mismatch), domain labels pending.

## 2026-09-01 - validated: run1 freeze integrity and contract gates (bounded data read)

### Permission (user-granted, recorded)

- Read: masked derivative only; the raw document (`data/raw/...`) is **not**
  permitted.
- Read/write: `data/processed/`, including
  `data/processed/review_pending/route_a/v2_task017_material_candidate/run1/`.

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`
  (this entry)
- `docs/tasks/V2-TASK016_material_cad_independent_validation/acceptance.md`
  (data-content permission box)

### Validation (run1, within the granted `data/processed/` scope)

- All five run1 artifacts re-hashed and matched the run manifest's
  authoritative `outputs.*.sha256`: candidate `2345af1d…cfb`, exclusions
  `37517e5f…b570`, lineage `5076bd51…5ad`, audit `12e94732…79134`,
  leak_report `c890b27b…1349`. Freeze integrity confirmed.
- Manifest: `run_id material_cef539710b861b7d`, `run_status complete_candidate`,
  `promotion_state candidate`, `graph_activation false`; config/schema/code/input
  digests match the handoff; `salt_source FAULTDX_MASKING_SALT`,
  `identity_rule_version material_identity_v1`.
- Candidate: 52 `ReplacementPart` nodes, 0 edges, all ids `RP_<64-hex>`,
  `schema_version 4.2`, `payload_kind diagnostic`; JSON Schema 4.2 validation
  errors 0.
- Counts reconcile: 53 consumable rows -> 52 nodes (one exact name+spec merge),
  0 collision_nodes, 0 spec_missing, 53 review entries, 53 lineage records,
  0 document exclusions.
- Lineage: 53 records, all `target_type=node`,
  `source=raw__C1STN_bom_material__L_ReplacementList`, anchors well-formed.
- Leakage: 23 forbidden values checked, `leak_count 0`.
- Rollback: `graph_import false`, `activation_required false`.

### Findings

- F1 (documentation, not a candidate defect): the handoff's declared
  `lineage.jsonl` sha256 line is a 62-hex transcription (missing `c0`); the
  authoritative 64-hex value in the manifest matches the file. Belongs to the
  TASK017 handoff document.
- F2 (format): `lineage.jsonl` is a JSON array, not line-delimited JSON, and
  lineage records carry no `run_id`; run-to-lineage binding is via the
  manifest's content digest. Acceptable; recorded for completeness.
- F3 (input verifiability): the raw input digest `b80f1d84…facdf` is
  manifest-declared only; it cannot be independently recomputed under the
  granted scope (raw access declined).

### State

- Review decision state: `planned`; run1 freeze/contract/leakage/provenance
  gates verified, domain scoring not started.
- Determinism rerun (run2) still requires a raw-input run with the run1 salt —
  data-owner executed; the reviewer verifies the result under `data/processed/`.

## 2026-09-01 - independent pre-read verification: fingerprints and synthetic suite

### Plan

- Verify the frozen material candidate's code/config/schema identities
  independently before any data-content read (reviewer instructions 1-2 and
  the acceptance independence gate).
- Confirm the synthetic suite and the salt-dependency of the run identity,
  then surface the determinism-rerun requirement.

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`
  (this entry)
- `docs/tasks/V2-TASK016_material_cad_independent_validation/review_labels_guide.md`
  (created): label format, maturity vocabulary, independence/leakage rules,
  applicability/exclusions, fill workflow.
- `docs/tasks/V2-TASK016_material_cad_independent_validation/review_labels.schema.json`
  (created): JSON Schema for one review-label record; validated with
  `jsonschema.Draft202012Validator.check_schema`.

### Validation

- Code fingerprint (service + CLI, the manifest's combined-files algorithm)
  recomputed: `96adf904dcacab3fbe0237fc7af447fa79bdeb0614b90f727c100e3ec7258c98`
  — matches the handoff and the TASK017 freeze record.
- Config `configs/pipelines/replacement_extract.yaml` sha256
  `fda9e16522e884c39543e97343d5d6a9dcf58a13670b065d2e5e7a66070c823f` — matches.
- Schema `contracts/schema/tpdx_kg_schema_v4_2.schema.json` sha256
  `1fb4d2ad4dea63cb0a875ffb1dd941a4fa86387e6bb92a58f9cb229f253f4310` — matches;
  `$id` = `tpdx_kg_schema_v4_2` and `x-contract-status` = `FROZEN` confirmed.
- Synthetic suite `tests/unit/test_material_layer_v2.py`: 19 passed (synthetic
  fixtures only; determinism, salt-sensitivity, leak fail-closed, and
  overwrite-refusal covered).
- No file under `data/` was opened, parsed, sampled, or otherwise content-read.

### Findings

- `run_id` is salt-dependent: `material_<sha256(config|inputs|schema|code|result)[:16]>`
  where `result` embeds the salted `RP_` node ids
  (`RP_ + sha256(salt + name|spec)`). Reproducing `material_cef539710b861b7d`
  therefore requires the identical `FAULTDX_MASKING_SALT` used by run1. That
  salt is a data-owner controlled secret cleared after the run; the manifest
  records only its env-var name, not its value. Consequence: the run2
  determinism rerun is a data-owner-executed action — an independent reviewer
  cannot reproduce the run_id without the salt. Recorded as a
  verifiability/reproducibility observation, not a candidate defect.

### State

- Review decision state: `planned`; independent verification started, candidate
  scoring not started.
- Blocker 2 (independent material/CAD review labels): label guide and schema
  scaffolded; domain labels are supplied by the domain reviewer (user decision).
- Determinism rerun (run2): user elected to provide the run1 salt plus bounded
  data permission; the rerun will be agent-executed once those are provided.

## 2026-09-01 - handoff received: material candidate frozen (receipt fact, not review)

Recorded by the `V2-TASK017` owner; no review work is performed here. The
2026-08-11 material-side blocker is closed:

- `V2-TASK017` froze run `material_cef539710b861b7d` (`complete_candidate`)
  and handed it off via
  `docs/tasks/V2-TASK017_material_parser_integration/material_candidate_handoff_task016.md`
  (freeze declaration, fingerprints, artifact digests, reviewer
  instructions, known open items).
- Frozen artifacts:
  `data/processed/review_pending/route_a/v2_task017_material_candidate/run1/`
  (candidate, exclusions, lineage, audit, leak report, manifest).
- Known open items carried in the handoff: real-data rerun determinism not
  yet demonstrated; optional candidate registration; masking-subtask
  independent review open.

Remaining startup blockers for the combined review: independent
maturity-tagged leakage-checked labels with bounded data permission
(blocker 2), and Git recoverability of the local freezes via a separately
authorized commit (blocker 3). Review owner: `data_quality_reviewer`, who
must be independent of the `V2-TASK017`/`V2-TASK015` implementation.

## 2026-07-31 - planned

### Plan

- Keep review independent from `V2-TASK017` and `V2-TASK015` implementation.
- Freeze candidate/config/manifest identities before evaluation.
- Preregister applicability, labels, exclusions, leakage checks, and go/no-go
  gates.
- Separate reproducibility, contract/pipeline correctness, domain correctness,
  regressions, and faithfulness/safety.
- Return an evidence-backed readiness recommendation without tuning candidates.

### Changed files

- `docs/tasks/V2-TASK016_material_cad_independent_validation/brief.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/acceptance.md`
- `docs/tasks/V2-TASK016_material_cad_independent_validation/notes.md`

### Validation

- Confirmed `V2-TASK016` was unused before allocation.
- Reviewed the independent quality-review role and workflow boundary.
- Named candidate suppliers, review owner, evidence inputs, scorecard layers,
  failure visibility, recommendation states, and next decision boundary.
- No candidate, material, CAD, or review data content was read.

### Risks

- Review cannot start until both candidates, configs, manifests, exclusions, and
  rollback evidence are frozen.
- Independent labels and bounded data permission remain unavailable.
- Material/CAD domain accuracy cannot be inferred from synthetic tests or KG
  output alone.

### State

Task decision state: `planned`.

## 2026-08-11 - startup blockers after Task015 CAD freeze

### Current evidence

- The former CAD-side blocker is closed. Task015 Phase 3 r10 is frozen in place
  with a complete failure inventory, governance references, 14 stage artifacts,
  and a 22-file local code/config/test fingerprint.
- The CAD freeze manifest is
  `data/processed/review_pending/route_a/v2_task015_cad_2d_pipeline_v2_candidate/task015_freeze_manifest.json`.
- The material-side blocker remains. Task017 is `planned`; no material parser,
  controlled configuration, tests, candidate, exclusions, audit, leakage
  report, or run manifest has been produced.

### Startup boundary

- Task016 remains `planned` and no independent candidate scoring has started.
- The quality reviewer may prepare the preregistered plan after normal startup
  confirmation, but the combined review cannot satisfy its candidate-freeze
  gate or issue a final recommendation until Task017 hands off a frozen material
  candidate.
- Any Task016 direct or indirect data read requires its own exact bounded user
  permission. Task015's freeze permission does not transfer to Task016.
- Task016 must not modify, tune, or repair the frozen CAD candidate.

### Open blockers

1. Task017 must name the authoritative compatibility decision and approved
   Schema 4.2 material surface, implement and validate the parser, and freeze a
   governed material candidate.
2. Task016 requires independent, maturity-tagged, leakage-checked CAD and
   material labels plus explicit bounded permission before scoring.
3. The Task015 code/config/test freeze is content-addressed but local-only until
   a separately authorized commit supplies Git recoverability.

### State

CAD candidate input: `frozen and handed off`.

Material candidate input: `blocked / absent`.

Task016 decision state: `planned`; combined evaluation not started.
