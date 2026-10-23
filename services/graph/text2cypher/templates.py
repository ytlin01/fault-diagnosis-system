"""Cypher query templates for the v3.2 CAD KG schema.

Each template uses $node_id as the sole parameter for the anchor node.
Templates are organised by intent and then by label (station / module /
component / subcomponent).

Intent constants
----------------
INTENT_HIERARCHY    — fetch the anchor node + its direct children
INTENT_CONNECTIONS  — fetch the anchor node + all HAS_CONNECTION neighbours
INTENT_CROSS_MODULE — fetch the anchor + all descendants (recursive)
"""

from __future__ import annotations

INTENT_HIERARCHY = "hierarchy"
INTENT_CONNECTIONS = "connections"
INTENT_CROSS_MODULE = "cross_module"
INTENT_DIAGNOSTIC_CHAIN = "diagnostic_chain"

VALID_INTENTS = {INTENT_HIERARCHY, INTENT_CONNECTIONS, INTENT_CROSS_MODULE, INTENT_DIAGNOSTIC_CHAIN}

# CYPHER[intent][label] -> parameterised Cypher string
CYPHER: dict[str, dict[str, str]] = {

    INTENT_HIERARCHY: {
        "station": """
MATCH (st:Station {station_id: $node_id})
OPTIONAL MATCH (st)-[:HAS_MODULE]->(m:Module)
RETURN st {.*} AS node,
       collect(m {.*}) AS children
""", 
        "module": """
MATCH (m:Module {module_id: $node_id})
OPTIONAL MATCH (m)-[:HAS_COMPONENT]->(c:Component)
RETURN m {.*} AS node,
       collect(c {.*}) AS children
""",
        "component": """
MATCH (c:Component {component_id: $node_id})
OPTIONAL MATCH (c)-[:HAS_SUBCOMPONENT]->(sc:SubComponent)
RETURN c {.*} AS node,
       collect(sc {.*}) AS children
""",
        "subcomponent": """
MATCH (sc:SubComponent {subcomponent_id: $node_id})
OPTIONAL MATCH (parent)-[:HAS_SUBCOMPONENT]->(sc)
RETURN sc {.*} AS node,
       labels(parent)[0] AS parent_label,
       parent {.*} AS parent_props
""",
    },

    INTENT_CONNECTIONS: {
        "station": """
MATCH (st:Station {station_id: $node_id})-[:HAS_MODULE]->(m:Module)
      -[r:HAS_CONNECTION]-(n)
RETURN st {.*} AS source,
       labels(n)[0] AS neighbor_label,
       n {.*} AS neighbor,
       r.connection_type AS connection_type,
       r.confidence AS confidence
ORDER BY r.confidence DESC
""",
        "module": """
MATCH (m:Module {module_id: $node_id})-[r:HAS_CONNECTION]-(n)
RETURN m {.*} AS source,
       labels(n)[0] AS neighbor_label,
       n {.*} AS neighbor,
       r.connection_type AS connection_type,
       r.confidence AS confidence
ORDER BY r.confidence DESC
""",
        "component": """
MATCH (c:Component {component_id: $node_id})-[r:HAS_CONNECTION]-(n)
RETURN c {.*} AS source,
       labels(n)[0] AS neighbor_label,
       n {.*} AS neighbor,
       r.connection_type AS connection_type,
       r.confidence AS confidence
ORDER BY r.confidence DESC
""",
        "subcomponent": """
MATCH (sc:SubComponent {subcomponent_id: $node_id})-[r:HAS_CONNECTION]-(n)
RETURN sc {.*} AS source,
       labels(n)[0] AS neighbor_label,
       n {.*} AS neighbor,
       r.connection_type AS connection_type,
       r.confidence AS confidence
ORDER BY r.confidence DESC
""",
    },

    INTENT_CROSS_MODULE: {
        "station": """
MATCH (st:Station {station_id: $node_id})
OPTIONAL MATCH (st)-[:HAS_MODULE]->(m:Module)
OPTIONAL MATCH (m)-[:HAS_COMPONENT]->(c:Component)
OPTIONAL MATCH (c)-[:HAS_SUBCOMPONENT*]->(sc:SubComponent)
RETURN st {.*} AS node,
       collect(distinct m {.*}) AS modules,
       collect(distinct c {.*}) AS components,
       collect(distinct sc {.*}) AS subcomponents
""",
        "module": """
MATCH (m:Module {module_id: $node_id})
OPTIONAL MATCH (m)-[:HAS_COMPONENT]->(c:Component)
OPTIONAL MATCH (c)-[:HAS_SUBCOMPONENT*]->(sc:SubComponent)
RETURN m {.*} AS node,
       collect(distinct c {.*}) AS components,
       collect(distinct sc {.*}) AS subcomponents
""",
        "component": """
MATCH (c:Component {component_id: $node_id})
OPTIONAL MATCH (c)-[:HAS_SUBCOMPONENT*]->(sc:SubComponent)
RETURN c {.*} AS node,
       collect(distinct sc {.*}) AS subcomponents
""",
        "subcomponent": """
MATCH (sc:SubComponent {subcomponent_id: $node_id})
OPTIONAL MATCH (sc)-[:HAS_SUBCOMPONENT*]->(child:SubComponent)
RETURN sc {.*} AS node,
       collect(distinct child {.*}) AS subcomponents
""",
    },
}

