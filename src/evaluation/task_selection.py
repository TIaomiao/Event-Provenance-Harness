"""Task-conditioned evidence selection v0.1: task specs, plan validation, executor, scorer.

This module is data-free.  It owns the *logic* that must be identical for every
condition: how a plan is validated, how a validated plan is executed over a
frozen record view, and how a selected record set is scored.

Design rules:

* The record view is frozen and shared by every condition.  Task-time selection
  happens here, never by re-picking "correct" rows upstream.
* A plan missing a required field is refused with an explicit reason.  Nothing
  is defaulted, because a silent default would manufacture an answer.
* Equal answers score the same: scoring works on record ids and semantic
  fields, so JSON key order or extra prose does not change the result.
* Records are grouped by a case-scoped relative-day coordinate.  Two cases never
  share a Day 0.
* A tie at the same day with insufficient precision stays undetermined instead
  of being resolved by an arbitrary pick.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

VERSION = "task-selection-v0.1"

TASKS = {
    "Q1": "latest target record at or before an explicit relative-day anchor",
    "Q2": "first target record strictly after an explicit relative-day anchor",
    "Q3": "every target record inside an explicit relative-day window",
}

TIME_ROLES = ("sampling", "collection", "report")
SELECTIONS = ("first", "latest", "all")
TIE_POLICIES = ("undetermined", "all_ties")
MISSING_POLICIES = ("undetermined", "skip")
PLAN_FIELDS = ("project", "time_role", "window", "selection", "scope",
               "tie_policy", "missing_policy")
WINDOW_FIELDS = ("from", "to", "include_from", "include_to")

RECORD_FIELDS = ("record_id", "case_token", "day_offset", "clock", "precision",
                 "value", "unit", "project_ref", "result_ref", "unit_ref",
                 "collection_ref", "report_ref", "identity_status")

CLOCK_RE = re.compile(r"^(?P<h>[01]\d|2[0-3]):(?P<m>[0-5]\d)(?::(?P<s>[0-5]\d))?$")


class SelectionError(ValueError):
    """Raised when the caller hands the executor something unusable."""


def clock_key(record):
    """Sort key for a clock on a given day; unknown clock sorts last."""
    clock = record.get("clock")
    if not isinstance(clock, str):
        return (1, 24, 60, 60)
    match = CLOCK_RE.match(clock.strip())
    if not match:
        return (1, 24, 60, 60)
    return (0, int(match.group("h")), int(match.group("m")),
            int(match.group("s") or 0))


def day_coordinate(records, origin_day):
    """Attach a case-scoped day offset to each record.

    ``origin_day`` is the case's own origin; the caller derives it per case, so
    two cases cannot be placed on one shared calendar.
    """
    out = []
    for record in records:
        entry = dict(record)
        raw_day = record.get("collection_day")
        entry["day_offset"] = None if raw_day is None else int(raw_day) - int(origin_day)
        out.append(entry)
    return out


def build_task(task_id, anchor_day, window=None, *, time_role="sampling",
               scope="frozen laboratory report", project="target analyte"):
    """Return the natural-language task and its explicit structured spec.

    The anchor and window are given in the task, never inferred from clinical
    context: this version deliberately has no notion of a surgery or treatment
    start.
    """
    if task_id not in TASKS:
        raise SelectionError("UNKNOWN_TASK:%s" % task_id)
    if task_id == "Q1":
        text = ("在相对日 %d（含当日）或之前，选出最近的一条%s记录。"
                "时间角色为%s。若最后一条记录所在日存在多条记录且精度不足以排序，"
                "返回 undetermined 而不是任选一条。" % (anchor_day, project, time_role))
        spec = {"selection": "latest", "window": {"from": None, "to": anchor_day,
                                                  "include_from": False, "include_to": True}}
    elif task_id == "Q2":
        text = ("在相对日 %d 之后（不含当日），选出最早的一条%s记录。"
                "时间角色为%s。若最早一条所在日存在并列且精度不足，返回 undetermined。"
                % (anchor_day, project, time_role))
        spec = {"selection": "first", "window": {"from": anchor_day, "to": None,
                                                 "include_from": False, "include_to": False}}
    else:
        start, end = window
        text = ("在相对日 %d 到 %d 之间（含两端），选出全部%s记录。"
                "时间角色为%s。若区间内没有记录，返回 empty 而不是最近的一条。"
                % (start, end, project, time_role))
        spec = {"selection": "all", "window": {"from": start, "to": end,
                                               "include_from": True, "include_to": True}}
    return {"task_id": task_id, "anchor_day": anchor_day, "time_role": time_role,
            "scope": scope, "project": project, "text": text, "spec": spec,
            "semantics": TASKS[task_id]}


def validate_plan(plan) -> tuple[bool, list[str]]:
    """Check a plan against the required fields.  Missing is never defaulted."""
    problems: list[str] = []
    if not isinstance(plan, dict):
        return False, ["PLAN_NOT_AN_OBJECT"]
    for field in PLAN_FIELDS:
        if field not in plan or plan[field] is None:
            problems.append("MISSING_%s" % field.upper())
    window = plan.get("window")
    if not isinstance(window, dict):
        problems.append("WINDOW_NOT_AN_OBJECT")
    else:
        for field in WINDOW_FIELDS:
            if field not in window:
                problems.append("MISSING_WINDOW_%s" % field.upper())
        for field in ("from", "to"):
            value = window.get(field)
            if value is not None and type(value) is not int:
                problems.append("WINDOW_%s_NOT_INTEGER" % field.upper())
        if window.get("from") is not None and window.get("to") is not None:
            if window["from"] > window["to"]:
                problems.append("WINDOW_INVERTED")
    for field, allowed in (("time_role", TIME_ROLES), ("selection", SELECTIONS),
                           ("tie_policy", TIE_POLICIES), ("missing_policy", MISSING_POLICIES)):
        value = plan.get(field)
        if value is not None and value not in allowed:
            problems.append("INVALID_%s:%s" % (field.upper(), value))
    selection = plan.get("selection")
    window = plan.get("window") if isinstance(plan.get("window"), dict) else {}
    if selection == "all" and (window.get("from") is None or window.get("to") is None):
        problems.append("SELECTION_ALL_NEEDS_BOTH_BOUNDS")
    if selection in {"first", "latest"} and window.get("from") is None and window.get("to") is None:
        problems.append("UNBOUNDED_SINGLE_SELECTION")
    return (not problems), problems


def _in_window(record, window):
    day = record.get("day_offset")
    if day is None:
        return False
    low, high = window.get("from"), window.get("to")
    if low is not None:
        if day < low or (day == low and not window.get("include_from")):
            return False
    if high is not None:
        if day > high or (day == high and not window.get("include_to")):
            return False
    return True


def eligible_records(records, plan):
    """Rows a validated plan may consider, split by data completeness."""
    usable, incomplete = [], []
    for record in records:
        if record.get("identity_status") != "explicit":
            incomplete.append(record)
            continue
        if record.get("value") is None or record.get("unit") is None:
            incomplete.append(record)
            continue
        if record.get("day_offset") is None:
            incomplete.append(record)
            continue
        if _in_window(record, plan["window"]):
            usable.append(record)
    return usable, incomplete


def execute_plan(plan, records) -> dict[str, Any]:
    """Execute a validated plan deterministically.  Refuses an invalid plan."""
    ok, problems = validate_plan(plan)
    if not ok:
        return {"status": "invalid_plan", "problems": problems, "selected": [],
                "reason": "PLAN_REFUSED"}
    usable, incomplete = eligible_records(records, plan)
    if not usable:
        status = "undetermined" if (incomplete and plan["missing_policy"] == "undetermined") else "empty"
        return {"status": status, "selected": [], "count": 0,
                "reason": "NO_ELIGIBLE_RECORD", "incomplete_considered": len(incomplete)}
    selection = plan["selection"]
    ordered = sorted(usable, key=lambda r: (r["day_offset"], clock_key(r)))
    if selection == "all":
        return {"status": "ok", "selected": [r["record_id"] for r in ordered],
                "count": len(ordered), "reason": None}
    record = ordered[-1] if selection == "latest" else ordered[0]
    same_day = [r for r in usable if r["day_offset"] == record["day_offset"]]
    ambiguous = False
    if len(same_day) > 1:
        clocks = {clock_key(r)[:3] for r in same_day}
        precise = all(r.get("precision") in {"second", "minute"} for r in same_day)
        if len(clocks) == 1 and not precise:
            ambiguous = True
    if ambiguous and plan["tie_policy"] == "undetermined":
        return {"status": "undetermined", "selected": [],
                "candidates": [r["record_id"] for r in same_day],
                "count": 0, "reason": "SAME_DAY_PRECISION_INSUFFICIENT"}
    if ambiguous and plan["tie_policy"] == "all_ties":
        return {"status": "ok", "selected": [r["record_id"] for r in same_day],
                "count": len(same_day), "reason": "TIE_RETURNED_ALL"}
    return {"status": "ok", "selected": [record["record_id"]], "count": 1, "reason": None}


def score(task, answer, records, reference_ids, *, plan=None, plan_ok=None):
    """Score a selected record set.  Set membership decides, not the JSON shape."""
    result = {"task_id": task["task_id"], "reference_ids": sorted(reference_ids),
              "selected_ids": [], "set_exact_match": None, "precision": None, "recall": None,
              "status_ok": None, "window_violation": 0, "order_violation": 0,
              "scope_violation": 0, "joint_fields_ok": None, "empty_handling": None,
              "plan_ok": plan_ok, "plan_problems": None}
    if plan is not None:
        _, problems = validate_plan(plan)
        result["plan_problems"] = problems
    if not isinstance(answer, dict):
        result["status"] = "format_failure"
        return result
    status = str(answer.get("status") or answer.get("decision") or "").lower() or None
    result["status"] = status
    selected = answer.get("selected_records")
    if selected is None:
        selected = answer.get("selected")
    ids: list[str] = []
    if isinstance(selected, list):
        for item in selected:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict):
                identifier = item.get("record_id") or item.get("id")
                if isinstance(identifier, str):
                    ids.append(identifier)
    result["selected_ids"] = ids
    reference_set, selected_set = set(reference_ids), set(ids)
    result["set_exact_match"] = reference_set == selected_set
    if selected_set:
        result["precision"] = len(reference_set & selected_set) / len(selected_set)
    elif not reference_set:
        result["precision"] = 1.0
    result["recall"] = (len(reference_set & selected_set) / len(reference_set)) if reference_set else (
        1.0 if not selected_set else 0.0)

    by_id = {record["record_id"]: record for record in records}
    window = task["spec"]["window"]
    for identifier in ids:
        record = by_id.get(identifier)
        if record is None:
            result["scope_violation"] += 1
            continue
        if not _in_window(record, window):
            result["window_violation"] += 1
        if record.get("case_token") != task.get("case_token") and task.get("case_token"):
            result["scope_violation"] += 1
    if len(ids) > 1 and task["spec"]["selection"] in {"first", "latest"}:
        days = [by_id[i]["day_offset"] for i in ids if i in by_id]
        if len(set(days)) > 1:
            result["order_violation"] = len(days) - 1
    if selected_set and selected_set <= set(by_id):
        fields_ok = all(
            by_id[i].get("value") is not None and by_id[i].get("unit") is not None
            and by_id[i].get("day_offset") is not None
            and any(by_id[i].get(ref) for ref in ("project_ref", "result_ref", "unit_ref"))
            for i in selected_set)
        result["joint_fields_ok"] = fields_ok
    expected_status = "ok" if reference_set else "empty"
    result["status_ok"] = status == expected_status
    result["empty_handling"] = (status == "empty") if not reference_set else None
    result["equivalent_answer"] = bool(result["set_exact_match"] and result["status_ok"])
    return result


def reference_for_task(task, records) -> list[str]:
    """Program reference for one task, produced by the same executor."""
    plan = {"project": task["project"], "time_role": task["time_role"],
            "window": task["spec"]["window"], "selection": task["spec"]["selection"],
            "scope": task["scope"], "tie_policy": "undetermined", "missing_policy": "undetermined"}
    return execute_plan(plan, records)["selected"]


def record_view_lines(records, *, limit=None) -> str:
    """Render the frozen record view as a stable, comparable table.

    The header is derived from :data:`RECORD_FIELDS`, so a column can never be
    rendered without appearing in the header.
    """
    lines = ["\t".join(RECORD_FIELDS)]
    for record in records if limit is None else records[:limit]:
        lines.append("\t".join(str(record.get(field)) for field in RECORD_FIELDS))
    return "\n".join(lines)
