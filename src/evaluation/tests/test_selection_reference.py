"""Boundary tests for the independent selection reference.

Every expectation is a literal written here, not derived from the module or from
the executor under test.  The last class also checks the two paths against each
other so a silent divergence cannot hide.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import selection_reference as sr  # noqa: E402
import task_selection as ts  # noqa: E402


def rec(record_id, day, clock=None, role="collection", value=10, unit="g/L",
        identity="explicit", case="CASE-SYNTHETIC", precision=None):
    return {"record_id": record_id, "case_token": case, "day_offset": day,
            "clock": clock, "time_role": role, "value": value, "unit": unit,
            "identity_status": identity,
            "precision": precision if precision is not None else ("second" if clock else "day")}


class WindowBoundaryTest(unittest.TestCase):
    def test_inclusive_upper_endpoint(self):
        window = {"from": None, "to": 5, "include_from": False, "include_to": True}
        self.assertTrue(sr.in_window(5, window))
        self.assertTrue(sr.in_window(4, window))

    def test_exclusive_upper_endpoint(self):
        window = {"from": 0, "to": 5, "include_from": True, "include_to": False}
        self.assertFalse(sr.in_window(5, window))
        self.assertTrue(sr.in_window(4, window))

    def test_exclusive_lower_endpoint(self):
        window = {"from": 0, "to": None, "include_from": False, "include_to": False}
        self.assertFalse(sr.in_window(0, window))
        self.assertTrue(sr.in_window(1, window))

    def test_closed_interval_includes_both_ends(self):
        window = {"from": 3, "to": 7, "include_from": True, "include_to": True}
        for day in (3, 5, 7):
            self.assertTrue(sr.in_window(day, window))
        self.assertFalse(sr.in_window(8, window))


class ReferenceBehaviourTest(unittest.TestCase):
    def test_empty_window_reports_empty(self):
        records = [rec("a", 1)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": 6, "to": 8, "include_from": True, "include_to": True},
                             selection="all")
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["selected"], [])

    def test_all_records_are_withheld_reports_undetermined(self):
        records = [rec("a", 5, value=None)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "ONLY_INCOMPLETE_RECORDS")

    def test_missing_clock_on_deciding_day_is_undetermined(self):
        records = [rec("timed", 5, clock="08:30"), rec("untimed", 5)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(sorted(result["candidates"]), ["timed", "untimed"])
        self.assertEqual(result["reason"], "MISSING_CLOCK_ON_DECIDING_DAY")

    def test_identical_clocks_are_undetermined_not_input_order(self):
        records = [rec("first", 5, clock="08:30"), rec("second", 5, clock="08:30")]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "IDENTICAL_CLOCKS_ON_DECIDING_DAY")

    def test_distinct_clocks_pick_the_latest(self):
        records = [rec("early", 5, clock="08:30"), rec("late", 5, clock="16:45")]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["selected"], ["late"])

    def test_first_after_anchor_is_strictly_after(self):
        records = [rec("anchor-day", 0), rec("next", 4)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": 0, "to": None, "include_from": False,
                                     "include_to": False}, selection="first")
        self.assertEqual(result["selected"], ["next"])

    def test_all_inside_closed_window(self):
        records = [rec("a", 0), rec("b", 2), rec("c", 5), rec("d", 9)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": 0, "to": 5, "include_from": True,
                                     "include_to": True}, selection="all")
        self.assertEqual(result["selected"], ["a", "b", "c"])

    def test_role_filter_applies(self):
        records = [rec("collection-row", 1), rec("report-row", 3, role="report")]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["selected"], ["collection-row"])

    def test_unknown_role_is_a_separate_outcome(self):
        records = [rec("a", 1, role="collection")]
        result = sr.expected(records=records, time_role="report",
                             window={"from": None, "to": 5, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["status"], "unsupported_time_role")
        self.assertEqual(result["reason"], "NO_RECORD_CARRIES_TIME_ROLE")

    def test_incomplete_record_outside_the_window_keeps_the_window_empty(self):
        # The record with a missing value sits on day 1, outside the queried window.
        # It is not a candidate at all, so it must not make the window undetermined.
        records = [rec("outside", 1, value=None)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": 38, "to": 40, "include_from": True,
                                     "include_to": True}, selection="all")
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["selected"], [])

    def test_incomplete_record_inside_the_window_is_undetermined(self):
        records = [rec("inside", 39, value=None)]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": 38, "to": 40, "include_from": True,
                                     "include_to": True}, selection="all")
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(result["reason"], "ONLY_INCOMPLETE_RECORDS")

    def test_day_precision_row_is_not_treated_as_a_midnight_clock(self):
        # A day-precision row and a second-precision row on the deciding day cannot
        # be ordered, so the outcome is undetermined rather than the timed row.
        records = [rec("day-precision", 32, clock="00:00:00", precision="day"),
                   rec("second-precision", 32, clock="10:15:00", precision="second")]
        result = sr.expected(records=records, time_role="collection",
                             window={"from": None, "to": 32, "include_from": False,
                                     "include_to": True}, selection="latest")
        self.assertEqual(result["status"], "undetermined")
        self.assertEqual(sorted(result["candidates"]), ["day-precision", "second-precision"])
        self.assertEqual(result["reason"], "MISSING_CLOCK_ON_DECIDING_DAY")


class CrossPathAgreementTest(unittest.TestCase):
    """The reference and the executor under test must agree on these cases."""

    def cases(self):
        base = {"from": None, "to": 5, "include_from": False, "include_to": True}
        return [
            ("single", [rec("a", 3)], base, "latest"),
            ("distinct clocks", [rec("a", 5, clock="08:30"), rec("b", 5, clock="16:45")],
             base, "latest"),
            ("missing clock", [rec("a", 5, clock="08:30"), rec("b", 5)], base, "latest"),
            ("identical clocks", [rec("a", 5, clock="08:30"), rec("b", 5, clock="08:30")],
             base, "latest"),
            ("empty", [rec("a", 1)], {"from": 6, "to": 8, "include_from": True,
                                      "include_to": True}, "all"),
            ("withheld only", [rec("a", 5, value=None)], base, "latest"),
            ("window closed", [rec("a", 0), rec("b", 4), rec("c", 9)],
             {"from": 0, "to": 5, "include_from": True, "include_to": True}, "all"),
            ("first after", [rec("a", 0), rec("b", 4)],
             {"from": 0, "to": None, "include_from": False, "include_to": False}, "first"),
            ("role mismatch", [rec("a", 1, role="report")], base, "latest"),
            ("incomplete outside window", [rec("outside", 1, value=None)],
             {"from": 38, "to": 40, "include_from": True, "include_to": True}, "all"),
            ("incomplete inside window", [rec("inside", 39, value=None)],
             {"from": 38, "to": 40, "include_from": True, "include_to": True}, "all"),
            ("day precision beats no clock", [rec("day-precision", 32, clock="00:00:00",
                                                  precision="day"),
                                              rec("second-precision", 32, clock="10:15:00",
                                                  precision="second")],
             {"from": None, "to": 32, "include_from": False, "include_to": True}, "latest"),
        ]

    def test_both_paths_agree_on_every_boundary_case(self):
        for name, records, window, selection in self.cases():
            with self.subTest(name=name):
                reference = sr.expected(records=records, time_role="collection",
                                        window=window, selection=selection)
                plan = {"project": "HGB", "time_role": "collection", "window": window,
                        "selection": selection, "scope": "test",
                        "tie_policy": "undetermined", "missing_policy": "undetermined"}
                execution = ts.execute_plan(plan, records)
                comparison = sr.compare_with_executor(reference, execution)
                self.assertTrue(comparison["agree"], "%s: %s" % (name, comparison))


if __name__ == "__main__":
    unittest.main()
