"""Dry-run outbound guard for future approved requests.

The default is deny.  This module never sends a request in dry-run mode and
does not store credentials or full patient payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Callable, Mapping, Sequence


RAW_MARKERS = re.compile(
    r"(?:CONTAINS_RAW_OCR_TEXT_LOCAL_ONLY|姓名|患者|病历号|病例号|Case\s*No|条码|Barcode|联系电话|电话|地址)",
    re.I,
)
REQUIRED_FIELDS = frozenset({"project_name", "value", "unit", "collection_time_role", "report_time_role", "source_anchor"})
PAYLOAD_MODES = frozenset({"synthetic", "deidentified_test", "raw_test"})


@dataclass(frozen=True)
class GuardConfig:
    """Explicit approval settings for a future run.

    Empty ``approved_destinations`` and ``allow_external=False`` intentionally
    keep the default closed.
    """

    code_version: str
    config_version: str
    approved_destinations: frozenset[str] = frozenset()
    approved_endpoints: frozenset[str] = frozenset()
    approved_pool_profiles: frozenset[str] = frozenset()
    allow_external: bool = False


@dataclass
class GuardResult:
    decision: str
    reasons: list[str] = field(default_factory=list)
    body_sha256: str | None = None
    request_metadata: dict[str, Any] = field(default_factory=dict)


def build_request_body(messages: Sequence[Mapping[str, Any]], model: str, max_tokens: int) -> dict[str, Any]:
    """Build the one request body used by both the guard and the client."""
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": list(messages),
    }


def request_body_bytes(messages: Sequence[Mapping[str, Any]], model: str, max_tokens: int) -> bytes:
    return json.dumps(
        build_request_body(messages, model, max_tokens),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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
    raw_body = request_body_bytes(messages, model, max_tokens)
    body_hash = hashlib.sha256(raw_body).hexdigest()
    reasons: list[str] = []
    if not config.allow_external:
        reasons.append("external_sending_disabled")
    if destination not in config.approved_destinations:
        reasons.append("destination_not_approved")
    endpoint = source.get("endpoint_config")
    pool_profile = source.get("pool_profile_id")
    if endpoint not in config.approved_endpoints:
        reasons.append("endpoint_config_not_approved")
    if pool_profile not in config.approved_pool_profiles:
        reasons.append("pool_profile_not_approved")
    payload_mode = source.get("payload_mode")
    if payload_mode not in PAYLOAD_MODES:
        reasons.append("payload_mode_missing_or_invalid")
    elif payload_mode == "raw_test" and source.get("raw_test_authorized") is not True:
        reasons.append("raw_test_authorization_missing")
    elif payload_mode == "deidentified_test" and source.get("api_ready") is not True:
        reasons.append("deidentified_package_not_api_ready")
    if payload_mode != "raw_test" and (source.get("raw_ocr") or "RAW" in str(source.get("sensitivity", "")).upper()):
        reasons.append("raw_ocr_source")
    if payload_mode != "raw_test" and source.get("api_ready") is not True:
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
    if payload_mode != "raw_test" and RAW_MARKERS.search(joined):
        reasons.append("raw_identifier_marker_in_messages")
    metadata = {
        "code_version": config.code_version,
        "config_version": config.config_version,
        "source_version": source.get("source_version"),
        "source_sha256": source.get("source_sha256"),
        "destination": destination,
        "endpoint_config": endpoint,
        "pool_profile_id": pool_profile,
        "purpose": purpose,
        "payload_mode": payload_mode,
        "body_sha256": body_hash,
        "sent": False,
    }
    return GuardResult(
        decision="allow" if not reasons else "block",
        reasons=reasons,
        body_sha256=body_hash,
        request_metadata=metadata,
    )


def dry_run_request(**kwargs: Any) -> GuardResult:
    """Build and inspect a request.  It never calls a network client."""
    return inspect_request(**kwargs)


def execute_request(
    *,
    mode: str,
    guard_check: Callable[[], GuardResult],
    body: bytes,
    sender: Callable[[bytes], Mapping[str, Any]],
    max_retries: int = 0,
    transient_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504}),
) -> dict[str, Any]:
    """Run the full guard-to-sender chain without allowing bypasses.

    ``sender`` is called only for an explicitly approved ``live`` mode.  The
    tests pass an intercepting sender; production callers must pass the same
    final body that was inspected.
    """
    if mode not in {"block", "dry-run", "live"}:
        return {"status": "blocked_not_sent", "reason": "execution_mode_unknown", "attempts": 0}
    if mode == "block":
        return {"status": "blocked_not_sent", "reason": "execution_mode_block", "attempts": 0}
    sent_attempts = []
    for attempt in range(max_retries + 1):
        try:
            guard = guard_check()
        except Exception as error:
            return {"status": "blocked_not_sent", "reason": "guard_exception", "error_type": type(error).__name__, "attempts": len(sent_attempts)}
        if not isinstance(guard, GuardResult) or guard.decision != "allow":
            return {"status": "blocked_not_sent", "reason": "guard_decision_not_allow", "attempts": len(sent_attempts)}
        if guard.body_sha256 != hashlib.sha256(body).hexdigest():
            return {"status": "blocked_not_sent", "reason": "body_hash_mismatch", "attempts": len(sent_attempts)}
        if mode == "dry-run":
            return {"status": "dry_run_not_sent", "attempts": len(sent_attempts)}
        try:
            response = dict(sender(body))
        except Exception as error:
            return {"status": "service_failure", "reason": "sender_exception", "error_type": type(error).__name__, "attempts": len(sent_attempts)}
        sent_attempts.append(response)
        if response.get("http") not in transient_statuses or attempt >= max_retries:
            status = "service_failure" if response.get("http") in transient_statuses else "sent"
            return {"status": status, "attempts": len(sent_attempts), "responses": sent_attempts}
    return {"status": "blocked_not_sent", "reason": "unreachable", "attempts": len(sent_attempts)}


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
