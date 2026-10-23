# V2-TASK020 acceptance

## Ownership and frozen contract

- [x] `V2-TASK020` was unused before allocation.
- [x] The frozen `faultdx_data_package_v1` contract is consumed without being
  redefined by the implementation owner.
- [ ] Affected component owners and independent reviewer are named.
- [ ] Exact governed package paths and bounded data-content permission are
  recorded before real package validation or production.

## Identity and component validation

- [ ] A conforming RFC 8785 implementation passes broad Unicode, escaped-text,
  integer, floating-point, and property-order vectors.
- [ ] Equivalent identity inputs produce the same package ID and equivalent
  package content produces the same content digest.
- [ ] Same identity with different content fails closed and is auditable.
- [ ] Topology, diagnostic, and replacement/material component packages bind
  to their exact payload contracts, source manifests, artifacts, and hashes.
- [ ] Artifact paths are package-relative, portable, present, digest-matched,
  size-matched, and count-validated.
- [ ] Lineage, masking coverage, review, serving, route, and promotion evidence
  are validated independently and cannot imply one another.

## Release composition

- [ ] A `tpdx_release` references zero or one accepted component of each
  allowed type.
- [ ] Duplicate component types fail closed even when package IDs differ.
- [ ] References match package ID, manifest digest, package type, release
  identity, Schema 4.2 binding, and accepted status.
- [ ] Missing, incomplete, incompatible, circular, conflicting, or unaccepted
  components prevent release-package publication.
- [ ] Component payload records are referenced rather than copied into the
  release package.

## Reproducibility and boundaries

- [ ] Equivalent inputs, contract, code, and configuration produce byte-
  equivalent component and release manifests.
- [ ] Synthetic positive and negative packages cover every frozen failure rule
  and all continuing Task 014 implementation conditions.
- [ ] Partial or failed publication cannot appear as an accepted package.
- [ ] Exact commands, changed files, validation evidence, rollback, and risks
  are recorded.
- [ ] No graph import, database switch, runtime activation, global release, or
  Data RC claim is made.

## Data-content permission

- [x] Task creation did not inspect any file contents under `data/`.
- [ ] Exact bounded paths and user permission are recorded before real package
  reads, validation, or writes.
