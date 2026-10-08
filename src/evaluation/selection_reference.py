"""Independent selection reference for task-conditioned evidence selection.

This module computes the expected selection *from the definition*, deliberately
without calling the executor that is under test (:mod:`task_selection`).  The two
paths share no helper, so an implementation bug in one is unlikely to be mirrored
in the other.  Disagreements are reported, never silently resolved.

Definitions used here:

* eligible = identity is explicit, value and unit are present, the record carries
  the task's time role, the collection day is known, and the day is inside the
  task window under the stated endpoint inclusion.
* ``latest`` / ``first`` = the single extreme record among the eligible records on
  the extreme collection day.  If that day holds more than one eligible record and
  the clocks cannot separate them (missing clock, or identical clock), the answer
  is undetermined and every record on that day is reported as a tie candidate.
* ``all`` = every eligible record inside the window.
* no eligible record = ``empty`` when nothing was withheld for missing data,
  otherwise ``undetermined`` under the declared missing policy.
"""
from __future__ import annotations

VERSION = "selection-reference-v0.1"


ROLE_FIELDS = ("collection", "report", "sampling")


def role_time(record, role):
    """``(day_offset, clock, precision)`` for the requested role, or all None.

    Per-role fields are authoritative when present, so one source record answers
    both a collection-time task and a report-time task without duplication.
    """
    prefixed = "%s_day_offset" % role
    if prefixed in record:
        return (record.get(prefixed), record.get("%s_clock" % role),
                record.get("%s_precision" % role))
    if record.get("time_role") == role:
        return (record.get("day_offset"), record.get("clock"), record.get("precision"))
    return (None, None, None)


def available_roles(record):
    roles = [role for role in ROLE_FIELDS if "%s_day_offset" % role in record]
    if roles:
        return roles
    role = record.get("time_role")
    return [role] if role else []


def _day(record, role=None):
    value = role_time(record, role)[0] if role else record.get("day_offset")
    return int(value) if isinstance(value, int) else None


def _clock_parts(record, role=None):
    """Return (h, m, s) or None.

    A row whose precision for this role is only a day has no usable clock: the
    ``00:00:00`` the rule path attaches is an artifact, not an observation.
    """
    _, clock, precision = role_time(record, role) if role else (
        None, record.get("clock"), record.get("precision"))
    if str(precision or "").lower() in {"day", "date", ""}:
        return None
    if not isinstance(clock, str):
        return None
    parts = clock.strip().split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if not (0 <= numbers[0] <= 23) or not all(0 <= part <= 59 for part in numbers[1:]):
        return None
    return tuple(numbers + [0] * (3 - len(numbers)))


def in_window(day, window):
    if day is None:
        return False
    low, high = window.get("from"), window.get("to")
    if low is not None and (day < low or (day == low and not window.get("include_from"))):
        return False
    if high is not None and (day > high or (day == high and not window.get("include_to"))):
        return False
    return True


def eligible(records, *, time_role, window):
    """Split by window and completeness for the requested role.

    A record is only *withheld for missing data* when it is already a candidate by
    role and by window.  A record outside the window is not a candidate at all, so
    it must not turn an empty window into an undetermined one.
    """
    keep, withheld = [], 0
    for record in records:
        if time_role not in available_roles(record):
            continue
        day = _day(record, time_role)
        if day is None or not in_window(day, window):
            continue
        if (record.get("identity_status") != "explicit"
                or record.get("value") is None or record.get("unit") is None):
            withheld += 1
            continue
        keep.append(record)
    return keep, withheld


def expected(*, records, time_role, window, selection, missing_policy="undetermined"):
    """Compute the expected outcome from the definition alone.

    A role no record carries is its own outcome, not an empty window: it means the
    frozen view cannot support the requested role at all.  This distinction was
    surfaced by the first cross-check against the executor and is now part of the
    definition on both paths.
    """
    if not any(time_role in available_roles(record) for record in records):
        return {"status": "unsupported_time_role", "selected": [], "candidates": [],
                "reason": "NO_RECORD_CARRIES_TIME_ROLE"}
    keep, withheld = eligible(records, time_role=time_role, window=window)
    if not keep:
        status = "undetermined" if (withheld and missing_policy == "undetermined") else "empty"
        return {"status": status, "selected": [], "candidates": [],
                "reason": "NOTHING_ELIGIBLE" if not withheld else "ONLY_INCOMPLETE_RECORDS"}
    if selection == "all":
        ordered = sorted(keep, key=lambda r: (_day(r, time_role),
                                              _clock_parts(r, time_role) or (99, 99, 99),
                                              str(r.get("record_id"))))
        return {"status": "ok", "selected": [r["record_id"] for r in ordered],
                "candidates": [], "reason": None}
    days = [_day(r, time_role) for r in keep]
    extreme = max(days) if selection == "latest" else min(days)
    pool = [r for r in keep if _day(r, time_role) == extreme]
    if len(pool) == 1:
        return {"status": "ok", "selected": [pool[0]["record_id"]], "candidates": [], "reason": None}
    clocks = [_clock_parts(r, time_role) for r in pool]
    if any(clock is None for clock in clocks):
        return {"status": "undetermined", "selected": [],
                "candidates": [r["record_id"] for r in pool],
                "reason": "MISSING_CLOCK_ON_DECIDING_DAY"}
    if len(set(clocks)) == 1:
        return {"status": "undetermined", "selected": [],
                "candidates": [r["record_id"] for r in pool],
                "reason": "IDENTICAL_CLOCKS_ON_DECIDING_DAY"}
    chosen = (max if selection == "latest" else min)(pool, key=lambda r: _clock_parts(r, time_role))
    return {"status": "ok", "selected": [chosen["record_id"]], "candidates": [], "reason": None}


def compare_with_executor(reference, execution):
    """Report whether the independent reference and the executor agree."""
    agree = (reference.get("status") == execution.get("status")
             and sorted(reference.get("selected") or []) == sorted(execution.get("selected") or []))
    candidates_agree = sorted(reference.get("candidates") or []) == sorted(
        execution.get("candidates") or [])
    return {"agree": bool(agree and candidates_agree), "status_agree":
            reference.get("status") == execution.get("status"),
            "selected_agree": sorted(reference.get("selected") or []) == sorted(
                execution.get("selected") or []),
            "candidates_agree": candidates_agree,
            "reference": {"status": reference.get("status"),
                          "selected": sorted(reference.get("selected") or []),
                          "candidates": sorted(reference.get("candidates") or [])},
            "executor": {"status": execution.get("status"),
                         "selected": sorted(execution.get("selected") or []),
                         "candidates": sorted(execution.get("candidates") or [])}}
