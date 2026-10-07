"""Task-conditioned evidence selection v0.2: task specs, plan validation, executor, scorer.

This module is data-free.  It owns the logic that must be identical for every
condition: how a plan is validated, how a validated plan is executed over a
frozen record view, and how a selected record set is scored.

Changes in v0.2 (2026-10-06), after the first real run:

* A true tie is a tie regardless of precision: two rows sharing the same day and
  the same clock are undetermined when the policy says so, instead of being
  resolved by input order.
* An unknown clock is never ordered as if it were 24:00.  If the deciding day
  mixes rows with and without a clock, the outcome is undetermined.
* A reference keeps ``status``, ``selected``, the undetermined candidates and a
  reason.  It is never collapsed to an empty selection.
* Scoring separates ``empty``, ``undetermined``, ``unsupported_time_role``,
  ``invalid_plan`` and ``invalid_task``; a correct record id with wrong or
  absent value/unit/time/source does not count as joint fields correct.
* ``time_role`` is either executed as a filter or refused.  An unsupported role
  is never silently executed as if it were the collection time.
"""
from __future__ import annotations

import re
from typing import Any

VERSION = "task-selection-v0.2"

TASKS = {
    "Q1": "latest target record at or before an explicit relative-day anchor",
    "Q2": "first target record strictly after an explicit relative-day anchor",
    "Q3": "every target record inside an explicit relative-day window",
}

TIME_ROLES = ("sampling", "collection", "report")
SELECTIONS = ("first", "latest", "all")
TIE_POLICIES = ("undetermined", "all_ties")
MISSING_POLICIES = ("undetermined", "skip")
# The model produces these two; the host binds and declares the rest.
PLAN_FIELDS = ("window", "selection")
BOUND_FIELDS = ("project", "time_role", "scope", "tie_policy", "missing_policy")
ALL_PLAN_FIELDS = ("project", "time_role", "window", "selection", "scope",
                   "tie_policy", "missing_policy")
WINDOW_FIELDS = ("from", "to", "include_from", "include_to")

RECORD_FIELDS = ("record_id", "case_token", "time_role", "day_offset", "clock", "precision",
                 "value", "unit", "project_name", "project_ref", "result_ref", "unit_ref",
                 "collection_ref", "report_ref", "identity_status")

# Statuses the executor may return.  They are deliberately distinct so an empty
# result is never confused with a refused plan or an unresolved tie.
STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_UNDETERMINED = "undetermined"
STATUS_UNSUPPORTED_ROLE = "unsupported_time_role"
STATUS_INVALID_PLAN = "invalid_plan"
STATUS_INVALID_TASK = "invalid_task"

CLOCK_RE = re.compile(r"^(?P<h>[01]\d|2[0-3]):(?P<m>[0-5]\d)(?::(?P<s>[0-5]\d))?$")


class SelectionError(ValueError):
    """Raised when the caller hands the executor something unusable."""


def has_clock(record) -> bool:
    clock = record.get("clock")
    return isinstance(clock, str) and bool(CLOCK_RE.match(clock.strip()))


def clock_key(record):
    """Absolute clock key.  Only meaningful together with :func:`has_clock`."""
    match = CLOCK_RE.match(record["clock"].strip())
    return (int(match.group("h")), int(match.group("m")), int(match.group("s") or 0))


def day_coordinate(records, origin_day):
    """Attach a case-scoped day offset.  Two cases never share a Day 0."""
    out = []
    for record in records:
        entry = dict(record)
        raw_day = record.get("collection_day")
        entry["day_offset"] = None if raw_day is None else int(raw_day) - int(origin_day)
        out.append(entry)
    return out


