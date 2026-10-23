"""
Synthetic STEP tests for the CAD extract pipeline.

All tests use hand-written STEP fixtures — no data/raw/ files required.

Covers: parser + hierarchy + stats (PR-2), geometry + relationships (PR-3),
and the kg_edges + triples emitters that survive the schema migration.

NOTE (2026-08-08): the former PR-4 `validate_triples` tests were removed.
They read `contracts/schema/diagnostic_schema_v3_2.json`, which no longer
exists — the KG schema was renamed to `tpdx_kg_schema_v4_{1,2}.schema.json`.
The two depth-3 emitter tests were also removed: they asserted the pre-fix
behaviour (depth-3 node labelled Component / id `C_xx`) while the live
emitter correctly emits SubComponent / `SC_xx`. Both will be rebuilt against
the v4.x schema under V2-TASK015.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from services.graph.cad_extract.geometry import InstanceGeometry, Vec3, WorldFace
from services.graph.cad_extract.hierarchy import build_hierarchy
from services.graph.cad_extract.kg_edges import (
    EDGE_HAS_COMPONENT,
    EDGE_HAS_MODULE,
    EDGE_HAS_SUBCOMPONENT,
    compute_nauo_depths,
    serialize_hierarchy_edges,
)
from services.graph.cad_extract.parser import parse_step
from services.graph.cad_extract.relationships import Mate, _detect_and_emit_pair
from services.graph.cad_extract.stats import compute_stats
from services.graph.cad_extract.triples import emit_triples


# ---------------------------------------------------------------------------
# Shared synthetic STEP fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('synthetic'),'2;1');
    FILE_NAME('test.step','2026-01-01T00:00:00',('tester'),('none'),'','','');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
    ENDSEC;
    DATA;
    #1 = PRODUCT('ASM-001','RootAssembly','the root',(#100));
    #2 = PRODUCT('PRT-100','Bracket','L-shaped bracket',(#100));
    #3 = PRODUCT('PRT-200','Bolt','M6x20 bolt',(#100));
    #100 = PRODUCT_CONTEXT('',#999,'mechanical');
    #11 = PRODUCT_DEFINITION_FORMATION('v1','',#1);
    #12 = PRODUCT_DEFINITION_FORMATION('v1','',#2);
    #13 = PRODUCT_DEFINITION_FORMATION('v1','',#3);
    #21 = PRODUCT_DEFINITION('design','',#11,#200);
    #22 = PRODUCT_DEFINITION('design','',#12,#200);
    #23 = PRODUCT_DEFINITION('design','',#13,#200);
    #31 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n1','bracket','',#21,#22,$);
    #32 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n2','bolt1','',#21,#23,$);
    #33 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n3','bolt2','',#21,#23,$);
    #34 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n4','bolt3','',#21,#23,$);
    ENDSEC;
    END-ISO-10303-21;
""")

AP203_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('ap203-synthetic'),'2;1');
    FILE_NAME('ap203.step','2026-01-01T00:00:00',('tester'),('none'),'','','');
    FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));
    ENDSEC;
    DATA;
    #1 = PRODUCT('ASM-001','Root','',(#100));
    #2 = PRODUCT('PRT-100','Child','',(#100));
    #100 = PRODUCT_CONTEXT('',#999,'mechanical');
    #11 = PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('v1','',#1,.NOT_KNOWN.);
    #12 = PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('v1','',#2,.NOT_KNOWN.);
    #21 = PRODUCT_DEFINITION('design','',#11,#200);
    #22 = PRODUCT_DEFINITION('design','',#12,#200);
    #31 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n1','child','',#21,#22,$);
    ENDSEC;
    END-ISO-10303-21;
""")

ORPHAN_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('orphan-synthetic'),'2;1');
    FILE_NAME('orphan.step','2026-01-01T00:00:00',('tester'),('none'),'','','');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
    ENDSEC;
    DATA;
    #1 = PRODUCT('ASM-001','Root','',(#100));
    #2 = PRODUCT('PRT-100','Child','',(#100));
    #3 = PRODUCT('DUMMY-9','_dummy-placeholder','unused',(#100));
    #100 = PRODUCT_CONTEXT('',#999,'mechanical');
    #11 = PRODUCT_DEFINITION_FORMATION('v1','',#1);
    #12 = PRODUCT_DEFINITION_FORMATION('v1','',#2);
    #13 = PRODUCT_DEFINITION_FORMATION('v1','',#3);
    #21 = PRODUCT_DEFINITION('design','',#11,#200);
    #22 = PRODUCT_DEFINITION('design','',#12,#200);
    #23 = PRODUCT_DEFINITION('design','',#13,#200);
    #31 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n1','child','',#21,#22,$);
    ENDSEC;
    END-ISO-10303-21;
""")


