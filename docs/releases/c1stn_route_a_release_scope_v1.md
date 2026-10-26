# C1STN Route A — first-release scope

Status: scope draft for owner review; release readiness is open.
Owner and final release authority: Alice Lin. Earlier A/N handoff assignments in
the inherited documents are historical for this personal repository.

This document selects the first release's product boundary. It does not approve
any data candidate, activate a graph, or claim that the system is deployable.
The task packages remain the source for implementation and review state.

## User promise

The first release supports **C1STN** diagnosis through **Route A** only. A user
may:

1. Enter a C1STN error code directly; or
2. Describe a C1STN error in ordinary language, which the system maps to a
   governed `Phenomenon` before following a reviewed diagnostic chain.

The answer may contain a reviewed phenomenon, code, cause, paired action,
action steps, and source references. It must distinguish a confirmed reviewed
chain from a candidate, an ambiguous match, and missing evidence. It must not
invent a cause, action, step, asset relationship, or material recommendation.

## Included data and contract boundary

- **Diagnostic facts:** the governed C1STN Error Code source only. Release 1
  does not require Repair SOP or reviewed table extractions as diagnostic
  sources. A producer task that still lists them must be narrowed before its
  release-1 implementation is accepted.
- **Asset context:** the C1STN CAD 2D A/B/C `phase3r10` candidate, subject to
  independent acceptance. The release does not claim 2D-to-3D reconciliation.
- **Material context:** the C1STN BOM04 replacement list, producing reviewed
  `ReplacementPart` nodes only. Station usage remains a review candidate;
  material-to-topology and action-to-material edges are absent until their
  source and endpoints are governed and reviewed.
- **Contracts:** TPDX KG Schema 4.2 and `faultdx_data_package_v1` version
  `1.0.0`. `Phenomenon` and `MappingRecord` keep their frozen meanings and
  provenance. Candidate, reviewed, serving, and released are separate states.

### Documented version register

The project owner chose to use documented versions for this scope exercise,
without opening files under `data/`. A listed digest is a historical task
claim unless explicitly marked as verified in this source snapshot. Final
input and package digests must be frozen and checked before release.

| Item | Selected documented identity | Current limitation |
|---|---|---|
| C1STN Error Code | `raw__C1STN_error_data__C1STN Error code`; raw path `data/raw/C1STN_error_data/C1STN Error code.xlsx`; corrected masking manifest `v2_task001_c1stn_error_code_seed_manifest_20260723T195218.json` | Raw workbook digest/version is not in this copied repository. The masked annotation input is development-only, not approved Route A truth. Freeze the actual input digest and governed review decisions before production. |
| CAD asset candidate | Task 015 `phase3r10`; freeze-manifest SHA-256 `e76469c5cb84bd37bfab883c0f9e6910990cd0dbe62b3feff5e52e7ca21452e8` | Task notes report a frozen review candidate; independent acceptance remains open. The manifest itself was excluded from this source copy, so its current digest and the historical code fingerprint were not rechecked. |
| BOM04 material input | `raw__C1STN_bom_material__L_ReplacementList`; workbook SHA-256 `b80f1d845884f5747818e76fe76b44f8aeab239b61b9349663826754167facdf` | Digest is declared in Task 017's old handoff. Run1 is superseded because its salt was lost. A new retained-salt candidate and matching rerun are required. |
| TPDX KG Schema 4.2 | Schema SHA-256 `1fb4d2ad4dea63cb0a875ffb1dd941a4fa86387e6bb92a58f9cb229f253f4310`; ontology SHA-256 `27e9bf79098a5e29787425f6c3b4287de022db6809014bd1544c6b94f7c9fd2b` | Both hashes were verified against this personal source snapshot. Contract is frozen; this does not approve candidate data. |
| Data package contract | `faultdx_data_package_v1` `1.0.0`; contract SHA-256 `737d14c7608a8ef086346780702b9f58daf8c006d61b6444cd593c828f01ab9f`; schema SHA-256 `e386857c88a7848f47b55e541cfa8558cf38031883fe170b983d2da9eb96e1d5` | Both hashes were verified against this personal source snapshot. A frozen envelope contract is not an assembled release package. |
| Evaluation reference | Task 001 reviewed gold v3, SHA-256 `471004a59a018d451f33d2a515d948b3b2c52ab426f9f0052e1c896e2d642e90` | Documented evaluation artifact, not a serving source; not included in this source copy. The old-KG run is a coverage baseline, not calibrated diagnostic quality. |

## Release acceptance criteria

The project owner can approve release only after the following evidence is
recorded against exact code, input, contract, package, graph, and query
versions:

1. **Governance:** every included source has owner, version, sensitivity,
   masking, lineage, review, route, and serving decisions. Only explicitly
   reviewed Route A assertions can reach user-facing results.
