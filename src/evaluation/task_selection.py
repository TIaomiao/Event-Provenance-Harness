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

import math
import re
from typing import Any

VERSION = "task-selection-v0.2"

TASKS = {
    "Q1": "latest target record at or before an explicit relative-day anchor",
    "Q2": "first target record strictly after an explicit relative-day anchor",
    "Q3": "every target record inside an explicit relative-day window",
}

TIME_ROLES = ("sampling", "collection", "report")
ROLE_FIELDS = ("collection", "report", "sampling")
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


def role_time(record, role):
    """Return ``(day_offset, clock, precision)`` for the requested time role.

    A record may carry several roles at once.  When the per-role fields are
    present they are authoritative, so one source record can answer both a
    collection-time task and a report-time task without being duplicated.  When
    they are absent the legacy single-role fields are used, which keeps the
    earlier development runs reproducible.
    """
    prefixed = "%s_day_offset" % role
    if prefixed in record:
        return (record.get(prefixed), record.get("%s_clock" % role),
                record.get("%s_precision" % role))
    if record.get("time_role") == role:
        return (record.get("day_offset"), record.get("clock"), record.get("precision"))
    return (None, None, None)


def available_roles(record):
    """Roles this record can answer for.  No role is ever synthesised."""
    roles = [role for role in ROLE_FIELDS if "%s_day_offset" % role in record]
    if roles:
        return roles
    role = record.get("time_role")
    return [role] if role else []


def has_clock(record, role=None) -> bool:
    """True only when the requested role carries an observed clock.

    A row recorded at day precision has no usable clock for that role: the
    ``00:00:00`` the rule path attaches to it is an artifact, and comparing it
    with a real time would invent an ordering.
    """
    if role is None:
        role = record.get("time_role")
    _, clock, precision = role_time(record, role)
    if str(precision or "").lower() in {"day", "date", ""}:
        return False
    return isinstance(clock, str) and bool(CLOCK_RE.match(clock.strip()))


def clock_key(record, role=None):
    """Absolute clock key for the requested role.  Pair with :func:`has_clock`."""
    if role is None:
        role = record.get("time_role")
    _, clock, _ = role_time(record, role)
    match = CLOCK_RE.match(clock.strip())
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


def _in_window(record, window, role=None):
    if role is None:
        role = record.get("time_role")
    day, _, _ = role_time(record, role)
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
    collection time.  A record outside the window is not a candidate at all, so it
    never turns an empty window into an undetermined one.

    The declared patient scope is *not* applied here: the caller hands in the rows
    the declared scope covers, so a stray case token cannot silently empty the
    candidate set.
    """
    usable, incomplete, role_supported = [], [], False
    role = plan.get("time_role")
    for record in records:
        if role in available_roles(record):
            role_supported = True
        else:
            continue
        day, _, _ = role_time(record, role)
        if day is None or not _in_window(record, plan["window"], role):
            continue
        if record.get("identity_status") != "explicit":
            incomplete.append(record)
            continue
        if record.get("value") is None or record.get("unit") is None:
            incomplete.append(record)
            continue
        usable.append(record)
    return usable, incomplete, role_supported


def _resolve_position(usable, selection, role):
    """Return (status, winners, reason) for a single-record selection.

    Ordering never invents a clock, and identical timestamps are a real tie.
    """
    days = [role_time(record, role)[0] for record in usable]
    target_day = max(days) if selection == "latest" else min(days)
    same_day = [record for record in usable if role_time(record, role)[0] == target_day]
    if len(same_day) == 1:
        return STATUS_OK, same_day, None
    unknown = [record for record in same_day if not has_clock(record, role)]
    known = [record for record in same_day if has_clock(record, role)]
    if unknown and known:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_CLOCK_UNKNOWN_FOR_SOME_RECORDS"
    if unknown and not known:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_CLOCK_UNKNOWN_FOR_ALL_RECORDS"
    keys = {clock_key(record, role) for record in known}
    if len(keys) == 1:
        return STATUS_UNDETERMINED, same_day, "SAME_DAY_IDENTICAL_TIMESTAMP"
    extreme = (max if selection == "latest" else min)(keys)
    winners = [record for record in known if clock_key(record, role) == extreme]
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
        ordered = sorted(usable, key=lambda r: (role_time(r, plan["time_role"])[0],
                                                clock_key(r, plan["time_role"])
                                                if has_clock(r, plan["time_role"])
                                                else (99, 99, 99)))
        return {"status": STATUS_OK, "selected": [r["record_id"] for r in ordered],
                "candidates": [], "count": len(ordered), "reason": None}
    status, winners, reason = _resolve_position(usable, plan["selection"], plan["time_role"])
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


def _norm_unit(text):
    return " ".join(str(text or "").split()).lower()


REQUIRED_ITEM_FIELDS = ("value", "unit", "time", "source")


def _finite(value):
    """A usable number, or None.  NaN and infinity are not usable numbers."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


