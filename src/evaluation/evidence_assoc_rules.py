"""Offline rules for evidence-association candidate drafts.

This module is deliberately separate from the historical pilot outputs.  It
does not create a gold answer and it never reads or sends a real patient file.
The tests use synthetic OCR rows only.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import re
from typing import Any, Iterable


NUMBER = re.compile(r"[<>]?[-+]?\d+(?:[.,]\d+)?")
RANGE = re.compile(r"[-+]?\d+(?:[.,]\d+)?\s*(?:--|[-~～至])\s*[-+]?\d+(?:[.,]\d+)?")
UNIT = re.compile(
    r"(?:g\s*/\s*dL|g\s*/\s*L|mg\s*/\s*dL|mg\s*/\s*L|mmol\s*/\s*L|10\s*\^?\s*9\s*/\s*L|%)",
    re.I,
)
HGB_ALIAS = re.compile(r"(?<![A-Za-z])HGB(?![A-Za-z])", re.I)
HGB_NAME = re.compile(r"(?:血红蛋白(?:量)?|hemoglobin)", re.I)
ROLE = {
    "collection": re.compile(r"(?:采集时间|采样时间|采血时间|collection\s*time|collected)", re.I),
    "report": re.compile(r"(?:报告时间|报告日期|report\s*time|reported)", re.I),
}
TIME = re.compile(
    r"(?P<year>20\d{2})\s*[-/.年]\s*(?P<month>\d{1,2})\s*[-/.月]\s*(?P<day>\d{1,2})"
    r"(?:\s*日)?(?:\s*(?P<hour>\d{1,2})\s*[:：]\s*(?P<minute>\d{2})"
    r"(?:\s*[:：]\s*(?P<second>\d{2}))?)?"
)


def _hash_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _text(row: dict[str, Any]) -> str:
    return str(row.get("text") or "").strip()


def _norm_unit(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", "", value.lower())
    return {
        "g/dl": "g/dL",
        "g/l": "g/L",
        "mg/dl": "mg/dL",
        "mg/l": "mg/L",
    }.get(compact, value)


def _number(text: str) -> float | None:
    token = NUMBER.search(text)
    if not token or RANGE.search(text):
        return None
    try:
        return float(token.group(0).replace(",", ".").replace("<", "").replace(">", ""))
    except ValueError:
        return None


def _to_g_l(value: float | None, unit: str | None) -> float | None:
    if value is None or unit is None:
        return None
    unit = _norm_unit(unit)
    if unit == "g/dL":
        return value * 10
    if unit == "g/L":
        return value
    if unit == "mg/dL":
        return value / 100
    if unit == "mg/L":
        return value / 1000
    return None


def _time_from_text(text: str) -> tuple[datetime | None, str]:
    match = TIME.search(text.replace("／", "/"))
    if not match:
        return None, "missing"
    parts = {k: int(v) for k, v in match.groupdict().items() if v is not None}
    precision = "second" if "second" in parts else "minute" if "minute" in parts else "day"
    try:
        return datetime(
            parts["year"], parts["month"], parts["day"], parts.get("hour", 0),
            parts.get("minute", 0), parts.get("second", 0),
        ), precision
    except ValueError:
        return None, "invalid"


def _role_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(rows):
        text = _text(row)
        for role, pattern in ROLE.items():
            if pattern.search(text):
                value, precision = _time_from_text(text)
                result.append({
                    "role": role,
                    "index": index,
                    "ref": row.get("line_ref"),
                    "time": value,
                    "precision": precision,
                })
    return result


def _project_at(rows: list[dict[str, Any]], index: int) -> tuple[str | None, str | None]:
    text = _text(rows[index])
    if HGB_NAME.search(text):
        return text, rows[index].get("line_ref")
    if HGB_ALIAS.search(text) and index > 0 and HGB_NAME.search(_text(rows[index - 1])):
        return _text(rows[index - 1]), rows[index - 1].get("line_ref")
    return None, None


def _find_hgb_starts(rows: list[dict[str, Any]]) -> list[int]:
    starts = []
    for index, row in enumerate(rows):
        text = _text(row)
        if HGB_NAME.search(text):
            starts.append(index)
        elif HGB_ALIAS.search(text) and (index == 0 or not HGB_NAME.search(_text(rows[index - 1]))):
            starts.append(index)
    return starts


def _nearest_role(role_rows: list[dict[str, Any]], role: str, index: int) -> dict[str, Any] | None:
    candidates = [r for r in role_rows if r["role"] == role and r["time"] is not None]
    following = [r for r in candidates if r["index"] >= index]
    pool = following or candidates
    return min(pool, key=lambda r: abs(r["index"] - index), default=None)


def extract_hgb_candidates(docs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract HGB drafts without turning reference ranges into results.

    A draft is ``invalid_task`` when project identity is not anchored.  A
    missing unit or unresolved time is a state, not an automatic contradiction.
    """
    output: list[dict[str, Any]] = []
    for doc in docs:
        if doc.get("category") != "laboratory_report":
            continue
        rows_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in doc.get("records") or []:
            rows_by_page[int(row.get("page") or row.get("page_number") or 0)].append(row)
        for page, rows in rows_by_page.items():
            role_rows = _role_rows(rows)
            for start in _find_hgb_starts(rows):
                project_name, project_ref = _project_at(rows, start)
                begin = start + 1
                result_ref = None
                result_text = None
                value = None
                unit = None
                unit_ref = None
                reference_text = None
                reference_ref = None
                for cursor in range(begin, min(len(rows), begin + 6)):
                    text = _text(rows[cursor])
                    if not text or ROLE["collection"].search(text) or ROLE["report"].search(text):
                        continue
                    if result_ref is None:
                        candidate_value = _number(text)
                        if candidate_value is not None:
                            result_ref = rows[cursor].get("line_ref")
                            result_text = text
                            value = candidate_value
                            inline_unit = UNIT.search(text)
                            if inline_unit:
                                unit = _norm_unit(inline_unit.group(0))
                                unit_ref = result_ref
                            continue
                    if result_ref is not None and unit is None:
                        inline_unit = UNIT.search(text)
                        if inline_unit:
                            unit = _norm_unit(inline_unit.group(0))
                            unit_ref = rows[cursor].get("line_ref")
                            continue
                    if result_ref is not None and RANGE.search(text):
                        reference_text = text
                        reference_ref = rows[cursor].get("line_ref")
                        break
                collection = _nearest_role(role_rows, "collection", start)
                report = _nearest_role(role_rows, "report", start)
                identity_status = "explicit" if project_name and project_ref else "invalid_task"
                source_refs = [x for x in [project_ref, result_ref, unit_ref, reference_ref,
                                           collection and collection["ref"], report and report["ref"]] if x]
                binding_status = "explicit" if result_ref and collection and project_ref else "unresolved"
                record_id = _hash_id(doc["doc"], str(page), str(project_ref), str(result_ref)) if identity_status == "explicit" else None
                output.append({
                    "record_id": record_id,
                    "identity_status": identity_status,
                    "binding_status": binding_status,
                    "doc": doc["doc"],
                    "page": page,
                    "project_name": project_name,
                    "project_ref": project_ref,
                    "result_text": result_text,
                    "result_ref": result_ref,
                    "value": value,
                    "unit": unit,
                    "unit_ref": unit_ref,
                    "reference_interval": reference_text,
                    "reference_ref": reference_ref,
                    "collection_ref": collection and collection["ref"],
                    "collection_time": collection and collection["time"],
                    "collection_precision": collection and collection["precision"],
                    "report_ref": report and report["ref"],
                    "report_time": report and report["time"],
                    "report_precision": report and report["precision"],
                    "value_g_l": _to_g_l(value, unit),
                    "source_refs": source_refs,
                })
    return output


def latest_by_collection_time(candidates: Iterable[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        c for c in candidates
        if c.get("identity_status") == "explicit" and c.get("collection_time") is not None
    ]
    if not eligible:
        return {"status": "insufficient", "candidates": [], "reason": "no_explicit_collection_time"}
    if any(c.get("collection_precision") not in {"second", "minute"} for c in eligible):
        return {"status": "insufficient", "candidates": eligible, "reason": "date_precision_insufficient"}
    latest_time = max(c["collection_time"] for c in eligible)
    latest = [c for c in eligible if c["collection_time"] == latest_time]
    if len(latest) > 1:
        return {"status": "undetermined", "candidates": latest, "reason": "collection_time_tie"}
    return {"status": "ok", "candidates": latest, "reason": None}


def classify_c_candidate(candidate: dict[str, Any], *, require_unit: bool = False) -> str:
    """Classify only an identity-complete draft; never call null a contradiction."""
    if candidate.get("identity_status") != "explicit":
        return "invalid_task"
    if candidate.get("value") is None or candidate.get("collection_time") is None:
        return "insufficient"
    if require_unit and candidate.get("unit") is None:
        return "insufficient"
    return "supported"
