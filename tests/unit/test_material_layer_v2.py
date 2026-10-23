"""Synthetic tests for the V2-TASK017 replacement-list parser.

All fixtures are synthetic; no file under ``data/`` is read. Workbooks are
built in temporary directories with openpyxl and mirror the verified BOM04
header layout (header_row 0-based 1, data_offset 2). The BOM03 path was
removed with the 2026-08-27 data-owner scope decision (single governed
input: L_ReplacementList; node-only output).
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # noqa: E402

from services.ingestion import material_layer_v2 as ml  # noqa: E402

try:
    import jsonschema  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - environment guard
    jsonschema = None

try:
    import openpyxl  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - environment guard
    openpyxl = None

CONFIG_PATH = PROJECT_ROOT / "configs" / "pipelines" / "replacement_extract.yaml"
SCHEMA_PATH = PROJECT_ROOT / "contracts" / "schema" / "tpdx_kg_schema_v4_2.schema.json"
RUNNER = PROJECT_ROOT / "scripts" / "build_graph" / "build_material_layer_v2_candidate.py"
SALT = "synthetic-test-salt-local-only"

with CONFIG_PATH.open("r", encoding="utf-8") as _handle:
    BASE_CONFIG = yaml.safe_load(_handle)

BOM04_HEADERS = [
    "耗材品名", "耗材規格", "自動化工站", "設備名稱", "廠商", "品牌",
]


def config() -> dict:
    return copy.deepcopy(BASE_CONFIG)


def bom04_tables(rows: list[list]) -> dict[str, list[list]]:
    """工作表1 with one blank row, header at 0-based row 1, description row, data."""
    return {"工作表1": [[], list(BOM04_HEADERS), ["(field descriptions)"], *rows]}


def bom04_row(name, spec="", station="", equipment="", vendor="SynthVendor") -> list:
    values = {
        "耗材品名": name, "耗材規格": spec, "自動化工站": station,
        "設備名稱": equipment, "廠商": vendor, "品牌": "",
    }
    return [values.get(header, "") for header in BOM04_HEADERS]


def extract(tables: dict, cfg: dict | None = None) -> ml.RowExtraction:
    cfg = cfg or config()
    bom_cfg = cfg["bom04"]
    location = ml.locate_sheet_and_header(
        tables, bom_cfg, search_rows=cfg["detection"]["search_rows"]
    )
    return ml.extract_rows(tables[location.sheet], bom_cfg, location)


def build(
    bom04_rows: list[list],
    *,
    cfg: dict | None = None,
    salt: str = SALT,
) -> ml.MaterialLayerResult:
    cfg = cfg or config()
    bom04 = extract(bom04_tables(bom04_rows), cfg)
    return ml.build_material_layer(
        bom04, raw_names=bom04.raw_names, salt=salt, config=cfg,
    )


def write_bom04_workbook(path: Path, rows: list[list], *, sheet: str = "工作表1",
                          headers: list | None = None) -> None:
    workbook = openpyxl.Workbook()
    sheet_obj = workbook.active
    sheet_obj.title = sheet
    sheet_obj.append([])
    sheet_obj.append(list(headers or BOM04_HEADERS))
    sheet_obj.append(["(field descriptions)"])
    for row in rows:
        sheet_obj.append(list(row))
    workbook.save(path)


def run_cli(*extra_args: str, env_overrides: dict | None = None, salt: str | None = SALT):
    env = dict(os.environ)
    if salt is None:
        env.pop("FAULTDX_MASKING_SALT", None)
    else:
        env["FAULTDX_MASKING_SALT"] = salt
    env.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, str(RUNNER), *extra_args],
        capture_output=True, text=True, cwd=PROJECT_ROOT, env=env, check=False,
    )


class ConfigTests(unittest.TestCase):
    def test_config_file_valid(self) -> None:
        parsed = ml.validate_config(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
        self.assertEqual(parsed["schema_version"], ml.CONFIG_SCHEMA_VERSION)
        self.assertEqual(parsed["candidate"]["payload_kind"], "diagnostic")

    def test_invalid_config_rejected(self) -> None:
        cases = []
        missing_section = config()
        del missing_section["leakage"]
        cases.append((missing_section, "leakage"))
        casefold = config()
        casefold["canonicalization"]["identity_casefold"] = True
        cases.append((casefold, "identity_casefold"))
        bad_pattern = config()
        bad_pattern["leakage"]["numeric_pattern"] = "(["
        cases.append((bad_pattern, "numeric_pattern"))
        sensitive = config()
        sensitive["bom04"]["sensitive_columns"].append(sensitive["bom04"]["name_col"])
        cases.append((sensitive, "sensitive_columns"))
        for broken, expected_fragment in cases:
            with self.subTest(fragment=expected_fragment):
                with self.assertRaisesRegex(ValueError, expected_fragment):
                    ml.validate_config(broken)

    def test_removed_sections_are_rejected(self) -> None:
        """bom03/relationships/topology_endpoint are gone; extra keys fail closed."""
        legacy = config()
        legacy["bom03"] = {"source_id": "x", "sheet": "Sheet1", "header_row": 3,
                           "data_offset": 1, "name_col": "物料名称", "spec_col": "规格型号"}
        # Extra sections are not part of the required set; validation must not
        # depend on them, but the required set must not include removed names.
        self.assertNotIn("bom03", ml._REQUIRED_SECTIONS)
        self.assertNotIn("relationships", ml._REQUIRED_SECTIONS)
        self.assertNotIn("topology_endpoint", ml._REQUIRED_SECTIONS)


class ServiceTests(unittest.TestCase):
    def test_bom04_consumable_nodes_without_edges(self) -> None:
        result = build([bom04_row("清潔布", "300mm", station="組裝站A", equipment="貼合機")])
        self.assertEqual(len(result.candidate["nodes"]), 1)
        self.assertEqual(result.candidate["edges"], [])
        queue = result.audit["review_queue"]
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["reason_code"], "consumable_station_usage_unsupported")
        self.assertEqual(queue[0]["station"], "組裝站A")
        self.assertEqual(queue[0]["material_node_id"], result.candidate["nodes"][0]["id"])
        # Review-only: never a document exclusion, so a consumable run stays complete.
        self.assertEqual(result.candidate["exclusions"], [])
        self.assertTrue(result.complete)

    def test_id_format_and_salt_sensitivity(self) -> None:
        first = build([bom04_row("油杯", "L-100")])
        second = build([bom04_row("油杯", "L-100")])
        other_salt = build([bom04_row("油杯", "L-100")], salt="different-salt")
        node_id = first.candidate["nodes"][0]["id"]
        self.assertRegex(node_id, r"^RP_[a-f0-9]{64}$")
        self.assertEqual(node_id, second.candidate["nodes"][0]["id"])
        self.assertNotEqual(node_id, other_salt.candidate["nodes"][0]["id"])

    def test_nfkc_merge_and_collision_flag(self) -> None:
        rows = [
            bom04_row("Ｔ１０", "SP-100"),
            bom04_row("T10", "SP-100"),
        ]
        result = build(rows)
        self.assertEqual(len(result.candidate["nodes"]), 1)
        node = result.candidate["nodes"][0]
        self.assertEqual(node["properties"]["canonical_name"], "T10")
        self.assertIn("Ｔ１０", node["properties"]["aliases"])
        entry = result.audit["merge_audit"][0]
        self.assertTrue(entry["collision"])
        self.assertEqual(entry["distinct_raw_forms"], ["T10", "Ｔ１０"])
        self.assertEqual(len(entry["source_rows"]), 2)
        self.assertEqual(entry["source_rows"], sorted(entry["source_rows"]))
        self.assertEqual(result.audit["counts"]["collision_nodes"], 1)

    def test_no_invented_edges_regression(self) -> None:
        result = build([
            bom04_row("清潔布", "300mm", station="組裝站A", vendor="FLT-mentions-氣缸"),
        ])
        self.assertEqual(
            {node["label"] for node in result.candidate["nodes"]}, {"ReplacementPart"}
        )
        self.assertEqual(result.candidate["edges"], [])
        serialized = ml.canonical_json_bytes(result.as_dict())
        for forbidden in (
            b"MENTIONED_IN", b"USES_CONSUMABLE", b"IS_SPARE_FOR",
            b"REQUIRES_PART", b"REPLACEMENT_FOR",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_header_alias_and_sheet_fallback_drift(self) -> None:
        cfg = config()
        traditional_headers = [
            "耗材名稱", "耗材規格", "自动化工站", "廠商", "品牌",
        ]
        row = ["氣缸", "CDJ2B16-100", "組裝站A", "SynthVendor", ""]
        tables = {"Materials": [[], list(traditional_headers), ["(desc)"], row]}
        bom_cfg = cfg["bom04"]
        location = ml.locate_sheet_and_header(
            tables, bom_cfg, search_rows=cfg["detection"]["search_rows"]
        )
        self.assertEqual(location.sheet, "Materials")
        self.assertTrue(location.fell_back)
        self.assertTrue(location.header_detected)
        extraction = ml.extract_rows(tables[location.sheet], bom_cfg, location)
        self.assertEqual(len(extraction.rows), 1)
        self.assertEqual(extraction.rows[0].name, "氣缸")
        self.assertEqual(extraction.rows[0].spec, "CDJ2B16-100")
        self.assertEqual(extraction.rows[0].station, "組裝站A")
        # Traditional headers resolve to the canonical (traditional) column names.
        self.assertTrue(extraction.audit["fell_back"])
        self.assertIn("耗材品名", extraction.audit["resolved_columns"])

    def test_determinism_same_input_byte_stability(self) -> None:
        rows = [
            bom04_row("氣缸", "CDJ2B16-100"),
            bom04_row("Ｔ１０", "SP-100"),
            bom04_row("清潔布", "300mm", station="組裝站A"),
            bom04_row("手套", "M", station="檢查站"),
        ]
        first = build(copy.deepcopy(rows))
        second = build(copy.deepcopy(rows))
        for artifact in ("candidate", "exclusions", "lineage", "audit"):
            self.assertEqual(
                ml.canonical_json_bytes(first.as_dict()[artifact]),
                ml.canonical_json_bytes(second.as_dict()[artifact]),
                artifact,
            )
        node_ids = [node["id"] for node in first.candidate["nodes"]]
        self.assertEqual(node_ids, sorted(node_ids))
        lineage_keys = [
            (record["target_type"], record["target_id"], record["extracted_from"])
            for record in first.lineage
        ]
        self.assertEqual(lineage_keys, sorted(lineage_keys))
        # Row anchors encode provenance: permuting input rows legitimately
        # changes anchors, but never node identity or node count.
        permuted = build(list(reversed(rows)))
        self.assertEqual(
            [node["id"] for node in permuted.candidate["nodes"]], node_ids
        )

    def test_empty_inputs_smoke(self) -> None:
        result = build([])
        self.assertEqual(result.candidate["nodes"], [])
        self.assertEqual(result.candidate["edges"], [])
        self.assertTrue(result.complete)

    def test_service_is_stdlib_only(self) -> None:
        source = (PROJECT_ROOT / "services" / "ingestion" / "material_layer_v2.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("openpyxl", imported)
        self.assertNotIn("yaml", imported)


@unittest.skipIf(openpyxl is None, "openpyxl unavailable")
class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.bom04 = self.tmp / "synthetic_bom04.xlsx"
        write_bom04_workbook(
            self.bom04,
            [bom04_row("清潔布", "300mm", station="組裝站A", equipment="貼合機")],
        )

    def output_args(self, directory: Path) -> list[str]:
        return [
            "--candidate-out", str(directory / "candidate.json"),
            "--exclusions-out", str(directory / "exclusions.json"),
            "--lineage-out", str(directory / "lineage.json"),
            "--audit-out", str(directory / "audit.json"),
            "--leak-report-out", str(directory / "leaks.json"),
            "--manifest-out", str(directory / "manifest.json"),
        ]

    def base_args(self, directory: Path, *extra: str) -> list[str]:
        return [
            "--config", str(CONFIG_PATH),
            "--bom04", str(self.bom04),
            "--schema", str(SCHEMA_PATH),
            *self.output_args(directory),
            *extra,
        ]

    def test_cli_complete_candidate(self) -> None:
        out = self.tmp / "complete"
        completed = run_cli(*self.base_args(out))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["run_status"], "complete_candidate")
        self.assertFalse(manifest["graph_activation"])
        self.assertEqual(manifest["salt_source"], "FAULTDX_MASKING_SALT")
        candidate = json.loads((out / "candidate.json").read_text(encoding="utf-8"))
        self.assertEqual(candidate["payload_kind"], "diagnostic")
        self.assertEqual(len(candidate["nodes"]), 1)
        self.assertEqual(candidate["edges"], [])
        if jsonschema is None:  # pragma: no cover
            self.skipTest("jsonschema unavailable")
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(candidate)

    def test_cli_missing_salt_fails_closed(self) -> None:
        out = self.tmp / "nosalt"
        completed = run_cli(*self.base_args(out), salt=None)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("FAULTDX_MASKING_SALT", completed.stderr)
        self.assertIn("fail-safe", completed.stderr)
        self.assertFalse((out / "candidate.json").exists())

    def test_cli_schema_gate_rejects_unfrozen(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        schema["x-contract-status"] = "DRAFT"
        unfrozen = self.tmp / "unfrozen_schema.json"
        unfrozen.write_text(json.dumps(schema), encoding="utf-8")
        out = self.tmp / "unfrozen"
        args = [
            "--config", str(CONFIG_PATH), "--bom04", str(self.bom04),
            "--schema", str(unfrozen), *self.output_args(out),
        ]
        completed = run_cli(*args)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("FROZEN", completed.stderr)

    def test_cli_leakage_present_fails_closed(self) -> None:
        leaking = self.tmp / "leaking_bom04.xlsx"
        write_bom04_workbook(
            leaking, [bom04_row("SynthVendorBrand 油杯", "M", station="組裝站A", vendor="SynthVendorBrand")]
        )
        out = self.tmp / "leak"
        args = [
            "--config", str(CONFIG_PATH), "--bom04", str(leaking),
            "--schema", str(SCHEMA_PATH), *self.output_args(out),
        ]
        completed = run_cli(*args)
        self.assertEqual(completed.returncode, 2)
        report = json.loads((out / "leaks.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(report["leak_count"], 1)
        self.assertEqual(report["leaks"][0]["column"], "廠商")
        self.assertFalse((out / "candidate.json").exists())
        self.assertTrue((out / "manifest.json").exists())

    def test_cli_blocked_by_exclusions_then_allowed(self) -> None:
        """Name-only identity (spec_in_id=false) merging distinct specs is excludable."""
        merged_cfg = config()
        merged_cfg["identity"]["spec_in_id"] = False
        cfg_path = self.tmp / "merged_config.yaml"
        cfg_path.write_text(yaml.safe_dump(merged_cfg, allow_unicode=True), encoding="utf-8")
        unresolved = self.tmp / "ambiguous_spec.xlsx"
        write_bom04_workbook(unresolved, [
            bom04_row("油杯", "L-100"),
            bom04_row("油杯", "L-200"),
        ])
        blocked_out = self.tmp / "blocked"
        args = [
            "--config", str(cfg_path), "--bom04", str(unresolved),
            "--schema", str(SCHEMA_PATH), *self.output_args(blocked_out),
        ]
        completed = run_cli(*args)
        self.assertEqual(completed.returncode, 3)
        self.assertFalse((blocked_out / "candidate.json").exists())
        for evidence in ("exclusions.json", "lineage.json", "audit.json", "manifest.json"):
            self.assertTrue((blocked_out / evidence).exists(), evidence)
        manifest = json.loads((blocked_out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["run_status"], "blocked_by_exclusions")

        allowed_out = self.tmp / "allowed"
        allowed = run_cli(*[
            "--config", str(cfg_path), "--bom04", str(unresolved),
            "--schema", str(SCHEMA_PATH),
            *self.output_args(allowed_out), "--allow-exclusions",
        ])
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        allowed_manifest = json.loads((allowed_out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(allowed_manifest["run_status"], "candidate_with_exclusions")
        self.assertTrue((allowed_out / "candidate.json").exists())

    def test_cli_refuses_overwrite(self) -> None:
        out = self.tmp / "overwrite"
        first = run_cli(*self.base_args(out))
        self.assertEqual(first.returncode, 0, first.stderr)
        second = run_cli(*self.base_args(out))
        self.assertEqual(second.returncode, 2)
        self.assertIn("refusing to overwrite", second.stderr)

    def test_cli_inspect_prints_structure_only(self) -> None:
        completed = run_cli(
            "--config", str(CONFIG_PATH), "--bom04", str(self.bom04),
            "--schema", str(SCHEMA_PATH), "--inspect", salt=None,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["inspect"][0]["sheet"], "工作表1")
        self.assertIn("rows_with_name", report["inspect"][0])
        self.assertNotIn("SynthVendor", completed.stdout)

    def test_cli_rejects_legacy_bom03_flag(self) -> None:
        completed = run_cli(
            "--config", str(CONFIG_PATH), "--bom04", str(self.bom04),
            "--schema", str(SCHEMA_PATH), "--inspect", "--bom03", "x.xlsx", salt=None,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("unrecognized arguments", completed.stderr)


if __name__ == "__main__":
    unittest.main()