# Diagnostic-chain templates.  Anchor is either an ErrorCode (param: $error_code)
# or a Component (param: $node_id via TRIGGERS edge).
# Each result row: one (fault, cause, action) combination with ordered steps.
CYPHER_DIAGNOSTIC: dict[str, str] = {

    "error_code": """
MATCH (ec:ErrorCode {code_id: $error_code})-[:INDICATES]->(f:Fault)
OPTIONAL MATCH (f)-[:HAS_CAUSE]->(ca:Cause)
OPTIONAL MATCH (ca)-[:RESOLVED_BY]->(act:Action)
OPTIONAL MATCH (act)-[:HAS_STEP]->(s:ActionStep)
WITH ec, f, ca, act, s
ORDER BY COALESCE(s.order, 0)
WITH ec, f, ca, act, collect(s {.*}) AS steps
RETURN ec {.*} AS error_code,
       f {.*} AS fault,
       ca {.*} AS cause,
       act {.*} AS action,
       steps
""",

    "component": """
MATCH (c:Component {component_id: $node_id})-[:TRIGGERS]->(f:Fault)
OPTIONAL MATCH (f)-[:HAS_CAUSE]->(ca:Cause)
OPTIONAL MATCH (ca)-[:RESOLVED_BY]->(act:Action)
OPTIONAL MATCH (act)-[:HAS_STEP]->(s:ActionStep)
WITH f, ca, act, s
ORDER BY COALESCE(s.order, 0)
WITH f, ca, act, collect(s {.*}) AS steps
RETURN f {.*} AS fault,
       ca {.*} AS cause,
       act {.*} AS action,
       steps
""",

    "module": """
MATCH (m:Module {module_id: $node_id})-[:HAS_COMPONENT]->(c:Component)-[:TRIGGERS]->(f:Fault)
OPTIONAL MATCH (f)-[:HAS_CAUSE]->(ca:Cause)
OPTIONAL MATCH (ca)-[:RESOLVED_BY]->(act:Action)
OPTIONAL MATCH (act)-[:HAS_STEP]->(s:ActionStep)
WITH c, f, ca, act, s
ORDER BY COALESCE(s.order, 0)
WITH c, f, ca, act, collect(s {.*}) AS steps
RETURN c {.*} AS component,
       f {.*} AS fault,
       ca {.*} AS cause,
       act {.*} AS action,
       steps
""",

    # Fault-text search: match faults whose name (with underscores removed) is contained
    # in the query text, or whose name directly contains the query text fragment.
    # $text should be the cleaned phenomenon text with question suffixes stripped.
    "fault_text": """
MATCH (f:Fault)
WHERE $text CONTAINS replace(f.name, '_', '')
   OR f.name CONTAINS $text
OPTIONAL MATCH (f)-[:HAS_CAUSE]->(ca:Cause)
OPTIONAL MATCH (ca)-[:RESOLVED_BY]->(act:Action)
OPTIONAL MATCH (act)-[:HAS_STEP]->(s:ActionStep)
WITH f, ca, act, s
ORDER BY COALESCE(s.order, 0)
WITH f, ca, act, collect(s {.*}) AS steps
RETURN f {.*} AS fault,
       ca {.*} AS cause,
       act {.*} AS action,
       steps
LIMIT 5
""",
}
