import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixtures import assertion, correct_prediction, gold_fixture
from scorer import score, summarize_cost


class ScorerTests(unittest.TestCase):
    def setUp(self):
        self.gold = gold_fixture()
        self.pred = correct_prediction()

    def run_score(self):
        return score(self.gold, self.pred)

    def test_correct_all_twelve(self):
        result = self.run_score()
        self.assertEqual(result["joint_tp"], 12)
        self.assertEqual(result["full_record_f1"], 1)
        self.assertEqual(result["unknown_sampling"], {"gold": 4, "predicted": 4, "correct": 4})
        self.assertEqual(result["identity"]["correct"], 3)
        self.assertEqual(result["identity"]["missing_decision"], 1)

    def test_value_error_keeps_alignment(self):
        self.pred["observations"][0]["value"] = "99"
        result = self.run_score()
        self.assertEqual(result["field_correct"]["value"], 11)
        self.assertEqual(result["field_correct"]["source_support"], 11)
        self.assertEqual(result["missing_observations"], 0)
        self.assertEqual((result["joint_tp"], result["joint_fp"], result["joint_fn"]), (11, 1, 1))

    def test_unit_error(self):
        self.pred["observations"][0]["unit"] = "V"
        self.assertEqual(self.run_score()["field_correct"]["unit"], 11)

    def test_numeric_equivalence_without_tolerance(self):
        self.pred["observations"][0]["value"] = "4.200"
        self.assertEqual(self.run_score()["joint_tp"], 12)
        self.pred["observations"][0]["value"] = "4.2001"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_comparator_is_not_dropped(self):
        self.pred["observations"][0]["value"] = "<4.2"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_sampling_report_role_swap(self):
        a, b = self.pred["observations"][0]["time_assertions"]
        a["role"], b["role"] = b["role"], a["role"]
        result = self.run_score()
        self.assertEqual(result["field_correct"]["value"], 12)
        self.assertEqual(result["field_correct"]["sampling_time"], 11)
        self.assertEqual(result["field_correct"]["source_support"], 11)

    def test_local_day_zero_not_same_coordinate(self):
        self.pred["observations"][6]["time_assertions"][0]["coordinate_id"] = "C1"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_sampling_unknown_cannot_use_report(self):
        obs = self.pred["observations"][4]
        obs["time_assertions"][0] = assertion("sampling", 2, "C1", "d4r", "lr", "t4")
        result = self.run_score()
        self.assertEqual(result["unknown_sampling"]["correct"], 3)
        self.assertEqual(result["joint_tp"], 11)

    def test_sampling_unknown_cannot_use_document(self):
        self.pred["observations"][5]["time_assertions"][0] = assertion("sampling", 2, "C1", "d5", "ld", "t5")
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_shared_header_can_support_two_rows(self):
        self.assertEqual(self.run_score()["field_correct"]["source_support"], 12)

    def test_existing_but_wrong_table_scope(self):
        self.pred["observations"][7]["time_assertions"][0]["scope_ref"] = "t1"
        result = self.run_score()
        self.assertEqual(result["field_correct"]["sampling_time"], 12)
        self.assertEqual(result["field_correct"]["source_support"], 11)

    def test_existing_but_wrong_date_citation(self):
        self.pred["observations"][0]["time_assertions"][0]["date_ref"] = "d6"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_existing_but_wrong_role_citation(self):
        self.pred["observations"][0]["time_assertions"][0]["role_ref"] = "lr-t1"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_cross_page_header_needs_support(self):
        self.pred["observations"][11]["time_assertions"][0] = assertion("sampling", 5, "C1", "d11", "ls", "t11")
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_conflict_must_retain_both_claims(self):
        self.pred["observations"][8]["time_assertions"].pop()
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_conflict_must_keep_status(self):
        self.pred["observations"][8]["time_assertions"][0]["binding_status"] = "explicit"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_unknown_and_unresolved_are_distinct(self):
        self.pred["observations"][9]["time_assertions"][0]["binding_status"] = "unknown"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_missing_observation(self):
        self.pred["observations"].pop(2)
        result = self.run_score()
        self.assertEqual((result["missing_observations"], result["joint_fn"], result["joint_fp"]), (1, 1, 0))
        self.assertEqual(result["identity"]["missing_decision"], 2)

    def test_duplicate_output_consumes_gold_once(self):
        extra = copy.deepcopy(self.pred["observations"][0])
        extra["observation_id"] = "new-id"
        self.pred["observations"].append(extra)
        result = self.run_score()
        self.assertEqual((result["joint_tp"], result["joint_fp"], result["extra_observations"]), (12, 1, 1))

    def test_nonexistent_source_is_not_supported(self):
        self.pred["observations"][0]["source_refs"] = ["invented"]
        result = self.run_score()
        self.assertEqual((result["joint_tp"], result["missing_observations"], result["extra_observations"]), (11, 1, 1))

    def test_unrelated_source_added_loses_support(self):
        self.pred["observations"][0]["source_refs"].append("r3")
        result = self.run_score()
        self.assertEqual(result["joint_tp"], 11)
        self.assertEqual(result["ambiguous_source_predictions"], 1)

    def test_false_merge_same_value_repeat(self):
        self.pred["event_groups"] = [["r1", "r4", "r3", "r11"]]
        result = self.run_score()
        self.assertEqual(result["identity"]["false_merge"], 2)
        self.assertEqual(result["joint_tp"], 12)

    def test_false_split_explicit_copy(self):
        self.pred["event_groups"] = [["r1"], ["r4"], ["r3"], ["r11"]]
        self.assertEqual(self.run_score()["identity"]["false_split"], 1)

    def test_unresolved_identity_not_forced(self):
        self.pred["event_groups"].append(["r7"])
        self.assertEqual(self.run_score()["identity"]["unsupported_resolution"], 1)

    def test_missing_groups_not_perfect_identity(self):
        del self.pred["event_groups"]
        result = self.run_score()["identity"]
        self.assertEqual(result["status"], "not_reported")
        self.assertEqual(result["missing_decision"], 4)

    def test_group_duplicate_row_invalid(self):
        self.pred["event_groups"].append(["r1"])
        self.assertEqual(self.run_score()["identity"]["status"], "invalid")

    def test_order_and_generated_ids_do_not_affect_score(self):
        before = self.run_score()
        self.pred["observations"].reverse()
        self.gold["observations"].reverse()
        self.gold["evidence"].reverse()
        for i, obs in enumerate(self.pred["observations"]):
            obs["observation_id"] = f"generated-{i}"
            obs["time_assertions"].reverse()
        self.assertEqual(self.run_score(), before)

    def test_cross_case_not_matched(self):
        self.pred["observations"][0]["case_token"] = "OTHER-SYNTHETIC"
        self.assertEqual(self.run_score()["joint_tp"], 11)

    def test_report_omission_secondary_not_sampling(self):
        self.pred["observations"][0]["time_assertions"].pop()
        result = self.run_score()
        self.assertEqual(result["joint_tp"], 12)
        self.assertEqual(result["full_record_tp"], 11)

    def test_empty_prediction(self):
        self.pred["observations"] = []
        result = self.run_score()
        self.assertIsNone(result["joint_precision"])
        self.assertEqual(result["joint_f1"], 0)
        self.assertEqual(result["missing_observations"], 12)

    def test_empty_both_is_undefined_not_perfect(self):
        self.gold["observations"] = []
        self.gold["identity_pairs"] = []
        self.pred["observations"] = []
        self.pred["event_groups"] = []
        self.assertIsNone(self.run_score()["joint_f1"])

    def test_invalid_pred_not_silently_skipped(self):
        del self.pred["observations"][0]["time_assertions"]
        result = self.run_score()
        self.assertEqual(result["status"], "invalid_output")
        self.assertEqual(result["joint_fn"], 12)

    def test_invalid_output_still_reports_cost(self):
        self.pred["observations"] = None
        self.pred["cost"] = {"attempts": [{"attempt_id": "a", "status": "failed"}]}
        result = self.run_score()
        self.assertEqual(result["status"], "invalid_output")
        self.assertEqual(result["cost"]["calls"], 1)

    def test_unhashable_role_is_invalid_output(self):
        self.pred["observations"][0]["time_assertions"][0]["role"] = []
        self.assertEqual(self.run_score()["status"], "invalid_output")

    def test_duplicate_prediction_id_invalid(self):
        self.pred["observations"][1]["observation_id"] = "expected-1"
        self.assertEqual(self.run_score()["error_code"], "DUPLICATE_OBSERVATION_ID")

    def test_missing_sampling_state_invalid(self):
        self.pred["observations"][4]["time_assertions"].pop(0)
        self.assertEqual(self.run_score()["error_code"], "SAMPLING_STATUS_MISSING")

    def test_boolean_day_invalid(self):
        self.pred["observations"][0]["time_assertions"][0]["relative_day"] = True
        self.assertEqual(self.run_score()["status"], "invalid_output")

    def test_duplicate_gold_row_rejected(self):
        self.gold["observations"][1]["source_refs"] = ["r1"]
        with self.assertRaisesRegex(ValueError, "GOLD_ROW_OWNERSHIP_AMBIGUOUS"):
            self.run_score()

    def test_source_registry_does_not_create_reference(self):
        self.gold["evidence"] = []
        with self.assertRaisesRegex(ValueError, "GOLD_ROW_REFERENCE_INVALID"):
            self.run_score()

    def test_cost_missing_is_unknown(self):
        self.assertIsNone(self.run_score()["cost"]["calls"])

    def test_failed_retry_cost_included(self):
        cost = {"attempts": [
            {"attempt_id": "a", "status": "timeout", "input_tokens": 10, "output_tokens": 2, "amount": .1},
            {"attempt_id": "b", "status": "success", "input_tokens": 20, "output_tokens": 4, "amount": .2},
        ], "wall_seconds": 3, "currency": "USD"}
        result = summarize_cost(cost)
        self.assertEqual((result["calls"], result["failed_calls"], result["input_tokens"], result["output_tokens"]), (2, 1, 30, 6))
        self.assertAlmostEqual(result["amount"], .3)

    def test_partial_cost_not_zero_filled(self):
        result = summarize_cost({"attempts": [{"attempt_id": "a", "status": "failed"}]})
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["input_tokens"])

    def test_negative_cost_rejected(self):
        with self.assertRaisesRegex(ValueError, "COST_VALUE_INVALID"):
            summarize_cost({"attempts": [{"attempt_id": "a", "status": "failed", "input_tokens": -1}]})

    def test_duplicate_attempt_rejected(self):
        a = {"attempt_id": "a", "status": "failed"}
        with self.assertRaisesRegex(ValueError, "COST_ATTEMPT_INVALID"):
            summarize_cost({"attempts": [a, a]})

    def test_aggregate_report_does_not_echo_payload(self):
        self.pred["observations"][0]["value"] = "SYNTHETIC_SENTINEL_DO_NOT_ECHO"
        output = json.dumps(self.run_score())
        self.assertNotIn("SYNTHETIC_SENTINEL", output)
        self.assertNotIn("source_refs", output)
        self.assertNotIn("SYNTHETIC-ONLY", output)


if __name__ == "__main__":
    unittest.main()
