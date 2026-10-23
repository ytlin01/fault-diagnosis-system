# V2-TASK021 acceptance

## Target safety and ownership

- [x] `V2-TASK021` was unused before allocation.
- [x] The task names one graph-mutation owner and independent reviewers.
- [ ] The authorized shadow database identity and operations owner are
  recorded before any database mutation.
- [ ] Preflight proves the target is not the active runtime or preserved Schema
  4.1 database.
- [ ] Exact package paths and bounded data-content permission are recorded
  before package reads.

## Schema and import behavior

- [ ] Schema 4.2 constraints and indexes are created and verified.
- [ ] Only an accepted, schema-valid, digest-valid `tpdx_release` and accepted
  referenced components can be imported.
- [ ] Assertion relationship identity includes `mapping_record_id` and
  `assertion_edge_id` wherever required by Schema 4.2.
- [ ] Orphan endpoints, dangling edges, duplicate payloads, duplicate assertion
  identities, contradictory assertions, unbacked projections, invalid labels,
  and legacy `HAS_STEP` fail closed.
- [ ] The import is transactional or recoverably staged and never reports a
  partial graph as complete.

## Verification and rollback

- [ ] Pre/post node, relationship, label, type, constraint, and index counts are
  recorded.
- [ ] Package, component, importer, and resulting graph digests are recorded.
- [ ] An exact reload is idempotent with unchanged counts and graph digest.
- [ ] A conflicting reload is rejected without changing the verified graph.
- [ ] Shadow teardown and rollback are tested against an exact allowlisted
  target and preserve Schema 4.1.
- [ ] Database-switch instructions are documented but not executed.

## Integration evidence

- [ ] Synthetic tests cover every fail-closed structural rule.
- [ ] Live integration tests run against an isolated shadow Neo4j instance.
- [ ] Credentials, private endpoints, and absolute local paths do not appear in
  code, manifests, logs, tests, or documentation.
- [ ] Exact commands, changed files, validation results, exclusions, and risks
  are recorded.
- [ ] No runtime activation, deployment, release, or Data RC claim is made.

## Data-content permission

- [x] Task creation did not inspect any file contents under `data/`.
- [ ] Exact bounded package paths and permission are recorded before import
  validation or execution.
