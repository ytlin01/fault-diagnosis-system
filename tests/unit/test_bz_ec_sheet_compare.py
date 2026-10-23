from __future__ import annotations

import unittest

from services.aggregation.bz_ec_sheet_compare import compare_sheet_rows


class CompareSheetRowsTests(unittest.TestCase):
    def test_compare_by_key_reports_changed_and_one_sided_rows(self) -> None:
        left = {
            "workbook_path": "left.xlsx",
            "sheet_name": "c1stn1",
            "header_row": 1,
            "headers": ["error code", "error description", "repair action"],
            "rows": [
                {"error code": "E001", "error description": "Alarm A", "repair action": "Reset", "_row_number": 2},
                {"error code": "E002", "error description": "Alarm B", "repair action": "Replace", "_row_number": 3},
            ],
        }
        right = {
            "workbook_path": "right.xlsx",
            "sheet_name": "c1stn2",
            "header_row": 1,
            "headers": ["error code", "error description", "repair action"],
            "rows": [
                {"error code": "E001", "error description": "Alarm A", "repair action": "Reset board", "_row_number": 2},
                {"error code": "E003", "error description": "Alarm C", "repair action": "Check cable", "_row_number": 3},
            ],
        }

        result = compare_sheet_rows(left, right, key_columns=["error code"])
        summary = result["comparison"]["row_count_summary"]

        self.assertEqual(summary["changed_keys"], 1)
        self.assertEqual(summary["left_only_keys"], 1)
        self.assertEqual(summary["right_only_keys"], 1)
        self.assertEqual(result["comparison"]["changed_rows"][0]["key"]["error code"], "E001")

    def test_compare_by_full_row_reports_extra_rows(self) -> None:
        left = {
            "workbook_path": "left.xlsx",
            "sheet_name": "c1stn1",
            "header_row": 1,
            "headers": ["error code", "error description"],
            "rows": [
                {"error code": "E001", "error description": "Alarm A", "_row_number": 2},
                {"error code": "E002", "error description": "Alarm B", "_row_number": 3},
            ],
        }
        right = {
            "workbook_path": "right.xlsx",
            "sheet_name": "c1stn2",
            "header_row": 1,
            "headers": ["error code", "error description"],
            "rows": [
                {"error code": "E001", "error description": "Alarm A", "_row_number": 2},
            ],
        }

        result = compare_sheet_rows(left, right)
        summary = result["comparison"]["row_count_summary"]

        self.assertEqual(summary["shared_exact_rows"], 1)
        self.assertEqual(summary["left_only_rows"], 1)
        self.assertEqual(summary["right_only_rows"], 0)


if __name__ == "__main__":
    unittest.main()
