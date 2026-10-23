**KG_LLM_FAULTDX**

Topology-Diagnostic Knowledge Graph Ontology

Version 4.2 - Frozen

# 1. Architecture Overview

Contract state: `FROZEN`.

Schema 4.2 is the complete, self-contained Route A knowledge-graph contract for
governed equipment topology, module-scoped diagnostic assertions, the explicit
diagnostic chain, and replacement parts. This ontology and
`tpdx_kg_schema_v4_2.schema.json` can be used without the Schema 4.1 files.
They do not activate, release, or deploy Schema 4.2. Frozen Schema 4.1 remains
unchanged as the historical comparison and rollback baseline.

## 1.0 Three-layer implementation plan

Ontology v4.2 is the topology-diagnosis KG (Route A) schema plan. It defines the three-layer published knowledge graph for reviewed equipment topology, diagnostic mappings, and
replacement parts.

The planned Schema 4.2 structure is a three-layer graph:

1. Equipment topology layer
   - Governs `Station -> Module -> Component -> SubComponent` hierarchy and
     topology connections.
   - Publishes controlled assembly occurrences with deterministic canonical IDs.
2. Diagnostic mapping layer
   - Governs `ErrorCode`, `Phenomenon`, `MappingRecord`, `Cause`, `Action`,
     and `ActionStep`.
   - Replaces the legacy direct `TRIGGERS` bridge with `MappingRecord`, a
     first-class governed assertion node scoped to one Module.
   - Keeps `Module`, `Component`, and `SubComponent` as router entry points;
     lower-level entries resolve to their ancestor Module before assertion lookup.
3. Replacement layer
   - Governs `ReplacementPart` compatibility and explicit action requirements.
   - Keeps replacement semantics separate from topology and diagnosis truth.

This plan remains the intended Schema 4.2 scope: Route A is the reviewed
published graph, while Route B and Route C remain evidence-only and
candidate-only lanes respectively.

The asset hierarchy remains:

`Station -> Module -> Component -> SubComponent`

The diagnostic layer replaces the legacy direct `TRIGGERS` bridge with a
reviewed, module-scoped source assertion and MappingRecord-backed projections:

```text
Module <- MappingRecord -> ErrorCode / Phenomenon / Cause / Action
Phenomenon -> ErrorCode
Phenomenon -> Cause -> Action -> ActionStep
```

| Layer | Core objects | Responsibility | Access mode |
| --- | --- | --- | --- |
| Equipment topology | Station · Module · Component · SubComponent | Governed assembly occurrences, hierarchy, names, and connections | Text2Cypher |
| Diagnostic mapping | ErrorCode · Phenomenon · MappingRecord · Cause · Action · ActionStep | Reviewed diagnostic assertions with source and topology scope | Text2Cypher |
| Replacement | ReplacementPart | Reviewed compatibility and explicit action requirements | Text2Cypher |

Route B remains `document_evidence + evidence_only`. Route C remains
`case_reference + candidate`. Neither route changes Route A truth.

## 1.1 Design Decisions

- `TopologyElement` is a secondary label on Station, Module, Component, and
  SubComponent; it is not an independent node.
- Topology nodes represent governed assembly occurrences, not runtime serialized
  equipment instances and not reusable product definitions.
- Repeated occurrences of one product definition are separate nodes when they
  occupy different topology positions.
- Canonical IDs are globally unique and are used for joins, graph edges, query
  parameters, manifests, and `MappingRecord-SCOPED_TO`.
- `name` is the conventional display name. It is not unique and is never
  rewritten to create identity. `aliases` are matching aids, not identities.
- Bare-name lookup returns all candidates. It must not silently select the first
  result. Parent context or review resolves ambiguity.
- Unknown module/component classification is the explicit enum value `unknown`;
  a producer must not infer type from a display name.
- `MappingRecord` is the only reviewed diagnostic-to-topology bridge.
- `MappingRecord` is a first-class assertion node, not a physical topology
  entity, a diagnostic concept, or a hierarchy-governing node.
- `MappingRecord-[:SCOPED_TO]->Module` is the only stored diagnostic scope
  relationship. MappingRecords are not duplicated onto Component or
  SubComponent nodes.
- Router entry points are Module, Component, and SubComponent. Component and
  SubComponent entries resolve through the governed hierarchy to their ancestor
  Module before MappingRecord retrieval.
- A module-scoped assertion retrieved from a lower-level entry remains
  module-scoped; it must not be presented as a direct Component or SubComponent
  assertion.
- Only reviewed, serving-safe, explicitly promoted Route A records may enter the
  published graph.
