import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from temporal_roles import bind_candidates, materialize_event_table

SCOPE = dict(case_token="CASE-SYNTHETIC", document_token="DOC-001", page_number=1)

class TemporalRoleTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [SCOPE | {"case_coordinate_day": day} for day in (0, 3)]
        self.row = SCOPE | dict(row_id="ROW-1", candidate_ordinals=[0], temporal_role="sampling")

    def test_explicit_row_binding(self):
        out = bind_candidates(self.candidates, [self.row])
        self.assertEqual(out[0]["temporal_role"], "sampling")
        self.assertEqual(out[1]["binding_status"], "unresolved")

    def test_invalid_role_rejected(self):
        with self.assertRaises(ValueError):
            bind_candidates(self.candidates, [self.row | {"temporal_role": "inferred"}])

    def test_inputs_unchanged(self):
        before = copy.deepcopy((self.candidates, self.row))
        bind_candidates(self.candidates, [self.row])
        self.assertEqual(before, (self.candidates, self.row))

    def test_unknown_role_remains_unresolved(self):
        del self.row["temporal_role"]
        out = bind_candidates(self.candidates, [self.row])
        self.assertEqual(out[0]["binding_status"], "unresolved")

    def test_roles_remain_distinct(self):
        for role in ("sampling", "report", "record", "document"):
            out = bind_candidates(self.candidates, [self.row | {"temporal_role": role}])
            self.assertEqual(out[0]["temporal_role"], role)
            self.assertNotIn("event_time", out[0])
            self.assertFalse(out[0]["clinical_time_roles_validated"])

    def test_cross_source_links_rejected(self):
        for field, value in (("case_token", "CASE-002"), ("document_token", "DOC-002"), ("page_number", 2)):
            with self.assertRaisesRegex(ValueError, "SOURCE_SCOPE_MISMATCH"):
                bind_candidates(self.candidates, [self.row | {field: value}])

    def test_invalid_ordinals_rejected(self):
        for ordinal in (-1, 2, True, "0"):
            with self.assertRaisesRegex(ValueError, "INVALID_CANDIDATE_ORDINAL"):
                bind_candidates(self.candidates, [self.row | {"candidate_ordinals": [ordinal]}])

    def test_duplicate_links_rejected(self):
        with self.assertRaisesRegex(ValueError, "AMBIGUOUS_ROW_BINDING"):
            bind_candidates(self.candidates, [self.row, self.row | {"row_id": "ROW-2"}])

    def test_duplicate_rows_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ROW_ID"):
            bind_candidates(self.candidates, [self.row, self.row | {"candidate_ordinals": [1]}])

    def test_missing_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "MISSING_SOURCE_SCOPE"):
            bind_candidates([{}], [])

    def test_header_date_applies_to_multiple_rows(self):
        header = dict(page_number=1, date="2026-01-04", role_label="采样时间", evidence_id="E-H", bbox=[[0, 0], [200, 0], [200, 20], [0, 20]])
        rows = [dict(row_id="R1", page_number=1, value="4.2", unit="U", evidence_id="E-R1", bbox=[[0, 30], [100, 30], [100, 45], [0, 45]]),
                dict(row_id="R2", page_number=1, value="5.1", unit="U", evidence_id="E-R2", bbox=[[0, 50], [100, 50], [100, 65], [0, 65]])]
        out = materialize_event_table([header], rows)
        self.assertEqual([e["event_time"] for e in out], ["2026-01-04", "2026-01-04"])
        self.assertEqual([e["value"] for e in out], ["4.2", "5.1"])
        self.assertIn("E-H", out[1]["evidence"])

    def test_ambiguous_headers_remain_unresolved(self):
        h = lambda d, eid: dict(page_number=1, date=d, role_label="报告时间", evidence_id=eid, bbox=[[0, 0], [200, 0], [200, 20], [0, 20]])
        row = dict(row_id="R1", page_number=1, value="x", unit="U", bbox=[[0, 30], [100, 30], [100, 45], [0, 45]])
        self.assertEqual(materialize_event_table([h("2026-01-01", "H1"), h("2026-01-02", "H2")], [row])[0]["binding_status"], "unresolved")

if __name__ == '__main__':
    unittest.main()
