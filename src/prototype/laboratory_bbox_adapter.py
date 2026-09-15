"""Conservative OCR-layout to laboratory record adapter v1.0."""
from __future__ import annotations
import re
from hashlib import sha256

VERSION = "laboratory-bbox-v1.0"
UNIT_RE = re.compile(r"(mmol/L|mg/L|g/L|U/L|10\^9/L|μmol/L|mg/dL|ng/mL|%)")
NUM_RE = re.compile(r"[<>]?\d+(?:\.\d+)?")

def _id(case, doc, page, index):
    return "row-" + sha256(f"{case}|{doc}|{page}|{index}".encode()).hexdigest()[:16]

def adapt_layout(layout, date_candidates=None):
    """Return schema-shaped records without emitting OCR text.

    ``date_candidates`` is an optional list of explicit, pre-parsed date objects;
    this adapter never infers dates or clinical roles from proximity.
    """
    case, doc = layout.get("case_token"), layout.get("document_token")
    if not isinstance(case, str) or not isinstance(doc, str):
        raise ValueError("SOURCE_SCOPE_MISSING")
    records = []
    for i, row in enumerate(layout.get("records", [])):
        text = row.get("text", "")
        if not isinstance(text, str):
            continue
        unit_match = UNIT_RE.search(text)
        nums = NUM_RE.findall(text[:unit_match.start()] if unit_match else text)
        unit = unit_match.group(1) if unit_match else None
        value = nums[-1] if nums else None
        issues = []
        if not unit: issues.append("UNIT_NOT_FOUND")
        if not value: issues.append("VALUE_NOT_FOUND")
        bbox = row.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4): issues.append("BBOX_INVALID")
        records.append({"record_id": _id(case, doc, row.get("page_number"), i),
                        "test_name": None, "test_code": None,
                        "value_numeric": float(value.replace("<", "")) if value and "<" not in value and ">" not in value else None,
                        "value_text": value, "unit": unit, "relative_day": None,
                        "source_page": row.get("page_number"), "source_bbox": bbox,
                        "source_cells": {"row_index": i}, "ocr_confidence": row.get("confidence"),
                        "category_parser_version": VERSION,
                        "column_reconstruction_status": "ambiguous" if issues else "complete",
                        "validation_status": "needs_review" if issues else "valid",
                        "quality_issues": issues})
    return {"parser_status": "complete" if records and all(r["validation_status"] == "valid" for r in records) else "needs_review",
            "parser_version": "bbox-table-v0.1", "target_tables": ["laboratory_observations"], "records": records}
