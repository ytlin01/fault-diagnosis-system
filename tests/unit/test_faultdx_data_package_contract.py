import copy
import hashlib
import json
from pathlib import Path
import unittest

from services.ingestion.dekg_legacy_adapter import adapt_dekg_legacy_document
from services.ingestion.fhkb_legacy_adapter import adapt_fhkb_legacy_records

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - dependency availability is environment-specific
    Draft202012Validator = None


_ROOT = Path(__file__).resolve().parents[2]
_CONTRACT_PATH = _ROOT / "contracts/package/faultdx_data_package_v1.json"
_SCHEMA_PATH = _ROOT / "contracts/package/faultdx_data_package_v1.schema.json"


class PackageValidationError(ValueError):
    pass


def _load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _canonical_bytes(value) -> bytes:
    """Test-local canonical JSON bytes.

    Deterministic for the synthetic fixtures, but deliberately NOT the RFC 8785
    JSON Canonicalization Scheme required by the frozen contract: this uses
    Python ``json.dumps`` (sort_keys + compact separators), which does not
    implement RFC 8785 number/Unicode normalization. The fixed
    ``package_id`` vector in ``test_package_identity_has_a_fixed_vector`` and
    every identity fixture in this module are bound to THIS canonicalizer; they
    will change when a conforming RFC 8785 canonicalizer is adopted (Task 014
    affected-consumer implementation condition #1).
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _package_id(package: dict) -> str:
    identity = [
        package["manifest_version"],
        package["knowledge_asset"],
        package["package_type"],
        package["release_id"],
        package["source"]["source_id"],
        package["source"]["source_version"],
        package["record_contract"]["contract_id"],
    ]
    return "PKG_" + hashlib.sha256(_canonical_bytes(identity)).hexdigest()


def _artifact_id(role: str, relative_path: str) -> str:
    return "ART_" + hashlib.sha256(
        _canonical_bytes([role, relative_path])
    ).hexdigest()


def _content_digest(package: dict) -> str:
    projection = copy.deepcopy(package)
    projection.pop("content_digest", None)
    return _sha256(_canonical_bytes(projection))


def _is_portable_path(value: str) -> bool:
    if not value or "\\" in value or "//" in value:
        return False
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        return False
    parts = value.split("/")
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


_PROFILES = {
    "TPDX": {
        "route": "route_a_structured",
        "contract": "tpdx_kg_schema_v4_2",
        "types": {
            "tpdx_topology_component",
            "tpdx_diagnostic_component",
            "tpdx_replacement_material_component",
            "tpdx_release",
        },
        "semantics": "reviewed_structured_fact",
        "promotion_allowed": True,
    },
    "DEKG": {
        "route": "route_b_document",
        "contract": "dekg_evidence_v2",
        "types": {"dekg_evidence"},
        "semantics": "evidence_only",
        "promotion_allowed": False,
    },
    "FHKB": {
        "route": "route_c_case",
        "contract": "fhkb_case_v1",
        "types": {"fhkb_case"},
        "semantics": "candidate",
        "promotion_allowed": False,
    },
}


def _validate_package(
    package: dict,
    *,
    artifact_bytes: dict[str, bytes],
    masking_manifest_bytes: dict[str, bytes],
    component_registry: dict[str, dict] | None = None,
    known_package_digests: dict[str, str] | None = None,
) -> None:
    profile = _PROFILES.get(package.get("knowledge_asset"))
    if profile is None:
        raise PackageValidationError("unknown knowledge asset")
    if package.get("route_family") != profile["route"]:
        raise PackageValidationError("route/asset mismatch")
    if package.get("package_type") not in profile["types"]:
        raise PackageValidationError("mixed or invalid package type")
    if package.get("record_contract", {}).get("contract_id") != profile["contract"]:
        raise PackageValidationError("route/contract mismatch")
    route_policy = package.get("route_policy", {})
    if route_policy.get("content_semantics") != profile["semantics"]:
        raise PackageValidationError("route semantics mismatch")
    if route_policy.get("promotion_allowed") is not profile["promotion_allowed"]:
        raise PackageValidationError("unsafe promotion policy")
    if package["knowledge_asset"] == "DEKG" and route_policy.get(
        "independent_corroboration"
    ) is not False:
        raise PackageValidationError("DEKG co-source evidence is not corroboration")

    expected_package_id = _package_id(package)
    if package.get("package_id") != expected_package_id:
        raise PackageValidationError("package_id does not match identity tuple")

    lineage = package.get("lineage", {})
    source_manifest_path = lineage.get("source_manifest_path", "")
    if not _is_portable_path(source_manifest_path):
        raise PackageValidationError("source manifest path is not portable")
    source_manifest = artifact_bytes.get(source_manifest_path)
    if source_manifest is None:
        raise PackageValidationError("missing source manifest")
    if lineage.get("source_manifest_digest") != _sha256(source_manifest):
        raise PackageValidationError("source manifest digest mismatch")

    artifacts = package.get("artifacts", [])
    artifact_ids: set[str] = set()
    artifact_paths: set[str] = set()
    payload_count = 0
    for artifact in artifacts:
        path = artifact.get("relative_path", "")
        if not _is_portable_path(path):
            raise PackageValidationError("artifact path is not portable")
        expected_artifact_id = _artifact_id(artifact["artifact_role"], path)
        if artifact.get("artifact_id") != expected_artifact_id:
            raise PackageValidationError("artifact_id does not match role/path")
        if artifact["artifact_id"] in artifact_ids or path in artifact_paths:
            raise PackageValidationError("duplicate artifact identity or path")
        artifact_ids.add(artifact["artifact_id"])
        artifact_paths.add(path)
        if artifact["artifact_role"] == "record_payload":
            payload_count += 1
        content = artifact_bytes.get(path)
        if content is None:
            raise PackageValidationError("missing artifact")
        if artifact.get("byte_size") != len(content):
            raise PackageValidationError("artifact byte_size mismatch")
        if artifact.get("sha256") != _sha256(content):
            raise PackageValidationError("artifact digest mismatch")

    is_release = package["package_type"] == "tpdx_release"
    if payload_count != (0 if is_release else 1):
        raise PackageValidationError("invalid record_payload count")

    effective_coverage: dict[str, int] = {}
    effective_masking_statuses: dict[str, list[str]] = {}
    effective_masking_reviewed = True
    for masking_ref in package.get("masking_evidence", []):
        path = masking_ref.get("manifest_path", "")
        if not _is_portable_path(path):
            raise PackageValidationError("masking manifest path is not portable")
        content = masking_manifest_bytes.get(path)
        if content is None:
            raise PackageValidationError("missing masking manifest")
        if masking_ref.get("manifest_digest") != _sha256(content):
            raise PackageValidationError("masking manifest digest mismatch")
        for artifact_id in masking_ref.get("covered_artifact_ids", []):
            if artifact_id not in artifact_ids:
                raise PackageValidationError("masking reference names unknown artifact")
            if masking_ref.get("effective"):
                effective_coverage[artifact_id] = effective_coverage.get(artifact_id, 0) + 1
                effective_masking_statuses.setdefault(artifact_id, []).append(
                    masking_ref.get("masking_status")
                )
        if masking_ref.get("effective") and (
            masking_ref.get("masking_status") not in {"reviewed_masked", "not_required"}
            or masking_ref.get("review_status") not in {"reviewed", "not_required"}
        ):
            effective_masking_reviewed = False

    for artifact in artifacts:
        coverage_count = effective_coverage.get(artifact["artifact_id"], 0)
        if artifact["requires_masking"] and coverage_count != 1:
            raise PackageValidationError("masking coverage must be exactly one")
        if artifact["requires_masking"] and effective_masking_statuses.get(
            artifact["artifact_id"]
        ) not in [["masked"], ["reviewed_masked"]]:
            raise PackageValidationError("masking-required artifact is not masked")
        if coverage_count > 1:
            raise PackageValidationError("overlapping masking coverage")

    decision = package.get("decision", {})
    if decision.get("serving_safe") and (
        decision.get("review_status") != "reviewed" or not effective_masking_reviewed
    ):
        raise PackageValidationError("serving-safe claim lacks review evidence")
    if package["knowledge_asset"] != "TPDX" and decision.get(
        "promotion_status"
    ) != "not_applicable":
        raise PackageValidationError("Route B/C promotion is forbidden")
    if decision.get("package_status") == "released":
        if not (
            decision.get("review_status") == "reviewed"
            and decision.get("serving_safe") is True
            and decision.get("route_eligible") is True
            and decision.get("release_decision_id")
        ):
            raise PackageValidationError("released claim lacks required evidence")
        if package["knowledge_asset"] == "TPDX" and decision.get(
            "promotion_status"
        ) != "reviewed":
            raise PackageValidationError("released TPDX package is not promoted")

    component_refs = package.get("component_refs", [])
    if not is_release and component_refs:
        raise PackageValidationError("only a TPDX release may reference components")
    if is_release:
        if not component_refs:
            raise PackageValidationError("TPDX release has no components")
        registry = component_registry or {}
        visited: set[str] = set()

        def visit(package_id: str, ancestors: set[str]) -> None:
            if package_id in ancestors:
                raise PackageValidationError("circular component dependency")
            if package_id in visited:
                return
            component = registry.get(package_id)
            if component is None:
                raise PackageValidationError("missing component package")
            visited.add(package_id)
            for child in component.get("component_refs", []):
                visit(child["package_id"], ancestors | {package_id})

        seen_components: set[str] = set()
        seen_component_types: set[str] = set()
        for component_ref in component_refs:
            component_id = component_ref["package_id"]
            if component_id == package["package_id"]:
                raise PackageValidationError("self-referential component")
            if component_id in seen_components:
                raise PackageValidationError("duplicate component reference")
            seen_components.add(component_id)
            component_type = component_ref["package_type"]
            if component_type in seen_component_types:
                raise PackageValidationError("duplicate component type")
            seen_component_types.add(component_type)
            component = registry.get(component_id)
            if component is None:
                raise PackageValidationError("missing component package")
            if component_ref.get("acceptance_status") != "accepted":
                raise PackageValidationError("unaccepted component reference")
            if component.get("decision", {}).get("package_status") != "accepted":
                raise PackageValidationError("component package is not accepted")
            if component.get("release_id") != package["release_id"]:
                raise PackageValidationError("component release mismatch")
            if component.get("record_contract", {}).get(
                "contract_id"
            ) != "tpdx_kg_schema_v4_2":
                raise PackageValidationError("component contract mismatch")
            if component_ref.get("package_type") != component.get("package_type"):
                raise PackageValidationError("component type mismatch")
            if component_ref.get("manifest_digest") != component.get("content_digest"):
                raise PackageValidationError("component manifest digest mismatch")
            visit(component_id, {package["package_id"]})

    expected_content_digest = _content_digest(package)
    if package.get("content_digest") != expected_content_digest:
        raise PackageValidationError("package content digest mismatch")
    known_digest = (known_package_digests or {}).get(package["package_id"])
    if known_digest is not None and known_digest != package["content_digest"]:
        raise PackageValidationError("package identity collision")


def _validate_route_payload_binding(package: dict, payload: dict) -> None:
    """Validate fields duplicated by the common and frozen route envelopes."""
    if package["knowledge_asset"] not in {"DEKG", "FHKB"}:
        return

    expected = {
        "release_id": package["release_id"],
        "source_id": package["source"]["source_id"],
        "source_version": package["source"]["source_version"],
        "manifest_digest": package["lineage"]["source_manifest_digest"],
        "lineage_ref": package["lineage"]["lineage_ref"],
        "serving_safe": package["decision"]["serving_safe"],
    }
    for field, expected_value in expected.items():
        if payload.get(field) != expected_value:
            raise PackageValidationError(
                f"route payload {field} does not match package envelope"
            )

    record_artifact_ids = {
        artifact["artifact_id"]
        for artifact in package["artifacts"]
        if artifact["artifact_role"] == "record_payload"
    }
    effective_statuses = {
        masking_ref["masking_status"]
        for masking_ref in package["masking_evidence"]
        if masking_ref["effective"]
        and record_artifact_ids.intersection(masking_ref["covered_artifact_ids"])
    }
    payload_status = payload.get("masking_status")
    compatible_statuses = {
        "masked": {"masked", "reviewed_masked"},
        "reviewed_masked": {"reviewed_masked"},
        "not_required": {"not_required"},
    }
    allowed_statuses = compatible_statuses.get(payload_status, set())
    if not effective_statuses or not effective_statuses.issubset(allowed_statuses):
        raise PackageValidationError(
            "route payload masking_status does not match effective package evidence"
        )


def _artifact(role: str, path: str, content: bytes, *, masking: bool) -> dict:
    return {
        "artifact_id": _artifact_id(role, path),
        "artifact_role": role,
        "relative_path": path,
        "media_type": "application/json",
        "sha256": _sha256(content),
        "byte_size": len(content),
        "record_count": 1 if role in {"record_payload", "exclusions", "review_queue"} else None,
        "requires_masking": masking,
    }


def _seal(package: dict) -> dict:
    package["package_id"] = _package_id(package)
    package["content_digest"] = _content_digest(package)
    return package


def _package(asset: str, *, package_type: str | None = None) -> tuple[dict, dict, dict]:
    profiles = {
        "TPDX": (
            "route_a_structured",
            package_type or "tpdx_diagnostic_component",
            "tpdx_kg_schema_v4_2",
            "contracts/schema/tpdx_kg_schema_v4_2.schema.json",
            "reviewed_structured_fact",
            True,
        ),
        "DEKG": (
            "route_b_document",
            "dekg_evidence",
            "dekg_evidence_v2",
            "contracts/evidence/dekg_evidence_v2.schema.json",
            "evidence_only",
            False,
        ),
        "FHKB": (
            "route_c_case",
            "fhkb_case",
            "fhkb_case_v1",
            "contracts/case/fhkb_case_v1.schema.json",
            "candidate",
            False,
        ),
    }
    route, resolved_type, contract, schema_path, semantics, promotion = profiles[asset]
    payload = b'{"synthetic":true}'
    masking_manifest = b'{"run_id":"maskrun-synthetic-1"}'
    source_manifest = b'{"manifest":"synthetic-source-v1"}'
    artifacts: list[dict] = []
    artifact_files: dict[str, bytes] = {}
    masking_refs: list[dict] = []
    if resolved_type == "tpdx_release":
        path = "reports/component-index.json"
        artifacts.append(_artifact("component_index", path, payload, masking=False))
        artifact_files[path] = payload
    else:
        path = "payload/records.json"
        record_artifact = _artifact("record_payload", path, payload, masking=True)
        artifacts.append(record_artifact)
        artifact_files[path] = payload
        masking_refs.append(
            {
                "run_id": "maskrun-synthetic-1",
                "manifest_path": "evidence/masking.json",
                "manifest_digest": _sha256(masking_manifest),
                "covered_artifact_ids": [record_artifact["artifact_id"]],
                "masking_status": "reviewed_masked",
                "review_status": "reviewed",
                "effective": True,
            }
        )
    package = {
        "manifest_version": "faultdx_data_package_v1",
        "package_id": "PKG_" + "0" * 64,
        "content_digest": "sha256:" + "0" * 64,
        "release_id": "synthetic-release-v1",
        "knowledge_asset": asset,
        "route_family": route,
        "package_type": resolved_type,
        "record_contract": {
            "contract_id": contract,
            "schema_path": schema_path,
            "contract_digest": "sha256:" + "1" * 64,
        },
        "source": {
            "source_id": f"synthetic-{asset.lower()}",
            "source_version": "v1",
        },
        "lineage": {
            "lineage_ref": "lineage:synthetic-v1",
            "source_manifest_path": "lineage/source-manifest.json",
            "source_manifest_digest": _sha256(source_manifest),
            "parent_package_ids": [],
        },
        "producer": {
            "name": "synthetic-contract-test",
            "version": "1",
            "code_revision": "synthetic-revision",
        },
        "artifacts": artifacts,
        "masking_evidence": masking_refs,
        "component_refs": [],
        "route_policy": {
            "content_semantics": semantics,
            "promotion_allowed": promotion,
            "independent_corroboration": False,
        },
        "decision": {
            "package_status": "accepted",
            "review_status": "reviewed",
            "serving_safe": True,
            "route_eligible": True,
            "promotion_status": "reviewed" if asset == "TPDX" else "not_applicable",
            "promotion_decision_id": "promotion:synthetic" if asset == "TPDX" else None,
            "release_decision_id": None,
        },
    }
    artifact_files["lineage/source-manifest.json"] = source_manifest
    return _seal(package), artifact_files, {"evidence/masking.json": masking_manifest}


class FaultDxDataPackageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load(_CONTRACT_PATH)
        cls.schema = _load(_SCHEMA_PATH)
        cls.validator = (
            Draft202012Validator(cls.schema) if Draft202012Validator else None
        )

    def assert_semantic_failure(self, package, artifact_files, masking_files, text, **kwargs):
        with self.assertRaises(PackageValidationError) as raised:
            _validate_package(
                package,
                artifact_bytes=artifact_files,
                masking_manifest_bytes=masking_files,
                **kwargs,
            )
        self.assertIn(text, str(raised.exception))

    def test_contract_is_frozen_and_selects_schema_4_2(self) -> None:
        self.assertEqual(self.contract["status"], "FROZEN")
        self.assertEqual(self.contract["version"], "1.0.0")
        self.assertEqual(
            self.contract["package_profiles"]["TPDX"]["record_contract_id"],
            "tpdx_kg_schema_v4_2",
        )
        self.assertEqual(
            self.contract["compatibility"]["TPDX"]["schema_4_1_role"],
            "rollback_and_comparison_only",
        )

    def test_all_package_profiles_have_distinct_route_contract_bindings(self) -> None:
        profiles = self.contract["package_profiles"]
        self.assertEqual(set(profiles), {"TPDX", "DEKG", "FHKB"})
        self.assertEqual(
            {profile["route_family"] for profile in profiles.values()},
            {"route_a_structured", "route_b_document", "route_c_case"},
        )
        self.assertEqual(
            {profile["record_contract_id"] for profile in profiles.values()},
            {"tpdx_kg_schema_v4_2", "dekg_evidence_v2", "fhkb_case_v1"},
        )
        # The frozen contract must reference governed contract artifacts, not
        # task packages or ad-hoc paths: every profile schema path is
        # structural and must resolve to an existing file under contracts/.
        for asset, profile in profiles.items():
            with self.subTest(asset=asset):
                schema_path = _ROOT / profile["record_contract_schema"]
                self.assertTrue(
                    schema_path.is_file(),
                    f"governed contract schema missing: {schema_path}",
                )
                schema_id = _load(schema_path).get("$id", "")
                self.assertTrue(
                    schema_id.startswith(profile["record_contract_id"]),
                    f"profile contract $id {schema_id!r} does not match "
                    f"record_contract_id {profile['record_contract_id']!r}",
                )

    def test_schema_declares_closed_draft_2020_12_contract(self) -> None:
        self.assertEqual(
            self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(
            self.schema["properties"]["manifest_version"]["const"],
            "faultdx_data_package_v1",
        )

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)

    def test_positive_tpdx_dekg_and_fhkb_packages(self) -> None:
        for asset in ("TPDX", "DEKG", "FHKB"):
            with self.subTest(asset=asset):
                package, artifacts, masking = _package(asset)
                if self.validator:
                    self.validator.validate(package)
                _validate_package(
                    package,
                    artifact_bytes=artifacts,
                    masking_manifest_bytes=masking,
                )

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_record_payloads_validate_with_the_selected_route_contracts(self) -> None:
        metadata = {
            "release_id": "synthetic-release-v1",
            "source_id": "synthetic-governed-source",
            "source_version": "v1",
            "manifest_digest": "sha256:" + "a" * 64,
            "lineage_ref": "synthetic-lineage-v1",
            "masking_status": "masked",
        }
        payloads = {
            "TPDX": {
                "schema_version": "4.2",
                "payload_kind": "topology",
                "nodes": [],
                "edges": [],
                "exclusions": [],
            },
            "DEKG": adapt_dekg_legacy_document(
                {
                    "doc_id": "DOC-1",
                    "blocks": [
                        {
                            "block_type": "text",
                            "block_id": "TEXT-1",
                            "anchor": "section-1",
                            "text": "Synthetic serving-safe evidence.",
                            "serving_eligible": True,
                            "retrieval_eligible": True,
                            "language": "en",
                        }
                    ],
                },
                **metadata,
            ),
            "FHKB": adapt_fhkb_legacy_records(
                [
                    {
                        "rag_candidate_id": "RAG-LEGACY-1",
                        "source_type": "field_case_without_standard_fp",
                        "relation_type": "historical_similarity",
                        "route_target": "rag_case_pool",
                        "field_fp_variants": ["Observed trip"],
                        "field_fp_normalized": "normalized trip",
                        "RC": ["candidate cause"],
                        "PA": None,
                        "evidence": {
                            "count": 1,
                            "total_dt_mins": 7.0,
                            "risk_counts": {"medium": 1},
                            "status_counts": {"closed": 1},
                            "qpl_values": ["Q1"],
                            "date_range": {
                                "min": "2026-01-01",
                                "max": "2026-01-01",
                            },
                        },
                        "source_refs": [
                            {
                                "source": "synthetic_downtime",
                                "record_index": 1,
                                "record_number": 2,
                                "record_id_field": "id",
                                "record_id_value": "ROW-1",
                            }
                        ],
                        "filter_basis": {
                            "reason": "synthetic allowlisted candidate",
                            "not_for_kg_text2cypher": True,
                        },
                    }
                ],
                **metadata,
            ),
        }
        schema_paths = {
            "TPDX": "contracts/schema/tpdx_kg_schema_v4_2.schema.json",
            "DEKG": "contracts/evidence/dekg_evidence_v2.schema.json",
            "FHKB": "contracts/case/fhkb_case_v1.schema.json",
        }
        for asset, payload in payloads.items():
            with self.subTest(asset=asset):
                route_schema = _load(_ROOT / schema_paths[asset])
                Draft202012Validator(route_schema).validate(payload)
                package, artifacts, masking = _package(asset)
                payload_path = "payload/records.json"
                payload_bytes = _canonical_bytes(payload)
                artifacts[payload_path] = payload_bytes
                record_artifact = package["artifacts"][0]
                record_artifact["sha256"] = _sha256(payload_bytes)
                record_artifact["byte_size"] = len(payload_bytes)
                record_artifact["record_count"] = len(
                    payload.get("records", payload.get("nodes", []))
                )
                if asset in {"DEKG", "FHKB"}:
                    package["source"]["source_id"] = payload["source_id"]
                    package["source"]["source_version"] = payload["source_version"]
                    package["lineage"]["lineage_ref"] = payload["lineage_ref"]
                    package["lineage"]["source_manifest_digest"] = payload[
                        "manifest_digest"
                    ]
                    artifacts["lineage/source-manifest.json"] = b"synthetic-lineage"
                    package["lineage"]["source_manifest_digest"] = _sha256(
                        artifacts["lineage/source-manifest.json"]
                    )
                    payload["manifest_digest"] = package["lineage"][
                        "source_manifest_digest"
                    ]
                    payload_bytes = _canonical_bytes(payload)
                    artifacts[payload_path] = payload_bytes
                    record_artifact["sha256"] = _sha256(payload_bytes)
                    record_artifact["byte_size"] = len(payload_bytes)
                _seal(package)
                self.validator.validate(package)
                _validate_package(
                    package,
                    artifact_bytes=artifacts,
                    masking_manifest_bytes=masking,
                )
                _validate_route_payload_binding(package, payload)

    def test_route_payload_binding_rejects_envelope_mismatch(self) -> None:
        for asset in ("DEKG", "FHKB"):
            with self.subTest(asset=asset):
                package, _, _ = _package(asset)
                payload = {
                    "release_id": package["release_id"],
                    "source_id": package["source"]["source_id"],
                    "source_version": package["source"]["source_version"],
                    "manifest_digest": package["lineage"]["source_manifest_digest"],
                    "lineage_ref": package["lineage"]["lineage_ref"],
                    "masking_status": "reviewed_masked",
                    "serving_safe": package["decision"]["serving_safe"],
                }
                _validate_route_payload_binding(package, payload)
                for field in (
                    "release_id",
                    "source_id",
                    "source_version",
                    "manifest_digest",
                    "lineage_ref",
                    "serving_safe",
                ):
                    with self.subTest(asset=asset, field=field):
                        conflicting = copy.deepcopy(payload)
                        conflicting[field] = (
                            not payload[field]
                            if isinstance(payload[field], bool)
                            else f"conflicting-{field}"
                        )
                        with self.assertRaisesRegex(
                            PackageValidationError,
                            f"route payload {field} does not match package envelope",
                        ):
                            _validate_route_payload_binding(package, conflicting)

                conflicting_masking = copy.deepcopy(payload)
                conflicting_masking["masking_status"] = "not_required"
                with self.assertRaisesRegex(
                    PackageValidationError,
                    "route payload masking_status does not match effective package evidence",
                ):
                    _validate_route_payload_binding(package, conflicting_masking)

    @unittest.skipUnless(Draft202012Validator, "jsonschema is not installed")
    def test_schema_rejects_unknown_fields_route_mismatch_and_unsafe_release(self) -> None:
        package, _, _ = _package("DEKG")
        package["unknown"] = True
        with self.assertRaises(Exception):
            self.validator.validate(package)

        package, _, _ = _package("DEKG")
        package["route_family"] = "route_a_structured"
        with self.assertRaises(Exception):
            self.validator.validate(package)

        package, _, _ = _package("TPDX")
        package["decision"]["package_status"] = "released"
        package["decision"]["review_status"] = "in_review"
        package["decision"]["release_decision_id"] = None
        with self.assertRaises(Exception):
            self.validator.validate(package)

    def test_tpdx_release_references_accepted_component(self) -> None:
        component, component_files, component_masking = _package("TPDX")
        _validate_package(
            component,
            artifact_bytes=component_files,
            masking_manifest_bytes=component_masking,
        )
        release, artifacts, masking = _package("TPDX", package_type="tpdx_release")
        release["component_refs"] = [
            {
                "package_id": component["package_id"],
                "package_type": component["package_type"],
                "manifest_path": "components/diagnostic/manifest.json",
                "manifest_digest": component["content_digest"],
                "acceptance_status": "accepted",
            }
        ]
        _seal(release)
        if self.validator:
            self.validator.validate(release)
        _validate_package(
            release,
            artifact_bytes=artifacts,
            masking_manifest_bytes=masking,
            component_registry={component["package_id"]: component},
        )

    def test_tpdx_release_rejects_duplicate_component_type(self) -> None:
        first, _, _ = _package("TPDX")
        second, _, _ = _package("TPDX")
        second["source"]["source_version"] = "v2"
        _seal(second)
        release, artifacts, masking = _package("TPDX", package_type="tpdx_release")
        release["component_refs"] = [
            {
                "package_id": component["package_id"],
                "package_type": component["package_type"],
                "manifest_path": f"components/diagnostic/{index}.json",
                "manifest_digest": component["content_digest"],
                "acceptance_status": "accepted",
            }
            for index, component in enumerate((first, second), start=1)
        ]
        _seal(release)
        if self.validator:
            with self.assertRaises(Exception):
                self.validator.validate(release)
        self.assert_semantic_failure(
            release,
            artifacts,
            masking,
            "duplicate component type",
            component_registry={
                first["package_id"]: first,
                second["package_id"]: second,
            },
        )

    def test_mixed_asset_and_route_contract_mismatches_fail(self) -> None:
        package, artifacts, masking = _package("TPDX")
        package["package_type"] = "dekg_evidence"
        self.assert_semantic_failure(
            package, artifacts, masking, "mixed or invalid package type"
        )
        package, artifacts, masking = _package("DEKG")
        package["record_contract"]["contract_id"] = "tpdx_kg_schema_v4_2"
        self.assert_semantic_failure(package, artifacts, masking, "route/contract mismatch")

    def test_unsafe_route_b_promotion_fails(self) -> None:
        package, artifacts, masking = _package("DEKG")
        package["route_policy"]["promotion_allowed"] = True
        self.assert_semantic_failure(package, artifacts, masking, "unsafe promotion policy")

    def test_masking_gap_overlap_and_unknown_artifact_fail(self) -> None:
        package, artifacts, masking = _package("TPDX")
        package["masking_evidence"] = []
        self.assert_semantic_failure(
            package, artifacts, masking, "masking coverage must be exactly one"
        )

        package, artifacts, masking = _package("TPDX")
        package["masking_evidence"].append(copy.deepcopy(package["masking_evidence"][0]))
        self.assert_semantic_failure(
            package, artifacts, masking, "masking coverage must be exactly one"
        )

        package, artifacts, masking = _package("TPDX")
        package["masking_evidence"][0]["covered_artifact_ids"] = ["ART_" + "f" * 64]
        self.assert_semantic_failure(
            package, artifacts, masking, "masking reference names unknown artifact"
        )

        package, artifacts, masking = _package("TPDX")
        package["masking_evidence"][0]["masking_status"] = "not_required"
        package["masking_evidence"][0]["review_status"] = "not_required"
        self.assert_semantic_failure(
            package, artifacts, masking, "masking-required artifact is not masked"
        )

    def test_path_escape_missing_artifact_and_digest_mismatch_fail(self) -> None:
        package, artifacts, masking = _package("FHKB")
        package["artifacts"][0]["relative_path"] = "../outside.json"
        self.assert_semantic_failure(package, artifacts, masking, "path is not portable")

        package, artifacts, masking = _package("FHKB")
        artifacts.pop(package["artifacts"][0]["relative_path"])
        self.assert_semantic_failure(package, artifacts, masking, "missing artifact")

        package, artifacts, masking = _package("FHKB")
        package["artifacts"][0]["sha256"] = "sha256:" + "f" * 64
        self.assert_semantic_failure(package, artifacts, masking, "artifact digest mismatch")

    def test_source_manifest_missing_and_digest_mismatch_fail(self) -> None:
        package, artifacts, masking = _package("DEKG")
        artifacts.pop(package["lineage"]["source_manifest_path"])
        self.assert_semantic_failure(
            package, artifacts, masking, "missing source manifest"
        )

        package, artifacts, masking = _package("DEKG")
        package["lineage"]["source_manifest_digest"] = "sha256:" + "f" * 64
        self.assert_semantic_failure(
            package, artifacts, masking, "source manifest digest mismatch"
        )

    def test_package_identity_collision_fails(self) -> None:
        package, artifacts, masking = _package("DEKG")
        self.assert_semantic_failure(
            package,
            artifacts,
            masking,
            "package identity collision",
            known_package_digests={package["package_id"]: "sha256:" + "f" * 64},
        )

    def test_component_digest_unaccepted_and_cycle_fail(self) -> None:
        component, _, _ = _package("TPDX")
        release, artifacts, masking = _package("TPDX", package_type="tpdx_release")
        ref = {
            "package_id": component["package_id"],
            "package_type": component["package_type"],
            "manifest_path": "components/diagnostic/manifest.json",
            "manifest_digest": "sha256:" + "f" * 64,
            "acceptance_status": "accepted",
        }
        release["component_refs"] = [ref]
        _seal(release)
        self.assert_semantic_failure(
            release,
            artifacts,
            masking,
            "component manifest digest mismatch",
            component_registry={component["package_id"]: component},
        )

        ref["manifest_digest"] = component["content_digest"]
        ref["acceptance_status"] = "candidate"
        _seal(release)
        self.assert_semantic_failure(
            release,
            artifacts,
            masking,
            "unaccepted component reference",
            component_registry={component["package_id"]: component},
        )

        ref["acceptance_status"] = "accepted"
        component["component_refs"] = [
            {
                "package_id": release["package_id"],
                "package_type": "tpdx_topology_component",
                "manifest_path": "cycle/release.json",
                "manifest_digest": release["content_digest"],
                "acceptance_status": "accepted",
            }
        ]
        _seal(release)
        self.assert_semantic_failure(
            release,
            artifacts,
            masking,
            "circular component dependency",
            component_registry={
                component["package_id"]: component,
                release["package_id"]: release,
            },
        )

    def test_released_claim_requires_review_and_release_decision(self) -> None:
        package, artifacts, masking = _package("TPDX")
        package["decision"]["package_status"] = "released"
        package["decision"]["release_decision_id"] = None
        self.assert_semantic_failure(
            package, artifacts, masking, "released claim lacks required evidence"
        )

    def test_content_digest_excludes_only_itself(self) -> None:
        package, _, _ = _package("TPDX")
        original_digest = package["content_digest"]
        package["content_digest"] = "sha256:" + "f" * 64
        self.assertEqual(_content_digest(package), original_digest)
        package["decision"]["review_status"] = "in_review"
        self.assertNotEqual(_content_digest(package), original_digest)

    def test_package_identity_has_a_fixed_vector(self) -> None:
        package, _, _ = _package("TPDX")
        self.assertEqual(
            package["package_id"],
            "PKG_d0259b121e228c9cefd2eb2e561e7ee76958909b6eb8049cf22cddcacb2af8ce",
        )


if __name__ == "__main__":
    unittest.main()