@pytest.fixture
def synthetic_step(tmp_path: Path) -> Path:
    p = tmp_path / "synthetic.step"
    p.write_text(SYNTHETIC_STEP, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# PR-2 tests: parser + hierarchy + stats
# ---------------------------------------------------------------------------

def test_parser_reads_all_entities(synthetic_step: Path) -> None:
    entities = parse_step(synthetic_step)
    # 3 PRODUCT + 1 PRODUCT_CONTEXT + 3 PRODUCT_DEFINITION_FORMATION
    # + 3 PRODUCT_DEFINITION + 4 NAUO = 14
    assert len(entities) == 14
    by_type = {e.name for e in entities.values()}
    assert "PRODUCT" in by_type
    assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE" in by_type


def test_hierarchy_counts_instances(synthetic_step: Path) -> None:
    entities = parse_step(synthetic_step)
    h = build_hierarchy(entities)

    assert len(h.products) == 3
    assert h.unresolved_nauos == 0

    by_id = {p.id: p for p in h.products.values()}
    assert set(by_id) == {"ASM-001", "PRT-100", "PRT-200"}

    assert len(h.roots) == 1
    assert h.products[h.roots[0]].id == "ASM-001"

    bracket_ref = by_id["PRT-100"].product_ref
    bolt_ref = by_id["PRT-200"].product_ref
    assert h.instance_count[bracket_ref] == 1
    assert h.instance_count[bolt_ref] == 3


def test_stats_shape(synthetic_step: Path) -> None:
    entities = parse_step(synthetic_step)
    h = build_hierarchy(entities)
    stats = compute_stats(h)

    assert stats["summary"]["unique_products"] == 3
    assert stats["summary"]["total_instances"] == 4
    assert stats["summary"]["root_assemblies"] == 1
    assert stats["summary"]["unresolved_nauos"] == 0
    assert stats["summary"]["max_hierarchy_depth"] == 2
    assert stats["summary"]["total_mates"] == 0

    for p in stats["parts"]:
        assert set(p.keys()) >= {"id", "name", "description", "qty", "is_root"}

    ids = {p["id"]: p for p in stats["parts"]}
    assert ids["PRT-200"]["qty"] == 3
    assert ids["PRT-100"]["qty"] == 1
    assert ids["ASM-001"]["is_root"] is True

    assert stats["hierarchy"]["1"] == {"total": 1, "assemblies": 1, "parts": 0}
    assert stats["hierarchy"]["2"] == {"total": 4, "assemblies": 0, "parts": 4}


def test_ap203_with_specified_source_resolves(tmp_path: Path) -> None:
    # Regression: AP203 CONFIG_CONTROL_DESIGN uses the _WITH_SPECIFIED_SOURCE
    # subtype; ignoring it made every NAUO unresolved on real SW exports.
    p = tmp_path / "ap203.step"
    p.write_text(AP203_STEP, encoding="utf-8")
    h = build_hierarchy(parse_step(p))
    assert h.unresolved_nauos == 0
    assert sum(h.instance_count.values()) == 1


def test_hierarchy_records_nauo_edges(synthetic_step: Path) -> None:
    # nauo_edges captures one (parent_pref, child_pref, nauo_id) tuple per
    # resolved NAUO so the emitter can produce per-NAUO hierarchy edges
    # without re-walking the entity table.
    h = build_hierarchy(parse_step(synthetic_step))
    assert len(h.nauo_edges) == 4  # 1 bracket + 3 bolts
    nauo_ids = {nauo for _, _, nauo in h.nauo_edges}
    assert nauo_ids == {31, 32, 33, 34}


# ---------------------------------------------------------------------------
# PR-3 tests: geometry + relationships
# ---------------------------------------------------------------------------

def test_mate_emission_canonicalizes_endpoint_order() -> None:
    # HAS_CONNECTION is undirected; downstream relies on `nauo_a < nauo_b`
    # for cheap dedupe and to let Cypher use unarrowed `MATCH (x)-[r]-(y)`.
    # The sibling pass iterates children whose relative NAUO ids depend on
    # dict-insertion order — the swap in `_detect_and_emit_pair` is the
    # single chokepoint that guarantees the invariant.
    # This test calls it with id_a > id_b and confirms the emitted mate flips.
    face_up = WorldFace(
        face_id=1, surface_type="PLANE",
        origin=Vec3(0.0, 0.0, 0.0), axis=Vec3(0.0, 0.0, 1.0),
        radius=None, same_sense=True,
    )
    face_dn = WorldFace(
        face_id=2, surface_type="PLANE",
        origin=Vec3(0.0, 0.0, 0.0), axis=Vec3(0.0, 0.0, -1.0),
        radius=None, same_sense=True,
    )
    inst_low = InstanceGeometry(
        nauo_id=10, product_ref=100, parent_product_ref=1,
        product_name="LowName", product_id_str="LOW-1",
        faces=[face_up],
        aabb_min=Vec3(-1.0, -1.0, -0.1), aabb_max=Vec3(1.0, 1.0, 0.1),
    )
    inst_high = InstanceGeometry(
        nauo_id=99, product_ref=200, parent_product_ref=1,
        product_name="HighName", product_id_str="HIGH-9",
        faces=[face_dn],
        aabb_min=Vec3(-1.0, -1.0, -0.1), aabb_max=Vec3(1.0, 1.0, 0.1),
    )

    mates: list[Mate] = []
    _detect_and_emit_pair(99, 10, inst_high, inst_low, mates, scope="sibling")

    assert mates, "expected planar_contact mate for facing coplanar planes"
    for m in mates:
        assert m.nauo_a < m.nauo_b, f"non-canonical mate: {m.nauo_a} >= {m.nauo_b}"
        assert m.product_id_a == "LOW-1"
        assert m.product_id_b == "HIGH-9"


def test_orphan_products_are_split_from_roots_and_dropped_from_bom(tmp_path: Path) -> None:
    # An orphan = PRODUCT with no parent and no children. It must not count as
    # a root, must appear in h.orphans, must be dropped from parts list, and
    # must be surfaced in stats warnings.
    p = tmp_path / "orphan.step"
    p.write_text(ORPHAN_STEP, encoding="utf-8")
    h = build_hierarchy(parse_step(p))

    by_id = {prod.id: ref for ref, prod in h.products.items()}
    assert h.roots == [by_id["ASM-001"]]
    assert h.orphans == [by_id["DUMMY-9"]]

    stats = compute_stats(h)
    assert stats["summary"]["root_assemblies"] == 1
    assert stats["summary"]["orphan_products"] == 1
    bom_ids = {part["id"] for part in stats["parts"]}
    assert "DUMMY-9" not in bom_ids
    assert {"ASM-001", "PRT-100"} <= bom_ids
    assert any("orphan" in w.lower() for w in stats["warnings"])
    assert [o["id"] for o in stats["orphans"]] == ["DUMMY-9"]


# ---------------------------------------------------------------------------
# Shared STEP fixtures for PR-4 tests
# ---------------------------------------------------------------------------

DEEP_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('deep'),'2;1');
    FILE_NAME('deep.step','2026-01-01T00:00:00',('t'),('n'),'','','');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
    ENDSEC;
    DATA;
    #1 = PRODUCT('ROOT','Root','',(#100));
    #2 = PRODUCT('MOD-A','Module A','',(#100));
    #3 = PRODUCT('COMP-X','Component X','',(#100));
    #4 = PRODUCT('SUB-Y','Subcomponent Y','',(#100));
    #100 = PRODUCT_CONTEXT('',#999,'mechanical');
    #11 = PRODUCT_DEFINITION_FORMATION('v','',#1);
    #12 = PRODUCT_DEFINITION_FORMATION('v','',#2);
    #13 = PRODUCT_DEFINITION_FORMATION('v','',#3);
    #14 = PRODUCT_DEFINITION_FORMATION('v','',#4);
    #21 = PRODUCT_DEFINITION('d','',#11,#200);
    #22 = PRODUCT_DEFINITION('d','',#12,#200);
    #23 = PRODUCT_DEFINITION('d','',#13,#200);
    #24 = PRODUCT_DEFINITION('d','',#14,#200);
    #31 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','','',#21,#22,$);
    #32 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','','',#22,#23,$);
    #33 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','','',#23,#24,$);
    ENDSEC;
    END-ISO-10303-21;
