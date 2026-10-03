"""Dry-run outbound guard for future approved requests.

The default is deny.  This module never sends a request in dry-run mode and
does not store credentials or full patient payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


RAW_MARKERS = re.compile(
    r"(?:CONTAINS_RAW_OCR_TEXT_LOCAL_ONLY|姓名|患者|病历号|病例号|Case\s*No|条码|Barcode|联系电话|电话|地址)",
    re.I,
)
REQUIRED_FIELDS = frozenset({"project_name", "value", "unit", "collection_time_role", "report_time_role", "source_anchor"})


@dataclass(frozen=True)
class GuardConfig:
    """Explicit approval settings for a future run.

    Empty ``approved_destinations`` and ``allow_external=False`` intentionally
    keep the default closed.
    """

    code_version: str
    config_version: str
    approved_destinations: frozenset[str] = frozenset()
    allow_external: bool = False


@dataclass
class GuardResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    body_sha256: str | None = None
    request_metadata: dict[str, Any] = field(default_factory=dict)


def _body_bytes(messages: Sequence[Mapping[str, Any]], model: str, max_tokens: int) -> bytes:
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": list(messages),
    }
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def inspect_request(
    *,
    messages: Sequence[Mapping[str, Any]],
    model: str,
    max_tokens: int,
    source: Mapping[str, Any],
    task_fields: Mapping[str, Any],
    destination: str,
    purpose: str,
    config: GuardConfig,
) -> GuardResult:
    """Inspect a final request body without sending it."""
    raw_body = _body_bytes(messages, model, max_tokens)
    body_hash = hashlib.sha256(raw_body).hexdigest()
    reasons: list[str] = []
    if not config.allow_external:
        reasons.append("external_sending_disabled")
    if destination not in config.approved_destinations:
        reasons.append("destination_not_approved")
    if source.get("raw_ocr") or "RAW" in str(source.get("sensitivity", "")).upper():
        reasons.append("raw_ocr_source")
    if source.get("api_ready") is not True:
        reasons.append("api_ready_not_true")
    if not source.get("source_version") or not source.get("source_sha256"):
        reasons.append("source_version_or_hash_missing")
    if not source.get("review_scope"):
        reasons.append("review_scope_missing")
    if source.get("purpose") != purpose:
        reasons.append("purpose_mismatch")
    if source.get("destination") != destination:
        reasons.append("source_destination_mismatch")
    if source.get("hash_matches") is not True:
        reasons.append("source_hash_mismatch")
    if source.get("unknown_state"):
        reasons.append("unknown_state_present")
    missing = sorted(REQUIRED_FIELDS - set(task_fields))
    if missing:
        reasons.append("task_fields_missing:" + ",".join(missing))
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    if RAW_MARKERS.search(joined):
        reasons.append("raw_identifier_marker_in_messages")
    metadata = {
        "code_version": config.code_version,
        "config_version": config.config_version,
        "source_version": source.get("source_version"),
        "source_sha256": source.get("source_sha256"),
        "destination": destination,
        "purpose": purpose,
        "body_sha256": body_hash,
        "sent": False,
    }
    return GuardResult(
        decision="allow_dry_run" if not reasons else "block",
        reasons=reasons,
        body_sha256=body_hash,
        request_metadata=metadata,
    )


def dry_run_request(**kwargs: Any) -> GuardResult:
    """Build and inspect a request.  It never calls a network client."""
    return inspect_request(**kwargs)


def request_ledger_metadata(result: GuardResult, *, request_id: str, cost_basis: Mapping[str, Any]) -> dict[str, Any]:
    """Return the controlled ledger fields for a future request.

    The full body belongs in a controlled store if an approved run occurs.  It
    is not returned by this helper and must never enter GitHub.
    """
    return {
        "request_id": request_id,
        "decision": result.decision,
        "body_sha256": result.body_sha256,
        **result.request_metadata,
        "cost_basis": dict(cost_basis),
        "full_body_storage": "controlled_only_if_approved",
    }