- Direct diagnostic-chain edges are projections of exactly one governed
  `MappingRecord`; they never replace the MappingRecord memberships.
- Cause-to-Action pairs must be explicit. A producer must not infer the
  Cartesian product of a record's causes and actions.
- `HAS_STEPS` is the only stored Schema 4.2 Action-to-ActionStep relationship;
  `HAS_STEP` is not part of Schema 4.2.

## 1.2 Layer Boundaries

- Runtime crawler occurrences are not static KG nodes.
- Candidate topology matches and diagnostic mappings remain outside the
  published graph until reviewed.
- Same-source Route A and Route B outputs are co-source, not independent
  corroboration.
- Legacy migration, runtime routing, and source-specific column mapping are
  separate contracts and tasks.

# 2. Equipment Topology Layer

Hierarchy:

`Station -> Module -> Component -> SubComponent -> SubComponent ...`

## 2.1 Node Definitions

| Node | Required properties | Constraints | Description | Access |
| --- | --- | --- | --- | --- |
| Station | station_id, name, station_type, identity_namespace, source_native_id, identity_rule_version | `station_id = node.id`; ID prefix `ST_`; non-empty conventional name | Governed top-level station occurrence | Text2Cypher |
| Module | module_id, name, module_type, station_id, identity_namespace, source_native_id, identity_rule_version | `module_id = node.id`; `module_type = mechanical / electrical / unknown`; exactly one Station parent | Direct Station child | Text2Cypher |
| Component | component_id, name, component_type, module_id, identity_namespace, source_native_id, identity_rule_version | `component_id = node.id`; `component_type = mechanical / electrical / unknown`; exactly one Module parent | Direct Module child | Text2Cypher |
| SubComponent | subcomponent_id, name, component_type, parent_label, parent_id, module_id, identity_namespace, source_native_id, identity_rule_version | `subcomponent_id = node.id`; parent label is Component or SubComponent; exactly one immediate parent | Nested assembly occurrence at depth 3 or greater | Text2Cypher |

`aliases` is optional on every topology node. Alias values may collide.

Station `name` is the conventional user-facing name; `station_type` is its
classification. Module, Component, and SubComponent `name` values are also
conventional user-facing names.

## 2.2 Relationship Definitions

| Relationship | From | To | Cardinality | Constraint | Access |
| --- | --- | --- | --- | --- | --- |
| HAS_MODULE | Station | Module | 1:N | Exactly one incoming HAS_MODULE per Module; edge agrees with `station_id` | Text2Cypher |
| HAS_COMPONENT | Module | Component | 1:N | Exactly one incoming HAS_COMPONENT per Component; edge agrees with `module_id` | Text2Cypher |
| HAS_SUBCOMPONENT | Component / SubComponent | SubComponent | 1:N | Exactly one incoming edge; endpoint agrees with `parent_label` and `parent_id` | Text2Cypher |
| HAS_CONNECTION | Module / Component / SubComponent | Module / Component / SubComponent | N:N | Undirected domain meaning; stored once in deterministic endpoint order | Text2Cypher |

The hierarchy must be acyclic. Self-parenting, missing parents, multiple parents,
and parent-property/edge disagreement are invalid.

For a SubComponent:

- if `parent_label = Component`, `parent_id` references a Component;
- if `parent_label = SubComponent`, `parent_id` references a SubComponent;
- the child `module_id` equals the ancestor Module ID of its parent.

## 2.3 Canonical Identity

Topology identity rule: `topology_identity_v1`.

Each node preserves:

- `identity_namespace`: governed source/asset namespace stable across snapshots;
- `source_native_id`: stable occurrence identifier supplied by the source; and
- one canonical FaultDx node ID.

The canonical ID suffix is the lowercase SHA-256 hex digest of the UTF-8 string:

```text
identity_namespace + U+001F + parent_canonical_id_or_empty + U+001F + source_native_id
```

The three governed input strings are hashed exactly as stored, including case
and whitespace. Producers must not apply implicit trimming, case folding, or
source-specific normalization under `topology_identity_v1`.

Label prefixes are:

| Label | Prefix |
| --- | --- |
| Station | `ST_` |
| Module | `M_` |
| Component | `C_` |
| SubComponent | `SC_` |

Names, aliases, source snapshots, row positions, and filenames are not identity
inputs. Therefore a name change or a new source snapshot does not change the ID
when namespace, parent identity, and source-native occurrence identity remain
unchanged.

If a source does not supply a stable occurrence identifier, the producer must
not invent a published topology identity. The record enters the exclusion or
identity-review queue until a governed surrogate is approved.

