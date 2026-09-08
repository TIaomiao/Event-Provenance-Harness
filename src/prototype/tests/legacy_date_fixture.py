"""Frozen pure producer date routines for synthetic compatibility tests."""
from __future__ import annotations
import re
from datetime import date

FULL_DATE_PATTERN = re.compile('(?<!\\d)(?P<year>(?:19|20)\\d{2})\\s*[-/.年]\\s*(?P<month>\\d{1,2})\\s*[-/.月]\\s*(?P<day>\\d{1,2})日?(?!\\d)|(?<!\\d)(?P<compact_year>(?:19|20)\\d{2})(?P<compact_month>\\d{2})(?P<compact_day>\\d{2})(?!\\d)')

ADJACENT_DATETIME_PATTERN = re.compile('(?<!\\d)(?P<year>(?:19|20)\\d{2})\\s*[-/.\\u5e74]\\s*(?P<month>\\d{1,2})\\s*[-/.\\u6708]\\s*(?P<day>\\d{2})\\u65e5?\\s*(?P<hour>[01]\\d|2[0-3])\\s*[:：]\\s*(?P<minute>[0-5]\\d)(?!\\d)')

SHORT_YEAR_DATE_PATTERN = re.compile('(?<!\\d)(?P<short_year>\\d{2})\\s*[-/.]\\s*(?P<short_month>\\d{1,2})\\s*[-/.]\\s*(?P<short_day>\\d{1,2})(?!\\d)')

PARTIAL_DATE_PATTERN = re.compile('(?<!\\d)(?P<month>0[1-9]|1[0-2])[-/.](?P<day>0[1-9]|[12]\\d|3[01])(?!\\d)')

def _normalize_text(text: str) -> str:
    text = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub('[ \\t\\u3000]+', ' ', text)
    text = re.sub('\\n{3,}', '\n\n', text)
    return text.strip()

def _date_from_match(match: re.Match[str]) -> date | None:
    try:
        if match.group('year'):
            return date(int(match.group('year')), int(match.group('month')), int(match.group('day')))
        return date(int(match.group('compact_year')), int(match.group('compact_month')), int(match.group('compact_day')))
    except ValueError:
        return None

def _relative_date_context(pages: list[PageText]) -> tuple[date | None, int | None]:
    dates: list[date] = []
    for page in pages:
        for match in ADJACENT_DATETIME_PATTERN.finditer(page.text):
            try:
                dates.append(date(int(match.group('year')), int(match.group('month')), int(match.group('day'))))
            except ValueError:
                continue
        for match in FULL_DATE_PATTERN.finditer(page.text):
            parsed = _date_from_match(match)
            if parsed is not None:
                dates.append(parsed)
        for match in SHORT_YEAR_DATE_PATTERN.finditer(page.text):
            try:
                dates.append(date(2000 + int(match.group('short_year')), int(match.group('short_month')), int(match.group('short_day'))))
            except ValueError:
                continue
    if not dates:
        return (None, None)
    latest = max(dates)
    encounter_dates = [item for item in dates if 0 <= (latest - item).days <= 400]
    anchor = min(encounter_dates)
    return (anchor, anchor.year)

def _replace_dates_with_relative_days(text: str, anchor: date | None, default_year: int | None) -> tuple[str, int]:
    if anchor is None or default_year is None:
        return (text, 0)
    count = 0

    def replace_full(match: re.Match[str]) -> str:
        nonlocal count
        parsed = _date_from_match(match)
        if parsed is None:
            return match.group(0)
        count += 1
        relative_day = (parsed - anchor).days
        if relative_day < -400 or relative_day > 400:
            return '[非就诊日期已移除]'
        return f'[相对日+{relative_day}]'

    def replace_adjacent_datetime(match: re.Match[str]) -> str:
        nonlocal count
        try:
            parsed = date(int(match.group('year')), int(match.group('month')), int(match.group('day')))
        except ValueError:
            return match.group(0)
        count += 1
        relative_day = (parsed - anchor).days
        date_text = '[非就诊日期已移除]' if relative_day < -400 or relative_day > 400 else f'[相对日+{relative_day}]'
        return f"{date_text} {match.group('hour')}:{match.group('minute')}"
    result = ADJACENT_DATETIME_PATTERN.sub(replace_adjacent_datetime, text)
    result = FULL_DATE_PATTERN.sub(replace_full, result)

    def replace_short_year(match: re.Match[str]) -> str:
        nonlocal count
        try:
            parsed = date(2000 + int(match.group('short_year')), int(match.group('short_month')), int(match.group('short_day')))
        except ValueError:
            return match.group(0)
        count += 1
        relative_day = (parsed - anchor).days
        if relative_day < -400 or relative_day > 400:
            return '[非就诊日期已移除]'
        return f'[相对日+{relative_day}]'
    result = SHORT_YEAR_DATE_PATTERN.sub(replace_short_year, result)

    def replace_partial(match: re.Match[str]) -> str:
        nonlocal count
        candidates: list[date] = []
        for candidate_year in (default_year - 1, default_year, default_year + 1):
            try:
                candidates.append(date(candidate_year, int(match.group('month')), int(match.group('day'))))
            except ValueError:
                continue
        forward_candidates = [item for item in candidates if 0 <= (item - anchor).days <= 400]
        if forward_candidates:
            parsed = min(forward_candidates, key=lambda item: (item - anchor).days)
        elif candidates:
            parsed = min(candidates, key=lambda item: abs((item - anchor).days))
        else:
            return match.group(0)
        count += 1
        return f'[相对日+{(parsed - anchor).days}]'
    return (PARTIAL_DATE_PATTERN.sub(replace_partial, result), count)

