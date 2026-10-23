from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import scripts.cli_route_abc as cli_route_abc
from services.eval.route_abc_cli_contract import (
    DEFAULT_JSON_OUTPUT_PATH,
    FIXTURE_PATHS,
    MANIFEST_PATH,
    QUERY_BANK_PATHS,
    ROUTE_TO_QUERY_BANK,
    load_manifest,
    route_default_sources,
)

CLI = REPO_ROOT / "scripts" / "cli_route_abc.py"
QUERY_BANKS = {
    "route_b": REPO_ROOT / "data" / "eval" / "route_b" / "route_b_query_bank_v1.json",
    "route_c": REPO_ROOT / "data" / "eval" / "route_c" / "route_c_query_bank_v1.json",
}
FIXTURES = {
    "route_b": REPO_ROOT / "data" / "eval" / "route_b" / "route_b_serving_safe_fixtures_v1.json",
    "route_c": REPO_ROOT / "data" / "eval" / "route_c" / "route_c_serving_safe_fixtures_v1.json",
}


class RouteBCQueryBankCliTests(unittest.TestCase):
    def test_cli_contract_manifest_keeps_current_eval_paths_stable(self) -> None:
        manifest = load_manifest()

        self.assertEqual(MANIFEST_PATH, REPO_ROOT / "configs" / "route_abc_cli_contract_v1.json")
        self.assertEqual(DEFAULT_JSON_OUTPUT_PATH, REPO_ROOT / "synthesis_out_abc.json")
        self.assertEqual(FIXTURE_PATHS, FIXTURES)
        self.assertEqual(QUERY_BANK_PATHS, QUERY_BANKS)
        self.assertEqual(ROUTE_TO_QUERY_BANK, {"b": "route_b", "c": "route_c"})
        self.assertEqual(route_default_sources("a"), ("reviewed_diagnostic_chain_v1",))
        self.assertEqual(manifest["routes"]["a"]["execution"], "full_route_graph")
        self.assertEqual(manifest["eval_directory_migration"]["status"], "route_b_route_c_completed")
        for path in [*FIXTURE_PATHS.values(), *QUERY_BANK_PATHS.values()]:
            self.assertTrue(path.exists(), str(path))

    def test_query_banks_parse_and_reference_serving_safe_fixtures(self) -> None:
        for bank_name, path in QUERY_BANKS.items():
            payload = _load_json(path)
            fixture_payload = _load_json(FIXTURES[bank_name])
            fixture_ids = {item["fixture_id"] for item in fixture_payload["fixtures"]}
            allowed_sources = set(payload["source_safety_notes"]["allowed_runtime_sources"])

            self.assertEqual(
                payload["version_info"]["source_fixtures"],
                [str(FIXTURES[bank_name].relative_to(REPO_ROOT)).replace("\\", "/")],
            )
            self.assertGreaterEqual(len(payload["queries"]), 5)
            for query in payload["queries"]:
                self.assertEqual(query["fixture"], bank_name)
                self.assertIn(query["fixture_id"], fixture_ids)
                self.assertTrue(set(query["available_sources"]).issubset(allowed_sources))
                if bank_name == "route_b":
                    self.assertEqual(query["route"], "b")
                    self.assertEqual(query["expected"]["answer_type"], "document_evidence")
                    self.assertEqual(query["expected"]["status"], "evidence_only")
                else:
                    self.assertEqual(query["route"], "c")
                    self.assertEqual(query["expected"]["answer_type"], "case_reference")
                    self.assertEqual(query["expected"]["status"], "candidate")

    def test_cli_stub_runs_route_b_and_route_c_query_bank_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            route_b = _run_cli("b", "RB-QB-001", Path(tmp) / "route_b.json")
            route_c = _run_cli("c", "RC-QB-001", Path(tmp) / "route_c.json")

        self.assertEqual(route_b["decision"]["answer_type"], "document_evidence")
        self.assertEqual(route_b["decision"]["status"], "evidence_only")
        self.assertEqual(route_b["diagnosis_results"][0]["result_type"], "document_evidence")
        self.assertEqual(route_b["diagnosis_results"][0]["status"], "evidence_only")
        _assert_not_promoted(self, route_b)

        self.assertEqual(route_c["decision"]["answer_type"], "case_reference")
        self.assertEqual(route_c["decision"]["status"], "candidate")
        self.assertEqual(route_c["diagnosis_results"][0]["result_type"], "case_reference")
        self.assertEqual(route_c["diagnosis_results"][0]["status"], "candidate")
        _assert_not_promoted(self, route_c)

    def test_cli_stub_no_hit_query_bank_cases_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            route_b = _run_cli("b", "RB-QB-002", Path(tmp) / "route_b_no_hit.json")
            route_c = _run_cli("c", "RC-QB-002", Path(tmp) / "route_c_no_hit.json")

        self.assertEqual(route_b["decision"]["answer_type"], "document_evidence")
        self.assertEqual(route_b["decision"]["status"], "evidence_only")
        self.assertEqual(route_b["diagnosis_results"], [])
        _assert_not_promoted(self, route_b)

        self.assertEqual(route_c["decision"]["answer_type"], "case_reference")
        self.assertEqual(route_c["decision"]["status"], "candidate")
        self.assertEqual(route_c["diagnosis_results"], [])
        _assert_not_promoted(self, route_c)

    def test_cli_can_list_query_bank(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CLI), "--list-query-bank", "route_b"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertIn("RB-QB-001", completed.stdout)
        self.assertIn("RB-QB-005", completed.stdout)

    def test_cli_can_render_answer_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            answer_path = Path(tmp) / "route_b_answer.txt"
            json_path = Path(tmp) / "route_b.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--route",
                    "b",
                    "--query-id",
                    "RB-QB-001",
                    "--provider",
                    "stub",
                    "--render-only",
                    "--answer-out",
                    str(answer_path),
                    "--out",
                    str(json_path),
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            rendered = answer_path.read_text(encoding="utf-8")
            self.assertIn("FaultDx Route ABC 答案", completed.stdout)
            self.assertIn("document_evidence / evidence_only", rendered)
            self.assertNotIn('"contract_version"', completed.stdout)
            self.assertEqual(_load_json(json_path)["decision"]["status"], "evidence_only")

    def test_route_a_manual_query_uses_full_route_graph(self) -> None:
        expected = {
            "contract_version": "1.0.0-draft",
            "decision": {
                "route_family": "route_a_structured",
                "route": "reviewed_diagnostic_chain",
                "answer_type": "confirmed_diagnosis",
                "status": "reviewed",
                "requires_review": False,
            },
        }
        provider = _StubProvider()

        with patch.object(cli_route_abc, "run_route_graph", return_value={"api_response": expected}) as full_run:
            with patch.object(cli_route_abc, "run_route_graph_dry_run") as dry_run:
                result = cli_route_abc._run_route("a", "Route A smoke", provider)

        self.assertEqual(result, expected)
        full_run.assert_called_once()
        dry_run.assert_not_called()
        request = full_run.call_args.args[0]
        self.assertEqual(request["query_text"], "Route A smoke")
        self.assertEqual(request["available_sources"], ["reviewed_diagnostic_chain_v1"])
        self.assertIs(request["_provider"], provider)


def _run_cli(route: str, query_id: str, out_path: Path) -> dict[str, Any]:
    subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--route",
            route,
            "--query-id",
            query_id,
            "--provider",
            "stub",
            "--out",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return _load_json(out_path)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_not_promoted(testcase: unittest.TestCase, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    testcase.assertNotIn("confirmed_diagnosis", text)
    testcase.assertNotIn('"status": "reviewed"', text)


class _StubProvider:
    provider_type = "stub"


if __name__ == "__main__":
    unittest.main()
