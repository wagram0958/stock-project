"""Offline fixtures for official TWSE 2026 annual schedule."""

import json
from datetime import date

import pytest

from hermes_data_engine.exchange_calendar import (
    CalendarDataError, TWSE_CALENDAR_URL, decode_calendar,
    latest_scheduled_session, scheduled_session,
)


def annual_rows():
    # Key cases from https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule
    # The annual response contains both closures and informational trading rows.
    events = [
        ("1150101", "中華民國開國紀念日", "依規定放假1日。"),
        ("1150102", "國曆新年開始交易日", "國曆新年開始交易。"),
        ("1150211", "農曆春節前最後交易日", "農曆春節前最後交易。"),
        ("1150212", "市場無交易，僅辦理結算交割作業", ""),
        ("1150213", "市場無交易，僅辦理結算交割作業", ""),
        ("1150215", "農曆除夕及春節", "依規定放假5日。"),
        ("1150216", "農曆除夕及春節", "依規定放假5日。"),
        ("1150217", "農曆除夕及春節", "依規定放假5日。"),
        ("1150218", "農曆除夕及春節", "依規定放假5日。"),
        ("1150219", "農曆除夕及春節", "依規定放假5日。"),
        ("1150220", "農曆除夕及春節", "補假。"),
        ("1150223", "農曆春節後開始交易日", "農曆春節後開始交易。"),
        ("1150227", "和平紀念日", "補假。"),
        ("1150228", "和平紀念日", "依規定放假1日。"),
        ("1150403", "兒童節及民族掃墓節", "補假。"),
        ("1150404", "兒童節及民族掃墓節", "放假。"),
        ("1150405", "兒童節及民族掃墓節", "放假。"),
        ("1150406", "兒童節及民族掃墓節", "補假。"),
        ("1150501", "勞動節", "放假。"),
        ("1150619", "端午節", "放假。"),
        ("1150925", "中秋節", "放假。"),
        ("1150928", "教師節", "放假。"),
        ("1151009", "國慶日", "補假。"),
        ("1151010", "國慶日", "放假。"),
        ("1151025", "臺灣光復日", "放假。"),
        ("1151026", "臺灣光復日", "補假。"),
        ("1151225", "行憲紀念日", "放假。"),
    ]
    return [{"Date": day, "Name": name, "Description": desc,
             "Weekday": "一"} for day, name, desc in events]


def calendar():
    return decode_calendar(json.dumps(annual_rows()), for_year=2026)


@pytest.mark.parametrize("day", ["2026-10-09", "2026-10-10", "2026-10-11",
                                 "2026-10-26", "2026-02-12", "2026-02-13",
                                 "2026-09-28"])
def test_official_market_closures(day):
    session = scheduled_session(date.fromisoformat(day), calendar())
    assert not session.scheduled_open
    assert session.source == TWSE_CALENDAR_URL


@pytest.mark.parametrize("day", ["2026-10-08", "2026-02-11", "2026-02-23",
                                 "2026-01-02"])
def test_normal_and_explicit_trading_dates(day):
    assert scheduled_session(date.fromisoformat(day), calendar()).scheduled_open


def test_last_scheduled_session_october_holiday_weekend():
    result = latest_scheduled_session(date(2026, 10, 11), calendar())
    assert result.date == "2026-10-08"


def test_last_scheduled_session_spring_festival_gap():
    result = latest_scheduled_session(date(2026, 2, 20), calendar())
    assert result.date == "2026-02-11"


def test_end_of_year_calendar_cannot_be_used_for_other_year():
    with pytest.raises(CalendarDataError, match="year"):
        decode_calendar(json.dumps(annual_rows()), for_year=2027)
    with pytest.raises(CalendarDataError, match="year"):
        scheduled_session(date(2027, 1, 4), calendar())


def test_unknown_calendar_year_cannot_be_silently_guessed():
    with pytest.raises(CalendarDataError):
        latest_scheduled_session(date(2026, 1, 1), calendar())


def test_incomplete_and_invalid_response_fail_closed():
    with pytest.raises(CalendarDataError):
        decode_calendar("[]", for_year=2026)
    with pytest.raises(CalendarDataError):
        decode_calendar("not json", for_year=2026)
    with pytest.raises(CalendarDataError, match="Incomplete"):
        decode_calendar(json.dumps(annual_rows()[:2]), for_year=2026)


def test_unrecognized_calendar_row_fails_closed():
    rows = annual_rows()
    rows[0]["Name"] = "未知公告"
    rows[0]["Description"] = "注意資訊"
    with pytest.raises(CalendarDataError, match="Ambiguous"):
        decode_calendar(json.dumps(rows), for_year=2026)


def test_duplicate_and_broken_roc_dates_fail_closed():
    rows = annual_rows()
    rows[1]["Date"] = rows[0]["Date"]
    with pytest.raises(CalendarDataError, match="duplicate"):
        decode_calendar(json.dumps(rows), for_year=2026)
    rows[1]["Date"] = "1151399"
    with pytest.raises(CalendarDataError, match="Invalid ROC"):
        decode_calendar(json.dumps(rows), for_year=2026)


def test_unplanned_closure_not_in_calendar_is_only_scheduled_open():
    # A typhoon emergency cannot be detected from an annual schedule alone.
    result = scheduled_session(date(2026, 10, 12), calendar())
    assert result.scheduled_open is True
    assert "預計開市" in result.reason
