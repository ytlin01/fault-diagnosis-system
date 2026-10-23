from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.governance import annotation_tracker, eval_run_log, index_registry, masking_log
from services.governance.storage import read_jsonl_rows


@pytest.fixture()
def governance_dir(tmp_path: Path) -> Path:
    return tmp_path / "governance"


def test_all_operational_logs_append_jsonl_rows(governance_dir: Path, tmp_path: Path) -> None:
    masking_log.record(
        source_id="source-a",
        run_id="maskrun-001",
        masking_source_name="demo_source",
        input_source_id="raw-source-a",
        canonical_source_id="canonical-source-a",
        serving_source_id="serving-source-a",
        rules_version=4,
        masking_action="structured_masking",
        input_path="data/raw/source-a.xlsx",
        output_canonical_path="data/processed/source-a.json",
        output_serving_path="data/serving/source-a.json",
        manifest_path="data/processed/_manifests/source-a.json",
        lineage_path="data/processed/_lineage/source-a.jsonl",
        operator="tester",
        log_id="mask-001",
        run_timestamp="2026-07-14T08:00:00+00:00",
        governance_dir=governance_dir,
    )
    annotation_tracker.record(
        source_id="source-a",
        source_version="sha256:v1",
        annotated_by="reviewer",
        annotation_type="diagnostic_mapping_review",
        annotation_id="annotation-001",
        annotated_at="2026-07-14T08:05:00+00:00",
        governance_dir=governance_dir,
    )
    payload = tmp_path / "snapshot.json"
    payload.write_text('{"value":1}', encoding="utf-8")
    index_registry.record(
        index_name="node_name_index",
        source_id="data/processed/structured/triples.json",
        serving_snapshot_id=index_registry.snapshot_id(payload),
        build_script="scripts/build_graph/build_node_name_index.py",
        index_type="node_name_lookup",
        build_timestamp="2026-07-14T08:10:00+00:00",
        governance_dir=governance_dir,
    )
    eval_run_log.record(
        eval_set="data/eval/route_a/golden_set.json",
        model="route_a_pipeline",
        route="route_a",
        score_summary={"passed": 3, "total": 4},
        run_id="eval-001",
        run_timestamp="2026-07-14T08:15:00+00:00",
        governance_dir=governance_dir,
    )

    masking_row = read_jsonl_rows(governance_dir / "masking_log.jsonl")[0]
    assert masking_row["log_id"] == "mask-001"
    assert masking_row["run_id"] == "maskrun-001"
    assert masking_row["source_id"] == "raw-source-a"
    assert masking_row["input_source_id"] == "raw-source-a"
    assert masking_row["canonical_source_id"] == "canonical-source-a"
    assert masking_row["serving_source_id"] == "serving-source-a"
    assert masking_row["manifest_path"].endswith("source-a.json")
    assert masking_row["lineage_path"].endswith("source-a.jsonl")
    assert read_jsonl_rows(governance_dir / "annotation_log.jsonl")[0]["source_version"] == "sha256:v1"
    assert read_jsonl_rows(governance_dir / "index_registry.jsonl")[0]["serving_snapshot_id"].startswith("sha256:")
    assert read_jsonl_rows(governance_dir / "eval_run_log.jsonl")[0]["score_summary"] == '{"passed":3,"total":4}'


def test_annotation_staleness_tracks_source_versions(governance_dir: Path) -> None:
    annotation_tracker.record(
        source_id="source-a",
        source_version="v1",
        annotated_by="reviewer",
        annotation_type="review",
        annotation_id="annotation-001",
        governance_dir=governance_dir,
    )

    assert not annotation_tracker.check_staleness(
        "source-a", "v1", governance_dir=governance_dir
    )
    assert annotation_tracker.check_staleness(
        "source-a", "v2", governance_dir=governance_dir
    )


def test_duplicate_event_id_is_rejected(governance_dir: Path) -> None:
    kwargs = {
        "source_id": "source-a",
        "rules_version": 4,
        "masking_action": "structured_masking",
        "input_path": "input.xlsx",
        "output_canonical_path": "canonical.json",
        "operator": "tester",
        "log_id": "mask-001",
        "governance_dir": governance_dir,
    }
    masking_log.record(**kwargs)
    with pytest.raises(ValueError, match="Duplicate masking_log record"):
        masking_log.record(**kwargs)


def test_dry_run_does_not_create_jsonl(governance_dir: Path) -> None:
    row = eval_run_log.record(
        eval_set="gold.json",
        model="route_a_pipeline",
        route="route_a",
        score_summary={"passed": 1},
        dry_run=True,
        governance_dir=governance_dir,
    )
    assert row["route"] == "route_a"
    assert not (governance_dir / "eval_run_log.jsonl").exists()


def test_jsonl_is_one_valid_json_object_per_line(governance_dir: Path) -> None:
    masking_log.record(
        source_id="source-a",
        rules_version=4,
        masking_action="structured_masking",
        input_path="input.xlsx",
        output_canonical_path="canonical.json",
        operator="tester",
        log_id="mask-001",
        governance_dir=governance_dir,
    )

    lines = (governance_dir / "masking_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["log_id"] == "mask-001"


def test_jsonl_reader_accepts_utf8_bom(governance_dir: Path) -> None:
    governance_dir.mkdir(parents=True)
    path = governance_dir / "masking_log.jsonl"
    path.write_text(
        '{"log_id":"mask-bom","source_id":"source-a"}\n',
        encoding="utf-8-sig",
    )

    rows = read_jsonl_rows(path)

    assert rows == [{"log_id": "mask-bom", "source_id": "source-a"}]
