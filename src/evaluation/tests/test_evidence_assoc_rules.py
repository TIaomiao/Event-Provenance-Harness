import sys
from datetime import datetime
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence_assoc_rules import classify_c_candidate, extract_hgb_candidates, latest_by_collection_time
from outbound_guard import GuardConfig, dry_run_request, request_ledger_metadata


def row(ref, text, page=1):
    return {"line_ref": ref, "page": page, "text": text, "bbox": []}


def lab(rows):
    return [{"doc": "DOC-SYN", "category": "laboratory_report", "records": rows}]


def hgb_block(prefix, project, value, unit, ref_range, collection, report, page=1):
    return [
        row(f"{prefix}:project", project, page),
        row(f"{prefix}:alias", "HGB", page),
        row(f"{prefix}:value", str(value), page),
        row(f"{prefix}:unit", unit, page),
        row(f"{prefix}:range", ref_range, page),
        row(f"{prefix}:collection", f"采集时间：{collection}", page),
        row(f"{prefix}:report", f"报告时间：{report}", page),
    ]


class CandidateRulesTests(unittest.TestCase):
    def test_reference_lower_bound_is_not_result(self):
        cands = extract_hgb_candidates(lab(hgb_block("a", "血红蛋白量", 119, "g/L", "115--150", "2024-01-02 08:00:00", "2024-01-02 09:00:00")))
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["value"], 119)
        self.assertEqual(cands[0]["reference_interval"], "115--150")
        self.assertNotEqual(cands[0]["value"], 115)

    def test_separate_unit_is_bound_without_using_range(self):
        cands = extract_hgb_candidates(lab(hgb_block("a", "血红蛋白量", 119, "g/L", "115--150", "2024-01-02 08:00:00", "2024-01-02 09:00:00")))
        self.assertEqual(cands[0]["unit"], "g/L")
        self.assertEqual(cands[0]["value_g_l"], 119)

    def test_shared_report_time_does_not_swap_project_and_result(self):
        rows = hgb_block("a", "血红蛋白量", 119, "g/L", "115--150", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
        rows += [row("wbc:project", "白细胞计数"), row("wbc:value", "7.1"), row("wbc:unit", "10^9/L"), row("wbc:range", "3.5--9.5"), row("wbc:collection", "采集时间：2024-01-02 08:00:00"), row("wbc:report", "报告时间：2024-01-02 09:00:00")]
        cands = extract_hgb_candidates(lab(rows))
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["project_name"], "血红蛋白量")
        self.assertEqual(cands[0]["result_ref"], "a:value")
        self.assertIn("a:report", cands[0]["source_refs"])
        self.assertNotIn("wbc:value", cands[0]["source_refs"])

    def test_collection_time_controls_order_not_report_time(self):
        rows = hgb_block("first", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
        rows += hgb_block("second", "血红蛋白量", 120, "g/L", "100--160", "2024-01-01 08:00:00", "2024-01-03 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidates"][0]["result_ref"], "first:value")

    def test_tie_keeps_all_records(self):
        rows = hgb_block("a", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
        rows += hgb_block("b", "血红蛋白量", 120, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual({c["result_ref"] for c in result["candidates"]}, {"a:value", "b:value"})

    def test_date_precision_is_unresolved(self):
        rows = hgb_block("a", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02", "2024-01-02 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["reason"], "date_precision_insufficient")

    def test_identity_missing_is_invalid_task_not_contradicted(self):
        rows = [row("alias", "HGB"), row("value", "119"), row("unit", "g/L"), row("range", "115--150"), row("collection", "采集时间：2024-01-02 08:00:00"), row("report", "报告时间：2024-01-02 09:00:00")]
        candidate = extract_hgb_candidates(lab(rows))[0]
        self.assertEqual(candidate["identity_status"], "invalid_task")
        self.assertEqual(classify_c_candidate(candidate), "invalid_task")

    def test_null_unit_is_not_automatic_contradiction(self):
        candidate = {"identity_status": "explicit", "value": 119, "collection_time": datetime(2024, 1, 2, 8), "unit": None}
        self.assertEqual(classify_c_candidate(candidate), "supported")
        self.assertEqual(classify_c_candidate(candidate, require_unit=True), "insufficient")


class OutboundGuardTests(unittest.TestCase):
    def setUp(self):
        self.config = GuardConfig(code_version="synthetic-code", config_version="synthetic-config", approved_destinations=frozenset({"synthetic-provider"}), allow_external=True)
        self.messages = [{"role": "system", "content": "JSON only"}, {"role": "user", "content": "redacted CASE-X observation"}]
        self.source = {"source_version": "snapshot-v1", "source_sha256": "abc", "hash_matches": True, "api_ready": True, "raw_ocr": False, "sensitivity": "REDACTED_SYNTHETIC", "review_scope": "DOC-SYN page 1", "purpose": "synthetic-eval", "destination": "synthetic-provider"}
        self.fields = {"project_name": "HGB", "value": 119, "unit": "g/L", "collection_time_role": "explicit", "report_time_role": "explicit", "source_anchor": "DOC-SYN:L1"}

    def inspect(self, **overrides):
        source = dict(self.source)
        source.update(overrides.pop("source", {}))
        kwargs = {"destination": "synthetic-provider", "purpose": "synthetic-eval", "config": self.config}
        kwargs.update(overrides)
        return dry_run_request(messages=self.messages, model="synthetic-model", max_tokens=10, source=source, task_fields=self.fields, **kwargs)

    def test_raw_fallback_blocked_before_network(self):
        result = self.inspect(source={"raw_ocr": True})
        self.assertEqual(result.decision, "block")
        self.assertIn("raw_ocr_source", result.reasons)

    def test_api_ready_false_blocked(self):
        result = self.inspect(source={"api_ready": False})
        self.assertEqual(result.decision, "block")
        self.assertIn("api_ready_not_true", result.reasons)

    def test_hash_mismatch_blocked(self):
        result = self.inspect(source={"hash_matches": False})
        self.assertEqual(result.decision, "block")
        self.assertIn("source_hash_mismatch", result.reasons)

    def test_unapproved_destination_blocked(self):
        result = self.inspect(destination="other-provider")
        self.assertEqual(result.decision, "block")
        self.assertIn("destination_not_approved", result.reasons)

    def test_unknown_state_blocked(self):
        result = self.inspect(source={"unknown_state": True})
        self.assertEqual(result.decision, "block")
        self.assertIn("unknown_state_present", result.reasons)

    def test_missing_task_field_blocked(self):
        result = self.inspect()
        result = dry_run_request(
            messages=self.messages,
            model="synthetic-model",
            max_tokens=10,
            source=self.source,
            task_fields={"project_name": "HGB"},
            destination="synthetic-provider",
            purpose="synthetic-eval",
            config=self.config,
        )
        self.assertEqual(result.decision, "block")
        self.assertTrue(any(reason.startswith("task_fields_missing:") for reason in result.reasons))

    def test_compliant_synthetic_request_is_dry_run_only(self):
        result = self.inspect()
        self.assertEqual(result.decision, "allow_dry_run")
        self.assertFalse(result.request_metadata["sent"])
        ledger = request_ledger_metadata(result, request_id="synthetic-1", cost_basis={"currency": "USD", "amount": 0})
        self.assertEqual(ledger["full_body_storage"], "controlled_only_if_approved")
        self.assertEqual(ledger["request_id"], "synthetic-1")


if __name__ == "__main__":
    unittest.main()
