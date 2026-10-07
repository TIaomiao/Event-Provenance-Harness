"""Tests for the governance input adapter.

All fixtures are synthetic: tokens, text and geometry are invented, so no
patient material is needed to exercise the adapter.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))

import governance_input_adapter as adapter  # noqa: E402


def bbox(x, y):
    return [[x, y], [x + 10, y], [x + 10, y + 5], [x, y + 5]]


def l1(records, schema="1.0", case="CASE-SYNTHETIC", doc="DOC-001"):
    return {"schema_version": schema, "sensitivity": "CONTAINS_RAW_OCR_TEXT_LOCAL_ONLY",
            "case_token": case, "document_token": doc, "page_count": 1,
            "line_count": len(records), "pages": [{"page_number": 1, "image_width": 100,
                                                   "image_height": 100}],
            "records": records}


def row(text, index, schema="1.0", case="CASE-SYNTHETIC", doc="DOC-001"):
    return {"case_token": case, "document_token": doc, "page_number": 1,
            "bbox": bbox(10, 10 * index + 5), "text": text, "confidence": 0.9,
            "source_kind": "ocr"}


def l2(records, schema="1.0", case="CASE-SYNTHETIC", doc="DOC-001", **over):
    data = {"schema_version": schema, "case_token": case, "document_token": doc,
            "page_count": 1, "line_count": len(records),
            "pages": [{"page_number": 1, "image_width": 100, "image_height": 100}],
            "records": records, "basic_rule_scan_passed": True,
            "manual_privacy_review_required": True, "api_ready": False,
            "redaction_hit_count": 0, "redaction_hits": [], "quarantine_required": False,
            "privacy_status": "manual_review_required", "residual_scan_hit_count": 0,
            "residual_scan_hits": [], "quality_warning_hit_count": 0,
            "quality_warning_hits": []}
    data.update(over)
    return data


class AdapterTest(unittest.TestCase):
    def build(self, l1_data, l2_data):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / adapter.L1_NAME).write_text(json.dumps(l1_data, ensure_ascii=False), encoding="utf-8")
        (root / adapter.L2_NAME).write_text(json.dumps(l2_data, ensure_ascii=False), encoding="utf-8")
        return root

    def tearDown(self):
        tmp = getattr(self, "tmp", None)
        if tmp is not None:
            tmp.cleanup()

    def test_unsupported_schema_fails_loudly(self):
        records = [row("血红蛋白", 0, schema="0.7")]
        root = self.build(l1(records, schema="0.7"), l2(records, schema="0.7"))
        with self.assertRaises(adapter.SchemaUnsupported) as caught:
            adapter.load_document(root, input_mode="raw_test")
        self.assertIn("0.7", str(caught.exception))

    def test_missing_schema_fails_loudly(self):
        records = [row("血红蛋白", 0)]
        data = l1(records)
        del data["schema_version"]
        root = self.build(data, l2(records))
        with self.assertRaises(adapter.SchemaUnsupported):
            adapter.load_document(root, input_mode="raw_test")

    def test_equal_counts_but_shifted_geometry_is_rejected(self):
        raw = [row("血红蛋白", 0), row("5.0 g/L", 1)]
        shifted = [dict(raw[0], bbox=bbox(10, 999)), raw[1]]
        root = self.build(l1(raw), l2(shifted))
        with self.assertRaises(adapter.AlignmentError):
            adapter.load_document(root, input_mode="raw_test")

    def test_different_counts_are_rejected(self):
        root = self.build(l1([row("血红蛋白", 0)]), l2([row("血红蛋白", 0), row("x", 1)]))
        with self.assertRaises(adapter.AlignmentError):
            adapter.load_document(root, input_mode="raw_test")

    def test_scope_mismatch_is_rejected(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records, doc="DOC-002"))
        with self.assertRaises(adapter.AlignmentError):
            adapter.load_document(root, input_mode="raw_test")

    def test_supported_schemas_both_load(self):
        for schema in ("0.9", "1.0"):
            records = [row("血红蛋白", 0, schema=schema)]
            root = self.build(l1(records, schema=schema), l2(records, schema=schema))
            view = adapter.load_document(root, input_mode="raw_test")
            self.assertEqual(view["source_snapshot"]["schema_version"], schema)
            self.assertEqual(view["counts"]["lines"], 1)

    def test_missing_and_empty_fields_differ(self):
        records = [row("血红蛋白", 0)]
        data = l2(records, privacy_status="", redaction_hits=[])
        del data["residual_scan_hit_count"]
        root = self.build(l1(records), data)
        view = adapter.load_document(root, input_mode="raw_test")
        self.assertEqual(view["privacy"]["privacy_status"][0], adapter.EMPTY)
        self.assertEqual(view["privacy"]["residual_scan_hit_count"][0], adapter.MISSING)
        self.assertIn("RESIDUAL_COUNT_MISSING", view["unresolved"])

    def test_raw_mode_gates_text(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        raw = adapter.load_document(root, input_mode="raw_test")
        deid = adapter.load_document(root, input_mode="deidentified_test")
        self.assertIn("text", raw["lines"][0])
        self.assertNotIn("text", deid["lines"][0])
        self.assertEqual(deid["source_snapshot"]["input_mode"], "deidentified_test")

    def test_ids_do_not_leak_case_or_doc(self):
        records = [row("血红蛋白", 0), row("血红蛋白", 1)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test")
        ids = [line["record_id"] for line in view["lines"]]
        self.assertEqual(len(set(ids)), 2)
        for record_id in ids:
            self.assertNotIn("CASE-SYNTHETIC", record_id)
            self.assertNotIn("DOC-001", record_id)

    def test_day0_coordinate_is_per_case(self):
        first = adapter.case_day0_coordinate("CASE-SYNTHETIC")
        second = adapter.case_day0_coordinate("CASE-SYNTHETIC-2")
        self.assertNotEqual(first, second)

    def test_candidates_keep_every_row_and_unresolved(self):
        records = [row("血红蛋白", 0), row("5.0", 1), row("平均红细胞血红蛋白量", 2),
                   row("血红蛋白", 3)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test")
        candidates = adapter.candidate_records(view, mode="per-row")
        anchors = [candidate["anchor"] for candidate in candidates]
        self.assertEqual(anchors, ["L0", "L3"])
        self.assertTrue(all("UNIT_NOT_FOUND" in candidate["unresolved"]
                            for candidate in candidates))
        self.assertTrue(all(candidate["extractor"] == "per-row" for candidate in candidates))

    def test_rule_mode_normalizes_extractor_output(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test")
        original = adapter._rules
        adapter._rules = lambda: (lambda docs: [{
            "project_name": "HGB", "value": 145.0, "unit": "g/L",
            "identity_status": "explicit", "project_ref": "L0", "result_ref": "L0",
            "unit_ref": "L2", "collection_ref": None, "report_ref": None,
            "page": 1, "collection_time": None, "collection_precision": None}])
        try:
            candidates = adapter.candidate_records(view)
        finally:
            adapter._rules = original
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["extractor"], "rule")
        self.assertEqual(candidate["value"], 145.0)
        self.assertEqual(candidate["unit"], "g/L")
        self.assertEqual(candidate["anchor"], "L0")
        self.assertEqual(candidate["identity_status"], "explicit")
        self.assertIn("COLLECTION_TIME_MISSING", candidate["unresolved"])
        self.assertIn("COLLECTION_ANCHOR_MISSING", candidate["unresolved"])
        self.assertIn("REPORT_ANCHOR_MISSING", candidate["unresolved"])
        self.assertNotIn("VALUE_MISSING", candidate["unresolved"])
        self.assertNotIn("CASE-SYNTHETIC", candidate["record_id"])

    def test_rule_mode_marks_missing_value_and_unit(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test")
        original = adapter._rules
        adapter._rules = lambda: (lambda docs: [{
            "project_name": "HGB", "value": None, "unit": None,
            "identity_status": "explicit", "project_ref": "L0", "result_ref": "L0",
            "unit_ref": None, "collection_ref": None, "report_ref": None,
            "page": 1, "collection_time": None, "collection_precision": None}])
        try:
            candidates = adapter.candidate_records(view)
        finally:
            adapter._rules = original
        self.assertIn("VALUE_MISSING", candidates[0]["unresolved"])
        self.assertIn("UNIT_MISSING", candidates[0]["unresolved"])

    def test_unknown_candidate_mode_is_refused(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test")
        with self.assertRaises(adapter.AdapterError):
            adapter.candidate_records(view, mode="guessed")

    def test_candidate_scan_requires_text(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="deidentified_test")
        with self.assertRaises(adapter.AdapterError):
            adapter.candidate_records(view)

    def test_quarantine_and_residual_surface_as_unresolved(self):
        records = [row("血红蛋白", 0)]
        data = l2(records, quarantine_required=True, residual_scan_hit_count=3,
                  residual_scan_hits=[{"rule": "possible_partial_date", "page_number": 1,
                                       "bbox": bbox(1, 1)}],
                  privacy_status="quarantined")
        root = self.build(l1(records), data)
        view = adapter.load_document(root, input_mode="raw_test")
        self.assertIn("QUARANTINED", view["unresolved"])
        self.assertIn("RESIDUAL_HITS_PRESENT:3", view["unresolved"])

    def test_source_snapshot_is_complete(self):
        records = [row("血红蛋白", 0)]
        root = self.build(l1(records), l2(records))
        view = adapter.load_document(root, input_mode="raw_test", review_scope="card-v0.3")
        snapshot = view["source_snapshot"]
        for key in ("case_token", "document_token", "schema_version", "page_range",
                    "l1_sha256", "l2_sha256", "day0_coordinate", "input_mode", "review_scope",
                    "adapter_version"):
            self.assertIn(key, snapshot)
        self.assertEqual(snapshot["page_range"], [1, 1])
        self.assertEqual(len(snapshot["l1_sha256"]), 64)
        self.assertEqual(snapshot["review_scope"], "card-v0.3")


if __name__ == "__main__":
    unittest.main()