## 2.4 Duplicate Names and Display

Canonical names remain conventional names even when duplicated. Query results
use canonical IDs and return `id`, `name`, `label`, and parent context.
User interfaces may display a derived breadcrumb such as
`parent name / conventional name`, but that breadcrumb is not identity and
must not overwrite `name`.

## 2.5 HAS_CONNECTION Properties

| Property | Type / enum | Description |
| --- | --- | --- |
| connection_type | pneumatic / hydraulic / planar_contact / concentric / tangent / proximity | Governed connection type |
| confidence | number from 0 to 1 | Source/extractor confidence |
| source | cad_geometry / schematic / manual | Connection provenance class |

# 3. Diagnostic Mapping Layer

## 3.1 Node Definitions

| Node | Core required properties | Description | Access |
| --- | --- | --- | --- |
| ErrorCode | error_code_id, namespace, code, identity_rule_version | Governed exact query key; runtime occurrence is not stored here | Text2Cypher |
| Phenomenon | phenomenon_id, canonical_text, identity_rule_version | Canonical observable condition | Text2Cypher |
| MappingRecord | mapping_record_id, source_id, source_snapshot_id, source_record_id, review_status, serving_safe, promotion_decision_id, identity_rule_version | First-class governed assertion node connecting one Module to one Phenomenon | Text2Cypher |
| Cause | cause_id, canonical_text, identity_rule_version | Possible cause asserted by a MappingRecord | Text2Cypher |
| Action | action_id, action_name, identity_rule_version | Source-supported recommended action | Text2Cypher |
| ActionStep | step_id, order, instruction | Ordered action step | Text2Cypher |

### 3.1.1 Optional and governance properties

| Node | Optional or governed properties | Constraint |
| --- | --- | --- |
| ErrorCode | device_family, description, aliases | Text values may be null; aliases are non-empty unique strings when present. |
| Phenomenon | aliases, language, severity | severity is low, medium, high, critical, or null. |
| MappingRecord | source_anchor, segment_index, reviewed_by, reviewed_at, warnings | segment_index is a non-negative integer; reviewed_at is date-time or null; warnings is an array of strings. |
| Action | action_type, requires_shutdown, prerequisites, required_tools, safety_warnings | requires_shutdown is boolean or null; the remaining list values are arrays of strings. |
| ActionStep | expected_result, safety_warning | Either is a string or null. |
| ReplacementPart | specification, aliases, replacement_policy | Text values may be null; aliases are non-empty unique strings when present. |

## 3.2 Relationship Definitions

| Relationship | From | To | Cardinality | Description |
| --- | --- | --- | --- | --- |
| USES_ERROR_CODE | MappingRecord | ErrorCode | 0..1 per MappingRecord | Optional governed code definition |
| OBSERVES | MappingRecord | Phenomenon | exactly 1 | Observable condition |
| SCOPED_TO | MappingRecord | Module | exactly 1 | Reviewed canonical Module assertion scope |
| ASSERTS_CAUSE | MappingRecord | Cause | 0..N | Source-supported possible causes |
| RECOMMENDS_ACTION | MappingRecord | Action | 0..N | Source-supported actions |
| HAS_CODE | Phenomenon | ErrorCode | 0..1 per backing record | MappingRecord-backed code projection |
| HAS_CAUSE | Phenomenon | Cause | 0..N per backing record | MappingRecord-backed cause projection |
| HAS_ACTION | Cause | Action | 0..N explicit pairs per backing record | Explicit MappingRecord-backed Cause-to-Action projection with one cause_action_pair_id |
| HAS_STEPS | Action | ActionStep | 0..N per backing record | Ordered MappingRecord-backed step projection |

## 3.3 MappingRecord Constraints

One MappingRecord is one reviewed source assertion. It replaces the legacy
stored `TRIGGERS` relationship by making provenance and publication state
first-class. Each published MappingRecord has:

- exactly one `SCOPED_TO` Module;
- exactly one `OBSERVES` Phenomenon;
- zero or one `USES_ERROR_CODE` ErrorCode;
- zero or more `ASSERTS_CAUSE` Cause targets; and
- zero or more `RECOMMENDS_ACTION` Action targets.

Name matching may create zero or many topology candidates, but only a reviewed
canonical Module ID may become the `SCOPED_TO` target. Ambiguous and unmatched
results remain `MappingCandidate` records outside the published graph.

`mapping_record_identity_v1` uses SHA-256 over these U+001F-delimited values:

```text
source_id
+ source_snapshot_id
+ source_record_id
+ scoped Module ID
+ observed Phenomenon ID
```

