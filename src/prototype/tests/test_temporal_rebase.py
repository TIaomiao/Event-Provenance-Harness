import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from temporal_rebase import (LegacyRules, TemporalError, audit_document, build_case_sidecar,
                             run_audit, RAW_SENSITIVITY, L2_SENSITIVITY, write_new_private_json)


FIXTURE = Path(__file__).with_name('legacy_date_fixture.py')


def pair(texts, sanitized, doc='DOC-001', case='CASE-SYNTHETIC', confidence=0.99):
    raw = {'case_token': case, 'document_token': doc, 'schema_version': '1.0',
           'sensitivity': RAW_SENSITIVITY, 'page_count': 1, 'line_count': len(texts),
           'pages': [{'page_number': 1, 'image_width': 1000, 'image_height': 1000}],
           'records': [{'case_token': case, 'document_token': doc, 'page_number': 1,
                        'bbox': [[0, i * 20], [100, i * 20], [100, i * 20 + 15], [0, i * 20 + 15]],
                        'text': t, 'confidence': confidence} for i, t in enumerate(texts)]}
    redacted = copy.deepcopy(raw)
    redacted['sensitivity'] = L2_SENSITIVITY
    for r, text in zip(redacted['records'], sanitized):
        r['text'] = text
    return raw, redacted


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.rules = LegacyRules(FIXTURE.read_text(encoding='utf-8'))

    def document(self, texts, sanitized, **kwargs):
        a, b = pair(texts, sanitized, **kwargs)
        result = audit_document(a, b, self.rules, l1_sha256='a' * 64, l2_sha256='b' * 64)
        return result

    def test_document_zeros_become_distinct_case_days_without_changing_inputs(self):
        a = self.document(['2026-01-01', '2026-01-02'], ['[相对日+0]', '[相对日+1]'])
        b = self.document(['2026-01-04'], ['[相对日+0]'], doc='DOC-002')
        sidecar = build_case_sidecar([b, a], self.rules)
        self.assertEqual(sidecar['documents'][1]['candidate_dates'][0]['case_coordinate_day'], 3)
        self.assertEqual(a['candidates'][0]['legacy_document_day'], 0)
        self.assertFalse(sidecar['api_ready'])
        self.assertFalse(sidecar['clinical_time_roles_validated'])

    def test_negative_case_coordinate_is_valid_with_pinned_later_origin(self):
        a = self.document(['2026-01-01'], ['[相对日+0]'])
        b = self.document(['2026-01-04'], ['[相对日+0]'], doc='DOC-002')
        sidecar = build_case_sidecar([a, b], self.rules, reference_document='DOC-002')
        self.assertEqual(sidecar['documents'][0]['candidate_dates'][0]['case_coordinate_day'], -3)

    def test_year_boundary_and_leap_day(self):
        for start, end, delta in [('2025-12-31', '2026-01-02', 2), ('2024-02-28', '2024-03-01', 2)]:
            a = self.document([start], ['[相对日+0]'])
            b = self.document([end], ['[相对日+0]'], doc='DOC-002')
            result = build_case_sidecar([a, b], self.rules)
            self.assertEqual(result['documents'][1]['candidate_dates'][0]['case_coordinate_day'], delta)

    def test_partial_and_two_digit_years_remain_unresolved(self):
        for ambiguous in ['01-02', '26-01-02']:
            d = self.document(['2026-01-01', ambiguous], ['[相对日+0]', '[相对日+1]'])
            self.assertEqual(len(d['candidates']), 1)
            self.assertEqual(d['issue_counts']['ambiguous_year'], 1)

    def test_replay_mismatch_is_not_silently_repaired(self):
        d = self.document(['2026-01-01'], ['[相对日+7]'])
        self.assertFalse(d['candidates'])
        self.assertEqual(d['issue_counts']['legacy_replay_mismatch'], 1)

    def test_missing_anchor_and_masked_date(self):
        a = self.document(['no dates'], ['[相对日+0]'])
        self.assertEqual(a['issue_counts']['missing_legacy_anchor'], 1)
        b = self.document(['2026-01-01'], ['[removed]'])
        self.assertFalse(b['candidates'])
        self.assertEqual(b['issue_counts']['source_date_not_retained_as_relative_token'], 1)

    def test_explicit_date_lost_in_l2_is_recovered_as_separate_candidate(self):
        a = self.document(['2026-01-01'], ['[相对日+0]'])
        b = self.document(['2026-01-04'], ['[日期已移除]'], doc='DOC-002')
        output = build_case_sidecar([a, b], self.rules)
        c = output['documents'][1]['candidate_dates'][0]
        self.assertEqual(c['case_coordinate_day'], 3)
        self.assertIsNone(c['legacy_document_day'])
        self.assertEqual(c['validation'], 'explicit_l1_date_with_co_located_l2_date_masks')
        self.assertEqual(c['l2_token_binding'], 'bbox_only_candidate')
        self.assertEqual(output['summary']['recovered_masked_date_candidates'], 1)
        self.assertFalse(output['applied_to_l4'])

    def test_missing_year_or_low_confidence_mask_is_not_recovered(self):
        for texts, l2, confidence in [(['2026-01-01', '01-02'], ['[相对日+0]', '[日期已移除]'], 0.99),
                                      (['2026-01-01'], ['[日期已移除]'], 0.5)]:
            output = build_case_sidecar([self.document(texts, l2, confidence=confidence)], self.rules)
            self.assertEqual(output['summary']['recovered_masked_date_candidates'], 0)

    def test_mask_count_and_old_history_guard(self):
        a = self.document(['2026-01-01; 2026-01-04'], ['[日期已移除]'])
        self.assertFalse(a['candidates'])
        self.assertIn('source_only_date_mask_count_mismatch', a['issue_counts'])
        b = self.document(['1980-01-01', '2026-01-01'], ['[日期已移除]', '[日期已移除]'])
        output = build_case_sidecar([b], self.rules)
        self.assertEqual(output['summary']['recovered_masked_date_candidates'], 1)
        self.assertIn('source_only_outside_legacy_window', output['summary']['source_only_issue_counts'])

    def test_preexisting_l1_mask_cannot_stand_in_for_a_removed_date(self):
        d = self.document(['[日期已移除] report 2026-01-01'], ['[日期已移除] [整栏已移除]'])
        self.assertFalse(d['candidates'])
        self.assertEqual(d['issue_counts']['source_only_preexisting_date_mask'], 1)

    def test_low_confidence_is_not_accepted_as_verified(self):
        d = self.document(['2026-01-01'], ['[相对日+0]'], confidence=0.5)
        self.assertFalse(d['candidates'])
        self.assertIn('low_confidence_source', d['issue_counts'])

    def test_malformed_legacy_negative_token(self):
        d = self.document(['2026-01-01'], ['[相对日+-1]'])
        self.assertFalse(d['candidates'])
        self.assertIn('legacy_malformed_negative_token', d['issue_counts'])

    def test_two_dates_on_one_line_preserve_ordinal(self):
        d = self.document(['2026-01-01 -> 2026-01-04'], ['[相对日+0] -> [相对日+3]'])
        sidecar = build_case_sidecar([d], self.rules)
        self.assertEqual([c['case_coordinate_day'] for c in sidecar['documents'][0]['candidate_dates']], [0, 3])

    def test_adjacent_datetime_keeps_date_but_not_time_role_claim(self):
        d = self.document(['2026-01-0112:30'], ['[相对日+0] 12:30'])
        self.assertEqual(len(d['candidates']), 1)
        self.assertEqual(d['candidates'][0]['temporal_role'], 'unclassified')

    def test_old_history_does_not_become_an_admission_origin(self):
        d = self.document(['1980-01-01', '2026-01-01'], ['[非就诊日期已移除]', '[相对日+0]'])
        sidecar = build_case_sidecar([d], self.rules)
        self.assertFalse(sidecar['origin_is_clinical_index_time'])
        self.assertEqual(sidecar['summary']['candidate_date_count'], 1)

    def test_birth_and_recent_history_stay_unclassified(self):
        for text, l2 in [('birthday 1980-01-01', 'birthday [相对日+0]'),
                         ('history 2025-12-01; report 2026-01-01', 'history [相对日+0]; report [相对日+31]')]:
            d = self.document([text], [l2])
            output = build_case_sidecar([d], self.rules)
            self.assertFalse(output['origin_is_clinical_index_time'])
            self.assertFalse(output['clinical_time_roles_validated'])
            self.assertTrue(all(c['temporal_role'] == 'unclassified' for c in output['documents'][0]['candidate_dates']))

    def test_pinned_origin_survives_added_earlier_document(self):
        a = self.document(['2026-01-04'], ['[相对日+0]'], doc='DOC-002')
        before = build_case_sidecar([a], self.rules)
        b = self.document(['2026-01-01'], ['[相对日+0]'], doc='DOC-001')
        after = build_case_sidecar([a, b], self.rules, origin_binding=before['origin_source'])
        self.assertEqual(before['case_coordinate_id'], after['case_coordinate_id'])
        self.assertEqual(after['documents'][0]['candidate_dates'][0]['case_coordinate_day'], -3)
        a['l1_sha256'] = 'c' * 64
        with self.assertRaises(TemporalError):
            build_case_sidecar([a, b], self.rules, origin_binding=before['origin_source'])

    def test_unresolved_counters_use_explicit_units(self):
        d = self.document(['2026-01-01', '01-02', '1980-01-01'], ['[相对日+0]', '[相对日+1]', '[removed]'])
        summary = build_case_sidecar([d], self.rules)['summary']
        self.assertEqual(summary['excluded_relative_token_counts'], {'ambiguous_year': 1})
        self.assertEqual(summary['source_date_lines_without_relative_token'], 1)

    def test_wrong_case_duplicate_coordinates_and_missing_pair_rejected(self):
        for mutate in ['case', 'duplicate', 'missing']:
            a, b = pair(['2026-01-01', '2026-01-02'], ['[相对日+0]', '[相对日+1]'])
            if mutate == 'case':
                b['case_token'] = 'CASE-99'
            elif mutate == 'duplicate':
                a['records'][1]['bbox'] = a['records'][0]['bbox']
            else:
                b['records'].pop()
            with self.assertRaises(TemporalError):
                audit_document(a, b, self.rules, l1_sha256='a', l2_sha256='b')

    def test_output_contains_no_text_absolute_date_or_internal_datetime(self):
        d = self.document(['2026-01-01 SYNTHETIC_PRIVATE'], ['[相对日+0] SYNTHETIC_PRIVATE'])
        data = build_case_sidecar([d], self.rules)
        encoded = json.dumps(data)
        self.assertNotIn('2026-01-01', encoded)
        self.assertNotIn('SYNTHETIC_PRIVATE', encoded)
        self.assertNotIn('"_anchor"', encoded)
        self.assertNotIn('"_date"', encoded)

    def test_all_unresolved_case_is_explicitly_empty(self):
        d = self.document(['no date'], ['no date'])
        output = build_case_sidecar([d], self.rules)
        self.assertIsNone(output['reference_document'])
        self.assertIsNone(output['documents'][0]['document_to_case_day_offset'])

    def test_mixed_cases_or_duplicate_documents_rejected(self):
        a = self.document(['2026-01-01'], ['[相对日+0]'])
        b = self.document(['2026-01-04'], ['[相对日+0]'], doc='DOC-002', case='CASE-99')
        for docs in [[a, b], [a, a]]:
            with self.assertRaises(TemporalError):
                build_case_sidecar(docs, self.rules)

    def test_end_to_end_new_sidecar_and_original_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            case = root / 'CASE-SYNTHETIC'
            doc = case / 'DOC-001'
            doc.mkdir(parents=True)
            a, b = pair(['2026-01-01'], ['[相对日+0]'])
            hashes = {}
            for name, payload in [('ocr_layout.json', a), ('deidentified_layout_NOT_SAFE.json', b)]:
                p = doc / name
                p.write_text(json.dumps(payload), encoding='utf-8')
                hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
            output = root / 'sidecar.json'
            report = run_audit(case, FIXTURE, output)
            self.assertEqual(report['candidate_date_count'], 1)
            self.assertTrue(report['input_hashes_unchanged'])
            for name, digest in hashes.items():
                self.assertEqual(hashlib.sha256((doc / name).read_bytes()).hexdigest(), digest)
            with self.assertRaises(TemporalError):
                run_audit(case, FIXTURE, output)
            with self.assertRaises(FileExistsError):
                write_new_private_json(output, {})
            second = root / 'second.json'
            run_audit(case, FIXTURE, second, reference_sidecar=output)
            self.assertEqual(json.loads(output.read_text())['case_coordinate_id'], json.loads(second.read_text())['case_coordinate_id'])


if __name__ == '__main__':
    unittest.main()