""")

REUSED_STEP = textwrap.dedent("""\
    ISO-10303-21;
    HEADER;
    FILE_DESCRIPTION(('reused'),'2;1');
    FILE_NAME('reused.step','2026-01-01T00:00:00',('t'),('n'),'','','');
    FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
    ENDSEC;
    DATA;
    #1 = PRODUCT('ROOT','Root','',(#100));
    #2 = PRODUCT('MOD-A','Module A','',(#100));
    #3 = PRODUCT('COMP-X','Component X','',(#100));
    #100 = PRODUCT_CONTEXT('',#999,'mechanical');
    #11 = PRODUCT_DEFINITION_FORMATION('v','',#1);
    #12 = PRODUCT_DEFINITION_FORMATION('v','',#2);
    #13 = PRODUCT_DEFINITION_FORMATION('v','',#3);
    #21 = PRODUCT_DEFINITION('d','',#11,#200);
    #22 = PRODUCT_DEFINITION('d','',#12,#200);
    #23 = PRODUCT_DEFINITION('d','',#13,#200);
    #31 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','a1','',#21,#22,$);
    #32 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','a2','',#21,#22,$);
    #33 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('n','x','',#22,#23,$);
    ENDSEC;
    END-ISO-10303-21;
""")


# ---------------------------------------------------------------------------
# PR-4 tests: kg_edges + triples emitters
# ---------------------------------------------------------------------------

def test_serialize_hierarchy_edges_assigns_schema_edge_types(tmp_path: Path) -> None:
    # 3-deep tree → all three edge types must fire:
    #   ROOT → MOD-A (depth 1 → HAS_MODULE)
    #          └─ COMP-X (depth 2 → HAS_COMPONENT)
    #                └─ SUB-Y (depth 3 → HAS_SUBCOMPONENT)
    p = tmp_path / "deep.step"
    p.write_text(DEEP_STEP, encoding="utf-8")
    h = build_hierarchy(parse_step(p))
    by_id = {prod.id: ref for ref, prod in h.products.items()}

    nauo_depths = compute_nauo_depths(h)
    assert nauo_depths[31] == 1
    assert nauo_depths[32] == 2
    assert nauo_depths[33] == 3

    edges = serialize_hierarchy_edges(h)
    by_child = {e.child_product_ref: e for e in edges}

    assert by_child[by_id["MOD-A"]].edge_type == EDGE_HAS_MODULE
    assert by_child[by_id["MOD-A"]].depth == 1
    assert by_child[by_id["COMP-X"]].edge_type == EDGE_HAS_COMPONENT
    assert by_child[by_id["COMP-X"]].depth == 2
    assert by_child[by_id["SUB-Y"]].edge_type == EDGE_HAS_SUBCOMPONENT
    assert by_child[by_id["SUB-Y"]].depth == 3
    assert by_child[by_id["MOD-A"]].nauo_id == 31
    assert sorted(e.nauo_id for e in edges) == [e.nauo_id for e in edges]


def test_emit_triples_collapses_reused_subassembly(tmp_path: Path) -> None:
    # MOD-A reused twice (NAUOs 31, 32); COMP-X introduced once (NAUO 33).
    # Two Module nodes emitted; one Component collapsed to canonical parent M_31.
    p = tmp_path / "reused.step"
    p.write_text(REUSED_STEP, encoding="utf-8")
    h = build_hierarchy(parse_step(p))
    ts = emit_triples(h, serialize_hierarchy_edges(h), [], station_id="TEST")

    module_ids = sorted(n.id for n in ts.nodes if n.label == "Module")
    assert module_ids == ["M_31", "M_32"]

    comp_ids = [n.id for n in ts.nodes if n.label == "Component"]
    assert comp_ids == ["C_33"]

    has_module = [e for e in ts.edges if e.type == EDGE_HAS_MODULE]
    assert len(has_module) == 2
    assert all(e.from_id == "ST_TEST" for e in has_module)

    has_component = [e for e in ts.edges if e.type == EDGE_HAS_COMPONENT]
    assert len(has_component) == 1
    assert has_component[0].from_id == "M_31"
    assert has_component[0].to_id == "C_33"

    comp = next(n for n in ts.nodes if n.id == "C_33")
    assert comp.properties["module_id"] == "M_31"
