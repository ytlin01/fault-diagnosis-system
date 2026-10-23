from __future__ import annotations

import unittest

from services.ingestion.field_actions import generalize
from services.ingestion.masking_engine import mask_row


class TypeMappingTests(unittest.TestCase):
    def test_to_type_defaults_to_placeholder_when_values_are_empty(self) -> None:
        mapped, detail = generalize(
            'Luster',
            config={
                'generalize_method': 'to_type',
                'type_mapping': {
                    'default': '[TO_TYPE]',
                    'values': {},
                },
            },
        )

        self.assertEqual(mapped, '[TO_TYPE]')
        self.assertEqual(detail, 'generalize(to_type)->default')

    def test_to_type_uses_configured_value_case_insensitively(self) -> None:
        mapped, detail = generalize(
            'luster',
            config={
                'generalize_method': 'to_type',
                'type_mapping': {
                    'default': '[TO_TYPE]',
                    'values': {
                        'Luster': 'VENDOR_TYPE_A',
                    },
                },
            },
        )

        self.assertEqual(mapped, 'VENDOR_TYPE_A')
        self.assertEqual(detail, 'generalize(to_type)->mapped')

    def test_mask_row_passes_type_mapping_from_column_rule(self) -> None:
        row = {'Vendor': 'Luster'}
        source_config = {
            'column_rules': {
                'Vendor': {
                    'level': 'B',
                    'canonical_action': 'passthrough',
                    'serving_action': 'generalize',
                    'generalize_method': 'to_type',
                    'type_mapping': {
                        'default': '[TO_TYPE]',
                        'values': {
                            'Luster': 'VENDOR_TYPE_A',
                        },
                    },
                },
            },
        }
        rules = {'tokenizer': {}}

        serving_row, log = mask_row(
            row,
            source_config=source_config,
            rules=rules,
            view='serving',
        )

        self.assertEqual(serving_row['Vendor'], 'VENDOR_TYPE_A')
        self.assertEqual(log[0]['detail'], 'generalize(to_type)->mapped')


if __name__ == '__main__':
    unittest.main()
