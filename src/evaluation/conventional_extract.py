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
DATE = re.compile(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})")


def _date(text):
    """An absolute date in the text as YYYY-MM-DD, or None."""
    found = DATE.search(text or "")
    if not found:
        return None
    year, month, day = (int(part) for part in found.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return "%04d-%02d-%02d" % (year, month, day)


def to_day_offsets(records):
    """Turn absolute collection dates into offsets from the earliest one."""
    dates = [r.get("collection_date") for r in records if r.get("collection_date")]
    if not dates:
        return records
    origin = min(dates)
    from datetime import date as _d
    base = _d(*[int(x) for x in origin.split("-")]).toordinal()
    for record in records:
        for role in ("collection", "report"):
            value = record.get("%s_date" % role)
            if value:
                record["%s_day_offset" % role] = (
                    _d(*[int(x) for x in value.split("-")]).toordinal() - base)
    return records


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


def _y(line):
    box = line.get("bbox") or [[0.0, 0.0]]
    return min(point[1] for point in box)


def _page_times(lines):
    """Every dated line, grouped by page, as (y, date_text) pairs.

    On a scanned lab report the collection and report stamps usually sit in the page
    header rather than on the result row, so they have to be associated across rows.
    """
    pages = {}
    for line in lines:
        if not line.get("bbox"):
            continue
        found = _date(str(line.get("text") or ""))
        if not found:
            continue
        pages.setdefault(line.get("page_number"), []).append((_y(line), found))
    for key in pages:
        pages[key].sort()
    return pages


def extract_rows(lines, project_markers):
    """Return one record per row band that mentions the project.

    The value is the first numeric token that is not a unit, the unit is the token that
    matches a unit pattern, and the two time roles come from the day markers in the band
    in reading order: collection first, then report.  A band without a value is skipped.
    """
    all_lines = list(lines)
    page_times = _page_times(all_lines)
    out = []
    for band in _bands(all_lines):
        ordered = sorted(band, key=_x)
        joined = " ".join(str(line.get("text") or "") for line in ordered)
        if not any(marker in joined for marker in project_markers):
            continue
        unit, value, days, dates, refs, name = None, None, [], [], [], None
        for line in ordered:
            raw = str(line.get("text") or "").strip()
            if not raw:
                continue
            refs.append(line.get("anchor"))
            if name is None and any(marker in raw for marker in project_markers):
                name = raw
            marker = DAY_MARKER.search(raw)
            if marker:
                days.append(int(marker.group(1)))
                continue
            absolute = _date(raw)
            if absolute:
                dates.append(absolute)
            # a date must not be read as a value, so dates are removed before numbers
            text = DATE.sub(" ", raw)
            text = DAY_MARKER.sub(" ", text)
            found_unit = UNIT.search(text)
            if found_unit and unit is None:
                unit = found_unit.group(0).replace(" ", "")
                if value is None:
                    before = NUMBER.findall(text[:found_unit.start()])
                    after = NUMBER.findall(text[found_unit.end():])
                    if before:
                        value = float(before[-1])
                    elif after:
                        value = float(after[0])
                continue
            if value is None:
                number = NUMBER.search(text)
                if number:
                    value = float(number.group(0))
        if value is None:
            continue
        if dates:
            pass
        else:
            # no date on the row itself: take the two nearest dated lines on the page
            candidates = page_times.get(ordered[0].get("page_number")) or []
            if candidates:
                band_y = _y(ordered[0])
                nearest = sorted(candidates, key=lambda item: abs(item[0] - band_y))[:2]
                nearest.sort()
                dates = [entry[1] for entry in nearest]
        out.append({"project_name": name, "value": value, "unit": unit,
                    "collection_day_offset": days[0] if days else None,
                    "report_day_offset": days[1] if len(days) > 1 else None,
                    "collection_date": dates[0] if dates else None,
                    "report_date": dates[1] if len(dates) > 1 else None,
                    "source_refs": [ref for ref in refs if ref]})
    return out
