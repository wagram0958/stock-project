"""Offline contract tests for official-session market-data readiness."""

from copy import deepcopy

import pytest

from hermes_data_engine.models import DATA_FIELDS, Observation, build_document
from hermes_data_engine.readiness import assess_market_readiness


DAY = "2026-07-10"
AFTER_CLOSE = "2026-07-10T16:00:00+08:00"
SOURCE = "Official TWSE trading-day record independently checked by operator"


def good_document():
    values = {field: 1 for field in DATA_FIELDS}
    values.update(date=DAY, price=42.5, volume=100000)
    observations = {
        field: Observation(value, "TWSE", DAY, AFTER_CLOSE, "verified")
        for field, value in values.items()
    }
    return build_document("3033", observations, AFTER_CLOSE)


def check(document=None, **kwargs):
    return assess_market_readiness(
        good_document() if document is None else document,
        DAY,
        session_confirmed=kwargs.pop("session_confirmed", True),
        session_source=kwargs.pop("session_source", SOURCE),
        **kwargs,
    )


def test_verified_closed_session_and_official_core_fields_pass():
    result = check()
    assert result["ready"] is True
    assert result["issues"] == []


def test_schema_valid_all_unavailable_market_data_fails_closed():
    doc = good_document()
    for field in ("date", "price", "volume"):
        doc[field] = None
        doc["sources"][field]["status"] = "unavailable"
        doc["sources"][field]["source"] = "Unavailable"
    doc["quality"]["status"] = "partial"
    result = check(doc)
    assert result["ready"] is False
    assert "price_missing_or_invalid" in result["issues"]
    assert "volume_missing_or_invalid" in result["issues"]


def test_weekday_is_not_proof_market_was_open():
    result = check(session_confirmed=False)
    assert result["ready"] is False
    assert "official_trading_session_not_independently_confirmed" in result["issues"]


def test_source_label_alone_is_not_a_trading_calendar():
    assert check(session_source="")["ready"] is False


@pytest.mark.parametrize("source,status", [
    ("Goodinfo", "unverified"),
    ("Yahoo(Fallback)", "fallback"),
    ("TWSE", "stale"),
    ("TWSE", "mismatch"),
])
def test_unsupported_critical_source_or_status_fails(source, status):
    doc = good_document()
    doc["sources"]["price"]["source"] = source
    doc["sources"]["price"]["status"] = status
    if status in {"stale", "mismatch"}:
        doc["quality"]["status"] = status
    result = check(doc)
    assert not result["ready"]
    assert "price_source_not_official_or_cross_verified" in result["issues"]


def test_verified_goodinfo_crosschecked_against_official_can_pass():
    doc = good_document()
    doc["sources"]["price"]["source"] = "Goodinfo"
    doc["sources"]["price"]["status"] = "verified"
    assert check(doc)["ready"] is True


def test_stale_or_wrong_date_fails_even_with_nonzero_prices():
    doc = good_document()
    doc["date"] = "2026-07-09"
    doc["sources"]["price"]["as_of"] = "2026-07-09"
    result = check(doc)
    assert not result["ready"]
    assert "trading_date_missing_or_mismatch" in result["issues"]
    assert "price_provenance_date_mismatch" in result["issues"]


def test_fetch_before_market_close_cannot_be_final_data():
    doc = good_document()
    doc["sources"]["price"]["fetched_at"] = "2026-07-10T12:30:00+08:00"
    result = check(doc)
    assert not result["ready"]
    assert "price_fetched_before_session_closed" in result["issues"]


@pytest.mark.parametrize("field,value", [
    ("price", 0),
    ("price", -1),
    ("price", float("nan")),
    ("volume", -1),
    ("volume", 12.5),
    ("volume", True),
])
def test_numeric_core_fields_are_checked(field, value):
    doc = good_document()
    doc[field] = value
    assert check(doc)["ready"] is False


def test_optional_financials_unavailable_dont_block_verified_daily_prices():
    doc = good_document()
    doc["eps"] = None
    doc["sources"]["eps"]["status"] = "unavailable"
    doc["quality"]["status"] = "partial"
    assert check(doc)["ready"] is True


def test_invalid_schema_returns_failure_not_exception():
    doc = good_document()
    del doc["sources"]["price"]["as_of"]
    result = check(doc)
    assert result["ready"] is False
    assert any(item.startswith("invalid_schema:") for item in result["issues"])


def test_unparseable_expected_date_fails_closed():
    result = assess_market_readiness(
        good_document(), "2026-02-30", session_confirmed=True,
        session_source=SOURCE
    )
    assert result["ready"] is False
    assert "invalid_expected_trading_date" in result["issues"]