def build_task(task_id, anchor_day, window=None, *, time_role="collection",
               scope="frozen laboratory report", project="the target analyte"):
    """Return the natural-language task and its explicit structured spec.

    Only ``window`` and ``selection`` are the model's to produce.  ``project``,
    ``time_role``, ``scope``, ``tie_policy`` and ``missing_policy`` are fixed
    context the host binds and declares in the protocol.
    """
    if task_id not in TASKS:
        raise SelectionError("UNKNOWN_TASK:%s" % task_id)
    if task_id == "Q1":
        text = ("在相对日 %d（含当日）或之前，选出最近的一条目标记录。"
                "时间角色为%s。若最后一条记录所在日存在并列、或该日有时间未知的记录，"
                "返回 undetermined 而不是任选一条。" % (anchor_day, time_role))
        spec = {"selection": "latest", "window": {"from": None, "to": anchor_day,
                                                  "include_from": False, "include_to": True}}
    elif task_id == "Q2":
        text = ("在相对日 %d 之后（不含当日），选出最早的一条目标记录。"
                "时间角色为%s。若最早一条所在日存在并列、或该日有时间未知的记录，"
                "返回 undetermined。" % (anchor_day, time_role))
        spec = {"selection": "first", "window": {"from": anchor_day, "to": None,
                                                 "include_from": False, "include_to": False}}
    else:
        start, end = window
        text = ("在相对日 %d 到 %d 之间（含两端），选出全部目标记录。"
                "时间角色为%s。若区间内没有记录，返回 empty 而不是最近的一条。"
                % (start, end, time_role))
        spec = {"selection": "all", "window": {"from": start, "to": end,
                                               "include_from": True, "include_to": True}}
    return {"task_id": task_id, "anchor_day": anchor_day, "time_role": time_role,
            "scope": scope, "project": project, "text": text, "spec": spec,
            "semantics": TASKS[task_id]}


def bound_context(task, *, project=None, scope=None, time_role=None,
                  tie_policy="undetermined", missing_policy="undetermined"):
    """The fixed conditions the host declares for a task family.

    These are environment facts, not things the model is asked to invent.  They
    are declared in the protocol so nothing is guessed after the fact.
    """
    return {"project": project if project is not None else task.get("project"),
            "time_role": time_role if time_role is not None else task.get("time_role"),
            "scope": scope if scope is not None else task.get("scope"),
            "tie_policy": tie_policy, "missing_policy": missing_policy}


def compose_plan(model_plan, bound):
    """Merge the model's part with the bound context.

    A field the model omits stays omitted unless the host bound it; the host
    never fills in the model's own two fields.
    """
    merged = dict(bound)
    if isinstance(model_plan, dict):
        for field in PLAN_FIELDS:
            if field in model_plan:
                merged[field] = model_plan[field]
        for field in BOUND_FIELDS:
            if merged.get(field) is None and model_plan.get(field) is not None:
                merged[field] = model_plan[field]
    return merged


def validate_plan(plan) -> tuple[bool, list[str]]:
    """Check a plan against the required fields.  Missing is never defaulted."""
    problems: list[str] = []
    if not isinstance(plan, dict):
        return False, ["PLAN_NOT_AN_OBJECT"]
    for field in ALL_PLAN_FIELDS:
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
    """Rows a validated plan may consider, split by data completeness.

    ``time_role`` is applied as a filter.  A role no record carries yields an
    empty eligible set and an explicit status, never a silent fallback to the
    collection time.
    """
    usable, incomplete, role_supported = [], [], False
    for record in records:
        if record.get("time_role") == plan.get("time_role"):
            role_supported = True
        else:
            continue
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
    return usable, incomplete, role_supported


def _resolve_position(usable, selection):
    """Return (status, winners, reason) for a single-record selection.

    Ordering never invents a clock, and identical timestamps are a real tie.
    """
    days = [record["day_offset"] for record in usable]
    target_day = max(days) if selection == "latest" else min(days)
    same_day = [record for record in usable if record["day_offset"] == target_day]
    if len(same_day) == 1:
        return STATUS_OK, same_day, None
    unknown = [record for record in same_day if not has_clock(record)]
    known = [record for record in same_day if has_clock(record)]
    if unknown and known:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_CLOCK_UNKNOWN_FOR_SOME_RECORDS"
    if unknown and not known:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_CLOCK_UNKNOWN_FOR_ALL_RECORDS"
    keys = {clock_key(record) for record in known}
    if len(keys) == 1:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_IDENTICAL_TIMESTAMP"
    extreme = (max if selection == "latest" else min)(keys)
    winners = [record for record in known if clock_key(record) == extreme]
    if len(winners) > 1:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_IDENTICAL_TIMESTAMP"
    return STATUS_OK, winners, None


