# RouteB Schema Boundary Decision

## 背景

本讨论围绕 RouteB 是否需要独立 schema，或是否应与现有
`diagnostic_schema` 合并展开。

当前事实：

- RouteB 当前唯一可按正式 schema 约束并发布的 domain 对象是
  `DocumentAsset`。
- `RouteBBlock`、`RouteBConcept`、`HAS_EVIDENCE_BLOCK`、
  `MENTIONS_CONCEPT`、`NEXT_BLOCK` 当前是检索支撑结构，不是正式诊断 KG
  本体。
- RouteB 输出语义应保持为 document evidence，而不是 confirmed diagnosis。

## 决策

当前阶段不建议为 RouteB 建一个完整独立的正式 KG schema，也不建议把
RouteB 的检索内部结构完全合并进 `diagnostic_schema`。

推荐做法是：

```text
diagnostic_schema_v3_2.json
  - 正式 KG ontology
  - DocumentAsset
  - DESCRIBES / REF_DOC
  - 最小 RouteB publication policy

route_b_evidence_v1.json
  - RouteB evidence contract
  - RouteB support artifacts
  - RouteB validator policy
  - API projection constraints
```

也就是说：分开写，但建立显式引用关系。

## 为什么不完全合并

`diagnostic_schema` 和 RouteB evidence contract 的生命周期不同。

`diagnostic_schema` 承载相对稳定的 KG 语义，例如资产层、诊断本体层、
`DocumentAsset`、`DESCRIBES`、`REF_DOC`。RouteB evidence contract 则会随着
检索实验、benchmark、block 粒度、rerank 特征和 Neo4j 可视化需求快速变化。
如果完全合并，正式 schema 会被检索实现细节频繁污染。

二者语义等级也不同。

`DocumentAsset` 是正式 schema 节点；`RouteBBlock` 和 `RouteBConcept` 当前只是
retrieval artifact。如果放进 `definitions.nodes`，后续 agent 或开发者容易误以为
它们也是正式诊断 KG node。

## 为什么不完全独立

RouteB 不是脱离 FaultDx KG worldview 的另一套本体。

RouteB 的文档资产、文档引用和文档描述关系仍应复用主 schema 中的正式语义：

```text
DocumentAsset
DocumentAsset -[DESCRIBES]-> Station / Module / Component
Action -[REF_DOC]-> DocumentAsset
```

所以 RouteB 不能完全自定义一套 ontology。它应该共享
`diagnostic_schema` 中的正式发布语义，同时把检索支撑结构留在自己的 evidence
contract 中。

## Evidence Contract

Evidence contract 定义 RouteB 允许生产、消费和对外投影的 evidence 形状。
它不是诊断 KG schema。

当前 RouteB evidence contract 应约束：

- 来源只允许 serving-safe 数据，例如 `data/serving_unstructured_vlm/`。
- evidence 是 document-oriented，不是 diagnosis-oriented。
- 核心 provenance anchor 包括：
  - `source_id`
  - `doc_id`
  - `block_id`
  - `chunk_id`
  - `anchor`
- 对外输出语义固定为：
  - `route_family = route_b_document`
  - `answer_type = document_evidence`
  - `status = evidence_only`
  - `evidence_type = document_snippet`
  - `source_type = serving_document`
- `RouteBBlock`、`RouteBConcept`、block adjacency、concept mention 等对象只能支撑
  retrieval、rerank、explanation 和 visualization。

Evidence contract 回答的问题是：

```text
RouteB 被允许产出什么形状的 evidence？
```

## Validator Policy

Validator policy 定义 RouteB evidence item 的治理判定。

当前 validator status 包括：

```text
published_graph
candidate_review
rejection
```

推荐政策：

- `DocumentAsset` 是当前 RouteB 唯一允许进入 `published_graph` 的 schema 节点。
- `RouteBBlock`、`RouteBConcept` 必须保持 `candidate_review`。
- `HAS_EVIDENCE_BLOCK`、`MENTIONS_CONCEPT`、`NEXT_BLOCK` 必须保持
  `candidate_review`。
- 所有 RouteB graph item 必须保持 `route_b_status = evidence_only`。
- raw/internal path、raw VLM response、endpoint/debug 字段、未脱敏文本等必须拒绝。
- RouteB evidence 不允许提升为 `confirmed_diagnosis`。

Validator policy 回答的问题是：

```text
给定一个 RouteB evidence item，它能发布、只能候选，还是必须拒绝？
```

## 推荐文件边界

推荐新增或保留以下边界：

```text
schema/diagnostic_schema_v3_2.json
schema/route_b_evidence_v1.json
```

`diagnostic_schema_v3_2.json` 负责：