CONTRACT_KEYS = ("required_fields", "display_precision", "source_mode")
DISPLAY_PRECISIONS = ("day", "second")
SOURCE_MODES = ("exact", "supported")


def check_contract(spec):
    """Validate a declared task contract, or return None for a legacy task.

    Selecting a record may need the finest available precision while the answer is
    only required to *show* a coarser one.  Those are different requirements and are
    declared separately.  A task that declares a contract must declare all of it: a
    partial contract is an error rather than a silent default.
    """
    contract = (spec or {}).get("contract")
    if contract is None:
        return None
    if not isinstance(contract, dict):
        raise SelectionError("CONTRACT_NOT_AN_OBJECT")
    missing = [key for key in CONTRACT_KEYS if key not in contract]
    if missing:
        raise SelectionError("CONTRACT_MISSING_%s" % "_".join(missing).upper())
    if contract["display_precision"] not in DISPLAY_PRECISIONS:
        raise SelectionError("CONTRACT_BAD_DISPLAY_PRECISION")
    if contract["source_mode"] not in SOURCE_MODES:
        raise SelectionError("CONTRACT_BAD_SOURCE_MODE")
    if not isinstance(contract["required_fields"], (list, tuple)):
        raise SelectionError("CONTRACT_BAD_REQUIRED_FIELDS")
    return contract