The output is `MR_<64 lowercase hexadecimal characters>`. Mutable governance
fields such as review status, serving safety, reviewer, review time, promotion
decision, and warnings are not identity inputs.

Every `HAS_CODE`, `HAS_CAUSE`, `HAS_ACTION`, and `HAS_STEPS` edge requires:

- `assertion_edge_id`;
- one backing `mapping_record_id`;
- non-empty `source` and `extracted_from`; and
- optional `confidence` from 0 through 1.

Every `HAS_ACTION` edge additionally requires a non-empty
`cause_action_pair_id` that identifies the reviewed source pairing. The
identifier is pairing evidence, not a generated Cartesian-product marker.

`assertion_edge_identity_v1` is `AE_` plus the lowercase SHA-256 digest of
these U+001F-delimited values:

```text
relationship_type + from_id + to_id + mapping_record_id
```

Independent MappingRecords supporting the same endpoint pair remain separate
assertions with distinct IDs. Aggregated read views may combine them only when
they return the complete backing-record set.

Backing invariants are:

- `Phenomenon-[:HAS_CODE]->ErrorCode` requires the backing record to
  `OBSERVES` the Phenomenon and `USES_ERROR_CODE` the ErrorCode.
- `Phenomenon-[:HAS_CAUSE]->Cause` requires the backing record to `OBSERVES`
  the Phenomenon and `ASSERTS_CAUSE` the Cause.
- `Cause-[:HAS_ACTION]->Action` requires the backing record to `ASSERTS_CAUSE`
  the Cause and `RECOMMENDS_ACTION` the Action.
- `Action-[:HAS_STEPS]->ActionStep` requires the backing record to
  `RECOMMENDS_ACTION` the Action.

After endpoint deduplication, one Action's step orders are unique and
contiguous from 1. Unbacked, contradictory, ambiguous, duplicate, or invalid
projections are excluded rather than silently published.

`TRIGGERS`, `HAS_FAULT`, and direct topology-to-Phenomenon edges are derived
semantic views, not stored Schema 4.2 relationships.

## 3.4 Topology-first query entry contract

The router/orchestrator resolves user context to one canonical topology entry:

| Router entry | Assertion scope | Resolution |
| --- | --- | --- |
| Module | same Module | `direct` |
| Component | ancestor Module | `ancestor_module` |
| SubComponent | ancestor Module | `ancestor_module` |

The stored diagnostic path is:

```text
(MappingRecord)-[:SCOPED_TO]->(Module)
(MappingRecord)-[:OBSERVES]->(Phenomenon)
(Phenomenon)-[:HAS_CODE]->(ErrorCode)
(Phenomenon)-[:HAS_CAUSE]->(Cause)
(Cause)-[:HAS_ACTION]->(Action)
(Action)-[:HAS_STEPS]->(ActionStep)
```

A Component query follows its incoming `HAS_COMPONENT` edge to the owning
Module. A SubComponent query follows its governed parent chain until it reaches
the owning Module. Query results preserve both contexts:

- `query_entry_label` and `query_entry_id`: what the router resolved;
- `assertion_scope_label = Module` and `assertion_scope_id`: where the
  MappingRecord is actually scoped; and
- `scope_resolution = direct / ancestor_module`: how the assertion scope was
  reached.

The router must return ambiguity for zero or multiple topology candidates rather
than selecting the first name match. Runtime routing remains N-owned; this
ontology defines the governed graph boundary and result identity semantics.

# 4. Replacement Layer

## 4.1 Node Definition

| Node | Required properties | Description | Access |
| --- | --- | --- | --- |
| ReplacementPart | replacement_part_id, canonical_name, identity_rule_version | Governed service/catalog part, not an installed topology occurrence | Text2Cypher |

## 4.2 Relationship Definitions

| Relationship | From | To | Description |
| --- | --- | --- | --- |
| REPLACEMENT_FOR | ReplacementPart | Module / Component / SubComponent | Reviewed compatibility |
| REQUIRES_PART | Action | ReplacementPart | Explicit reviewed action requirement |

Compatibility does not imply that an action requires the part. Textual mention
alone creates neither relationship.

# 5. Generation Constraints

- Node envelope `id` equals its label-specific ID property.
- Canonical topology IDs are globally unique in a published graph.
- Repeated assembly occurrences are separate nodes when their parent or
  source-native occurrence identity differs.
- Required type fields use `unknown`, never null or inferred values.
- Bare-name collisions return all candidates; first-match resolution is invalid.
- Invalid hierarchy records are excluded with a recorded reason; they are not
  silently dropped.
- Published Route A records require reviewed state, serving safety, promotion
  evidence, and a governed source snapshot.
