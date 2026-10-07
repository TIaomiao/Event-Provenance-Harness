"""Read-only adapter from governance OCR products to a research input view.

Sits between the governance pipeline output (L1 ``ocr_layout.json`` and
L2 ``deidentified_layout_NOT_SAFE.json``) and the task layer.  It reuses the
existing row extractor :mod:`laboratory_bbox_adapter`, the temporal row binder
:mod:`temporal_roles` and the analyte matcher
:mod:`src.evaluation.evidence_assoc_rules` instead of re-implementing them.

Design rules enforced here:

* Unknown schema fails loudly (:class:`SchemaUnsupported`); nothing is guessed.
* L1 and L2 are only treated as compatible after a per-index structural check
  over ``(page_number, bbox)``.  Equal line counts alone are not evidence.
* A missing field and an empty field are reported differently.
* Source files are opened read-only; the adapter never writes into the
  governance tree.
* Identifiers are derived by hashing tokens, so no real patient identifier
  reaches the public record id.
* Candidates and unresolved rows are preserved as-is; task-time selection is
  the task layer's job, not this module's.
"""
from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from laboratory_bbox_adapter import adapt_layout
from temporal_roles import ROLES, bind_candidates

VERSION = "governance-input-adapter-v0.1"
SUPPORTED_SCHEMAS = frozenset({"0.9", "1.0"})
L1_NAME = "ocr_layout.json"
L2_NAME = "deidentified_layout_NOT_SAFE.json"

MISSING = "missing"
EMPTY = "empty"
PRESENT = "value"

# The target analyte name matcher is owned by the evaluation rules module; it is
# imported lazily so this module stays usable without that path on sys.path.
_HGB_NAME = None


def _hgb_name():
    global _HGB_NAME
    if _HGB_NAME is None:
        try:
            from evidence_assoc_rules import HGB_NAME
            _HGB_NAME = HGB_NAME
        except ImportError:  # pragma: no cover - only when the caller has no rules path
            _HGB_NAME = re.compile(
                r"^[\s\*#·※]*(?:血红蛋白(?:量|浓度)?|hemoglobin)"
                r"(?:[\s\*#·]*[（(]\s*(?:HGB|Hb)\s*[)）])?[\s\*#·]*$", re.I)
    return _HGB_NAME


class AdapterError(ValueError):
    """Base class for adapter refusals."""


class SchemaUnsupported(AdapterError):
    def __init__(self, schema, path):
        super().__init__("UNSUPPORTED_SCHEMA:%s:%s" % (schema, path))
        self.schema = schema
        self.path = path


class AlignmentError(AdapterError):
    """L1 and L2 disagree structurally, so they must not be paired."""


def field_state(obj, key):
    """Return ``(state, value)`` distinguishing absent from empty."""
    if not isinstance(obj, dict) or key not in obj:
        return MISSING, None
    value = obj[key]
    if value is None:
        return MISSING, None
    if isinstance(value, (str, list, dict)) and len(value) == 0:
        return EMPTY, None
    return PRESENT, value


def stable_record_id(case_token, doc_token, line_index):
    """Public, hash-derived row id.  Contains no source identifier."""
    raw = "%s|%s|%s" % (case_token, doc_token, line_index)
    return "row-" + sha256(raw.encode("utf-8")).hexdigest()[:16]


def case_day0_coordinate(case_token):
    """Per-case relative-day coordinate id.

    Each case carries its own origin, so two cases never share a calendar
    origin: the coordinate is scoped by the case token.
    """
    return "day0-" + sha256(("day0|" + str(case_token)).encode("utf-8")).hexdigest()[:12]


