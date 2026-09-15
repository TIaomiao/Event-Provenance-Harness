import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from laboratory_bbox_adapter import adapt_layout

class LaboratoryAdapterTests(unittest.TestCase):
    def test_extracts_value_unit_and_stable_id(self):
        layout={"case_token":"CASE-SYNTHETIC","document_token":"DOC-001","records":[{"page_number":1,"bbox":[[0,0],[1,0],[1,1],[0,1]],"confidence":.99,"text":"X: 4.2 mmol/L"}]}
        out=adapt_layout(layout); r=out["records"][0]
        self.assertEqual(r["value_numeric"],4.2); self.assertEqual(r["unit"],"mmol/L"); self.assertEqual(out["parser_status"],"complete")

    def test_missing_fields_are_review(self):
        layout={"case_token":"CASE-SYNTHETIC","document_token":"DOC-001","records":[{"page_number":1,"bbox":[],"confidence":.5,"text":"X"}]}
        r=adapt_layout(layout)["records"][0]
        self.assertEqual(r["validation_status"],"needs_review"); self.assertIn("VALUE_NOT_FOUND",r["quality_issues"])

if __name__ == '__main__': unittest.main()