- MappingRecord `SCOPED_TO` endpoints are Module IDs only.
- Module, Component, and SubComponent are query entry points, but only Module is
  the stored diagnostic assertion scope.
- Ancestor-module resolution preserves the lower-level query entry identity and
  does not create or imply direct MappingRecord edges to descendants.
- All node and relationship endpoints must reference definitions contained in
  the self-contained Schema 4.2 JSON contract.
- Every direct diagnostic-chain edge must resolve its endpoints and backing
  MappingRecord in the validated bundle or explicitly governed graph context.
- Producers must never publish both `HAS_STEP` and `HAS_STEPS` as parallel
  truth edges.

## 5.1 Governed exclusions

Every exclusion contains source_native_id and one of these governed reasons:

| Reason | Meaning |
| --- | --- |
| missing_stable_native_id | No stable source-native identity is available. |
| duplicate_canonical_id | More than one record resolves to one canonical identity. |
| missing_parent | A required hierarchy parent is absent. |
| multiple_parents | A hierarchy node has more than one parent. |
| self_parent | A hierarchy node points to itself. |
| cycle | The hierarchy contains a cycle. |
| parent_mismatch | Parent fields and hierarchy edge disagree. |
| cross_namespace_without_merge | A cross-namespace join lacks an approved merge decision. |
| invalid_type | A controlled type or label is invalid. |
| other | A governed exclusion not covered above; detail is required when supplied. |

# 6. Compatibility and Migration

`HAS_CODE`, `HAS_CAUSE`, and `HAS_ACTION` are additive relative to Schema 4.1.
The stored relationship rename from `HAS_STEP` to `HAS_STEPS` is breaking for
loaders, queries, evaluation, and documentation.

Migration requires:

1. validate the Schema 4.1 input and MappingRecord memberships;
2. generate deterministic assertion projections;
3. convert only valid, uniquely backed `HAS_STEP` edges to `HAS_STEPS`;
4. require reviewed Cause-to-Action pairs instead of generating a Cartesian
   product;
5. validate the complete Schema 4.2 candidate and manifest;
6. compare old/new graph behavior before consumer activation.

Legacy `Fault`, `INDICATES`, and `RESOLVED_BY` vocabulary is pre-existing
consumer drift, not a Schema 4.2 alias. Rollback retains the unchanged frozen
Schema 4.1 contract and graph.

# 7. Validation and Gates

Contract validation has two layers:

1. Draft 2020-12 validation of the single Schema 4.2 JSON file. Every `$ref`
   must resolve to local `$defs`; no external schema file may be required.
2. Semantic validation of deterministic assertion IDs, governed backing
   records, required memberships, endpoint resolution, explicit Cause/Action
   pairing, duplicates, and ActionStep ordering.

Independent quality review and the workflow-lead freeze decision are complete.
Pipeline/KG, Text2Cypher/runtime activation, deployment, and release remain
separately owned.

# 8. Change Decision Record

Schema 4.2 selects the explicit diagnostic chain while retaining MappingRecord
as the authoritative governed assertion. Rejected alternatives are:

- membership-only traversal, because it cannot represent explicit
  Cause-to-Action pairs in multi-cause, multi-action records;
- replacing MappingRecord memberships with direct edges, because that loses
  source, scope, review, serving, and promotion authority;
- inferred Cause-to-Action Cartesian products;
- dual publication of `HAS_STEP` and `HAS_STEPS`; and
- FP, EC, RC, RA, or RS as new canonical labels.

The JSON contract and this ontology are both self-contained for direct use.
Frozen Schema 4.1 remains immutable. Schema 4.2 is now the frozen contract for
approved new consumers; the recorded decision may mark 4.1 superseded for those
consumers without reopening or modifying its artifacts.

# 9. Version Notes

| Version | Date | Status | Summary |
| --- | --- | --- | --- |
| v3.2 | 2026-05 | historical | Station-to-SubComponent hierarchy with local extraction IDs and direct legacy diagnostic structures. |
| v4.0 | 2026-07 | historical draft | Added global topology identity, MappingRecord, and replacement semantics. |
| v4.1 | 2026-07-23 | `FROZEN` | Immutable rollback baseline with MappingRecord-governed diagnostic memberships and `HAS_STEP`. |
| v4.2 | 2026-08-10 | `FROZEN` | Complete self-contained ontology and JSON contract adding MappingRecord-backed `HAS_CODE`, `HAS_CAUSE`, `HAS_ACTION`, and `HAS_STEPS`; independently reviewed and frozen with the breaking migration and direct-use requirement. |