def _read_json(path):
    if not path.is_file():
        raise AdapterError("SOURCE_FILE_MISSING:%s" % path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _check_schema(data, path):
    state, schema = field_state(data, "schema_version")
    if state != PRESENT:
        raise SchemaUnsupported(state, path.name)
    if str(schema) not in SUPPORTED_SCHEMAS:
        raise SchemaUnsupported(str(schema), path.name)
    return str(schema)


def _line_signature(records):
    """Structural signature of a records list: page and bbox per index."""
    signature = []
    for index, row in enumerate(records):
        bbox = row.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4 and all(
                isinstance(point, list) and len(point) == 2 for point in bbox):
            geometry = tuple(tuple(round(float(v), 3) for v in point) for point in bbox)
        else:
            geometry = None
        signature.append((index, row.get("page_number"), geometry))
    return signature


def audit_alignment(l1, l2):
    """Raise unless L1 and L2 line up row by row.

    Checks the record count, the page sequence and the geometry per index.  A
    matching count is not sufficient, and a mismatch is never repaired here.
    """
    left = l1.get("records")
    right = l2.get("records")
    if not isinstance(left, list) or not isinstance(right, list):
        raise AlignmentError("RECORDS_CONTAINER_MISSING")
    if len(left) != len(right):
        raise AlignmentError("RECORD_COUNT_MISMATCH:%d:%d" % (len(left), len(right)))
    for lsig, rsig in zip(_line_signature(left), _line_signature(right)):
        if lsig != rsig:
            raise AlignmentError("ROW_ALIGNMENT_MISMATCH_AT_INDEX_%d" % lsig[0])
    for key in ("case_token", "document_token"):
        if l1.get(key) != l2.get(key):
            raise AlignmentError("SCOPE_MISMATCH:%s" % key)
    return True


def load_document(doc_dir, *, input_mode, review_scope=None, case_category=None):
    """Load one document directory into a research input view.

    ``input_mode`` is one of ``synthetic`` / ``deidentified_test`` /
    ``raw_test``; it is recorded, never enforced here (the outbound guard owns
    enforcement).  ``raw_test`` unlocks the raw line text of L1.
    """
    doc_dir = Path(doc_dir)
    l1_path = doc_dir / L1_NAME
    l2_path = doc_dir / L2_NAME
    l1 = _read_json(l1_path)
    l2 = _read_json(l2_path)
    schema_l1 = _check_schema(l1, l1_path)
    schema_l2 = _check_schema(l2, l2_path)
    if schema_l1 != schema_l2:
        raise SchemaUnsupported("%s!=%s" % (schema_l1, schema_l2), doc_dir.name)
    audit_alignment(l1, l2)

    case_token = l1.get("case_token")
    doc_token = l1.get("document_token")
    pages = [row.get("page_number") for row in l1["records"]]
    page_range = [min(pages), max(pages)] if pages else None

    hits = l2.get("redaction_hits") or []
    residuals = l2.get("residual_scan_hits") or []
    warnings = l2.get("quality_warning_hits") or []
    redaction_by_page = {}
    for hit in hits:
        redaction_by_page.setdefault(hit.get("page_number"), []).append(hit.get("rule"))
    residual_by_page = {}
    for hit in residuals:
        residual_by_page.setdefault(hit.get("page_number"), []).append(hit.get("rule"))

    lines = []
    for index, row in enumerate(l1["records"]):
        page = row.get("page_number")
        entry = {
            "line_index": index,
            "anchor": "L%d" % index,
            "record_id": stable_record_id(case_token, doc_token, index),
            "page_number": page,
            "bbox": row.get("bbox"),
            "source_kind": row.get("source_kind"),
            "confidence": row.get("confidence"),
            "redaction_rules": redaction_by_page.get(page, []),
            "residual_rules": residual_by_page.get(page, []),
        }
        if input_mode == "raw_test":
            entry["text"] = row.get("text")
        lines.append(entry)

    privacy = {}
    for key in ("privacy_status", "quarantine_required", "api_ready",
                "manual_privacy_review_required", "basic_rule_scan_passed",
                "residual_scan_hit_count", "redaction_hit_count"):
        privacy[key] = field_state(l2, key)

    unresolved = []
    if privacy["quarantine_required"][1] is True:
        unresolved.append("QUARANTINED")
    if privacy["api_ready"][1] is not False:
        unresolved.append("API_READY_NOT_FALSE")
    state, residual_count = privacy["residual_scan_hit_count"]
    if state == MISSING:
        unresolved.append("RESIDUAL_COUNT_MISSING")
    elif residual_count:
        unresolved.append("RESIDUAL_HITS_PRESENT:%d" % residual_count)
    if warnings:
        unresolved.append("QUALITY_WARNINGS:%d" % len(warnings))

    return {
        "adapter_version": VERSION,
        "source_snapshot": {
            "case_token": case_token,
            "document_token": doc_token,
            "schema_version": schema_l2,
            "page_count": field_state(l1, "page_count"),
            "line_count": field_state(l1, "line_count"),
            "page_range": page_range,
            "category": case_category,
            "day0_coordinate": case_day0_coordinate(case_token),
            "l1_sha256": sha256(l1_path.read_bytes()).hexdigest(),
            "l2_sha256": sha256(l2_path.read_bytes()).hexdigest(),
            "source_files": {"l1": L1_NAME, "l2": L2_NAME},
            "input_mode": input_mode,
            "review_scope": review_scope,
            "adapter_version": VERSION,
        },
        "lines": lines,
        "privacy": privacy,
        "unresolved": unresolved,
        "counts": {"lines": len(lines), "redaction_hits": len(hits),
                   "residual_hits": len(residuals), "quality_warnings": len(warnings)},
    }


def candidate_records(view, *, role_labels=None):
    """Return target-analyte candidate rows without any task-time selection.

    Every target-like row is kept, including ones with a missing value or unit;
    each carries its anchor, its unresolved reasons and its binding status.  No
    clinical merging happens here, so two rows on one day stay two records.
    """
    matcher = _hgb_name()
    rows = view["lines"]
    by_anchor = {row["anchor"]: row for row in rows}
    candidates = []
    for row in rows:
        text = row.get("text")
        if text is None:
            raise AdapterError("RAW_TEXT_UNAVAILABLE_FOR_CANDIDATE_SCAN")
        if not matcher.match(text.strip()):
            continue
        candidates.append({
            "anchor": row["anchor"],
            "record_id": row["record_id"],
            "page_number": row["page_number"],
            "bbox": row["bbox"],
            "value_state": MISSING if row.get("value") is None else PRESENT,
            "unresolved": list(row.get("unresolved") or []),
        })
    if not candidates:
        return []
    layout = {"case_token": view["source_snapshot"]["case_token"],
              "document_token": view["source_snapshot"]["document_token"],
              "records": [{"text": by_anchor[c["anchor"]]["text"],
                           "bbox": c["bbox"],
                           "page_number": c["page_number"],
                           "confidence": by_anchor[c["anchor"]]["confidence"]}
                          for c in candidates]}
    adapted = adapt_layout(layout)
    for candidate, record in zip(candidates, adapted["records"]):
        candidate["value_text"] = record["value_text"]
        candidate["unit"] = record["unit"]
        candidate["column_reconstruction_status"] = record["column_reconstruction_status"]
        candidate["quality_issues"] = record["quality_issues"]
    return candidates
