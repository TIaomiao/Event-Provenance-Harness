"""Replay legacy date transforms and create a separate candidate time-coordinate sidecar.

Run beside protected L1/L2 files. Never emit source text or absolute dates.
The sidecar does not establish a clinical event role or authorize data release.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import date
import hashlib
import json
import math
import os
from pathlib import Path
import re
from types import SimpleNamespace


VERSION = 'temporal-rebase-v0.3.1'
TOKEN = re.compile(r'\[相对日\+(-?\d+)\]')
DATE_MASK = re.compile(r'\[(?:日期已移除|非就诊日期已移除)\]')
CASE = re.compile(r'CASE-(?:\d{2,8}|SYNTHETIC)')
DOCUMENT = re.compile(r'(?:DOC-\d{3,8}|case-(?:\d{2,8}|synthetic)-doc-\d{3,8})', re.I)
RAW_SENSITIVITY = 'CONTAINS_RAW_OCR_TEXT_LOCAL_ONLY'
L2_SENSITIVITY = 'BASIC_RULE_REDACTED_NOT_SAFE_MANUAL_REVIEW_REQUIRED'


class TemporalError(ValueError):
    """Messages are fixed safe codes, never input values or paths."""


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class LegacyRules:
    """Load only audited pure date functions from the actual producer source."""

    NAMES = {
        'FULL_DATE_PATTERN', 'ADJACENT_DATETIME_PATTERN', 'SHORT_YEAR_DATE_PATTERN',
        'PARTIAL_DATE_PATTERN', '_normalize_text', '_date_from_match',
        '_relative_date_context', '_replace_dates_with_relative_days',
    }

    def __init__(self, source: str):
        tree = ast.parse(source)
        selected, found = [], set()
        for node in tree.body:
            name = node.name if isinstance(node, ast.FunctionDef) else (
                node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) else None
            )
            if name in self.NAMES:
                if name in found:
                    raise TemporalError('DUPLICATE_LEGACY_DEFINITION')
                selected.append(node)
                found.add(name)
        if found != self.NAMES:
            raise TemporalError('LEGACY_DATE_RULES_INCOMPLETE')
        future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
        module = ast.fix_missing_locations(ast.Module(body=[future, *selected], type_ignores=[]))
        self.namespace = {'re': re, 'date': date}
        exec(compile(module, '<legacy-date-rules>', 'exec'), self.namespace)
        self.source_sha256 = digest_bytes(source.encode('utf-8'))
        self.rule_sha256 = digest_bytes(ast.dump(module, include_attributes=False).encode())

    def anchor(self, pages):
        return self.namespace['_relative_date_context'](pages)[0]

    def replace(self, text, anchor):
        return self.namespace['_replace_dates_with_relative_days'](text, anchor, anchor.year)[0]

    def normalize(self, text):
        return self.namespace['_normalize_text'](text)

    def full_dates(self, text):
        """Conservative explicit dates; reject two-digit years, month/day, invalid dates."""
        remaining = list(text)
        spans = []
        for name in ['ADJACENT_DATETIME_PATTERN', 'FULL_DATE_PATTERN']:
            for match in self.namespace[name].finditer(''.join(remaining)):
                try:
                    parsed = date(int(match['year']), int(match['month']), int(match['day'])) if name == 'ADJACENT_DATETIME_PATTERN' else self.namespace['_date_from_match'](match)
                except ValueError:
                    parsed = None
                if parsed is None:
                    return [], 'invalid_explicit_date'
                spans.append((match.start(), parsed))
                remaining[match.start():match.end()] = ' ' * (match.end() - match.start())
        rest = ''.join(remaining)
        if any(self.namespace[n].search(rest) for n in ['SHORT_YEAR_DATE_PATTERN', 'PARTIAL_DATE_PATTERN']):
            return [], 'ambiguous_year'
        return [d for _, d in sorted(spans)], None


def layout_key(record):
    page, bbox = record.get('page_number'), record.get('bbox')
    if type(page) is not int or page < 1 or not isinstance(bbox, list) or len(bbox) != 4:
        raise TemporalError('INVALID_LAYOUT_GEOMETRY')
    if any(not isinstance(pair, list) or len(pair) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in pair) for pair in bbox):
        raise TemporalError('INVALID_LAYOUT_GEOMETRY')
    return page, tuple(tuple(pair) for pair in bbox)


def validate_pair(raw, redacted):
    if raw.get('sensitivity') != RAW_SENSITIVITY or redacted.get('sensitivity') != L2_SENSITIVITY:
        raise TemporalError('WRONG_SOURCE_LAYER')
    case, doc = raw.get('case_token'), raw.get('document_token')
    if not isinstance(case, str) or not CASE.fullmatch(case) or not isinstance(doc, str) or not DOCUMENT.fullmatch(doc):
        raise TemporalError('INVALID_ANONYMOUS_BINDING')
    for field in ['case_token', 'document_token', 'schema_version', 'page_count', 'line_count']:
        if raw.get(field) != redacted.get(field):
            raise TemporalError('L1_L2_BINDING_MISMATCH')
    for payload in [raw, redacted]:
        pages, records = payload.get('pages'), payload.get('records')
        if not isinstance(pages, list) or not isinstance(records, list) or not pages:
            raise TemporalError('INVALID_LAYOUT_SHAPE')
        if payload.get('page_count') != len(pages) or payload.get('line_count') != len(records):
            raise TemporalError('LAYOUT_COUNT_MISMATCH')
        numbers = [p.get('page_number') for p in pages]
        if numbers != list(range(1, len(pages) + 1)):
            raise TemporalError('INVALID_PAGE_SEQUENCE')
        keys = []
        previous_page = 0
        for record in records:
            key = layout_key(record)
            if key[0] not in numbers or key[0] < previous_page:
                raise TemporalError('INVALID_RECORD_PAGE_SEQUENCE')
            previous_page = key[0]
            if record.get('case_token') != case or record.get('document_token') != doc:
                raise TemporalError('RECORD_BINDING_MISMATCH')
            confidence = record.get('confidence')
            if not isinstance(record.get('text'), str) or type(confidence) not in (float, int) or not 0 <= confidence <= 1:
                raise TemporalError('INVALID_RECORD_CONTENT_METADATA')
            keys.append(key)
        if len(set(keys)) != len(keys):
            raise TemporalError('DUPLICATE_LAYOUT_COORDINATES')
    if raw['pages'] != redacted['pages']:
        # Rendering metadata may differ; geometry must agree.
        geometry = lambda p: [(x.get('page_number'), x.get('image_width'), x.get('image_height')) for x in p['pages']]
        if geometry(raw) != geometry(redacted):
            raise TemporalError('PAGE_GEOMETRY_MISMATCH')
    if {layout_key(r) for r in raw['records']} != {layout_key(r) for r in redacted['records']}:
        raise TemporalError('L1_L2_COORDINATE_MISMATCH')
    return case, doc


def audit_document(raw, redacted, rules, *, l1_sha256, l2_sha256):
    case, doc = validate_pair(raw, redacted)
    pages = [SimpleNamespace(text=rules.normalize('\n'.join(r['text'] for r in raw['records'] if r['page_number'] == p['page_number']))) for p in raw['pages']]
    anchor = rules.anchor(pages)
    lookup = {layout_key(r): r for r in redacted['records']}
    issues, candidates = Counter(), []
    l2_occurrences = 0
    for index, record in enumerate(raw['records']):
        l2 = lookup[layout_key(record)]
        tokens = TOKEN.findall(l2['text'])
        l2_occurrences += len(tokens)
        if not tokens:
            explicit, reason = rules.full_dates(record['text'])
            if explicit or reason:
                issues['source_date_not_retained_as_relative_token'] += 1
            masks = DATE_MASK.findall(l2['text'])
            # Separate recovery path: a paired L2 date mask, never an arbitrary missing line.
            if masks and explicit and not reason:
                if DATE_MASK.search(record['text']):
                    issues['source_only_preexisting_date_mask'] += 1
                elif anchor is None:
                    issues['source_only_missing_anchor'] += 1
                elif record['confidence'] < 0.8:
                    issues['source_only_low_confidence'] += 1
                elif len(masks) != len(explicit):
                    issues['source_only_date_mask_count_mismatch'] += 1
                else:
                    for occurrence, absolute in enumerate(explicit):
                        # Do not turn old birth/history removals into current encounter events.
                        if not 0 <= (absolute - anchor).days <= 400:
                            issues['source_only_outside_legacy_window'] += 1
                            continue
                        candidates.append({'source_record_index': index, 'page_number': record['page_number'], 'bbox': record['bbox'],
                                           'token_ordinal': occurrence, 'legacy_document_day': None, '_date': absolute,
                                           'temporal_role': 'unclassified', 'l2_token_binding': 'bbox_only_candidate',
                                           'validation': 'explicit_l1_date_with_co_located_l2_date_masks'})
            continue
        reason = None
        if anchor is None:
            reason = 'missing_legacy_anchor'
        elif any(t.startswith('-') for t in tokens):
            reason = 'legacy_malformed_negative_token'
        elif record['confidence'] < 0.8:
            reason = 'low_confidence_source'
        elif TOKEN.findall(rules.replace(record['text'], anchor)) != tokens:
            reason = 'legacy_replay_mismatch'
        explicit, parse_reason = rules.full_dates(record['text'])
        reason = reason or parse_reason
        if not reason and len(explicit) != len(tokens):
            reason = 'date_token_count_mismatch'
        if not reason and [(d - anchor).days for d in explicit] != [int(t) for t in tokens]:
            reason = 'explicit_date_relative_value_mismatch'
        if reason:
            issues[reason] += len(tokens)
            continue
        for occurrence, (day, absolute) in enumerate(zip(tokens, explicit)):
            candidates.append({'source_record_index': index, 'page_number': record['page_number'], 'bbox': record['bbox'],
                               'token_ordinal': occurrence, 'legacy_document_day': int(day), '_date': absolute,
                               'temporal_role': 'unclassified', 'l2_token_binding': 'sequence_replay_verified',
                               'validation': 'explicit_date_and_legacy_replay_match'})
    return {'case_token': case, 'document_token': doc, '_anchor': anchor, 'page_count': len(raw['pages']),
            'l1_sha256': l1_sha256, 'l2_sha256': l2_sha256, 'candidates': candidates,
            'relative_token_count': l2_occurrences, 'issue_counts': dict(issues)}


def build_case_sidecar(documents, rules, *, reference_document=None, origin_binding=None):
    if not documents or len({d['case_token'] for d in documents}) != 1:
        raise TemporalError('CASE_SCOPE_MISMATCH')
    if len({d['document_token'] for d in documents}) != len(documents):
        raise TemporalError('DUPLICATE_DOCUMENT_BINDING')
    candidates = sorted((d for d in documents if d['candidates'] and d['_anchor'] is not None), key=lambda d: d['document_token'])
    if origin_binding:
        if reference_document and reference_document != origin_binding.get('document_token'):
            raise TemporalError('CONFLICTING_ORIGIN_SELECTION')
        reference_document = origin_binding.get('document_token')
        if not reference_document:
            raise TemporalError('INVALID_ORIGIN_BINDING')
    reference = next((d for d in candidates if d['document_token'] == reference_document), None) if reference_document else next(iter(candidates), None)
    if reference_document and reference is None:
        raise TemporalError('REFERENCE_DOCUMENT_NOT_USABLE')
    # Coordinate origin is an explicit source date, never an inferred admission date.
    origin_record = min(reference['candidates'], key=lambda c: (c['legacy_document_day'] is None, c['_date'], c['source_record_index'], c['token_ordinal'])) if reference else None
    if origin_binding:
        if any(reference[k] != origin_binding.get(k) for k in ['l1_sha256', 'l2_sha256']):
            raise TemporalError('ORIGIN_SOURCE_CHANGED')
        origin_record = next((c for c in reference['candidates'] if c['source_record_index'] == origin_binding.get('source_record_index') and c['token_ordinal'] == origin_binding.get('token_ordinal')), None)
        if origin_record is None:
            raise TemporalError('ORIGIN_RECORD_NOT_USABLE')
    origin = origin_record['_date'] if origin_record else None
    origin_source = ({k: reference[k] for k in ['document_token', 'l1_sha256', 'l2_sha256']} |
                     {k: origin_record[k] for k in ['source_record_index', 'token_ordinal']}) if reference else None
    coordinate_id = digest_bytes(json.dumps({'case': documents[0]['case_token'], 'origin': origin_source,
                                            'rules': rules.rule_sha256}, sort_keys=True).encode())
    output = []
    issues = Counter()
    for d in sorted(documents, key=lambda d: d['document_token']):
        issues.update(d['issue_counts'])
        offset = (d['_anchor'] - origin).days if origin and d['candidates'] else None
        records = []
        for c in d['candidates']:
            entry = {k: v for k, v in c.items() if k != '_date'}
            entry['case_coordinate_day'] = (c['_date'] - origin).days
            if entry['legacy_document_day'] is not None:
                assert entry['case_coordinate_day'] == entry['legacy_document_day'] + offset
            records.append(entry)
        output.append({k: d[k] for k in ['document_token', 'l1_sha256', 'l2_sha256', 'page_count', 'relative_token_count', 'issue_counts']} | {
            'document_to_case_day_offset': offset, 'candidate_dates': records})
    return {'schema_version': VERSION, 'case_token': documents[0]['case_token'],
            'source_rule_sha256': rules.rule_sha256, 'producer_source_sha256': rules.source_sha256,
            'reference_document': reference['document_token'] if reference else None,
            'origin_source': origin_source, 'case_coordinate_id': coordinate_id,
            'origin_policy': 'pinned_reference_explicit_date_preferring_legacy_replay',
            'origin_is_clinical_index_time': False, 'source_files_modified': False,
            'api_ready': False, 'applied_to_l4': False, 'clinical_time_roles_validated': False,
            'documents': output,
            'summary': {'document_count': len(output), 'page_count': sum(d['page_count'] for d in documents),
                        'candidate_date_count': sum(len(d['candidate_dates']) for d in output),
                        'replayed_relative_token_candidates': sum(c['legacy_document_day'] is not None for d in output for c in d['candidate_dates']),
                        'recovered_masked_date_candidates': sum(c['legacy_document_day'] is None for d in output for c in d['candidate_dates']),
                        'relative_token_count': sum(d['relative_token_count'] for d in output),
                        'distinct_legacy_anchors': len({d['_anchor'] for d in documents if d['_anchor'] is not None}),
                        'documents_with_nonzero_offset': sum(d['document_to_case_day_offset'] not in (None, 0) for d in output),
                        'excluded_relative_token_counts': {k: v for k, v in issues.items() if k != 'source_date_not_retained_as_relative_token' and not k.startswith('source_only_')},
                        'source_only_issue_counts': {k: v for k, v in issues.items() if k.startswith('source_only_')},
                        'source_date_lines_without_relative_token': issues.get('source_date_not_retained_as_relative_token', 0),
                        'issue_counts': dict(issues)}}


def write_new_private_json(path, data):
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Parent is created explicitly by the runner; never overwrite a previous run.
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def run_audit(case_dir, producer_source, output, *, max_documents=30, max_pages=250, reference_sidecar=None):
    case_dir, producer_source, output = Path(case_dir), Path(producer_source), Path(output)
    rules = LegacyRules(producer_source.read_text(encoding='utf-8'))
    pairs = []
    for doc in sorted(case_dir.glob('DOC-*')):
        if doc.is_symlink() or not doc.is_dir():
            continue
        a, b = doc / 'ocr_layout.json', doc / 'deidentified_layout_NOT_SAFE.json'
        if any(p.is_symlink() for p in [a, b]):
            raise TemporalError('SYMLINK_SOURCE_REJECTED')
        if not a.is_file() or not b.is_file():
            raise TemporalError('INCOMPLETE_LAYOUT_PAIR')
        pairs.append((a, b))
    if not 1 <= len(pairs) <= max_documents:
        raise TemporalError('DOCUMENT_SCOPE_EXCEEDED')
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise TemporalError('OUTPUT_MUST_BE_NEW_WITH_EXISTING_PARENT')
    if case_dir.resolve() in output.resolve().parents:
        raise TemporalError('OUTPUT_MUST_BE_OUTSIDE_SOURCE_CASE')
    documents, bindings, total_pages = [], [], 0
    for a, b in pairs:
        if max(a.stat().st_size, b.stat().st_size) > 40_000_000:
            raise TemporalError('SOURCE_FILE_SIZE_EXCEEDED')
        ra, rb = a.read_bytes(), b.read_bytes()
        raw, redacted = json.loads(ra), json.loads(rb)
        total_pages += int(raw.get('page_count', 0))
        if total_pages > max_pages:
            raise TemporalError('PAGE_SCOPE_EXCEEDED')
        ha, hb = digest_bytes(ra), digest_bytes(rb)
        documents.append(audit_document(raw, redacted, rules, l1_sha256=ha, l2_sha256=hb))
        bindings.extend([(a, ha), (b, hb)])
    previous = None
    if reference_sidecar:
        previous = json.loads(Path(reference_sidecar).read_text(encoding='utf-8'))
        if previous.get('case_token') != documents[0]['case_token'] or previous.get('source_rule_sha256') != rules.rule_sha256 or not previous.get('origin_source'):
            raise TemporalError('REFERENCE_SIDECAR_INCOMPATIBLE')
    sidecar = build_case_sidecar(documents, rules, origin_binding=previous['origin_source'] if previous else None)
    if previous and sidecar['case_coordinate_id'] != previous.get('case_coordinate_id'):
        raise TemporalError('COORDINATE_ID_MISMATCH')
    if any(digest_bytes(p.read_bytes()) != digest for p, digest in bindings):
        raise TemporalError('SOURCE_CHANGED_DURING_AUDIT')
    write_new_private_json(output, sidecar)
    return sidecar['summary'] | {'input_hashes_unchanged': True, 'api_ready': False, 'applied_to_l4': False,
                                 'sidecar_sha256': digest_bytes(output.read_bytes())}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-dir', required=True)
    parser.add_argument('--producer-source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--reference-sidecar', help='Pin an existing coordinate system when adding documents')
    args = parser.parse_args()
    try:
        print(json.dumps(run_audit(args.case_dir, args.producer_source, args.output, reference_sidecar=args.reference_sidecar)))
    except TemporalError as error:
        print(json.dumps({'status': 'blocked', 'reason': str(error)}))
        raise SystemExit(2)
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'error_type': type(error).__name__}))
        raise SystemExit(2)