def execute_plan(plan, records) -> dict[str, Any]:
    """Execute a validated plan deterministically.  Refuses an invalid plan."""
    ok, problems = validate_plan(plan)
    if not ok:
        return {"status": STATUS_INVALID_PLAN, "problems": problems, "selected": [],
                "candidates": [], "reason": "PLAN_REFUSED"}
    usable, incomplete, role_supported = eligible_records(records, plan)
    if not role_supported:
        return {"status": STATUS_UNSUPPORTED_ROLE, "selected": [], "candidates": [],
                "reason": "NO_RECORD_CARRIES_TIME_ROLE:%s" % plan.get("time_role")}
    if not usable:
        status = (STATUS_UNDETERMINED
                  if (incomplete and plan["missing_policy"] == "undetermined")
                  else STATUS_EMPTY)
        return {"status": status, "selected": [], "candidates": [],
                "reason": "NO_ELIGIBLE_RECORD", "incomplete_considered": len(incomplete)}
    if plan["selection"] == "all":
        ordered = sorted(usable, key=lambda r: (r["day_offset"],
                                                clock_key(r) if has_clock(r) else (99, 99, 99)))
        return {"status": STATUS_OK, "selected": [r["record_id"] for r in ordered],
                "candidates": [], "count": len(ordered), "reason": None}
    status, winners, reason = _resolve_position(usable, plan["selection"])
    if status != STATUS_OK:
        if plan["tie_policy"] == "all_ties":
            return {"status": STATUS_OK, "selected": [r["record_id"] for r in winners],
                    "candidates": [], "count": len(winners), "reason": "TIE_RETURNED_ALL"}
        return {"status": STATUS_UNDETERMINED, "selected": [],
                "candidates": [r["record_id"] for r in winners], "count": 0, "reason": reason}
    return {"status": STATUS_OK, "selected": [winners[0]["record_id"]],
            "candidates": [], "count": 1, "reason": None}


def reference_for_task(task, records, bound=None) -> dict[str, Any]:
    """Program reference for one task: status, selection, tie candidates, reason.

    Produced by the same executor, so it is a rule reference and NOT an
    independent gold standard.  It is never collapsed to an empty selection.
    """
    base = dict(bound if bound is not None else bound_context(task))
    base["window"] = task["spec"]["window"]
    base["selection"] = task["spec"]["selection"]
    result = execute_plan(base, records)
    return {"status": result.get("status"), "selected": result.get("selected") or [],
            "candidates": result.get("candidates") or [], "reason": result.get("reason"),
            "task_id": task["task_id"]}


def expand_selected(view_by_id, selected_ids):
    """Host-side field expansion for a model that submits only record ids."""
    out = []
    for identifier in selected_ids:
        record = view_by_id.get(identifier)
        if record is None:
            out.append({"record_id": identifier, "resolved": False})
            continue
        out.append({"record_id": identifier, "resolved": True,
                    "value": record.get("value"), "unit": record.get("unit"),
                    "day_offset": record.get("day_offset"), "clock": record.get("clock"),
                    "source_refs": [record.get(field) for field in
                                    ("project_ref", "result_ref", "unit_ref",
                                     "collection_ref", "report_ref")]})
    return out


def _supplied_fields(answer):
    """Which semantic fields the model actually provided for its selection."""
    supplied = {"record_ids": False, "value": False, "unit": False,
                "time": False, "source": False}
    selected = answer.get("selected_records")
    if selected is None:
        selected = answer.get("selected") or []
    if not isinstance(selected, list):
        return supplied
    for item in selected:
        if isinstance(item, str):
            supplied["record_ids"] = True
            continue
        if not isinstance(item, dict):
            continue
        if item.get("record_id") or item.get("id"):
            supplied["record_ids"] = True
        if item.get("value") is not None:
            supplied["value"] = True
        if item.get("unit") is not None:
            supplied["unit"] = True
        if item.get("collection_time") is not None or item.get("day_offset") is not None:
            supplied["time"] = True
        if item.get("source_refs"):
            supplied["source"] = True
    return supplied