- 正式 KG nodes / relationships。
- `DocumentAsset` required fields。
- `DESCRIBES` / `REF_DOC` 的 from-to 约束。
- 最小 RouteB publication policy，例如：

```json
{
  "publication_policy": {
    "route_b": {
      "published_node_types": ["DocumentAsset"]
    }
  }
}
```

`route_b_evidence_v1.json` 负责：

- `evidence_contract`
- `support_artifacts`
- `validator_policy`
- `api_projection_constraints`

示例结构：

```json
{
  "$id": "route_b_evidence_v1",
  "schema_version_ref": "diagnostic_schema_v3_2",
  "evidence_contract": {
    "semantics": "document_evidence_only",
    "allowed_source_ids": ["data/serving_unstructured_vlm"],
    "required_source_ref_fields": [
      "source_id",
      "doc_id",
      "block_id",
      "chunk_id",
      "anchor"
    ],
    "output_constraints": {
      "route_family": "route_b_document",
      "answer_type": "document_evidence",
      "status": "evidence_only",
      "evidence_type": "document_snippet",
      "source_type": "serving_document"
    }
  },
  "support_artifacts": {
    "nodes": {
      "RouteBBlock": {
        "validator_status": "candidate_review",
        "description": "Serving-safe block/chunk evidence anchor, not a KG fact."
      },
      "RouteBConcept": {
        "validator_status": "candidate_review",
        "description": "Retrieval concept extracted from evidence, not a diagnosis fact."
      }
    },
    "edges": {
      "HAS_EVIDENCE_BLOCK": {
        "validator_status": "candidate_review"
      },
      "MENTIONS_CONCEPT": {
        "validator_status": "candidate_review"
      },
      "NEXT_BLOCK": {
        "validator_status": "candidate_review"
      }
    }
  },
  "validator_policy": {
    "statuses": ["published_graph", "candidate_review", "rejection"],
    "published_node_types": ["DocumentAsset"],
    "support_node_types": ["RouteBBlock", "RouteBConcept"],
    "support_edge_types": [
      "HAS_EVIDENCE_BLOCK",
      "MENTIONS_CONCEPT",
      "NEXT_BLOCK"
    ],
    "required_runtime_fields": [
      "route_b_status",
      "validator_status",
      "reviewed",
      "serving_safe"
    ],
    "blocked_value_markers": [
      "data/raw",
      "data/processed/unstructured",
      "response_text",
      "raw_response",
      "endpoint",
      "debug"
    ],
    "diagnosis_promotion": "forbidden"
  }
}
```

## 代码落地建议

后续如果要把现有 hard-coded policy 改成 schema-driven，可以按以下方式改：

- `SCHEMA3_PUBLISHED_NODE_TYPES` 从
  `route_b_evidence_v1.validator_policy.published_node_types` 读取。
- `ROUTE_B_SUPPORT_NODE_TYPES` 从
  `route_b_evidence_v1.validator_policy.support_node_types` 读取。
- `ROUTE_B_SUPPORT_EDGE_TYPES` 从
  `route_b_evidence_v1.validator_policy.support_edge_types` 读取。
- `BLOCKED_GRAPH_VALUE_MARKERS` 从
  `route_b_evidence_v1.validator_policy.blocked_value_markers` 读取。
- `DocumentAsset` 的正式字段合法性继续由
  `diagnostic_schema_v3_2.definitions.nodes.DocumentAsset` 约束。
- `/api/diagnose` RouteB projection 继续由 RouteB evidence contract 和
  result API schema 双重约束。

## 判断规则

后续评审时可以用以下规则避免边界混乱：

```text
KG 里允许什么正式节点/边？
  -> 看 diagnostic_schema

RouteB evidence 怎么组织、怎么验证？
  -> 看 route_b_evidence_v1

RouteB 什么能 published_graph？
  -> 以 diagnostic_schema 的正式语义为准，以 route_b validator policy 执行

RouteB evidence 能否变成 confirmed diagnosis？
  -> 不能，validator_policy.diagnosis_promotion = forbidden
```

## 未来何时需要调整

只有当 RouteB 后续稳定证明 block/chunk-level graph structure 具有长期价值，并且
需要把以下对象升级为受治理的一等图谱对象时，才需要重新开 schema review：

```text
DocumentBlock
DocumentChunk
DocumentAsset -[HAS_BLOCK]-> DocumentBlock
DocumentBlock -[NEXT_BLOCK]-> DocumentBlock
DocumentBlock -[MENTIONS]-> Concept
```

在此之前，`RouteBBlock`、`RouteBConcept` 和相关边都应留在 RouteB evidence
contract 中，而不是进入正式 `diagnostic_schema.definitions.nodes`。