def _field_mismatches(identifier, item, record, role, contract=None):
    """Compare the fields the model supplied against the frozen record.

    A required field the answer omits is a failure, not a neutral omission.  Values
    must be finite numbers and the day offset must be an exact integer.  Time precision
    is checked against what the contract requires the answer to *show*: with day
    display a day offset is enough and a missing clock is not a fault, while with
    second display the clock must be present and equal, and a record that carries only
    a day cannot be answered with an invented clock.  When no contract is declared the
    record's own precision governs, which keeps earlier tasks reproducible.  Unusable
    input is recorded as a mismatch instead of raising.
    """
    if not isinstance(item, dict):
        return ["%s:missing_%s" % (identifier, field) for field in REQUIRED_ITEM_FIELDS]
    out = []

    expected_value = _finite(record.get("value"))
    if item.get("value") is None:
        out.append("%s:missing_value" % identifier)
    else:
        supplied_value = _finite(item.get("value"))
        if supplied_value is None or expected_value is None:
            out.append("%s:value" % identifier)
        elif abs(supplied_value - expected_value) > 1e-6 * max(1.0, abs(expected_value)):
            out.append("%s:value" % identifier)

    if item.get("unit") is None:
        out.append("%s:missing_unit" % identifier)
    elif _norm_unit(item.get("unit")) != _norm_unit(record.get("unit")):
        out.append("%s:unit" % identifier)

    supplied_day = item.get("day_offset")
    if supplied_day is None:
        supplied_day = item.get("%s_day_offset" % role)
    supplied_clock = item.get("clock")
    if supplied_clock is None:
        supplied_clock = item.get("%s_clock" % role)
    if supplied_day is None and supplied_clock is None:
        out.append("%s:missing_time" % identifier)
    else:
        expected_day, expected_clock, expected_precision = role_time(record, role)
        day_ok = False
        if supplied_day is None:
            out.append("%s:time" % identifier)
        else:
            number = _finite(supplied_day)
            if number is None or not float(number).is_integer():
                out.append("%s:time" % identifier)
            elif expected_day is None or int(number) != int(expected_day):
                out.append("%s:time" % identifier)
            else:
                day_ok = True
        if day_ok:
            display = (contract or {}).get("display_precision")
            if display is None:
                # legacy: the record's own precision governs
                display = "second" if str(expected_precision or "").lower() == "second" else "day"
            if display == "second":
                if supplied_clock is None:
                    out.append("%s:time_precision" % identifier)
                elif not CLOCK_RE.match(str(supplied_clock).strip()):
                    out.append("%s:time" % identifier)
                elif expected_clock and str(supplied_clock).strip() != str(expected_clock).strip():
                    out.append("%s:time" % identifier)
            elif supplied_clock is not None and str(expected_precision or "").lower() != "second":
                # day display: the answer shows more precision than the record carries
                out.append("%s:time_precision" % identifier)

    claimed = item.get("source_refs")
    if claimed is None:
        out.append("%s:missing_source" % identifier)
    else:
        expected_refs = sorted(str(record.get(field)) for field in
                               ("project_ref", "result_ref", "unit_ref",
                                "collection_ref", "report_ref") if record.get(field))
        mode = (contract or {}).get("source_mode", "exact")
        if not isinstance(claimed, (list, tuple)) or not claimed:
            out.append("%s:source" % identifier)
        else:
            got = sorted(str(ref) for ref in claimed)
            if mode == "supported":
                # any non-empty subset of the record's own lines genuinely supports it,
                # so an equivalent valid anchor set is accepted
                if not set(got) <= set(expected_refs):
                    out.append("%s:source" % identifier)
            elif got != expected_refs:
                out.append("%s:source" % identifier)
    return out


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
              "plan_ok": plan_ok, "plan_problems": None,
              "task_success": False}
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
    pairs: list[tuple[str, object]] = []
    if isinstance(selected, list):
        for item in selected:
            if isinstance(item, str):
                ids.append(item)
                pairs.append((item, None))
            elif isinstance(item, dict):
                identifier = item.get("record_id") or item.get("id")
                if isinstance(identifier, str):
                    ids.append(identifier)
                    pairs.append((identifier, item))
    result["selected_ids"] = ids
    result["fields_supplied"] = _supplied_fields(answer)
    result["fields_match"] = None
    result["field_mismatches"] = []
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
        # A correct abstention delivers the right thing: nothing selected, right status.
        result["task_success"] = result["equivalent_answer"]
        return result
    if reference_status == STATUS_UNSUPPORTED_ROLE:
        result["status_ok"] = status == STATUS_UNSUPPORTED_ROLE
        result["equivalent_answer"] = bool(result["status_ok"] and not selected_set)
        result["task_success"] = result["equivalent_answer"]
        return result

    result["set_exact_match"] = reference_set == selected_set
    if selected_set:
        result["precision"] = len(reference_set & selected_set) / len(selected_set)
    elif not reference_set:
        result["precision"] = 1.0
    result["recall"] = (len(reference_set & selected_set) / len(reference_set)) if reference_set else (
        1.0 if not selected_set else 0.0)

    window = task["spec"]["window"]
    role = task.get("time_role")
    for identifier in ids:
        record = by_id.get(identifier)
        if record is None:
            result["scope_violation"] += 1
            continue
        if not _in_window(record, window, role):
            result["window_violation"] += 1
        if task.get("case_token") and record.get("case_token") != task["case_token"]:
            result["scope_violation"] += 1
    if len(ids) > 1 and task["spec"]["selection"] in {"first", "latest"}:
        days = [role_time(by_id[i], role)[0] for i in ids if i in by_id]
        if len(set(days)) > 1:
            result["order_violation"] = len(days) - 1

    expected_status = STATUS_OK if reference_set else STATUS_EMPTY
    result["status_ok"] = status == expected_status
    result["empty_handling"] = None if reference_set else (status == STATUS_EMPTY)
    if selected_set and selected_set <= set(by_id):
        supplied = result["fields_supplied"]
        mismatches = []
        contract = check_contract(task.get("spec"))
        for identifier, item in pairs:
            record = by_id.get(identifier)
            if record is None:
                continue
            mismatches.extend(_field_mismatches(identifier, item, record, role, contract))
        result["field_mismatches"] = mismatches
        # Whoever produced the fields, the final answer is judged the same way: an
        # expanded field is verified against the record rather than trusted, and the
        # host flag never decides the verdict by itself.
        result["fields_match"] = not mismatches
        # joint_fields_ok keeps its existing meaning, which is only that the frozen
        # record itself carries the joint fields; it is NOT a statement that the
        # answer's own claims were right.
        if fields_expanded_by_host or (supplied["value"] and supplied["unit"]):
            result["joint_fields_ok"] = all(
                by_id[i].get("value") is not None and by_id[i].get("unit") is not None
                and role_time(by_id[i], role)[0] is not None
                and role in available_roles(by_id[i])
                for i in selected_set)
        else:
            result["joint_fields_ok"] = None
            result["fields_insufficient"] = True
    result["equivalent_answer"] = bool(result["set_exact_match"] and result["status_ok"])
    # Final task success: the task's own required fields and source must be delivered,
    # so an omitted field cannot pass.  When nothing is selected there is nothing to
    # bind, so a correct empty answer is not penalised for having no fields.
    # equivalent_answer keeps its older set+status reading and is reported alongside.
    result["task_success"] = bool(result["set_exact_match"] and result["status_ok"]
                                  and (result["fields_match"] is True
                                       or not selected_set))
    return result


def record_view_lines(records, *, limit=None) -> str:
    """Render the frozen record view as a stable, comparable table."""
    lines = ["\t".join(RECORD_FIELDS)]
    for record in records if limit is None else records[:limit]:
        lines.append("\t".join(str(record.get(field)) for field in RECORD_FIELDS))
    return "\n".join(lines)
