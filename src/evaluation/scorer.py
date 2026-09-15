"""Offline synthetic-development evaluator; never imports the system under test.

See DESIGN.md for the provisional C-owned serialization and matching profile.
Public reports contain aggregate counters only, never evidence or answer values.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path

VERSION = "c-eval-dev-v0.1"
PROTOCOL = "research-card-v0.3/shared-synthetic-v0.1"
ROLES = {"sampling", "report", "record", "document", "unknown"}
BINDINGS = {"explicit", "unknown", "unresolved", "conflicting"}


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value, nonempty=False):
    return (isinstance(value, list) and (bool(value) or not nonempty)
            and all(_text(v) for v in value) and len(value) == len(set(value)))


def _value(value):
    """Decimal equality only; comparators/text remain literal. No unit conversion."""
    value = value.strip()
    try:
        number = Decimal(value)
        if number.is_finite():
            return ("number", number)
    except InvalidOperation:
        pass
    return ("literal", value)


def _semantic(assertion):
    return tuple(assertion[k] for k in
                 ("role", "relative_day", "coordinate_id", "binding_status"))


def _provenance(assertion):
    return tuple(assertion[k] for k in
                 ("date_ref", "role_ref", "scope_ref"))


def _times(observation, role=None):
    return Counter(_semantic(a) for a in observation["time_assertions"]
                   if role is None or a["role"] == role)


def _validate_observations(observations):
    _require(isinstance(observations, list), "OBSERVATIONS_NOT_LIST")
    ids = set()
    for obs in observations:
        _require(isinstance(obs, dict), "OBSERVATION_NOT_OBJECT")
        _require(all(_text(obs.get(k)) for k in
                     ("observation_id", "case_token", "item", "value", "unit")),
                 "OBSERVATION_FIELDS_INVALID")
        key = (obs["case_token"], obs["observation_id"])
        _require(key not in ids, "DUPLICATE_OBSERVATION_ID")
        ids.add(key)
        _require(_strings(obs.get("source_refs"), nonempty=True), "SOURCE_REFS_INVALID")
        assertions = obs.get("time_assertions")
        _require(isinstance(assertions, list) and assertions, "TIME_ASSERTIONS_INVALID")
        seen = set()
        for a in assertions:
            _require(isinstance(a, dict), "TIME_ASSERTION_NOT_OBJECT")
            _require(a.get("role") in ROLES and a.get("binding_status") in BINDINGS,
                     "TIME_STATUS_INVALID")
            _require(all(k in a for k in ("relative_day", "coordinate_id", "date_ref",
                                         "role_ref", "scope_ref")), "TIME_FIELDS_MISSING")
            day = a["relative_day"]
            _require(day is None or type(day) is int, "RELATIVE_DAY_INVALID")
            _require(all(a[k] is None or _text(a[k]) for k in
                         ("coordinate_id", "date_ref", "role_ref", "scope_ref")),
                     "TIME_REFERENCE_INVALID")
            if day is not None:
                _require(_text(a["coordinate_id"]) and _text(a["date_ref"]),
                         "DATED_ASSERTION_MISSING_PROVENANCE")
            if a["binding_status"] in {"explicit", "conflicting"}:
                _require(day is not None and a["role"] != "unknown"
                         and _text(a["role_ref"]) and _text(a["scope_ref"]),
                         "BOUND_ASSERTION_MISSING_SUPPORT")
            encoded = _semantic(a) + _provenance(a)
            _require(encoded not in seen, "DUPLICATE_TIME_ASSERTION")
            seen.add(encoded)
        _require(any(a["role"] == "sampling" for a in assertions),
                 "SAMPLING_STATUS_MISSING")


def _validate_gold(gold):
    _require(isinstance(gold, dict) and gold.get("protocol") == PROTOCOL,
             "GOLD_PROTOCOL_MISMATCH")
    _validate_observations(gold.get("observations"))
    evidence = gold.get("evidence")
    _require(isinstance(evidence, list), "GOLD_EVIDENCE_INVALID")
    index = {}
    for ref in evidence:
        _require(isinstance(ref, dict) and _text(ref.get("evidence_id"))
                 and _text(ref.get("case_token")) and ref.get("kind") in
                 {"row", "date", "role", "scope"}, "GOLD_EVIDENCE_INVALID")
        _require(ref["evidence_id"] not in index, "GOLD_DUPLICATE_EVIDENCE")
        index[ref["evidence_id"]] = ref
    owned_rows = set()
    for obs in gold["observations"]:
        refs = set(obs["source_refs"])
        _require(all(r in index and index[r]["kind"] == "row" for r in refs),
                 "GOLD_ROW_REFERENCE_INVALID")
        _require(not owned_rows.intersection(refs), "GOLD_ROW_OWNERSHIP_AMBIGUOUS")
        owned_rows.update(refs)
        for a in obs["time_assertions"]:
            for key, kind in (("date_ref", "date"), ("role_ref", "role"), ("scope_ref", "scope")):
                ref = a[key]
                if ref is not None:
                    _require(ref in index and index[ref]["kind"] == kind,
                             "GOLD_TIME_REFERENCE_INVALID")
                    refs.add(ref)
        _require(all(index[r]["case_token"] == obs["case_token"] for r in refs),
                 "GOLD_CROSS_CASE_REFERENCE")
    seen_pairs = set()
    for pair in gold.get("identity_pairs", []):
        _require(isinstance(pair, dict) and _strings(pair.get("rows"))
                 and len(pair["rows"]) == 2 and pair.get("relation") in
                 {"same", "different", "unresolved"}, "GOLD_PAIR_INVALID")
        key = tuple(sorted(pair["rows"]))
        _require(key not in seen_pairs and set(key) <= owned_rows, "GOLD_PAIR_INVALID")
        _require(index[key[0]]["case_token"] == index[key[1]]["case_token"],
                 "GOLD_CROSS_CASE_PAIR")
        seen_pairs.add(key)
    return index


def _match(edges):
    """Maximum-cardinality bipartite matching, independent of input order."""
    owner = {}

    def visit(pred, seen):
        for ref in edges[pred]:
            if ref in seen:
                continue
            seen.add(ref)
            if ref not in owner or visit(owner[ref], seen):
                owner[ref] = pred
                return True
        return False

    for pred in range(len(edges)):
        visit(pred, set())
    return [(pred, ref) for ref, pred in sorted(owner.items())]


def _checks(pred, ref):
    value_ok = pred["item"].strip() == ref["item"].strip() and _value(pred["value"]) == _value(ref["value"])
    unit_ok = pred["unit"].strip() == ref["unit"].strip()
    sampling_ok = _times(pred, "sampling") == _times(ref, "sampling")
    times_ok = _times(pred) == _times(ref)
    # The independent reference specifies which claim each citation supports.
    # A real-but-unrelated ID, label or table scope cannot earn support credit.
    allowed = {_semantic(a) + _provenance(a) for a in ref["time_assertions"]}
    source_ok = (value_ok and unit_ok
                 and set(pred["source_refs"]) == set(ref["source_refs"])
                 and all(_semantic(a) + _provenance(a) in allowed
                         for a in pred["time_assertions"]))
    return {"value": value_ok, "unit": unit_ok, "sampling_time": sampling_ok,
            "all_time_assertions": times_ok, "source_support": source_ok,
            "joint": value_ok and unit_ok and sampling_ok and source_ok,
            "full_record": value_ok and unit_ok and times_ok and source_ok}


def _identity(gold, prediction, index):
    groups = prediction.get("event_groups")
    result = {"status": "not_reported", "same_pairs": 0, "different_pairs": 0,
              "unresolved_pairs": 0, "correct": 0, "false_merge": 0,
              "false_split": 0, "missing_decision": 0, "unsupported_resolution": 0}
    membership = {}
    emitted_rows = {r for obs in prediction["observations"] for r in obs["source_refs"]
                    if r in index and index[r]["kind"] == "row"
                    and index[r]["case_token"] == obs["case_token"]}
    if groups is not None:
        _require(isinstance(groups, list), "EVENT_GROUPS_INVALID")
        for ordinal, group in enumerate(groups):
            _require(_strings(group, nonempty=True), "EVENT_GROUP_INVALID")
            for row in group:
                _require(row in index and index[row]["kind"] == "row"
                         and row not in membership, "EVENT_GROUP_ROW_INVALID")
                if row in emitted_rows:
                    membership[row] = ordinal
            _require(len({index[row]["case_token"] for row in group}) == 1,
                     "EVENT_GROUP_CROSS_CASE")
        result["status"] = "reported"
    for pair in gold.get("identity_pairs", []):
        relation = pair["relation"]
        result[relation + "_pairs"] += 1
        left, right = pair["rows"]
        if left not in membership or right not in membership:
            result["missing_decision"] += 1
            continue
        if relation == "unresolved":
            result["unsupported_resolution"] += 1
        elif membership[left] == membership[right]:
            result["correct" if relation == "same" else "false_merge"] += 1
        else:
            result["correct" if relation == "different" else "false_split"] += 1
    return result


def summarize_cost(cost):
    if cost is None:
        return {"status": "not_recorded", "calls": None, "failed_calls": None,
                "input_tokens": None, "output_tokens": None, "wall_seconds": None,
                "amount": None, "currency": None}
    _require(isinstance(cost, dict) and isinstance(cost.get("attempts"), list), "COST_INVALID")
    totals = {"status": "recorded", "calls": len(cost["attempts"]), "failed_calls": 0}
    for key in ("input_tokens", "output_tokens", "amount"):
        totals[key] = 0
    attempt_ids = set()
    for attempt in cost["attempts"]:
        _require(isinstance(attempt, dict) and _text(attempt.get("attempt_id"))
                 and attempt["attempt_id"] not in attempt_ids
                 and attempt.get("status") in {"success", "failed", "timeout"}, "COST_ATTEMPT_INVALID")
        attempt_ids.add(attempt["attempt_id"])
        totals["failed_calls"] += attempt["status"] != "success"
        for key in ("input_tokens", "output_tokens", "amount"):
            value = attempt.get(key)
            _require(value is None or (type(value) in (int, float) and math.isfinite(value)
                                      and value >= 0), "COST_VALUE_INVALID")
            if key != "amount":
                _require(value is None or type(value) is int, "TOKEN_COUNT_INVALID")
            if value is None or totals[key] is None:
                totals[key] = None
            else:
                totals[key] += value
    wall = cost.get("wall_seconds")
    _require(wall is None or (type(wall) in (int, float) and math.isfinite(wall) and wall >= 0),
             "COST_WALL_TIME_INVALID")
    currency = cost.get("currency")
    _require(currency is None or currency in {"USD", "CNY", "EUR"}, "COST_CURRENCY_INVALID")
    _require(totals["amount"] in (None, 0) or currency is not None, "COST_CURRENCY_MISSING")
    totals.update(wall_seconds=wall, currency=currency)
    if any(totals[k] is None for k in ("input_tokens", "output_tokens", "amount", "wall_seconds")):
        totals["status"] = "partial"
    return totals


def score(gold, prediction):
    index = _validate_gold(gold)
    _require(isinstance(prediction, dict), "PREDICTION_NOT_OBJECT")
    refs = sorted(gold["observations"], key=lambda x: (x["case_token"], sorted(x["source_refs"])))
    report = {"evaluator_version": VERSION, "protocol": PROTOCOL,
              "scope": "synthetic_development", "gold_count": len(refs)}
    # Keep failed/invalid submissions in the cost ledger too.
    try:
        report["cost"] = summarize_cost(prediction.get("cost"))
    except (ValueError, TypeError) as exc:
        report["cost"] = {"status": "invalid", "error_code":
                          str(exc) if isinstance(exc, ValueError) else "COST_INVALID"}
    try:
        _require(prediction.get("protocol") == PROTOCOL, "PREDICTION_PROTOCOL_MISMATCH")
        _validate_observations(prediction.get("observations"))
        preds = sorted(prediction["observations"], key=lambda x: json.dumps(x, sort_keys=True))
    except (ValueError, TypeError) as exc:
        rows = prediction.get("observations")
        report.update(status="invalid_output", error_code=str(exc) if isinstance(exc, ValueError)
                      else "PREDICTION_SCHEMA_INVALID", joint_tp=0,
                      joint_fn=len(refs), joint_fp=len(rows) if isinstance(rows, list) else None)
        return report
    report.update(status="scored", prediction_count=len(preds))
    anchors = [[j for j, ref in enumerate(refs) if pred["case_token"] == ref["case_token"]
                and set(pred["source_refs"]) & set(ref["source_refs"])] for pred in preds]
    aligned = _match(anchors)
    checks = {(i, j): _checks(preds[i], refs[j]) for i, j in aligned}
    names = ("value", "unit", "sampling_time", "all_time_assertions", "source_support", "joint", "full_record")
    report["aligned_count"] = len(aligned)
    report["missing_observations"] = len(refs) - len(aligned)
    report["extra_observations"] = len(preds) - len(aligned)
    report["ambiguous_source_predictions"] = sum(len(e) > 1 for e in anchors)
    # Ambiguous anchors get no diagnostic credit: no score-maximizing field alignment.
    report["field_correct"] = {name: sum(checks[i, j][name] for i, j in aligned
                                        if len(anchors[i]) == 1) for name in names}
    for name in ("joint", "full_record"):
        edges = [[j for j in anchors[i] if _checks(pred, refs[j])[name]]
                 for i, pred in enumerate(preds)]
        tp = len(_match(edges))
        report.update({name + "_tp": tp, name + "_fn": len(refs) - tp,
                       name + "_fp": len(preds) - tp,
                       name + "_precision": tp / len(preds) if preds else None,
                       name + "_recall": tp / len(refs) if refs else None,
                       name + "_f1": 2 * tp / (len(refs) + len(preds)) if refs or preds else None})
    report["unknown_sampling"] = {
        "gold": sum(all(key[1] is None for key in _times(r, "sampling")) for r in refs),
        "predicted": sum(all(key[1] is None for key in _times(p, "sampling")) for p in preds),
        "correct": sum(_times(refs[j], "sampling") == _times(preds[i], "sampling")
                       and all(key[1] is None for key in _times(refs[j], "sampling"))
                       for i, j in aligned if len(anchors[i]) == 1)}
    try:
        report["identity"] = _identity(gold, prediction, index)
    except ValueError as exc:
        report["identity"] = {"status": "invalid", "error_code": str(exc)}
    return report


def main():
    parser = argparse.ArgumentParser(description="Aggregate-only offline development scoring")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = score(json.loads(args.gold.read_text(encoding="utf-8")),
                       json.loads(args.prediction.read_text(encoding="utf-8")))
    except (ValueError, TypeError, KeyError, OSError):
        print(json.dumps({"status": "input_error", "error_code": "INPUT_REJECTED"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "scored" else 2


if __name__ == "__main__":
    raise SystemExit(main())
