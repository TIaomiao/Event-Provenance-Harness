"""Tests for task-conditioned evidence selection v0.1.

Synthetic records only; no patient material is involved.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_selection as ts  # noqa: E402


def record(record_id, day, clock=None, precision="day", value="10", unit="g/L",
           case="CASE-SYNTHETIC", identity="explicit", **over):
    data = {"record_id": record_id, "case_token": case, "collection_day": day,
            "day_offset": day, "clock": clock, "precision": precision, "value": value,
            "unit": unit, "project_ref": "L1", "result_ref": "L2", "unit_ref": "L3",
            "collection_ref": "L4", "report_ref": "L5", "identity_status": identity}
    data.update(over)
    return data


def plan_for(task, **over):
    plan = {"project": "target analyte", "time_role": "sampling",
            "window": dict(task["spec"]["window"]), "selection": task["spec"]["selection"],
            "scope": task["scope"], "tie_policy": "undetermined",
            "missing_policy": "undetermined"}
    plan.update(over)
    return plan


class TaskSpecTest(unittest.TestCase):
    def test_q1_window_includes_anchor(self):
        task = ts.build_task("Q1", 5)
        self.assertTrue(task["spec"]["window"]["include_to"])
        self.assertFalse(task["spec"]["window"]["include_from"])
        self.assertEqual(task["spec"]["selection"], "latest")

    def test_q2_window_excludes_anchor(self):
        task = ts.build_task("Q2", 5)
        window = task["spec"]["window"]
        self.assertFalse(window["include_from"])
        self.assertFalse(window["include_to"])
        self.assertIsNone(window["to"])
        self.assertEqual(task["spec"]["selection"], "first")

    def test_q3_window_is_closed(self):
        task = ts.build_task("Q3", 3, window=(3, 7))
        window = task["spec"]["window"]
        self.assertTrue(window["include_from"])
        self.assertTrue(window["include_to"])
        self.assertEqual(window["from"], 3)
        self.assertEqual(window["to"], 7)

    def test_unknown_task_is_refused(self):
        with self.assertRaises(ts.SelectionError):
            ts.build_task("Q9", 1)

    def test_anchor_is_explicit_not_inferred(self):
        task = ts.build_task("Q1", 4)
        self.assertEqual(task["anchor_day"], 4)
        self.assertIn("4", task["text"])


class PlanValidationTest(unittest.TestCase):
    def test_missing_field_is_refused_not_defaulted(self):
        task = ts.build_task("Q1", 5)
        plan = plan_for(task)
        del plan["tie_policy"]
        ok, problems = ts.validate_plan(plan)
        self.assertFalse(ok)
        self.assertIn("MISSING_TIE_POLICY", problems)

    def test_every_required_field_is_checked(self):
        for field in ts.PLAN_FIELDS:
            plan = plan_for(ts.build_task("Q1", 5))
            del plan[field]
            ok, problems = ts.validate_plan(plan)
            self.assertFalse(ok, field)
            self.assertTrue(any(problem.startswith("MISSING_") for problem in problems), field)

    def test_invalid_enum_is_refused(self):
        task = ts.build_task("Q1", 5)
        ok, problems = ts.validate_plan(plan_for(task, selection="nearest"))
        self.assertFalse(ok)
        self.assertIn("INVALID_SELECTION:nearest", problems)

    def test_selection_all_requires_two_bounds(self):
        task = ts.build_task("Q3", 3, window=(3, 7))
        plan = plan_for(task)
        plan["window"]["to"] = None
        ok, problems = ts.validate_plan(plan)
        self.assertFalse(ok)
        self.assertIn("SELECTION_ALL_NEEDS_BOTH_BOUNDS", problems)

    def test_inverted_window_is_refused(self):
        task = ts.build_task("Q3", 3, window=(3, 7))
        plan = plan_for(task)
        plan["window"].update({"from": 9, "to": 2})
        ok, problems = ts.validate_plan(plan)
        self.assertFalse(ok)
        self.assertIn("WINDOW_INVERTED", problems)

    def test_execute_refuses_invalid_plan(self):
        result = ts.execute_plan({"selection": "all"}, [record("r1", 1)])
        self.assertEqual(result["status"], "invalid_plan")
        self.assertEqual(result["selected"], [])


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.records = [record("r1", 1), record("r2", 3), record("r3", 5, clock="08:30", precision="minute"),
                        record("r4", 5, clock="16:45", precision="minute"), record("r5", 9)]

    def test_q1_picks_latest_at_or_before_anchor(self):
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected"], ["r4"])

    def test_q1_excludes_later_days(self):
        task = ts.build_task("Q1", 4)
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["selected"], ["r2"])

    def test_q2_picks_first_strictly_after_anchor(self):
        task = ts.build_task("Q2", 5)
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["selected"], ["r5"])

    def test_q3_returns_every_record_in_closed_window(self):
        task = ts.build_task("Q3", 1, window=(1, 5))
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["selected"], ["r1", "r2", "r3", "r4"])

    def test_empty_window_is_empty_not_nearest(self):
        task = ts.build_task("Q3", 1, window=(6, 8))
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["selected"], [])

    def test_single_selection_without_candidates_is_empty(self):
        task = ts.build_task("Q2", 20)
        result = ts.execute_plan(plan_for(task), self.records)
        self.assertEqual(result["status"], "empty")

    def test_day_precision_tie_is_undetermined(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["selected"], [])
        self.assertEqual(sorted(result["candidates"]), ["a", "b"])

    def test_minute_precision_tie_is_resolved_by_clock(self):
        records = [record("a", 5, clock="08:30", precision="minute"),
                   record("b", 5, clock="16:45", precision="minute")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected"], ["b"])

    def test_tie_policy_all_ties_returns_every_tie(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task, tie_policy="all_ties"), records)
        self.assertEqual(sorted(result["selected"]), ["a", "b"])

    def test_incomplete_records_stay_out_of_the_selection(self):
        records = [record("a", 5, value=None), record("b", 3)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["selected"], ["b"])

    def test_incomplete_only_yields_undetermined_under_missing_policy(self):
        records = [record("a", 5, value=None)]
        task = ts.build_task("Q1", 5)
        undetermined = ts.execute_plan(plan_for(task), records)
        skipped = ts.execute_plan(plan_for(task, missing_policy="skip"), records)
        self.assertEqual(undetermined["status"], "undetermined")
        self.assertEqual(skipped["status"], "empty")

    def test_non_explicit_identity_is_not_selectable(self):
        records = [record("a", 5, identity="ambiguous"), record("b", 4)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["selected"], ["b"])


class DayCoordinateTest(unittest.TestCase):
    def test_offsets_are_relative_to_the_case_origin(self):
        records = [{"record_id": "a", "collection_day": 100}, {"record_id": "b", "collection_day": 103}]
        first = ts.day_coordinate(records, 100)
        second = ts.day_coordinate(records, 90)
        self.assertEqual([r["day_offset"] for r in first], [0, 3])
        self.assertEqual([r["day_offset"] for r in second], [10, 13])

    def test_unknown_day_stays_none(self):
        out = ts.day_coordinate([{"record_id": "a", "collection_day": None}], 0)
        self.assertIsNone(out[0]["day_offset"])


class ScoringTest(unittest.TestCase):
    def setUp(self):
        self.records = [record("r1", 1), record("r2", 3), record("r3", 5)]
        self.task = ts.build_task("Q1", 3)
        self.reference = ["r2"]

    def test_exact_match_and_status(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": [{"record_id": "r2"}]},
                          self.records, self.reference)
        self.assertTrue(result["set_exact_match"])
        self.assertTrue(result["status_ok"])
        self.assertTrue(result["equivalent_answer"])

    def test_bare_id_list_scores_the_same(self):
        one = ts.score(self.task, {"status": "ok", "selected_records": ["r2"]},
                       self.records, self.reference)
        two = ts.score(self.task, {"status": "ok", "selected_records": [{"record_id": "r2",
                                                                        "extra": "noise"}]},
                       self.records, self.reference)
        self.assertEqual(one["equivalent_answer"], two["equivalent_answer"])

    def test_partial_selection_reports_precision_and_recall(self):
        task = ts.build_task("Q3", 1, window=(1, 5))
        result = ts.score(task, {"status": "ok", "selected_records": ["r1", "r2"]},
                          self.records, ["r1", "r2", "r3"])
        self.assertAlmostEqual(result["precision"], 1.0)
        self.assertAlmostEqual(result["recall"], 2 / 3)

    def test_window_violation_is_counted(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["r3"]},
                          self.records, self.reference)
        self.assertEqual(result["window_violation"], 1)
        self.assertFalse(result["set_exact_match"])

    def test_unknown_id_counts_as_scope_violation(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["ghost"]},
                          self.records, self.reference)
        self.assertEqual(result["scope_violation"], 1)
        self.assertIsNone(result["joint_fields_ok"])

    def test_empty_reference_expects_empty_status(self):
        task = ts.build_task("Q2", 20)
        correct = ts.score(task, {"status": "empty", "selected_records": []}, self.records, [])
        wrong = ts.score(task, {"status": "ok", "selected_records": ["r1"]}, self.records, [])
        self.assertTrue(correct["empty_handling"])
        self.assertTrue(correct["status_ok"])
        self.assertFalse(wrong["status_ok"])

    def test_joint_fields_checked_on_selected_records(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["r2"]},
                          self.records, self.reference)
        self.assertTrue(result["joint_fields_ok"])

    def test_format_failure_is_recorded_separately(self):
        result = ts.score(self.task, None, self.records, self.reference)
        self.assertEqual(result["status"], "format_failure")
        self.assertIsNone(result["set_exact_match"])

    def test_plan_problems_are_attached(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["r2"]},
                          self.records, self.reference, plan={"selection": "latest"}, plan_ok=False)
        self.assertIn("MISSING_PROJECT", result["plan_problems"])

    def test_reference_matches_the_executor(self):
        for task in (ts.build_task("Q1", 3), ts.build_task("Q2", 3),
                     ts.build_task("Q3", 1, window=(1, 5))):
            self.assertEqual(ts.reference_for_task(task, self.records),
                             ts.execute_plan(plan_for(task), self.records)["selected"])


class RecordViewTest(unittest.TestCase):
    def test_view_has_a_header_and_one_line_per_record(self):
        records = [record("r1", 1), record("r2", 2)]
        lines = ts.record_view_lines(records).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertIn("record_id", lines[0])
        for field in ts.RECORD_FIELDS:
            self.assertIn(field, lines[0])


if __name__ == "__main__":
    unittest.main()