def score(task, answer, records, reference, *, plan=None, plan_ok=None,
          fields_expanded_by_host=False):
    """Score a selected record set against a reference that keeps its status.

    Set membership decides.  A correct record id alone does not make the
    value/unit/time/source correct: those count only when the model supplied
    them and they match the frozen record, or when the host expanded them for
    every condition.
    """
    reference_status = reference.get("status")
    reference_ids = reference.get("selected") or []
    result = {"task_id": task["task_id"], "reference_status": reference_status,
              "reference_ids": sorted(reference_ids),
              "reference_candidates": sorted(reference.get("candidates") or []),
              "reference_reason": reference.get("reason"),
              "selected_ids": [], "status": None, "set_exact_match": None,
              "precision": None, "recall": None, "status_ok": None,
              "window_violation": 0, "order_violation": 0, "scope_violation": 0,
              "joint_fields_ok": None, "fields_supplied": None,
              "fields_expanded_by_host": fields_expanded_by_host,
              "empty_handling": None, "undetermined_handling": None,
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
    result["fields_supplied"] = _supplied_fields(answer)
    by_id = {record["record_id"]: record for record in records}
    reference_set, selected_set = set(reference_ids), set(ids)

    if reference_status == STATUS_UNDETERMINED:
        candidates = set(reference.get("candidates") or [])
        result["undetermined_handling"] = (status == STATUS_UNDETERMINED and not selected_set)
        result["status_ok"] = status == STATUS_UNDETERMINED
        result["set_exact_match"] = (status == STATUS_UNDETERMINED) if not selected_set else (
            selected_set == candidates)
        result["precision"] = (len(candidates & selected_set) / len(selected_set)) if selected_set else None
        result["recall"] = (len(candidates & selected_set) / len(candidates)) if candidates else None
        result["equivalent_answer"] = bool(result["status_ok"] and not selected_set)
        return result
    if reference_status == STATUS_UNSUPPORTED_ROLE:
        result["status_ok"] = status == STATUS_UNSUPPORTED_ROLE
        result["equivalent_answer"] = bool(result["status_ok"] and not selected_set)
        return result

    result["set_exact_match"] = reference_set == selected_set
    if selected_set:
        result["precision"] = len(reference_set & selected_set) / len(selected_set)
    elif not reference_set:
        result["precision"] = 1.0
    result["recall"] = (len(reference_set & selected_set) / len(reference_set)) if reference_set else (
        1.0 if not selected_set else 0.0)

    window = task["spec"]["window"]
    for identifier in ids:
        record = by_id.get(identifier)
        if record is None:
            result["scope_violation"] += 1
            continue
        if not _in_window(record, window):
            result["window_violation"] += 1
        if task.get("case_token") and record.get("case_token") != task["case_token"]:
            result["scope_violation"] += 1
    if len(ids) > 1 and task["spec"]["selection"] in {"first", "latest"}:
        days = [by_id[i]["day_offset"] for i in ids if i in by_id]
        if len(set(days)) > 1:
            result["order_violation"] = len(days) - 1

    expected_status = STATUS_OK if reference_set else STATUS_EMPTY
    result["status_ok"] = status == expected_status
    result["empty_handling"] = None if reference_set else (status == STATUS_EMPTY)
    if selected_set and selected_set <= set(by_id):
        supplied = result["fields_supplied"]
        if fields_expanded_by_host:
            result["joint_fields_ok"] = all(
                by_id[i].get("value") is not None and by_id[i].get("unit") is not None
                and by_id[i].get("day_offset") is not None and by_id[i].get("time_role")
                for i in selected_set)
        elif not (supplied["value"] and supplied["unit"]):
            result["joint_fields_ok"] = None
            result["fields_insufficient"] = True
        else:
            result["joint_fields_ok"] = all(
                by_id[i].get("value") is not None and by_id[i].get("unit") is not None
                and by_id[i].get("day_offset") is not None and by_id[i].get("time_role")
                for i in selected_set)
    result["equivalent_answer"] = bool(result["set_exact_match"] and result["status_ok"])
    return result


def record_view_lines(records, *, limit=None) -> str:
    """Render the frozen record view as a stable, comparable table."""
    lines = ["\t".join(RECORD_FIELDS)]
    for record in records if limit is None else records[:limit]:
        lines.append("\t".join(str(record.get(field)) for field in RECORD_FIELDS))
    return "\n".join(lines)
