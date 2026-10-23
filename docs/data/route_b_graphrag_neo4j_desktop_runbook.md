# Route B GraphRAG Neo4j Desktop Runbook

> **Retired 2026-08-08.** The export script this runbook drove
> (`scripts/export_route_b_graphrag_neo4j.py`) was removed with the GraphRAG v1
> retirement. Retained as a historical reference for the Neo4j import/query
> procedure.

## Purpose

This runbook is for local Neo4j Desktop visualization of the Route B GraphRAG
v1 evidence graph. It does not require proxy settings or online package
installation if you use the generated Cypher artifact.

## Generate Artifacts

From the repository root:

```powershell
python scripts\export_route_b_graphrag_neo4j.py
```

Expected outputs:

```text
artifacts/route_b_graphrag_v1/route_b_graphrag_v1.json
artifacts/route_b_graphrag_v1/route_b_graphrag_v1.cypher
artifacts/route_b_graphrag_v1/cypher_parts/
```

The full Cypher file is best for `cypher-shell`. The split files under
`cypher_parts/` are easier to inspect or run in smaller chunks.

## Recommended Neo4j Desktop Import

1. Open Neo4j Desktop.
2. Start the target local DBMS/database. The status should be running.
3. Confirm the Bolt connector is enabled and note the displayed Bolt port. The
   FaultDx standard is `bolt://127.0.0.1:7687`.
4. Open the DBMS terminal or a system terminal where `cypher-shell` is
   available.
5. Run:

```powershell
cypher-shell -u <neo4j_user> -p <neo4j_password> -a bolt://127.0.0.1:7687 -f artifacts\route_b_graphrag_v1\route_b_graphrag_v1.cypher
```

If your Neo4j Desktop DBMS uses a different Bolt port, replace `7687`.

## Troubleshooting: Connection Refused

If direct Python write or `cypher-shell` reports a connection-refused error for
`127.0.0.1:7687`, check these items in Neo4j Desktop:

1. The DBMS is started.
2. The database is online.
3. The Bolt connector is enabled.
4. The Bolt port matches `FAULTDX_NEO4J_HOST`.
5. No other local Neo4j instance is occupying the same port.

If Desktop shows a different Bolt URL, update local `.env`:

```text
FAULTDX_NEO4J_HOST=bolt://127.0.0.1:<desktop-bolt-port>
```

If Desktop shows the database name as lowercase `neo4j`, use:

```text
FAULTDX_NEO4J_DATABASE=neo4j
```

If the team route A config uses `NEO4J` and your local Desktop accepts it, that
can stay as-is.

## Alternative: Browser / Smaller Chunks

If `cypher-shell` is not available, open Neo4j Browser and run the files under:

```text
artifacts/route_b_graphrag_v1/cypher_parts/
```

Run them in numeric order:

```text
route_b_graphrag_v1_part_001.cypher
route_b_graphrag_v1_part_002.cypher
...
```

This is slower than `cypher-shell`, but avoids Python driver installation.

## Optional Direct Python Write

Direct write is available only if the optional Python `neo4j` package is
installed and the local DBMS is running:

```powershell
python scripts\export_route_b_graphrag_neo4j.py --write-neo4j
```

The script reads these keys from `.env` without printing secret values:

```text
FAULTDX_NEO4J_HOST
FAULTDX_NEO4J_USER
FAULTDX_NEO4J_PASSWORD
FAULTDX_NEO4J_DATABASE
```

Example host value:

```text
bolt://127.0.0.1:7687
```

Neo4j Desktop may default new connections to `neo4j+s://`. For this local
standalone setup, switch the scheme to plain Bolt and reconnect:

```text
bolt://127.0.0.1:7687
```

Because the current local setup has no proxy configured, the Cypher import path
is the safest default. Do not install packages or change proxy settings just to
inspect the graph.

If Neo4j Desktop reports that the configured database does not exist, either
set `FAULTDX_NEO4J_DATABASE` to the exact local database name shown in Desktop
or leave it empty so the driver uses the DBMS default database.

## Useful Neo4j Browser Queries

Show sample Route B graph:

```cypher
MATCH p=(n:RouteBGraphNode)-[r]-(m:RouteBGraphNode)
RETURN p
LIMIT 100;
```

Show serving documents:

```cypher
MATCH (d:RouteBDocument)
RETURN d.doc_id, d.source_name, d.route_b_status, d.validator_status;
```

Show evidence blocks for one document:

```cypher
MATCH (d:RouteBDocument)-[:HAS_EVIDENCE_BLOCK]->(b:RouteBBlock)
WHERE d.doc_id = "C1STN-_SOPV1.2_8aff482b6083"
RETURN d, b
LIMIT 100;
```

Show concepts around the hard-case terms:

```cypher
MATCH p=(b:RouteBBlock)-[:MENTIONS_CONCEPT]->(c:RouteBConcept)
WHERE c.name IN ["automatic", "take", "install", "screw", "cg", "cowling", "sensor"]
RETURN p
LIMIT 200;
```

Show validator buckets:

```cypher
MATCH (n:RouteBGraphNode)
RETURN n.validator_status AS status, count(*) AS count
ORDER BY count DESC;
```

Show Route B support edges:

```cypher
MATCH ()-[r]->()
RETURN type(r) AS edge_type, r.validator_status AS status, count(*) AS count
ORDER BY count DESC;
```

## Boundary Reminder

This graph is a Route B document-evidence graph:

- `DocumentAsset` nodes are schema 3.0 aligned.
- `RouteBBlock`, `RouteBConcept`, and support edges remain
  `candidate_review`.
- Nothing in this graph is a confirmed diagnosis.
- This graph must remain separate from the Route A reviewed diagnosis KG.
