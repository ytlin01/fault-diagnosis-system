from __future__ import annotations

import copy
import unittest

from services.evaluation.route_a_golden_annotation import GoldenAnnotationInputError, create_review_record, queue_case, validate_annotation_queue


def _queue() -> dict:
    return {
        "schema_version": "route_a_annotation_queue_v1",
        "queue_id": "queue-1",
        "cases": [
            {"case_id": "case-1", "scenario_id": "RA-GOLD-EC-01", "partition": "development", "query": "Controlled query", "query_language": "en", "coverage": {"query_type": "ec", "difficulty": "low", "equipment_scope": "module"}},
            {"case_id": "case-blind", "scenario_id": "RA-GOLD-EC-06", "partition": "blind", "query": "Blind query", "query_language": "en", "coverage": {"query_type": "ec", "difficulty": "high", "equipment_scope": "module"}},
        ],
        "cause_catalog": [{"cause_id": "cause-1", "display_name": "Cause one"}],
        "cause_action_pair_catalog": [{"cause_id": "cause-1", "action_id": "action-1", "display_name": "Cause one / action one"}],
    }


def _anchors() -> list[dict]:
    return [{"source_id": "source-1", "anchor": "approved-anchor", "source_review_state": "reviewed", "allowed_use": "annotation_and_evaluation"}]


class GoldenAnnotationTests(unittest.TestCase):
    def test_creates_append_only_review_record(self) -> None:
        queue = _queue()
        validate_annotation_queue(queue)
        record = create_review_record(queue, case_id="case-1", reviewer_id="expert-1", role="domain_reviewer", decision="accept", label_maturity="reviewed", abstention="not_expected", cause_ids=["cause-1"], cause_action_pairs=[{"cause_id": "cause-1", "action_id": "action-1"}], source_anchors=_anchors(), rationale_anchor="review-note")
        self.assertEqual("route_a_annotation_review_v1", record["schema_version"])
        self.assertEqual("case-1", record["case_id"])
        self.assertEqual("reviewed", record["label_maturity"])

    def test_blocks_blind_case_without_explicit_authorization(self) -> None:
        with self.assertRaises(GoldenAnnotationInputError):
            queue_case(_queue(), "case-blind")

    def test_rejects_labels_outside_controlled_catalog(self) -> None:
        with self.assertRaises(GoldenAnnotationInputError):
            create_review_record(_queue(), case_id="case-1", reviewer_id="expert-1", role="annotator", decision="accept", label_maturity="provisional", abstention="not_expected", cause_ids=["not-catalogued"], cause_action_pairs=[], source_anchors=_anchors(), rationale_anchor="review-note")

    def test_required_abstention_cannot_include_label(self) -> None:
        with self.assertRaises(GoldenAnnotationInputError):
            create_review_record(_queue(), case_id="case-1", reviewer_id="expert-1", role="annotator", decision="accept", label_maturity="provisional", abstention="required", cause_ids=["cause-1"], cause_action_pairs=[], source_anchors=_anchors(), rationale_anchor="review-note")

    def test_rejects_scenario_variants_crossing_partitions(self) -> None:
        queue = _queue()
        variant = copy.deepcopy(queue["cases"][0])
        variant["case_id"] = "case-variant"
        variant["partition"] = "validation"
        queue["cases"].append(variant)
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "crosses partitions"
        ):
            validate_annotation_queue(queue)

    def test_rejects_unknown_coverage_tag(self) -> None:
        queue = _queue()
        queue["cases"][0]["coverage"]["query_type"] = "free_form"
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "query_type is invalid"
        ):
            validate_annotation_queue(queue)

    def test_only_adjudicator_can_set_adjudicated_maturity(self) -> None:
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "requires an adjudicator"
        ):
            create_review_record(
                _queue(),
                case_id="case-1",
                reviewer_id="expert-1",
                role="domain_reviewer",
                decision="accept",
                label_maturity="adjudicated",
                abstention="not_expected",
                cause_ids=["cause-1"],
                cause_action_pairs=[
                    {"cause_id": "cause-1", "action_id": "action-1"}
                ],
                source_anchors=_anchors(),
                rationale_anchor="review-note",
            )

    def test_reviewed_gold_requires_evaluation_eligible_anchor(self) -> None:
        anchors = _anchors()
        anchors[0]["allowed_use"] = "annotation_only"
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "not eligible for evaluation"
        ):
            create_review_record(
                _queue(),
                case_id="case-1",
                reviewer_id="expert-1",
                role="domain_reviewer",
                decision="accept",
                label_maturity="reviewed",
                abstention="not_expected",
                cause_ids=["cause-1"],
                cause_action_pairs=[],
                source_anchors=anchors,
                rationale_anchor="review-note",
            )

    def test_pair_must_reference_selected_cause(self) -> None:
        queue = _queue()
        queue["cause_catalog"].append(
            {"cause_id": "cause-2", "display_name": "Cause two"}
        )
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "must reference a selected cause_id"
        ):
            create_review_record(
                queue,
                case_id="case-1",
                reviewer_id="expert-1",
                role="domain_reviewer",
                decision="accept",
                label_maturity="reviewed",
                abstention="not_expected",
                cause_ids=["cause-2"],
                cause_action_pairs=[
                    {"cause_id": "cause-1", "action_id": "action-1"}
                ],
                source_anchors=_anchors(),
                rationale_anchor="review-note",
            )

    def test_blind_case_cannot_remain_provisional(self) -> None:
        with self.assertRaisesRegex(
            GoldenAnnotationInputError, "blind cases require reviewed"
        ):
            create_review_record(
                _queue(),
                case_id="case-blind",
                reviewer_id="expert-1",
                role="domain_reviewer",
                decision="accept",
                label_maturity="provisional",
                abstention="not_expected",
                cause_ids=["cause-1"],
                cause_action_pairs=[],
                source_anchors=_anchors(),
                rationale_anchor="review-note",
                allow_blind=True,
            )


if __name__ == "__main__":
    unittest.main()
