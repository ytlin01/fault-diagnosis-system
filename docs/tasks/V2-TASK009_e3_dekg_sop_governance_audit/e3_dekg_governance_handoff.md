# E3 DEKG governance handoff

## Purpose

Perform a standalone, read-only inventory and governance audit of every SOP
already deployed in DEKG on E3. This session does not run VLM, build evidence
packages, mutate Neo4j, replace `DocumentAsset`, or activate a runtime.

## Owners and boundary

- E3 evidence provider and custodian: N / system line
- Governance recorder: `data_workflow_lead`
- Contract reviewer: `data_contract_engineer`
- Independent reviewer: `data_quality_reviewer`
- Downstream replacement owner: `data_pipeline_kg_engineer`, only after this
  audit fixes the complete reviewed corpus

Keep this governance session separate from the Task 010 replacement handoff
and every VLM or producer run. Graph presence is deployment evidence, not
proof of masking, serving safety, review, or diagnostic truth.

## Before connecting

Record the E3 custodian, hostname/environment identity, Neo4j database name,
server version, graph/index identity, deployment or run identifier, audit UTC
timestamp, and the exact read-only access method. Stop if the database or
access boundary is ambiguous.

Do not export credentials, endpoints, document text, images, embeddings,
unmasked properties, raw/internal paths, or unrestricted query results.

## Stage 1: metadata-only deployed-corpus inventory

Using demonstrably read-only queries, capture:

- counts for legacy `RouteBGraphNode` and `DocumentAsset` representations and
  frozen-v2-derived `DEKGEvidence` representations;
- every deployed SOP document identity, source/version marker, labels,
  ingestion mode, release/run marker, and producer metadata that is present;
- per-document block, chunk, media, and relationship counts;
- the set of property names used by each relevant label, without exporting
  property values that may contain content or sensitive paths;
- duplicate document/source/evidence identities, orphan blocks or chunks,
  dangling edges, conflicting versions, and records with missing provenance;
- the completeness rule used to find SOPs, including labels and provenance
  relationships rather than filename matching alone.

Save the query text, database identity, audit timestamp, row counts, and a
SHA-256 checksum of the approved metadata-only result bundle.

## Stage 2: governance reconciliation

Return one row per deployed SOP with these fields, using `missing` explicitly:

| Field group | Required result |
|---|---|
| deployment | database, representation, graph/index version, run ID, ingestion time, producer identity |
| source | deployed ID, governed `source_id`, mother-document ID, source version, custody match |
| governance | sensitivity, masking, serving, route, review, promotion, and release states kept separate |
| contract | legacy or frozen-v2 derivative, `evidence_id` lineage, ingestion mode, contract version |
| partition | excluded Route A anchors, no-overlap assertion, co-source group, corroboration restriction |
| structure | block/chunk/media/edge counts, duplicates, orphans, dangling edges, collisions |
| disposition | `inventory_match`, `unregistered`, `ambiguous`, `stale`, `duplicate`, `forbidden`, or `missing_evidence` |

The reference-only repair SOP must be absent. The Vision SOP must not be
reported as a produced DEKG candidate unless separately authorized real-source
production evidence exists. Do not promote any document evidence to
`Phenomenon`, `MappingRecord`, or diagnosis.

## Stage 3: permission checkpoint for content

Metadata findings do not authorize content sampling. If a finding cannot be
resolved without content, stop and request explicit permission naming the
exact E3 query or bounded artifacts. Record the sampling rule and reviewer
before any approved sample is opened.

## Return bundle

Return only the approved metadata bundle containing:

1. target/database/version and audit manifest;
2. read-only query bundle and execution record;
3. complete per-SOP inventory and structural counts;
4. governance/contract reconciliation table;
5. duplicate, orphan, dangling-edge, collision, route-leakage, unsafe-field,
   and promotion findings;
6. bundle checksums, exclusions, unresolved fields, and required remediation.

Do not return raw SOP content, embeddings, secrets, endpoints, credentials, or
unapproved internal paths.

## Review and next gate

The workflow lead first verifies completeness and provenance. The contract
engineer reviews identity, mode, partition, and frozen-contract alignment.
The quality reviewer then independently issues `READY`,
`READY_WITH_EXCLUSIONS`, or `NOT_READY` per SOP and for the corpus.

Task 010 package freezing, backup, replacement, and E3 apply remain blocked
until the reviewed E3 inventory agrees exactly with the complete replacement
package list.

## Stop conditions

Stop and return the incomplete evidence without mutation if:

- read-only access cannot be demonstrated;
- the target database, graph/index version, or corpus completeness rule is
  unresolved;
- required metadata can be obtained only by exporting content or secrets;
- deployed identities cannot be reconciled without additional permission;
- the result bundle omits failures or exclusions;
- any requested step would run VLM, produce packages, write Neo4j, or perform
  the Task 010 replacement.
