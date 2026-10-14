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


if __name__ == "__main__":
    unittest.main()
