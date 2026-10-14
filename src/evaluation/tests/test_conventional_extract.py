"""Tests for the independent conventional extractor.

Synthetic rows only.  The last test is the independence guarantee: the module must not
borrow the harness's own extraction or temporal-role modules, otherwise arm B is not a
conventional baseline at all.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import conventional_extract as ce  # noqa: E402


def line(anchor, text, x, y):
    return {"anchor": anchor, "text": text, "bbox": [[x, y], [x + 40, y + 8]]}


class ConventionalExtractTest(unittest.TestCase):

    def test_a_band_yields_one_record_with_unit_and_both_days(self):
        rows = [
            line("L1", "HGB 血红蛋白量", 10, 100),
            line("L2", "119", 120, 100),
            line("L3", "g/L", 180, 100),
            line("L4", "相对日 0", 240, 100),
            line("L5", "相对日 1", 300, 100),
            line("L9", "白细胞计数", 10, 200),
            line("L10", "7.2", 120, 200),
        ]
        records = ce.extract_rows(rows, ("HGB", "血红蛋白"))
        self.assertEqual(len(records), 1, "only the project band becomes a record")
        record = records[0]
        self.assertEqual(record["value"], 119.0)
        self.assertEqual(record["unit"], "g/L")
        self.assertEqual(record["collection_day_offset"], 0)
        self.assertEqual(record["report_day_offset"], 1)
        self.assertIn("L2", record["source_refs"])

    def test_a_band_without_a_value_is_skipped(self):
        rows = [line("L1", "HGB 血红蛋白量", 10, 100)]
        self.assertEqual(ce.extract_rows(rows, ("HGB", "血红蛋白")), [])

    def test_lines_without_a_bbox_are_ignored_not_crashing(self):
        rows = [{"anchor": "L1", "text": "HGB 119 g/L"}]
        self.assertEqual(ce.extract_rows(rows, ("HGB",)), [])

    def test_two_bands_on_one_page_yield_two_records(self):
        rows = [
            line("L1", "HGB 血红蛋白量", 10, 100),
            line("L2", "119", 120, 100),
            line("L3", "g/L", 180, 100),
            line("L4", "HGB 血红蛋白量", 10, 300),
            line("L5", "133", 120, 300),
            line("L6", "g/L", 180, 300),
        ]
        records = ce.extract_rows(rows, ("HGB",))
        self.assertEqual([r["value"] for r in records], [119.0, 133.0])

    def test_the_module_does_not_borrow_the_harness_library(self):
        source = pathlib.Path(ce.__file__).read_text(encoding="utf-8")
        for forbidden in ("evidence_assoc_rules", "temporal_roles",
                          "laboratory_bbox_adapter", "governance_input_adapter"):
            self.assertNotIn("import %s" % forbidden, source,
                             "arm B must not borrow %s" % forbidden)
        self.assertNotIn("extract_hgb_candidates", source)

    def test_absolute_dates_are_read_and_turned_into_offsets(self):
        rows = [
            line("L1", "HGB 血红蛋白量", 10, 100),
            line("L2", "119", 120, 100),
            line("L3", "g/L", 180, 100),
            line("L4", "采集时间：2025-04-27 17:16:14", 240, 100),
            line("L5", "报告时间：2025-05-02 08:00:00", 300, 100),
        ]
        records = ce.extract_rows(rows, ("HGB",))
        self.assertEqual(records[0]["collection_date"], "2025-04-27")
        self.assertEqual(records[0]["report_date"], "2025-05-02")
        ce.to_day_offsets(records)
        self.assertEqual(records[0]["collection_day_offset"], 0)
        self.assertEqual(records[0]["report_day_offset"], 5)

    def test_a_chinese_date_format_is_read_too(self):
        rows = [
            line("L1", "HGB 血红蛋白量", 10, 100),
            line("L2", "119", 120, 100),
            line("L3", "g/L", 180, 100),
            line("L4", "记录时间：2025年4月27日", 240, 100),
        ]
        records = ce.extract_rows(rows, ("HGB",))
        self.assertEqual(records[0]["collection_date"], "2025-04-27")

    def test_an_impossible_date_is_ignored(self):
        rows = [
            line("L1", "HGB 血红蛋白量", 10, 100),
            line("L2", "119", 120, 100),
            line("L3", "g/L", 180, 100),
            line("L4", "时间：2025-13-45", 240, 100),
        ]
        records = ce.extract_rows(rows, ("HGB",))
        self.assertIsNone(records[0]["collection_date"])


if __name__ == "__main__":
    unittest.main()
