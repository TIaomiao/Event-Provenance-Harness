"""An independent conventional extractor, deliberately not the harness library.

Purpose: arm B must be a conventional baseline that does not borrow the harness's own
extraction or temporal-role modules.  This module therefore imports nothing from
evidence_assoc_rules, temporal_roles or laboratory_bbox_adapter, and re-derives rows from
the line text and bounding box alone.

Scope note: it is written against the documented line shape (text plus bbox) and is
validated on synthetic rows.  Validating it on real material is a local, zero-cost step
that has not been run yet.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")
UNIT = re.compile(
    r"(?:g\s*/\s*dL|g\s*/\s*L|mg\s*/\s*dL|mg\s*/\s*L|mmol\s*/\s*L|10\s*\^?\s*9\s*/\s*L|%)",
    re.I)
DAY_MARKER = re.compile(r"(?:相对日|day)\s*([-+]?\d+)", re.I)


def _bands(lines, tolerance=4.0):
    """Group lines whose vertical spans overlap: a plain row reconstruction."""
    bands, spans = [], []
    for line in lines:
        box = line.get("bbox") or []
        if not box:
            continue
        ys = [point[1] for point in box]
        top, bottom = min(ys), max(ys)
        placed = False
        for index, (other_top, other_bottom) in enumerate(spans):
            if not (bottom < other_top - tolerance or top > other_bottom + tolerance):
                bands[index].append(line)
                spans[index] = (min(top, other_top), max(bottom, other_bottom))
                placed = True
                break
        if not placed:
            bands.append([line])
            spans.append((top, bottom))
    return bands


def _x(line):
    box = line.get("bbox") or [[0.0, 0.0]]
    return min(point[0] for point in box)


def extract_rows(lines, project_markers):
    """Return one record per row band that mentions the project.

    The value is the first numeric token that is not a unit, the unit is the token that
    matches a unit pattern, and the two time roles come from the day markers in the band
    in reading order: collection first, then report.  A band without a value is skipped.
    """
    out = []
    for band in _bands(list(lines)):
        ordered = sorted(band, key=_x)
        joined = " ".join(str(line.get("text") or "") for line in ordered)
        if not any(marker in joined for marker in project_markers):
            continue
        unit, value, days, refs, name = None, None, [], [], None
        for line in ordered:
            text = str(line.get("text") or "").strip()
            if not text:
                continue
            refs.append(line.get("anchor"))
            if name is None and any(marker in text for marker in project_markers):
                name = text
            found_unit = UNIT.search(text)
            if found_unit and unit is None and not DAY_MARKER.search(text):
                unit = found_unit.group(0).replace(" ", "")
                continue
            marker = DAY_MARKER.search(text)
            if marker:
                days.append(int(marker.group(1)))
                continue
            if value is None:
                number = NUMBER.search(text)
                if number:
                    value = float(number.group(0))
        if value is None:
            continue
        out.append({"project_name": name, "value": value, "unit": unit,
                    "collection_day_offset": days[0] if days else None,
                    "report_day_offset": days[1] if len(days) > 1 else None,
                    "source_refs": [ref for ref in refs if ref]})
    return out
