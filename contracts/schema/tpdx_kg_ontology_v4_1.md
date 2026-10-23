**KG_LLM_FAULTDX**

Topology-Diagnostic Knowledge Graph Ontology

Version 4.1 - Frozen Contract

# 1. Architecture Overview

Contract state: `FROZEN` (N/system-line confirmation recorded on 2026-07-23).
This state removes the draft designation but is not Data Contract Freeze;
workflow-lead, independent quality, and affected-consumer approval remain open.

Schema 4.1 defines the reviewed Route A knowledge graph for governed equipment
topology, module-scoped diagnostic assertions, and replacement parts.

## 1.0 Three-layer implementation plan

Ontology v4.1 is the topology-diagnosis KG (Route A) schema plan. It defines the three-layer published knowledge graph for reviewed equipment topology, diagnostic mappings, and
replacement parts.

The planned Schema 4.1 structure is a three-layer graph:

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

This plan remains the intended Schema 4.1 scope: Route A is the reviewed
published graph, while Route B and Route C remain evidence-only and
candidate-only lanes respectively.

The asset hierarchy remains:

`Station -> Module -> Component -> SubComponent`

The diagnostic layer replaces the legacy direct `TRIGGERS` bridge with a
reviewed, module-scoped source assertion:

`Module <- MappingRecord -> ErrorCode / Phenomenon / Cause / Action`

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

## 3.2 Relationship Definitions

| Relationship | From | To | Cardinality | Description |
| --- | --- | --- | --- | --- |
| USES_ERROR_CODE | MappingRecord | ErrorCode | 0..1 per MappingRecord | Optional governed code definition |
| OBSERVES | MappingRecord | Phenomenon | exactly 1 | Observable condition |
| SCOPED_TO | MappingRecord | Module | exactly 1 | Reviewed canonical Module assertion scope |
| ASSERTS_CAUSE | MappingRecord | Cause | 0..N | Source-supported possible causes |
| RECOMMENDS_ACTION | MappingRecord | Action | 0..N | Source-supported actions |
| HAS_STEP | Action | ActionStep | 0..N | Ordered action steps |

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

`TRIGGERS`, `HAS_FAULT`, and direct topology-to-Phenomenon edges are derived
semantic views, not stored Schema 4.1 relationships.

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
- All node and relationship endpoints must reference Schema 4.1 definitions.

# 6. Version Notes

| Version | Date | Summary |
| --- | --- | --- |
| v3.2 | 2026-05 | Station -> Module -> Component -> SubComponent hierarchy; local extraction IDs; direct legacy diagnostic structures |
| v4.0 draft | 2026-07 | Global deterministic topology identity, conventional non-unique names, explicit SubComponent parent fields, MappingRecord diagnostic bridge, and ReplacementPart semantics |
| v4.1 reviewed proposal | 2026-07 | Accepted by the data owner. Defines MappingRecord as a first-class governed assertion node replacing stored TRIGGERS; restricts SCOPED_TO to exactly one Module; keeps Module, Component, and SubComponent as router entry points through direct or ancestor-module resolution; preserves query-entry and assertion-scope identities separately; prohibits descendant edge duplication and direct component-specific claims from module-scoped assertions. Runtime activation and implementation migration remain separately gated. |
