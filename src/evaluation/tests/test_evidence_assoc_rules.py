import sys
from datetime import datetime
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evidence_assoc_rules import classify_c_candidate, extract_hgb_candidates, latest_by_collection_time
from outbound_guard import GuardConfig, GuardResult, dry_run_request, execute_request, request_ledger_metadata, request_body_bytes


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

    def test_single_day_precision_candidate_is_the_latest(self):
        # One record: nothing to order against, so its own clock precision
        # cannot change the maximum.
        rows = hgb_block("a", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02", "2024-01-02 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidates"][0]["result_ref"], "a:value")

    def test_day_precision_does_not_block_when_dates_differ(self):
        rows = hgb_block("first", "血红蛋白量", 110, "g/L", "100--160", "2024-01-03", "2024-01-03 09:00:00")
        rows += hgb_block("second", "血红蛋白量", 120, "g/L", "100--160", "2024-01-01 08:00:00", "2024-01-01 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidates"][0]["result_ref"], "first:value")

    def test_same_day_day_precision_stays_undetermined(self):
        rows = hgb_block("a", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02", "2024-01-02 09:00:00")
        rows += hgb_block("b", "血红蛋白量", 120, "g/L", "100--160", "2024-01-02", "2024-01-02 10:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "same_day_overlap_precision_insufficient")

    def test_same_day_resolved_by_clock(self):
        rows = hgb_block("a", "血红蛋白量", 110, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
        rows += hgb_block("b", "血红蛋白量", 120, "g/L", "100--160", "2024-01-02 07:00:00", "2024-01-02 09:00:00")
        result = latest_by_collection_time(extract_hgb_candidates(lab(rows)))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["candidates"][0]["result_ref"], "a:value")

    def test_related_hemoglobin_analytes_are_not_the_target(self):
        # MCH/MCHC, HbA1c and blood-gas haemoglobins contain 血红蛋白 but are
        # different analytes; they must not become anchored target records.
        # A bare "HGB" on the following row has no project name of its own, so
        # it may only surface as invalid_task, never as an explicit record.
        for name in ("平均红细胞血红蛋白量", "红细胞平均血红蛋白浓度", "糖化血红蛋白",
                     "氧合血红蛋白", "碳氧血红蛋白", "高铁血红蛋白", "还原血红蛋白",
                     "Glycated Hemoglobin Report"):
            rows = hgb_block("x", name, 110, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
            found = extract_hgb_candidates(lab(rows))
            self.assertEqual([c for c in found if c["identity_status"] == "explicit"], [], name)

    def test_whole_hemoglobin_project_names_are_still_the_target(self):
        for name in ("血红蛋白", "血红蛋白量", "血红蛋白浓度", "*血红蛋白", "*#血红蛋白量"):
            rows = hgb_block("x", name, 110, "g/L", "100--160", "2024-01-02 08:00:00", "2024-01-02 09:00:00")
            found = extract_hgb_candidates(lab(rows))
            self.assertEqual(len(found), 1, name)
            self.assertEqual(found[0]["value"], 110, name)

    def test_identity_missing_is_invalid_task_not_contradicted(self):
        rows = [row("alias", "HGB"), row("value", "119"), row("unit", "g/L"), row("range", "115--150"), row("collection", "采集时间：2024-01-02 08:00:00"), row("report", "报告时间：2024-01-02 09:00:00")]
        candidate = extract_hgb_candidates(lab(rows))[0]
        self.assertEqual(candidate["identity_status"], "invalid_task")
        self.assertEqual(classify_c_candidate(candidate)["status"], "invalid_task")

    def test_null_unit_is_not_automatic_contradiction(self):
        candidate = {"identity_status": "explicit", "value": 119, "collection_time": datetime(2024, 1, 2, 8), "unit": None, "source_refs": ["DOC-SYN:L1"]}
        self.assertEqual(classify_c_candidate(candidate)["status"], "complete")
        self.assertEqual(classify_c_candidate(candidate, require_unit=True)["status"], "incomplete")

    def test_structure_does_not_judge_consistent_or_conflicting_facts(self):
        base = {"identity_status": "explicit", "collection_time": datetime(2024, 1, 2, 8), "source_refs": ["DOC-SYN:L1"], "unit": "g/L"}
        consistent = {**base, "value": 119}
        conflicting = {**base, "value": 118}
        self.assertEqual(classify_c_candidate(consistent)["status"], "complete")
        self.assertEqual(classify_c_candidate(conflicting)["status"], "complete")


class OutboundGuardTests(unittest.TestCase):
    def setUp(self):
        self.config = GuardConfig(code_version="synthetic-code", config_version="synthetic-config", approved_destinations=frozenset({"synthetic-provider"}), approved_endpoints=frozenset({"synthetic-endpoint"}), approved_pool_profiles=frozenset({"synthetic-pool"}), allow_external=True)
        self.messages = [{"role": "system", "content": "JSON only"}, {"role": "user", "content": "redacted CASE-X observation"}]
        self.source = {"source_version": "snapshot-v1", "source_sha256": "abc", "hash_matches": True, "api_ready": True, "raw_ocr": False, "payload_mode": "synthetic", "sensitivity": "REDACTED_SYNTHETIC", "review_scope": "DOC-SYN page 1", "purpose": "synthetic-eval", "destination": "synthetic-provider", "endpoint_config": "synthetic-endpoint", "pool_profile_id": "synthetic-pool"}
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

    def test_deidentified_test_requires_api_ready(self):
        result = self.inspect(source={"payload_mode": "deidentified_test", "api_ready": False})
        self.assertEqual(result.decision, "block")
        self.assertIn("deidentified_package_not_api_ready", result.reasons)

    def test_raw_test_requires_explicit_authorization(self):
        result = self.inspect(source={"payload_mode": "raw_test", "raw_ocr": True, "api_ready": False})
        self.assertEqual(result.decision, "block")
        self.assertIn("raw_test_authorization_missing", result.reasons)

    def test_authorized_raw_test_can_pass_guard_without_api_ready(self):
        result = self.inspect(source={"payload_mode": "raw_test", "raw_ocr": True, "api_ready": False, "raw_test_authorized": True, "sensitivity": "CONTAINS_RAW_OCR_TEXT_LOCAL_ONLY"})
        self.assertEqual(result.decision, "allow")

    def test_deidentified_test_with_reviewed_package_can_pass_guard(self):
        result = self.inspect(source={"payload_mode": "deidentified_test", "api_ready": True, "raw_ocr": False, "sensitivity": "REDACTED_REVIEWED"})
        self.assertEqual(result.decision, "allow")

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
        self.assertEqual(result.decision, "allow")
        self.assertFalse(result.request_metadata["sent"])
        ledger = request_ledger_metadata(result, request_id="synthetic-1", cost_basis={"currency": "USD", "amount": 0})
        self.assertEqual(ledger["full_body_storage"], "controlled_only_if_approved")
        self.assertEqual(ledger["request_id"], "synthetic-1")

    def test_execute_block_calls_sender_zero_times(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        calls = []
        result = execute_request(mode="live", guard_check=lambda: GuardResult("block", ["blocked"]), body=body, sender=lambda payload: calls.append(payload) or {"http": 200})
        self.assertEqual(result["status"], "blocked_not_sent")
        self.assertEqual(len(calls), 0)

    def test_execute_dry_run_calls_sender_zero_times(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        checked = self.inspect()
        calls = []
        result = execute_request(mode="dry-run", guard_check=lambda: checked, body=body, sender=lambda payload: calls.append(payload) or {"http": 200})
        self.assertEqual(result["status"], "dry_run_not_sent")
        self.assertEqual(len(calls), 0)

    def test_execute_guard_exception_unknown_and_body_change_block(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        calls = []
        for guard in [lambda: (_ for _ in ()).throw(RuntimeError("guard")), lambda: GuardResult("mystery", []), lambda: GuardResult("allow", [], "wrong")]:
            result = execute_request(mode="live", guard_check=guard, body=body, sender=lambda payload: calls.append(payload) or {"http": 200})
            self.assertEqual(result["status"], "blocked_not_sent")
        self.assertEqual(len(calls), 0)

    def test_execute_allowed_live_calls_sender_once(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        checked = self.inspect()
        calls = []
        result = execute_request(mode="live", guard_check=lambda: checked, body=body, sender=lambda payload: calls.append(payload) or {"http": 200})
        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(calls), 1)

    def test_execute_503_retry_rechecks_guard(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        checked = self.inspect()
        calls = []
        checks = []
        def guard():
            checks.append(True)
            return checked
        def sender(payload):
            calls.append(payload)
            return {"http": 503 if len(calls) == 1 else 200}
        result = execute_request(mode="live", guard_check=guard, body=body, sender=sender, max_retries=1)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(checks), 2)

    def test_final_503_is_service_failure_not_content_or_format(self):
        body = request_body_bytes(self.messages, "synthetic-model", 10)
        checked = self.inspect()
        result = execute_request(mode="live", guard_check=lambda: checked, body=body, sender=lambda payload: {"http": 503}, max_retries=1)
        self.assertEqual(result["status"], "service_failure")
        self.assertEqual(result["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