2. **Diagnostic authority:** Error Code records preserve source anchors,
   `Phenomenon`/`MappingRecord` identity, and explicit reviewed
   Cause-to-Action pairing. Missing or conflicting facts enter reason-coded
   queues or exclusions. No source heading or extraction result grants review
   authority.
3. **Two input flows:** a known in-scope code returns the corresponding
   reviewed chain; a description resolves through governed phenomenon
   labels/aliases. Multiple plausible matches ask for clarification or return
   an explicit ambiguous state. Unknown codes, unmatched descriptions, and
   incomplete reviewed chains abstain safely.
4. **Result faithfulness:** every displayed cause, action, step, asset, and
   material claim is backed by a permitted source anchor and review state.
   Unreviewed candidates and unsupported material relationships never appear
   as confirmed answers.
5. **Reproducibility and integration:** accepted components produce stable
   identities, manifests, hashes, and exclusions under equivalent inputs.
   The assembled package validates against the frozen contract; shadow-graph
   import, read-only queries, provenance, state filtering, idempotency, and
   executable rollback are demonstrated before runtime use.
6. **Independent evaluation:** applicability, labels, thresholds, exclusions,
   and safety gates are frozen before scoring. Pipeline, graph, domain,
   query, provenance, and safety results are reported separately, including
   regressions, ambiguity, missingness, and abstention. Blocking safety or
   provenance failures prevent release regardless of aggregate scores.
7. **Owner decision:** Alice Lin reviews the evidence and records one release
   decision and its exact included versions, exclusions, rollback steps, and
   unresolved risks. `READY_WITH_EXCLUSIONS` is acceptable only when every
   exclusion is bounded and enforceable in the running system.

The exact quantitative evaluation thresholds and case applicability must be
preregistered before candidate scoring; none are invented by this scope note.

## Explicit deferrals

- Route B document evidence and Route C historical cases, including their
  retrieval and answer paths. Tasks 008–011 do not gate release 1.
- Repair SOP and table extraction as diagnostic fact sources. The currently
  registered Repair SOP is a vocabulary-design reference only.
- 2D-to-3D reconciliation and any claim of complete physical topology.
- Material-to-asset or action-to-material relationships without governed
  topology and reviewed endpoint/pairing evidence; station usage is not an
  edge. Material nodes alone do not justify a repair recommendation.
- GraphRAG as a default diagnostic path, unreviewed semantic promotion, and
  autonomous repair actions.
- Additional equipment beyond C1STN and any historical old-KG answer path.

## Shipping backlog status reconciliation

This is a routing snapshot from the copied task documents, not a fresh data or
deployment validation. The owning task notes decide implementation state.

| Work | Evidence-backed state for release planning | Next gate |
|---|---|---|
| Task 001 C1STN gold/evaluation | Reviewed gold v3 and evaluator exist; old-KG comparison established a coverage mismatch | New-KG evaluation with frozen candidate and preregistered applicability |
| Task 012 Schema 4.2 | Frozen contract | Preserve exact version and semantics |
| Task 014 package contract | Frozen `faultdx_data_package_v1` 1.0.0 envelope | Produce and validate actual component/release packages |
| Task 015 CAD | `phase3r10` candidate frozen for Task 016; not released | Independent domain/contract review and reconciliation of accepted code with the frozen fingerprint |
| Task 017 material | Run1 superseded by lost salt; masking evidence review remains open | Retain new salt, add fingerprint, produce matching fresh-dir runs, issue corrected handoff |
| Task 016 independent CAD/material review | Open; material determinism and domain labels block final recommendation | Verify new material handoff and independent labels; review CAD and material |
| Task 019 diagnostic producer | Planned; brief still names three source families | Narrow release-1 source adapters to Error Code and record exact governed input/review authority |
| Tasks 020–022 package, shadow graph, query adapter | Planned | Implement in dependency order after accepted components and query contract |
| Task 023 independent Data RC | Planned | Freeze inputs, score six layers, issue independent readiness recommendation |
| Task 024 governance test set | Planned review | Resolve governance fields and independent applicability/label review |
| System release | Not approved or deployed | Validate both C1STN user flows against accepted versions, rehearse rollback, then obtain the owner's decision |

## Scope closure and next work

The product boundary and release-1 source selection reflect the owner's
decisions. The owner still needs to accept the proposed release criteria in
this document before milestone 1 is marked complete. Exact raw input
fingerprints, accepted candidate versions, quantitative thresholds,
independent review, and deployment evidence are delivery gates, not claims of
completion here. Once scope is accepted, start with Task 017's retained-salt
material re-freeze and Task 016's independent labels; Task 019's Error
Code-only producer design can advance after its brief and acceptance are
narrowed.

No file contents under `data/` were inspected to prepare this scope note.
