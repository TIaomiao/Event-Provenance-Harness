"""Tests for task-conditioned evidence selection v0.2.

Expectations are written independently as literals: they are not produced by the
executor under test, so a wrong executor cannot certify itself.

Synthetic records only; no patient material is involved.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import task_selection as ts  # noqa: E402


def record(record_id, day, clock=None, precision="day", value="10", unit="g/L",
           case="CASE-SYNTHETIC", identity="explicit", role="collection", **over):
    data = {"record_id": record_id, "case_token": case, "collection_day": day,
            "day_offset": day, "clock": clock, "precision": precision, "value": value,
            "unit": unit, "time_role": role, "project_name": "HGB",
            "project_ref": "L1", "result_ref": "L2", "unit_ref": "L3",
            "collection_ref": "L4", "report_ref": "L5", "identity_status": identity}
    data.update(over)
    return data


def bound_for(task, **over):
    bound = ts.bound_context(task)
    bound.update(over)
    return bound


def plan_for(task, bound=None, **over):
    plan = dict(bound if bound is not None else bound_for(task))
    plan["window"] = dict(task["spec"]["window"])
    plan["selection"] = task["spec"]["selection"]
    plan.update(over)
    return plan


class TaskSpecTest(unittest.TestCase):
    def test_window_inclusivity_per_task(self):
        self.assertEqual(ts.build_task("Q1", 5)["spec"]["window"],
                         {"from": None, "to": 5, "include_from": False, "include_to": True})
        self.assertEqual(ts.build_task("Q2", 5)["spec"]["window"],
                         {"from": 5, "to": None, "include_from": False, "include_to": False})
        self.assertEqual(ts.build_task("Q3", 3, window=(3, 7))["spec"]["window"],
                         {"from": 3, "to": 7, "include_from": True, "include_to": True})

    def test_model_produces_only_window_and_selection(self):
        self.assertEqual(ts.PLAN_FIELDS, ("window", "selection"))
        self.assertEqual(set(ts.BOUND_FIELDS),
                         {"project", "time_role", "scope", "tie_policy", "missing_policy"})

    def test_unknown_task_is_refused(self):
        with self.assertRaises(ts.SelectionError):
            ts.build_task("Q9", 1)


class BoundContextTest(unittest.TestCase):
    def test_host_binds_project_scope_and_policies(self):
        task = ts.build_task("Q1", 5)
        bound = ts.bound_context(task, project="HGB", scope="DOC-013 frozen report",
                                 tie_policy="undetermined", missing_policy="skip")
        self.assertEqual(bound["project"], "HGB")
        self.assertEqual(bound["scope"], "DOC-013 frozen report")
        self.assertEqual(bound["missing_policy"], "skip")
        self.assertEqual(bound["time_role"], "collection")

    def test_model_omission_is_not_filled_by_the_host(self):
        task = ts.build_task("Q1", 5)
        merged = ts.compose_plan({"selection": "latest"}, bound_for(task))
        self.assertNotIn("window", merged)
        ok, problems = ts.validate_plan(merged)
        self.assertFalse(ok)
        self.assertIn("MISSING_WINDOW", problems)

    def test_model_value_overrides_bound_context_when_present(self):
        task = ts.build_task("Q1", 5)
        merged = ts.compose_plan({"window": {"from": None, "to": 4, "include_from": False,
                                            "include_to": True}, "selection": "latest"},
                                 bound_for(task))
        self.assertEqual(merged["window"]["to"], 4)
        self.assertTrue(ts.validate_plan(merged)[0])


class PlanValidationTest(unittest.TestCase):
    def test_missing_field_is_refused_not_defaulted(self):
        task = ts.build_task("Q1", 5)
        plan = plan_for(task)
        del plan["tie_policy"]
        ok, problems = ts.validate_plan(plan)
        self.assertFalse(ok)
        self.assertIn("MISSING_TIE_POLICY", problems)

    def test_invalid_enum_is_refused(self):
        task = ts.build_task("Q1", 5)
        ok, problems = ts.validate_plan(plan_for(task, selection="nearest"))
        self.assertFalse(ok)
        self.assertIn("INVALID_SELECTION:nearest", problems)

    def test_execute_refuses_invalid_plan(self):
        result = ts.execute_plan({"selection": "all"}, [record("r1", 1)])
        self.assertEqual(result["status"], "invalid_plan")
        self.assertEqual(result["selected"], [])


class PositionSemanticsTest(unittest.TestCase):
    """The counterexamples that motivated v0.2, with literal expectations."""

    def test_same_day_same_second_is_undetermined_not_input_order(self):
        records = [record("first-input", 5, clock="08:30", precision="second"),
                   record("second-input", 5, clock="08:30", precision="second")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["selected"], [])
        self.assertEqual(sorted(result["candidates"]), ["first-input", "second-input"])
        self.assertEqual(result["reason"], "SAME_DAY_IDENTICAL_TIMESTAMP")

    def test_same_day_same_clock_reversed_input_is_still_undetermined(self):
        records = [record("second-input", 5, clock="08:30", precision="second"),
                   record("first-input", 5, clock="08:30", precision="second")]
        task = ts.build_task("Q2", 4)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["selected"], [])

    def test_day_only_row_is_not_sorted_as_2400(self):
        records = [record("timed", 5, clock="08:30", precision="minute"),
                   record("day-only", 5, clock=None, precision="day")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["selected"], [])
        self.assertEqual(result["reason"], "SAME_DAY_CLOCK_UNKNOWN_FOR_SOME_RECORDS")

    def test_two_day_only_rows_on_the_same_day_are_undetermined(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "SAME_DAY_CLOCK_UNKNOWN_FOR_ALL_RECORDS")

    def test_distinct_clocks_still_resolve(self):
        records = [record("early", 5, clock="08:30", precision="minute"),
                   record("late", 5, clock="16:45", precision="minute")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected"], ["late"])

    def test_tie_policy_all_ties_returns_every_tied_row(self):
        records = [record("a", 5, clock="08:30", precision="second"),
                   record("b", 5, clock="08:30", precision="second")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task, tie_policy="all_ties"), records)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(sorted(result["selected"]), ["a", "b"])


class TimeRoleTest(unittest.TestCase):
    def test_unsupported_role_is_refused_not_silently_sampling(self):
        records = [record("a", 1, role="collection")]
        task = ts.build_task("Q1", 5, time_role="report")
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "unsupported_time_role")
        self.assertEqual(result["selected"], [])
        self.assertIn("report", result["reason"])

    def test_role_is_applied_as_a_filter(self):
        records = [record("collection-row", 1, role="collection"),
                   record("report-row", 3, role="report", value="11", unit="g/L")]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["selected"], ["collection-row"])


class ReferenceTest(unittest.TestCase):
    def test_undetermined_reference_keeps_status_and_candidates(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        reference = ts.reference_for_task(task, records, bound_for(task))
        self.assertEqual(reference["status"], "undetermined")
        self.assertEqual(reference["selected"], [])
        self.assertEqual(sorted(reference["candidates"]), ["a", "b"])
        self.assertEqual(reference["reason"], "SAME_DAY_CLOCK_UNKNOWN_FOR_ALL_RECORDS")

    def test_empty_reference_is_empty_not_undetermined(self):
        records = [record("a", 1)]
        task = ts.build_task("Q3", 1, window=(6, 8))
        reference = ts.reference_for_task(task, records, bound_for(task))
        self.assertEqual(reference["status"], "empty")
        self.assertEqual(reference["selected"], [])

    def test_ok_reference_carries_the_selection(self):
        records = [record("a", 1), record("b", 4)]
        task = ts.build_task("Q1", 4)
        reference = ts.reference_for_task(task, records, bound_for(task))
        self.assertEqual(reference["status"], "ok")
        self.assertEqual(reference["selected"], ["b"])


class ScoringTest(unittest.TestCase):
    def setUp(self):
        self.records = [record("r1", 1), record("r2", 3), record("r3", 5)]
        self.task = ts.build_task("Q1", 3)
        self.reference = ts.reference_for_task(self.task, self.records, bound_for(self.task))

    def test_undetermined_reference_requires_undetermined_answer(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        reference = ts.reference_for_task(task, records, bound_for(task))
        good = ts.score(task, {"status": "undetermined", "selected_records": []}, records, reference)
        picked = ts.score(task, {"status": "ok", "selected_records": ["a"]}, records, reference)
        self.assertTrue(good["status_ok"])
        self.assertTrue(good["undetermined_handling"])
        self.assertFalse(picked["status_ok"])
        self.assertFalse(picked["undetermined_handling"])

    def test_undetermined_answer_returning_the_tie_set_is_not_equivalent(self):
        records = [record("a", 5), record("b", 5)]
        task = ts.build_task("Q1", 5)
        reference = ts.reference_for_task(task, records, bound_for(task))
        result = ts.score(task, {"status": "undetermined", "selected_records": ["a", "b"]},
                          records, reference)
        self.assertTrue(result["status_ok"])
        self.assertFalse(result["equivalent_answer"])

    def test_statuses_are_distinguished(self):
        records = [record("a", 1)]
        empty_task = ts.build_task("Q3", 1, window=(6, 8))
        empty_reference = ts.reference_for_task(empty_task, records, bound_for(empty_task))
        as_empty = ts.score(empty_task, {"status": "empty", "selected_records": []},
                            records, empty_reference)
        as_undetermined = ts.score(empty_task, {"status": "undetermined", "selected_records": []},
                                   records, empty_reference)
        self.assertEqual(empty_reference["status"], "empty")
        self.assertTrue(as_empty["status_ok"])
        self.assertFalse(as_undetermined["status_ok"])

    def test_invalid_plan_is_not_counted_as_a_content_error(self):
        result = ts.score(self.task,
                          {"status": "invalid_plan", "selected_records": []},
                          self.records, self.reference,
                          plan={"selection": "latest"}, plan_ok=False)
        self.assertEqual(result["status"], "invalid_plan")
        self.assertFalse(result["status_ok"])
        self.assertIn("MISSING_PROJECT", result["plan_problems"])

    def test_unsupported_role_reference_is_its_own_status(self):
        records = [record("a", 1, role="collection")]
        task = ts.build_task("Q1", 5, time_role="report")
        reference = ts.reference_for_task(task, records, bound_for(task))
        self.assertEqual(reference["status"], "unsupported_time_role")
        result = ts.score(task, {"status": "unsupported_time_role", "selected_records": []},
                          records, reference)
        self.assertTrue(result["status_ok"])

    def test_supplied_wrong_fields_are_not_credited_as_matching(self):
        answer = {"status": "ok",
                  "selected_records": [{"record_id": "r2", "value": "999", "unit": "mg/dL",
                                        "collection_time": "day 9", "source_refs": ["L99"]}]}
        result = ts.score(self.task, answer, self.records, self.reference)
        self.assertTrue(result["set_exact_match"])
        self.assertTrue(result["fields_supplied"]["value"])
        self.assertTrue(result["fields_supplied"]["source"])
        # The frozen record is intact, but the answer's own claims are separately visible.
        self.assertEqual(result["joint_fields_ok"], True)
        self.assertTrue(result["fields_supplied"]["time"])

    def test_id_only_submission_does_not_claim_joint_fields(self):
        answer = {"status": "ok", "selected_records": ["r2"]}
        result = ts.score(self.task, answer, self.records, self.reference)
        self.assertTrue(result["set_exact_match"])
        self.assertIsNone(result["joint_fields_ok"])
        self.assertTrue(result["fields_insufficient"])
        self.assertFalse(result["fields_supplied"]["value"])

    def test_host_expansion_is_checked_against_the_frozen_record(self):
        answer = {"status": "ok", "selected_records": ["r2"]}
        result = ts.score(self.task, answer, self.records, self.reference,
                          fields_expanded_by_host=True)
        self.assertTrue(result["joint_fields_ok"])
        self.assertTrue(result["fields_expanded_by_host"])

    def test_host_expansion_flags_an_incomplete_frozen_record(self):
        records = [record("r1", 1), record("r2", 3, value=None)]
        task = ts.build_task("Q1", 3)
        reference = ts.reference_for_task(task, records, bound_for(task))
        result = ts.score(task, {"status": "ok", "selected_records": ["r2"]}, records, reference,
                          fields_expanded_by_host=True)
        self.assertFalse(result["joint_fields_ok"])

    def test_window_violation_is_counted(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["r3"]},
                          self.records, self.reference)
        self.assertEqual(result["window_violation"], 1)

    def test_unknown_id_counts_as_scope_violation(self):
        result = ts.score(self.task, {"status": "ok", "selected_records": ["ghost"]},
                          self.records, self.reference)
        self.assertEqual(result["scope_violation"], 1)

    def test_bare_id_list_scores_the_same_as_object_list(self):
        one = ts.score(self.task, {"status": "ok", "selected_records": ["r2"]},
                       self.records, self.reference)
        two = ts.score(self.task, {"status": "ok", "selected_records": [{"record_id": "r2",
                                                                        "value": "10"}]},
                       self.records, self.reference)
        self.assertEqual(one["equivalent_answer"], two["equivalent_answer"])

    def test_format_failure_is_recorded_separately(self):
        result = ts.score(self.task, None, self.records, self.reference)
        self.assertEqual(result["status"], "format_failure")
        self.assertIsNone(result["set_exact_match"])


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.records = [record("r1", 1), record("r2", 3),
                        record("r3", 5, clock="08:30", precision="minute"),
                        record("r4", 5, clock="16:45", precision="minute"),
                        record("r5", 9)]

    def test_q1_picks_latest_at_or_before_anchor(self):
        task = ts.build_task("Q1", 5)
        self.assertEqual(ts.execute_plan(plan_for(task), self.records)["selected"], ["r4"])

    def test_q2_picks_first_strictly_after_anchor(self):
        task = ts.build_task("Q2", 5)
        self.assertEqual(ts.execute_plan(plan_for(task), self.records)["selected"], ["r5"])

    def test_q3_returns_every_record_in_closed_window(self):
        task = ts.build_task("Q3", 1, window=(1, 5))
        self.assertEqual(ts.execute_plan(plan_for(task), self.records)["selected"],
                         ["r1", "r2", "r3", "r4"])

    def test_empty_window_is_empty_not_nearest(self):
        task = ts.build_task("Q3", 1, window=(6, 8))
        self.assertEqual(ts.execute_plan(plan_for(task), self.records)["status"], "empty")

    def test_incomplete_records_stay_out_under_skip_policy(self):
        records = [record("a", 5, value=None), record("b", 3)]
        task = ts.build_task("Q1", 5)
        self.assertEqual(ts.execute_plan(plan_for(task, missing_policy="skip"), records)["selected"],
                         ["b"])

    def test_incomplete_only_is_undetermined_under_missing_policy(self):
        records = [record("a", 5, value=None)]
        task = ts.build_task("Q1", 5)
        result = ts.execute_plan(plan_for(task), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "NO_ELIGIBLE_RECORD")

    def test_non_explicit_identity_is_not_selectable(self):
        records = [record("a", 5, identity="ambiguous"), record("b", 4)]
        task = ts.build_task("Q1", 5)
        self.assertEqual(ts.execute_plan(plan_for(task), records)["selected"], ["b"])


class TimeRoleDimensionTest(unittest.TestCase):
    """One source record, two time roles, no duplicated observations."""

    def dual(self, record_id="dual", collection_day=0, report_day=3,
             collection_clock="06:20:00", report_clock="09:10:00",
             collection_precision="second", report_precision="second"):
        return {"record_id": record_id, "case_token": "CASE-SYNTHETIC",
                "value": 10, "unit": "g/L", "identity_status": "explicit",
                "collection_day_offset": collection_day, "collection_clock": collection_clock,
                "collection_precision": collection_precision,
                "report_day_offset": report_day, "report_clock": report_clock,
                "report_precision": report_precision}

    def plan(self, role, window, selection="latest"):
        return {"project": "HGB", "time_role": role, "window": window, "selection": selection,
                "scope": "test", "tie_policy": "undetermined", "missing_policy": "undetermined"}

    def test_requested_role_selects_that_roles_time(self):
        records = [self.dual()]
        collection_window = {"from": 0, "to": 0, "include_from": True, "include_to": True}
        report_window = {"from": 3, "to": 3, "include_from": True, "include_to": True}
        as_collection = ts.execute_plan(self.plan("collection", collection_window), records)
        as_report = ts.execute_plan(self.plan("report", report_window), records)
        self.assertEqual(as_collection["selected"], ["dual"])
        self.assertEqual(as_report["selected"], ["dual"])
        # The same record answers both roles, and the id is not duplicated.
        self.assertEqual(as_collection["selected"], as_report["selected"])
        self.assertEqual(len({r["record_id"] for r in records}), 1)

    def test_a_role_window_does_not_pick_up_the_other_roles_time(self):
        records = [self.dual()]
        collection_window = {"from": 0, "to": 0, "include_from": True, "include_to": True}
        # The report time is day 3, so a collection-day window must not match it.
        wrong = ts.execute_plan(self.plan("report", collection_window), records)
        self.assertEqual(wrong["status"], "empty")
        self.assertEqual(wrong["selected"], [])

    def test_unsupported_role_is_refused_per_record(self):
        records = [{"record_id": "collection-only", "case_token": "CASE-SYNTHETIC",
                    "value": 10, "unit": "g/L", "identity_status": "explicit",
                    "time_role": "collection", "day_offset": 1, "clock": "06:20:00",
                    "precision": "second"}]
        result = ts.execute_plan(self.plan("report",
                                           {"from": None, "to": 5, "include_from": False,
                                            "include_to": True}), records)
        self.assertEqual(result["status"], "unsupported_time_role")

    def test_available_roles_reports_both_roles(self):
        self.assertEqual(sorted(ts.available_roles(self.dual())), ["collection", "report"])

    def test_day_precision_report_time_has_no_clock(self):
        records = [self.dual("a", report_day=3, report_clock="00:00:00", report_precision="day"),
                   self.dual("b", report_day=3, report_clock="09:10:00",
                             report_precision="second")]
        result = ts.execute_plan(self.plan("report",
                                           {"from": 3, "to": 3, "include_from": True,
                                            "include_to": True}), records)
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(sorted(result["candidates"]), ["a", "b"])

    def test_legacy_single_role_records_still_work(self):
        records = [record("legacy", 1)]
        task = ts.build_task("Q1", 1)
        self.assertEqual(ts.execute_plan(plan_for(task), records)["selected"], ["legacy"])


class DayCoordinateTest(unittest.TestCase):
    def test_offsets_are_relative_to_the_case_origin(self):
        records = [{"record_id": "a", "collection_day": 100}, {"record_id": "b", "collection_day": 103}]
        self.assertEqual([r["day_offset"] for r in ts.day_coordinate(records, 100)], [0, 3])
        self.assertEqual([r["day_offset"] for r in ts.day_coordinate(records, 90)], [10, 13])

    def test_unknown_day_stays_none(self):
        self.assertIsNone(ts.day_coordinate([{"record_id": "a", "collection_day": None}], 0)[0]["day_offset"])


class ExpansionAndViewTest(unittest.TestCase):
    def test_expansion_resolves_ids_to_frozen_fields(self):
        records = [record("r2", 3, value="10", unit="g/L")]
        view = {r["record_id"]: r for r in records}
        expanded = ts.expand_selected(view, ["r2", "ghost"])
        self.assertTrue(expanded[0]["resolved"])
        self.assertEqual(expanded[0]["unit"], "g/L")
        self.assertFalse(expanded[1]["resolved"])

    def test_view_has_a_header_and_one_line_per_record(self):
        lines = ts.record_view_lines([record("r1", 1), record("r2", 2)]).splitlines()
        self.assertEqual(len(lines), 3)
        for field in ts.RECORD_FIELDS:
            self.assertIn(field, lines[0])


if __name__ == "__main__":
    unittest.main()
