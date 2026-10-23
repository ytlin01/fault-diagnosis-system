from __future__ import annotations

import unittest

from services.aggregation.structured_fp_join_semantic import (
    build_review_report,
    build_review_summary,
    build_semantic_fp_join,
    build_standard_fp_review,
    build_standard_fp_review_summary,
    default_config,
)


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> dict[str, list[float]]:
        vectors = {}
        for text in texts:
            if '\u4e0a\u6599\u4ed3' in text or 'Z\u8f74' in text or 'z\u8f74' in text:
                vectors[text] = [1.0, 0.0, 0.0]
            elif '\u6025\u505c' in text:
                vectors[text] = [0.0, 1.0, 0.0]
            else:
                vectors[text] = [0.0, 0.0, 1.0]
        return vectors


class StructuredFpJoinSemanticTests(unittest.TestCase):
    def test_builds_review_only_semantic_candidates(self) -> None:
        config = default_config()
        config['candidate_generation']['top_k_per_downtime_fp'] = 1
        config['candidate_generation']['min_embedding_similarity'] = 0.9
        config['candidate_generation']['min_final_score'] = 0.9
        config['provider']['model'] = 'fake-embedding'
        rules = {
            'normalization': {'replacements': {'\u6a21\u5757': '\u6a21\u7ec4'}},
            'feature_terms': {
                'modules': {'\u4e0a\u6599\u4ed3': {'aliases': ['\u4e0a\u6599\u4ed3', '\u4e0a\u6599\u4ed3\u6a21\u7ec4']}},
                'axes': {'Z\u8f74': {'aliases': ['Z\u8f74', 'z\u8f74']}},
                'components': {},
                'fault_modes': {'\u5f02\u5e38': {'aliases': ['\u5f02\u5e38']}},
            },
        }
        error_codes = [
            {'Index': 1, 'Error code': 'EC-Z', 'Description': '\u4e0a\u6599\u4ed3\u6a21\u7ec4_Z\u8f74\u4f3a\u670d\u9a71\u52a8\u5668\u901a\u8baf\u5f02\u5e38'},
            {'Index': 2, 'Error code': 'EC-STOP', 'Description': '\u6025\u505c\u6309\u94ae\u5df2\u6309\u4e0b'},
        ]
        downtime = [
            {'\u5e8f\u865f': 1, '\u7570\u5e38\u63cf\u6558': '\u4e0a\u6599\u4ed3Z\u8f74\u5f02\u5e38', '\u539f\u56e0': '\u7ebf\u7f06\u677e\u52a8', '\u7dad\u4fee\u52d5\u4f5c': '\u91cd\u65b0\u63d2\u62d4\u7ebf\u7f06', 'DT(Mins)': 5},
        ]

        payload = build_semantic_fp_join(
            error_codes,
            downtime,
            rules=rules,
            config=config,
            embedding_provider=FakeEmbeddingProvider(),
            generated_at='2026-04-15T00:00:00+00:00',
        )
        report = build_review_report(payload)
        summary = build_review_summary(report)

        self.assertEqual(payload['metadata']['summary']['candidate_records'], 1)
        record = payload['records'][0]
        self.assertEqual(record['EC'], 'EC-Z')
        self.assertEqual(record['match_type'], 'semantic_embedding_candidate')
        self.assertEqual(record['route_target'], 'fp_review_governance')
        self.assertIs(record['kg_diagnosis_eligible'], False)
        self.assertEqual(record['review_status'], 'needs_review')
        self.assertEqual(record['RC'], ['\u7ebf\u7f06\u677e\u52a8'])
        self.assertEqual(record['PA'], ['\u91cd\u65b0\u63d2\u62d4\u7ebf\u7f06'])
        self.assertEqual(summary['summary']['candidate_records'], 1)
        self.assertEqual(summary['sample_buckets'][0]['sample_candidates'][0]['EC'], 'EC-Z')

    def test_standard_fp_review_groups_multiple_field_fps(self) -> None:
        config = default_config()
        config['candidate_generation']['top_k_per_downtime_fp'] = 1
        config['candidate_generation']['min_embedding_similarity'] = 0.9
        config['candidate_generation']['min_final_score'] = 0.9
        config['provider']['model'] = 'fake-embedding'
        rules = {
            'normalization': {'replacements': {'\u6a21\u5757': '\u6a21\u7ec4'}},
            'feature_terms': {
                'modules': {'\u4e0a\u6599\u4ed3': {'aliases': ['\u4e0a\u6599\u4ed3', '\u4e0a\u6599\u4ed3\u6a21\u7ec4']}},
                'axes': {'Z\u8f74': {'aliases': ['Z\u8f74', 'z\u8f74']}},
                'components': {},
                'fault_modes': {'\u5f02\u5e38': {'aliases': ['\u5f02\u5e38']}},
            },
        }
        error_codes = [
            {'Index': 1, 'Error code': 'EC-Z', 'Description': '\u4e0a\u6599\u4ed3\u6a21\u7ec4_Z\u8f74\u4f3a\u670d\u9a71\u52a8\u5668\u901a\u8baf\u5f02\u5e38'},
        ]
        downtime = [
            {'\u5e8f\u865f': 1, '\u7570\u5e38\u63cf\u6558': '\u4e0a\u6599\u4ed3Z\u8f74\u5f02\u5e38', '\u539f\u56e0': '\u7ebf\u7f06\u677e\u52a8', '\u7dad\u4fee\u52d5\u4f5c': '\u91cd\u65b0\u63d2\u62d4\u7ebf\u7f06', 'DT(Mins)': 5},
            {'\u5e8f\u865f': 2, '\u7570\u5e38\u63cf\u6558': '\u4e0a\u6599\u4ed3z\u8f74\u6389\u7ebf', '\u539f\u56e0': '\u901a\u8baf\u7ebf\u677e\u52a8', '\u7dad\u4fee\u52d5\u4f5c': '\u590d\u4f4d\u5e76\u91cd\u63d2', 'DT(Mins)': 7},
        ]

        payload = build_semantic_fp_join(
            error_codes,
            downtime,
            rules=rules,
            config=config,
            embedding_provider=FakeEmbeddingProvider(),
            generated_at='2026-04-15T00:00:00+00:00',
        )
        report = build_standard_fp_review(payload)
        summary = build_standard_fp_review_summary(report)

        self.assertEqual(report['metadata']['summary']['standard_fp_count'], 1)
        group = report['standard_fp_groups'][0]
        self.assertEqual(group['EC'], 'EC-Z')
        self.assertEqual(group['summary']['candidate_field_fp_count'], 2)
        self.assertEqual(group['summary']['candidate_record_count'], 2)
        self.assertEqual(summary['sample_standard_fp_groups'][0]['summary']['candidate_field_fp_count'], 2)
        self.assertEqual(len(summary['sample_standard_fp_groups'][0]['sample_field_fp_candidates']), 2)


if __name__ == '__main__':
    unittest.main()
