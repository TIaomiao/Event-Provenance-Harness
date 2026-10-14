"""Tests for the baseline v1 probe: budget, resume, fingerprints, summary.

Synthetic material only; no patient data is involved.  The transport is injected, so no
network call is made and no cost is incurred.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import necessity_probe as np  # noqa: E402
import task_selection as ts  # noqa: E402

PRICE = (0.3, 1.5)


def record(record_id, day, value, clock=None, precision="day"):
    return {"record_id": record_id, "case_token": "CASE-SYNTHETIC", "day_offset": day,
            "clock": clock, "precision": precision, "value": value, "unit": "g/L",
            "time_role": "collection", "project_name": "HGB", "project_ref": "L1",
            "result_ref": "L2", "unit_ref": "L3", "collection_ref": "L4",
            "report_ref": "L5", "identity_status": "explicit"}


def contract(**over):
    base = {"project": "HGB", "time_role": "collection",
            "window": {"from": None, "to": 0, "include_from": False, "include_to": True},
            "selection": "latest", "tie_policy": "undetermined",
            "missing_policy": "undetermined",
            "required_fields": ["value", "unit", "time", "source"],
            "display_precision": "day", "source_mode": "supported"}
    base.update(over)
    return base


class ProbeTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.records = [record("r1", 0, 5.0)]
        self.bundle = {
            "probe_version": np.VERSION,
            "scorer_sha256": np.scorer_fingerprint()["sha256"],
            "tasks": [{
                "task_id": "t1",
                "instruction": "取相对日 0 当天或之前最近一次",
                "contract": contract(),
                "reference": {"status": "ok", "selected": ["r1"], "candidates": []},
                "records": self.records,
                "context": {"A_raw_tools": "L1 HGB 5.0 g/L",
                            "B_extracted_sql": "r1 HGB 5.0 g/L day 0"},
            }],
        }
        self.bundle_path = self.tmp / "bundle.json"
        self.bundle_path.write_text(json.dumps(self.bundle, ensure_ascii=False),
                                    encoding="utf-8")
        self.ledger = self.tmp / "ledger.jsonl"
        self.responses = self.tmp / "responses"

    def _transport(self, calls, raw=None):
        def call(**kwargs):
            calls.append(kwargs)
            return {"status": "ok", "model_returned": "synthetic-model",
                    "tokens_in": 1000, "tokens_out": 100,
                    "raw": raw or json.dumps(
                        {"status": "ok", "selected": [
                            {"record_id": "r1", "value": 5.0, "unit": "g/L",
                             "day_offset": 0, "source_refs": ["L1"]}]})}
        return call

    def test_dry_run_makes_no_calls_and_reports_the_plan(self):
        calls = []
        report = np.run(self.bundle_path, self.responses, self.ledger,
                        self._transport(calls), model="m", price_per_million=PRICE,
                        dry_run=True)
        self.assertTrue(report["dry_run"])
        self.assertEqual(calls, [])
        self.assertEqual(report["planned_calls"], 2)

    def test_run_calls_the_transport_once_per_arm_and_records_the_ledger(self):
        calls = []
        report = np.run(self.bundle_path, self.responses, self.ledger,
                        self._transport(calls), model="m", price_per_million=PRICE)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(report["runs"]), 2)
        rows = np.load_ledger(self.ledger)
        self.assertEqual({row["arm"] for row in rows}, set(np.ARMS))
        for row in rows:
            self.assertEqual(row["model_returned"], "synthetic-model")
            self.assertGreater(row["cost_usd"], 0)

    def test_resume_skips_completed_items_and_does_not_recharge(self):
        calls = []
        np.run(self.bundle_path, self.responses, self.ledger,
               self._transport(calls), model="m", price_per_million=PRICE)
        self.assertEqual(len(calls), 2)
        report = np.run(self.bundle_path, self.responses, self.ledger,
                        self._transport(calls), model="m", price_per_million=PRICE)
        self.assertEqual(len(calls), 2, "no new call on resume")
        self.assertEqual(report["planned_calls"], 0)
        self.assertEqual(report["already_done"], 2)

    def test_budget_stops_before_overspending(self):
        calls = []
        report = np.run(self.bundle_path, self.responses, self.ledger,
                        self._transport(calls), model="m", price_per_million=PRICE,
                        max_usd=0.000001)
        self.assertEqual(report.get("stopped"), "BUDGET")
        self.assertEqual(calls, [], "nothing is called once the budget is short")

    def test_a_bundle_from_another_scorer_is_refused_before_any_call(self):
        self.bundle["scorer_sha256"] = "0" * 64
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")
        calls = []
        with self.assertRaises(np.ProbeError):
            np.run(self.bundle_path, self.responses, self.ledger,
                   self._transport(calls), model="m", price_per_million=PRICE)
        self.assertEqual(calls, [])

    def test_a_partial_contract_is_refused_before_any_call(self):
        self.bundle["tasks"][0]["contract"] = {"display_precision": "day"}
        self.bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")
        calls = []
        with self.assertRaises(ts.SelectionError):
            np.run(self.bundle_path, self.responses, self.ledger,
                   self._transport(calls), model="m", price_per_million=PRICE)
        self.assertEqual(calls, [])

    def test_rescore_rebuilds_the_summary_without_network(self):
        np.run(self.bundle_path, self.responses, self.ledger,
               self._transport(calls := []), model="m", price_per_million=PRICE)
        summary = np.rescore(self.bundle_path, self.responses, self.tmp / "summary.json")
        self.assertEqual(summary["items"], 2)
        for arm in np.ARMS:
            self.assertEqual(summary["by_arm"][arm]["task_success"], 1)
        self.assertTrue((self.tmp / "summary.json").is_file())

    def test_missing_responses_are_counted_as_failures_not_dropped(self):
        summary = np.rescore(self.bundle_path, self.responses, None)
        self.assertEqual(summary["items"], 2)
        self.assertEqual(len(summary["missing_responses"]), 2)
        for arm in np.ARMS:
            self.assertEqual(summary["by_arm"][arm]["task_success"], 0)

    def test_a_malformed_response_is_a_scored_failure_not_a_crash(self):
        np.run(self.bundle_path, self.responses, self.ledger,
               self._transport([], raw="not json at all"), model="m",
               price_per_million=PRICE)
        summary = np.rescore(self.bundle_path, self.responses, None)
        for arm in np.ARMS:
            self.assertEqual(summary["by_arm"][arm]["task_success"], 0)

    def test_estimate_cost_uses_the_declared_price(self):
        self.assertAlmostEqual(np.estimate_cost(1_000_000, 1_000_000, PRICE), 1.8, places=6)


class RetrievalToolTest(unittest.TestCase):
    """Arm A gets a tool the program actually runs, not a promise in the prompt."""

    def test_retrieval_keeps_the_answer_bearing_line_and_shrinks_the_input(self):
        context = "\n".join(["填充行 %d" % i for i in range(200)] +
                             ["L77 HGB 血红蛋白 7.0 g/L"])
        text, kept = np.retrieve_lines(context, "取血红蛋白最近一次", top_k=5)
        self.assertIn("L77", text)
        self.assertLess(kept, 200)

    def test_retrieval_without_terms_returns_the_context_unchanged(self):
        context = "L1 HGB 5.0 g/L"
        text, kept = np.retrieve_lines(context, "")
        self.assertEqual(text, context)

    def test_the_engine_runs_retrieval_for_arm_a_and_records_it(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        rec = record("r1", 0, 5.0)
        contract = {"project": "HGB", "time_role": "collection",
                    "window": {"from": None, "to": 0, "include_from": False,
                               "include_to": True},
                    "selection": "latest", "tie_policy": "undetermined",
                    "missing_policy": "undetermined",
                    "required_fields": ["value", "unit", "time", "source"],
                    "display_precision": "day", "source_mode": "supported"}
        long_context = "\n".join(["噪声 %d" % i for i in range(400)] + ["L9 HGB 血红蛋白 5.0"])
        bundle = {"probe_version": np.VERSION,
                  "scorer_sha256": np.scorer_fingerprint()["sha256"],
                  "a_retrieval_tool": True,
                  "tasks": [{"task_id": "t1", "instruction": "取血红蛋白最近一次",
                             "contract": contract,
                             "reference": {"status": "ok", "selected": ["r1"],
                                           "candidates": []},
                             "records": [rec],
                             "context": {"A_raw_tools": long_context,
                                         "B_extracted_sql": "r1 HGB 5.0 day 0"}}]}
        bundle_path = tmp / "b.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        seen = {}

        def transport(**kwargs):
            seen["user"] = kwargs["messages"][1]["content"]
            return {"status": "ok", "model_returned": "synthetic", "tokens_in": 10,
                    "tokens_out": 5, "raw": json.dumps(
                        {"status": "ok", "selected": [
                            {"record_id": "r1", "value": 5.0, "unit": "g/L",
                             "day_offset": 0, "source_refs": ["L1"]}]})}

        report = np.run(bundle_path, tmp / "resp", tmp / "ledger.jsonl", transport,
                        model="m", price_per_million=PRICE)
        self.assertEqual(len(report["runs"]), 2)
        arm_a = [r for r in report["runs"] if r["arm"] == "A_raw_tools"][0]
        self.assertIsNotNone(arm_a["retrieved_lines"], "the tool ran for arm A")
        self.assertLess(len(seen["user"]), len(long_context), "the input was actually cut")


class RunIdentityTest(unittest.TestCase):
    """Resuming must not silently reuse answers produced by a different experiment."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.records = [record("r1", 0, 5.0)]
        self.bundle = {
            "probe_version": np.VERSION,
            "scorer_sha256": np.scorer_fingerprint()["sha256"],
            "tasks": [{"task_id": "t1", "instruction": "take the latest",
                       "contract": contract(),
                       "reference": {"status": "ok", "selected": ["r1"], "candidates": []},
                       "records": self.records,
                       "context": {"A_raw_tools": "L1 HGB 5.0 g/L",
                                   "B_extracted_sql": "r1 HGB 5.0 g/L day 0"}}]}
        self.bundle_path = self.tmp / "bundle.json"
        self.bundle_path.write_text(json.dumps(self.bundle, ensure_ascii=False),
                                    encoding="utf-8")
        self.calls = []

    def _transport(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "ok", "model_returned": "synthetic", "tokens_in": 100,
                "tokens_out": 10,
                "raw": json.dumps({"status": "ok", "selected": [
                    {"record_id": "r1", "value": 5.0, "unit": "g/L", "day_offset": 0,
                     "source_refs": ["L1"]}]})}

    def _run(self, model):
        return np.run(self.bundle_path, self.tmp / "resp", self.tmp / "ledger.jsonl",
                      self._transport, model=model, price_per_million=PRICE,
                      run_dir=self.tmp / "run")

    def test_swapping_the_model_is_refused_before_any_call(self):
        self._run("model-one")
        self.assertEqual(len(self.calls), 2)
        with self.assertRaises(np.RunIdentityMismatch):
            self._run("model-two")
        self.assertEqual(len(self.calls), 2, "the refused run made no call")

    def test_the_refusal_names_what_differed(self):
        self._run("model-one")
        try:
            self._run("model-two")
        except np.RunIdentityMismatch as error:
            self.assertIn("model", str(error))
        else:
            self.fail("a different model must be refused")

    def test_the_same_identity_resumes_without_calling_again(self):
        self._run("model-one")
        report = self._run("model-one")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(report["planned_calls"], 0)
        self.assertEqual(report["identity_state"], "matched")

    def test_a_deleted_ledger_is_rebuilt_from_responses_without_calling(self):
        self._run("model-one")
        self.assertEqual(len(self.calls), 2)
        (self.tmp / "ledger.jsonl").unlink()
        report = self._run("model-one")
        self.assertEqual(len(self.calls), 2, "recovery must not call again")
        self.assertEqual(report["recovered_from_response"], 2)
        self.assertEqual(report["planned_calls"], 0)
        self.assertEqual(len(np.load_ledger(self.tmp / "ledger.jsonl")), 2)

    def test_a_request_without_a_saved_result_is_not_treated_as_free(self):
        def failing(**kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("connection dropped after the request was sent")

        report = np.run(self.bundle_path, self.tmp / "resp", self.tmp / "ledger.jsonl",
                        failing, model="model-one", price_per_million=PRICE,
                        run_dir=self.tmp / "run")
        rows = np.load_ledger(self.tmp / "ledger.jsonl")
        self.assertTrue(all(row["status"] == "result_unknown" for row in rows))
        self.assertTrue(all(row["cost_usd"] is None for row in rows),
                        "an unsaved result must not be recorded as free")
        self.assertEqual(report["unknown_cost_rows"], 2)

    def test_an_attempted_unknown_row_is_not_retried_as_if_unpaid(self):
        def failing(**kwargs):
            self.calls.append(kwargs)
            raise RuntimeError("boom")

        np.run(self.bundle_path, self.tmp / "resp", self.tmp / "ledger.jsonl", failing,
               model="model-one", price_per_million=PRICE, run_dir=self.tmp / "run")
        before = len(self.calls)
        report = np.run(self.bundle_path, self.tmp / "resp", self.tmp / "ledger.jsonl",
                        self._transport, model="model-one", price_per_million=PRICE,
                        run_dir=self.tmp / "run")
        self.assertEqual(len(self.calls), before, "unknown rows are not silently retried")
        self.assertEqual(report["planned_calls"], 0)


class MatcherTest(unittest.TestCase):
    """The matcher links an answer to a record; it never invents the answer."""

    def _records(self):
        return [{"record_id": "a", "value": 119.0, "unit": "g/L",
                 "collection_day_offset": 0, "collection_ref": "L2223",
                 "result_ref": "L2160", "alias_refs": ["L2159"]},
                {"record_id": "b", "value": 119.0, "unit": "g/L",
                 "collection_day_offset": 5, "collection_ref": "L9",
                 "result_ref": "L10", "alias_refs": []}]

    def test_no_candidate_leaves_the_item_unmatched_and_the_prediction_intact(self):
        items = [{"value": 999.0, "unit": "g/L", "day_offset": 0}]
        resolved, unresolved, ambiguous = np.resolve_items(items, self._records(),
                                                           "collection")
        self.assertEqual(unresolved, 1)
        self.assertEqual(ambiguous, 0)
        self.assertNotIn("record_id", resolved[0],
                         "a prediction with no candidate is kept, not dropped")

    def test_one_candidate_is_linked(self):
        records = [self._records()[1]]
        items = [{"value": 119.0, "unit": "g/L", "day_offset": 5}]
        resolved, unresolved, ambiguous = np.resolve_items(items, records, "collection")
        self.assertEqual((unresolved, ambiguous), (0, 0))
        self.assertEqual(resolved[0]["record_id"], "b")

    def test_several_candidates_are_narrowed_by_the_answers_own_day(self):
        items = [{"value": 119.0, "unit": "g/L", "day_offset": 5}]
        resolved, unresolved, ambiguous = np.resolve_items(items, self._records(),
                                                           "collection")
        self.assertEqual((unresolved, ambiguous), (0, 0))
        self.assertEqual(resolved[0]["record_id"], "b")

    def test_several_candidates_are_narrowed_by_the_answers_own_source(self):
        items = [{"value": 119.0, "unit": "g/L", "source_refs": ["L10"]}]
        resolved, unresolved, ambiguous = np.resolve_items(items, self._records(),
                                                           "collection")
        self.assertEqual((unresolved, ambiguous), (0, 0))
        self.assertEqual(resolved[0]["record_id"], "b")

    def test_still_several_is_ambiguous_and_never_the_first_candidate(self):
        records = [dict(self._records()[0]), dict(self._records()[1])]
        items = [{"value": 119.0, "unit": "g/L"}]
        resolved, unresolved, ambiguous = np.resolve_items(items, records, "collection")
        self.assertEqual(ambiguous, 1)
        self.assertEqual(unresolved, 0)
        self.assertNotIn("record_id", resolved[0],
                         "an ambiguous item must not be silently pinned to the first")

    def test_a_non_integer_day_offset_cannot_narrow_and_yields_ambiguity(self):
        items = [{"value": 119.0, "unit": "g/L", "day_offset": 3.9}]
        resolved, _, ambiguous = np.resolve_items(items, self._records(), "collection")
        self.assertEqual(ambiguous, 1)
        self.assertNotIn("record_id", resolved[0])

    def test_a_string_id_is_passed_through(self):
        resolved, unresolved, ambiguous = np.resolve_items(["a"], self._records(),
                                                           "collection")
        self.assertEqual(resolved, ["a"])
        self.assertEqual((unresolved, ambiguous), (0, 0))


class ExecutorTest(unittest.TestCase):
    """The plan comes from the model; the selection is done by code; the answer by code."""

    def _records(self):
        return [{"record_id": "a", "value": 119.0, "unit": "g/L",
                 "collection_day_offset": 0, "collection_clock": "17:16:14",
                 "project_ref": "L1", "result_ref": "L2", "unit_ref": "L3",
                 "collection_ref": "L4", "report_ref": "L5"},
                {"record_id": "b", "value": 114.0, "unit": "g/L",
                 "collection_day_offset": 5, "collection_clock": "06:33:31",
                 "project_ref": "L9", "result_ref": "L10", "unit_ref": "L11",
                 "collection_ref": "L12", "report_ref": "L13"}]

    def test_a_valid_plan_executes_and_the_answer_is_built_from_the_records(self):
        plan = {"project": "HGB", "time_role": "collection", "cutoff_day": 0,
                "selection": "latest"}
        ok, problems = np.validate_plan(plan, contract())
        self.assertTrue(ok)
        self.assertEqual(problems, [])
        ids, execute_problems = np.execute_plan(plan, self._records(), contract())
        self.assertEqual(ids, ["a"])
        self.assertEqual(execute_problems, [])
        answer = np.build_answer(ids, self._records(), contract())
        self.assertEqual(answer["status"], "ok")
        self.assertEqual(answer["selected_records"][0]["value"], 119.0)
        self.assertIn("L2", answer["selected_records"][0]["source_refs"])

    def test_a_bad_selection_value_is_a_plan_error(self):
        plan = {"project": "HGB", "time_role": "collection", "cutoff_day": 0,
                "selection": "nearest"}
        ok, problems = np.validate_plan(plan, contract())
        self.assertFalse(ok)
        self.assertIn("plan_bad_selection", problems)

    def test_a_missing_plan_is_a_plan_error(self):
        ok, problems = np.validate_plan(None, contract())
        self.assertFalse(ok)
        self.assertIn("plan_missing", problems)

    def test_free_text_instead_of_a_plan_is_a_plan_error(self):
        self.assertIsNone(np.parse_plan("the latest value is 119 g/L"))

    def test_a_well_formed_but_wrong_plan_is_followed_not_replaced(self):
        """The validator checks shape only; it never swaps in the right plan."""
        plan = {"project": "HGB", "time_role": "collection", "cutoff_day": 5,
                "selection": "latest"}
        ok, _ = np.validate_plan(plan, contract())
        self.assertTrue(ok, "a plan can be well formed and still wrong")
        ids, _ = np.execute_plan(plan, self._records(), contract())
        self.assertEqual(ids, ["b"], "the wrong plan is executed, not corrected")

    def test_an_empty_window_is_an_execution_error(self):
        plan = {"project": "HGB", "time_role": "collection", "cutoff_day": 0,
                "selection": "latest"}
        records = [record for record in self._records() if record["record_id"] != "a"]
        ids, problems = np.execute_plan(plan, records, contract())
        self.assertEqual(ids, [])
        self.assertIn("execute_no_records_in_window", problems)

    def test_a_record_without_a_time_role_is_not_selectable(self):
        plan = {"project": "HGB", "time_role": "report", "cutoff_day": 9,
                "selection": "all"}
        ids, problems = np.execute_plan(plan, self._records(), contract())
        self.assertEqual(ids, [])
        self.assertIn("execute_no_records_in_window", problems)

    def test_the_answer_carries_the_two_time_roles_and_the_anchors(self):
        ids, _ = np.execute_plan({"project": "HGB", "time_role": "collection",
                                  "cutoff_day": 9, "selection": "all"},
                                 self._records(), contract())
        answer = np.build_answer(ids, self._records(), contract())
        self.assertEqual(len(answer["selected_records"]), 2)
        for item in answer["selected_records"]:
            self.assertIn("collection_day_offset", item)
            self.assertTrue(item["source_refs"])


if __name__ == "__main__":
    unittest.main()
