from __future__ import annotations

import unittest

from services.aggregation.structured_fp_join import (
    build_review_decisions_template,
    build_review_report,
    build_review_summary,
    build_structured_fp_join,
    extract_fp_features,
    normalize_fp,
)


class StructuredFpJoinTests(unittest.TestCase):
    def test_normalize_fp_strips_markers_spaces_and_punctuation(self) -> None:
        self.assertEqual(normalize_fp('  1、Cowling 组装 NG； '), 'cowling组装ng')

    def test_builds_exact_join_with_possible_causes_and_repair_actions(self) -> None:
        error_codes = [
            {'Index': 1, 'Item': '装配', 'Error code': 'EC-001', 'Description': 'Cowling 组装NG'},
        ]
        downtime = [
            {
                '序號': 10,
                '異常描敘': 'cowling 组装 NG',
                '原因': '机械手点位不佳',
                '維修動作': '优化点位',
                'DT(Mins)': 5,
                'Risk': 'High',
                'Status': 'Monitor',
            },
            {
                '序號': 11,
                '異常描敘': 'Cowling 组装NG',
                '原因': '坐标原点丢失',
                '維修動作': '重新校正原点',
                'DT(Mins)': 7,
                'Risk': 'High',
                'Status': 'Closed',
            },
        ]

        payload = build_structured_fp_join(error_codes, downtime, generated_at='2026-04-14T00:00:00+00:00')

        self.assertEqual(payload['metadata']['summary']['join_records'], 1)
        record = payload['records'][0]
        self.assertEqual(record['match_type'], 'normalized_exact')
        self.assertEqual(record['EC'], 'EC-001')
        self.assertEqual(record['RC'], ['机械手点位不佳', '坐标原点丢失'])
        self.assertEqual(record['PA'], ['优化点位', '重新校正原点'])
        self.assertEqual(record['semantics']['RC'], 'Possible Causes / candidate causes; not a verified unique root cause')
        self.assertIs(record['kg_diagnosis_eligible'], True)
        self.assertEqual(record['chain_status'], 'complete_confirmed')
        self.assertEqual(record['route_target'], 'text2cypher_diagnosis')
        self.assertEqual(record['missing_chain_fields'], [])
        self.assertEqual(payload['metadata']['summary']['kg_diagnosis_eligible_records'], 1)
        self.assertEqual(record['evidence']['count'], 2)
        self.assertEqual(record['evidence']['total_dt_mins'], 12.0)

    def test_builds_contains_candidate_and_unmatched_outputs(self) -> None:
        error_codes = [
            {'Index': 1, 'Item': '供料', 'Error code': 'EC-002', 'Description': '供料器间取料位无料'},
            {'Index': 2, 'Item': '安全', 'Error code': 'EC-003', 'Description': '急停按钮已按下'},
        ]
        downtime = [
            {
                '序號': 20,
                '異常描敘': '供料器间取料位无料，空吸',
                '原因': '供料器转动时未取到螺丝',
                '維修動作': '继续分析',
                'DT(Mins)': 80,
            },
            {
                '序號': 21,
                '異常描敘': '未出现在错误码中的现象',
                '原因': '待分析',
                '維修動作': '观察',
                'DT(Mins)': 3,
            },
        ]

        payload = build_structured_fp_join(error_codes, downtime, generated_at='2026-04-14T00:00:00+00:00')

        self.assertEqual(payload['records'][0]['match_type'], 'contains_candidate')
        self.assertIs(payload['records'][0]['kg_diagnosis_eligible'], False)
        self.assertEqual(payload['records'][0]['chain_status'], 'complete_candidate_review_required')
        self.assertEqual(payload['records'][0]['route_target'], 'fp_review_governance')
        self.assertEqual(payload['metadata']['summary']['kg_diagnosis_eligible_records'], 0)
        self.assertEqual(payload['metadata']['summary']['unmatched_error_code_fps'], 1)
        self.assertEqual(payload['metadata']['summary']['unmatched_downtime_fps'], 1)
        self.assertEqual(payload['unmatched']['error_code_fps'][0]['EC'], 'EC-003')
        self.assertEqual(payload['unmatched']['downtime_fps'][0]['field_fp_variants'], ['未出现在错误码中的现象'])

    def test_review_report_proposes_feature_candidate_bucket(self) -> None:
        rules = {
            'normalization': {'replacements': {'倉': '仓', '軸': '轴', '模块': '模组', '通訊': '通讯'}},
            'feature_terms': {
                'modules': {'上料仓': {'aliases': ['上料仓', '上料仓模组']}},
                'axes': {'Z轴': {'aliases': ['Z轴', 'z轴']}},
                'components': {'伺服驱动器': {'aliases': ['伺服驱动器']}},
                'fault_modes': {
                    '通讯异常': {'aliases': ['通讯异常'], 'parent': '异常'},
                    '异常': {'aliases': ['异常']},
                },
            },
            'review': {
                'min_shared_features': 2,
                'max_candidates_per_bucket': 5,
                'feature_weights': {'modules': 3, 'axes': 3, 'components': 2, 'fault_modes': 2},
                'bucket_priority_features': ['modules', 'axes', 'components', 'fault_modes'],
            },
        }
        error_codes = [
            {'Index': 78, 'Item': '电机', 'Error code': 'M07LOM1-01-03', 'Description': '上料仓模组_Z轴伺服驱动器通讯异常'},
        ]
        downtime = [
            {'序號': 47, '異常描敘': '上料仓Z轴异常', '原因': 'TBD', '維修動作': '重新固定感应器并调整感应器位置', 'DT(Mins)': 6},
        ]

        report = build_review_report(error_codes, downtime, rules, generated_at='2026-04-14T00:00:00+00:00')

        self.assertEqual(report['metadata']['summary']['buckets_with_candidates'], 1)
        bucket = report['buckets'][0]
        self.assertEqual(bucket['bucket_id'], 'modules=上料仓|axes=Z轴|fault_modes=异常')
        self.assertEqual(bucket['candidate_error_codes'][0]['EC'], 'M07LOM1-01-03')
        self.assertEqual(bucket['candidate_error_codes'][0]['standard_fp'], '上料仓模组_Z轴伺服驱动器通讯异常')
        relation = bucket['candidate_error_codes'][0]['candidate_reason']['fault_mode_relation']
        self.assertEqual(relation['type'], 'parent_child_fault_mode')

    def test_extract_fp_features_normalizes_traditional_aliases(self) -> None:
        rules = {
            'normalization': {'replacements': {'倉': '仓', '軸': '轴', '失敗': '失败'}},
            'feature_terms': {
                'modules': {'上料仓': {'aliases': ['上料仓']}},
                'axes': {'Z轴': {'aliases': ['Z轴']}},
                'components': {},
                'fault_modes': {'使能失败': {'aliases': ['使能失败']}},
            },
        }

        features = extract_fp_features('上料倉Z軸使能失敗', rules)

        self.assertEqual(features['modules'], ['上料仓'])
        self.assertEqual(features['axes'], ['Z轴'])
        self.assertEqual(features['fault_modes'], ['使能失败'])



    def test_review_report_groups_overlapping_features_under_primary_bucket(self) -> None:
        rules = {
            'normalization': {'replacements': {}},
            'feature_terms': {
                'modules': {
                    'cowling': {'aliases': ['cowling', 'Cowling']},
                    '上料仓': {'aliases': ['上料仓']},
                    '取料模组': {'aliases': ['取料']},
                },
                'axes': {},
                'components': {},
                'fault_modes': {
                    '刮伤': {'aliases': ['刮伤'], 'parent': '异常'},
                    'NG': {'aliases': ['组装NG'], 'parent': '异常'},
                    '异常': {'aliases': ['异常']},
                },
            },
            'review': {
                'min_shared_features': 1,
                'max_candidates_per_bucket': 5,
                'feature_weights': {'modules': 3, 'fault_modes': 2},
                'bucket_priority_features': ['modules', 'fault_modes'],
                'primary_bucket_strategy': {
                    'default': 'unclassified',
                    'feature_priority': {
                        'modules': ['cowling', '上料仓', '取料模组'],
                        'fault_modes': ['NG', '刮伤', '异常'],
                    },
                    'sub_bucket_features': ['fault_modes', 'modules'],
                },
            },
        }
        error_codes = [
            {'Index': 1, 'Item': '装配', 'Error code': 'EC-COWL-1', 'Description': 'Cowling组装工位_压块气缸伸出异常'},
        ]
        downtime = [
            {'序號': 1, '異常描敘': 'cowling刮伤', '原因': '夹爪毛刺', '維修動作': '更换夹爪', 'DT(Mins)': 10},
            {'序號': 2, '異常描敘': 'Cowling上料仓组装NG', '原因': '点位偏移', '維修動作': '调整点位', 'DT(Mins)': 20},
        ]

        report = build_review_report(error_codes, downtime, rules, generated_at='2026-04-14T00:00:00+00:00')

        self.assertEqual(report['metadata']['summary']['primary_bucket_count'], 1)
        self.assertGreaterEqual(report['metadata']['summary']['flat_bucket_count'], 2)
        primary = report['primary_buckets'][0]
        self.assertEqual(primary['primary_bucket'], 'cowling')
        self.assertEqual(primary['summary']['fp_group_count'], 2)
        self.assertGreaterEqual(len(primary['sub_buckets']), 2)


    def test_review_summary_shows_review_actions(self) -> None:
        rules = {
            'normalization': {'replacements': {}},
            'feature_terms': {
                'modules': {
                    '夹爪': {'aliases': ['夹爪']},
                    '上料仓': {'aliases': ['上料仓', '上料仓模组']},
                },
                'axes': {'Z轴': {'aliases': ['Z轴']}},
                'components': {},
                'fault_modes': {
                    '报警': {'aliases': ['报警'], 'parent': '异常'},
                    '通讯异常': {'aliases': ['掉线'], 'parent': '异常'},
                    '异常': {'aliases': ['异常']},
                },
            },
            'review': {
                'min_shared_features': 2,
                'max_candidates_per_bucket': 5,
                'feature_weights': {'modules': 3, 'axes': 3, 'fault_modes': 2},
                'bucket_priority_features': ['modules', 'axes', 'fault_modes'],
                'primary_bucket_strategy': {
                    'default': 'unclassified',
                    'feature_priority': {
                        'modules': ['夹爪', '上料仓'],
                        'fault_modes': ['报警', '通讯异常', '异常'],
                    },
                    'sub_bucket_features': ['axes', 'fault_modes'],
                },
            },
        }
        error_codes = [
            {'Index': 1, 'Item': '电机', 'Error code': 'EC-Z-ALARM', 'Description': '上料仓模组_Z轴报警'},
        ]
        downtime = [
            {'序號': 1, '異常描敘': '上料仓Z轴报警', '原因': 'pending', '維修動作': '复位', 'DT(Mins)': 3},
            {'序號': 2, '異常描敘': '组装夹爪掉线，不装盖板', '原因': 'pending', '維修動作': '重启', 'DT(Mins)': 4},
        ]

        summary = build_review_summary(build_review_report(error_codes, downtime, rules, generated_at='2026-04-14T00:00:00+00:00'))
        buckets = {bucket['primary_bucket']: bucket for bucket in summary['sample_primary_buckets']}

        self.assertEqual(buckets['上料仓']['review_action'], 'review_candidates')
        self.assertEqual(buckets['夹爪']['review_action'], 'classify_or_add_rule')
        self.assertEqual(buckets['夹爪']['sample_sub_buckets'][0]['review_action'], 'classify_or_add_rule')
    def test_confirmed_review_decision_promotes_candidate_into_join(self) -> None:
        rules = {
            'normalization': {'replacements': {'模块': '模组'}},
            'feature_terms': {
                'modules': {'上料仓': {'aliases': ['上料仓', '上料仓模组']}},
                'axes': {'Z轴': {'aliases': ['Z轴', 'z轴']}},
                'components': {'伺服驱动器': {'aliases': ['伺服驱动器']}},
                'fault_modes': {
                    '通讯异常': {'aliases': ['通讯异常'], 'parent': '异常'},
                    '异常': {'aliases': ['异常']},
                },
            },
            'review': {
                'min_shared_features': 2,
                'max_candidates_per_bucket': 5,
                'feature_weights': {'modules': 3, 'axes': 3, 'components': 2, 'fault_modes': 2},
                'bucket_priority_features': ['modules', 'axes', 'components', 'fault_modes'],
                'primary_bucket_strategy': {
                    'default': 'unclassified',
                    'feature_priority': {'modules': ['上料仓']},
                    'sub_bucket_features': ['axes', 'fault_modes'],
                },
            },
        }
        error_codes = [
            {'Index': 78, 'Item': '电机', 'Error code': 'M07LOM1-01-03', 'Description': '上料仓模组_Z轴伺服驱动器通讯异常'},
        ]
        downtime = [
            {'序號': 47, '異常描敘': '上料仓Z轴异常', '原因': 'TBD', '維修動作': '重新固定感应器并调整感应器位置', 'DT(Mins)': 6},
        ]
        decisions = build_review_decisions_template()
        decisions['decisions'] = [{
            'decision_id': 'confirm-upstream-z-axis',
            'decision': 'confirmed',
            'EC': 'M07LOM1-01-03',
            'field_fp': '上料仓Z轴异常',
            'field_fp_normalized': '上料仓z轴异常',
            'primary_bucket': '上料仓',
            'sub_bucket_id': 'axes=Z轴|fault_modes=异常',
            'reviewer': 'unit-test',
            'note': 'Known site wording for the standard FP.',
        }]

        payload = build_structured_fp_join(error_codes, downtime, rules=rules, review_decisions=decisions, generated_at='2026-04-14T00:00:00+00:00')
        review_summary = build_review_summary(build_review_report(error_codes, downtime, rules, review_decisions=decisions, generated_at='2026-04-14T00:00:00+00:00'))

        self.assertEqual(payload['metadata']['summary']['join_records'], 1)
        self.assertEqual(payload['records'][0]['match_type'], 'human_confirmed_review_candidate')
        self.assertIs(payload['records'][0]['kg_diagnosis_eligible'], True)
        self.assertEqual(payload['records'][0]['chain_status'], 'complete_confirmed')
        self.assertEqual(payload['records'][0]['route_target'], 'text2cypher_diagnosis')
        self.assertEqual(payload['records'][0]['match_basis']['review_decision']['decision_id'], 'confirm-upstream-z-axis')
        self.assertEqual(payload['metadata']['review_decisions']['promoted_join_records'], 1)
        self.assertEqual(payload['metadata']['summary']['unmatched_error_code_fps'], 0)
        self.assertEqual(payload['metadata']['summary']['unmatched_downtime_fps'], 0)
        bucket = review_summary['sample_primary_buckets'][0]
        self.assertEqual(bucket['candidate_decision_counts']['confirmed'], 1)
        self.assertEqual(bucket['sample_candidates'][0]['review_status'], 'confirmed')

    def test_review_report_adds_lightweight_semantic_candidate_without_shared_module(self) -> None:
        rules = {
            'normalization': {'replacements': {'模块': '模组'}},
            'feature_terms': {
                'modules': {'上料仓': {'aliases': ['上料仓', '上料仓模组']}},
                'axes': {'Z轴': {'aliases': ['Z轴', 'z轴']}},
                'components': {'伺服驱动器': {'aliases': ['伺服驱动器']}},
                'fault_modes': {
                    '通讯异常': {'aliases': ['通讯异常'], 'parent': '异常'},
                    '异常': {'aliases': ['异常']},
                },
            },
            'review': {
                'min_shared_features': 2,
                'max_candidates_per_bucket': 5,
                'feature_weights': {'modules': 3, 'axes': 3, 'components': 2, 'fault_modes': 2},
                'bucket_priority_features': ['modules', 'axes', 'components', 'fault_modes'],
                'semantic_candidates': {
                    'enabled': True,
                    'min_score': 0.35,
                    'require_any_feature_overlap': True,
                    'require_shared_module': False,
                    'char_ngram_n': [2, 3],
                    'weights': {'char_ngram': 0.5, 'feature': 0.5},
                },
            },
        }
        error_codes = [
            {'Index': 78, 'Item': '电机', 'Error code': 'M07LOM1-01-03', 'Description': '上料仓模组_Z轴伺服驱动器通讯异常'},
        ]
        downtime = [
            {'序號': 47, '異常描敘': 'Z轴通讯异常', '原因': 'TBD', '維修動作': '检查线缆', 'DT(Mins)': 6},
        ]

        report = build_review_report(error_codes, downtime, rules, generated_at='2026-04-14T00:00:00+00:00')

        self.assertEqual(report['metadata']['summary']['semantic_candidate_links'], 1)
        candidate = report['buckets'][0]['candidate_error_codes'][0]
        self.assertEqual(candidate['EC'], 'M07LOM1-01-03')
        self.assertEqual(candidate['candidate_reason']['candidate_type'], 'semantic_candidate')
        self.assertEqual(candidate['route_target'], 'fp_review_governance')
        self.assertIs(candidate['kg_diagnosis_eligible'], False)
        self.assertGreaterEqual(candidate['candidate_reason']['semantic_score'], 0.35)

if __name__ == '__main__':
    unittest.main()




