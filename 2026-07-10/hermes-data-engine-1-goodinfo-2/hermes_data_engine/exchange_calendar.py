"""Official TWSE *scheduled* trading sessions (not live-execution proof).

The TWSE OpenAPI calendar lists closures AND informational open-day rows.
Never equate every listed date with a holiday. Unscheduled typhoon closures
are not guaranteed to appear; market-data readiness remains a separate gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

TWSE_CALENDAR_URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"

_OPEN_HINTS = ("開始交易日", "最後交易日")
_CLOSED_HINTS = ("無交易", "放假", "補假")


class CalendarDataError(ValueError):
    """Official schedule missing, stale, contradictory or unrecognizable."""


@dataclass(frozen=True)
class Session:
    date: str
    scheduled_open: bool
    source: str
    reason: str


def _roc_date(value: Any) -> date:
    if not isinstance(value, str) or not value.isdigit() or len(value) < 6:
        raise CalendarDataError("Invalid ROC calendar date")
    year = int(value[:-4]) + 1911
    try:
        return date(year, int(value[-4:-2]), int(value[-2:]))
    except ValueError as exc:
        raise CalendarDataError("Invalid ROC calendar date") from exc


def decode_calendar(text: str, *, for_year: int) -> dict[date, tuple[bool, str]]:
    """Parse annual TWSE schedule, retaining explicit open-day exceptions."""
    try:
        items = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CalendarDataError("TWSE calendar is not valid JSON") from exc
    if not isinstance(items, list) or not items:
        raise CalendarDataError("TWSE calendar has no schedule rows")
    rows: dict[date, tuple[bool, str]] = {}
    for row in items:
        if not isinstance(row, dict):
            raise CalendarDataError("TWSE calendar row is not an object")
        day = _roc_date(row.get("Date"))
        if day.year != for_year:
            raise CalendarDataError("TWSE calendar year mismatch; fail closed")
        if day in rows:
            raise CalendarDataError("TWSE calendar has duplicate dates")
        name, description = row.get("Name"), row.get("Description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise CalendarDataError("TWSE calendar row lacks Name or Description")
        combined = name + " " + description
        opened = any(hint in name for hint in _OPEN_HINTS)
        closed = any(hint in combined for hint in _CLOSED_HINTS)
        if opened == closed:
            raise CalendarDataError("Ambiguous TWSE calendar row: " + day.isoformat())
        rows[day] = (opened, name)
    # A few sample lines are not a trustworthy *annual* calendar.
    if len(rows) < 10:
        raise CalendarDataError("Incomplete TWSE annual calendar")
    return rows


def scheduled_session(day: date, calendar: dict[date, tuple[bool, str]]) -> Session:
    if not calendar or any(record.year != day.year for record in calendar):
        raise CalendarDataError("Official calendar does not cover requested year")
    explicit = calendar.get(day)
    if explicit is not None:
        is_open, reason = explicit
        if day.weekday() >= 5 and is_open:
            # Such an exceptional weekend opening is never assumed without
            # additional trade evidence. A calendar listing alone is insufficient.
            raise CalendarDataError("Weekend trading exception requires review")
        return Session(day.isoformat(), is_open, TWSE_CALENDAR_URL, reason)
    return Session(
        day.isoformat(), day.weekday() < 5, TWSE_CALENDAR_URL,
        "普通平日（排程預計開市；仍須以官方盤後行情確認）"
        if day.weekday() < 5 else "週末休市",
    )


def latest_scheduled_session(
    as_of: date, calendar: dict[date, tuple[bool, str]], max_days: int = 31
) -> Session:
    """Find the last scheduled session, but never silently cross calendar years."""
    for offset in range(max_days + 1):
        target = as_of - timedelta(days=offset)
        if target.year != as_of.year:
            break
        session = scheduled_session(target, calendar)
        if session.scheduled_open:
            return session
    raise CalendarDataError("No confirmed scheduled session within annual calendar")
