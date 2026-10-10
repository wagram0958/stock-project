import json
from decimal import Decimal
from pathlib import Path

import pytest

from hermes_data_engine.providers.twse import ProviderDataError, TwseProvider


FIXTURES = Path(__file__).parent / "fixtures"
FETCHED_AT = "2026-07-10T08:00:00+08:00"


def _fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _provider(overrides=None):
    payloads = {
        "STOCK_DAY": _fixture("twse_price.json"),
        "MI_MARGN": _fixture("twse_margin.json"),
        "TWTB4U": _fixture("twse_daytrade.json"),
        "T86": _fixture("twse_institutional.json"),
        "BWIBBU": _fixture("twse_valuation.json"),
    }
    payloads.update(overrides or {})

    def fetcher(url):
        return next(value for key, value in payloads.items() if key in url)

    return TwseProvider(fetcher=fetcher, clock=lambda: FETCHED_AT)


def test_fetches_official_cross_validation_fields_with_units_and_provenance():
    result = _provider().fetch("3033", "2026-07-09")

    assert result["price"].value == Decimal("42.50")
    assert result["volume"].value == 1_234_567
    assert result["margin"].value == {"balance": 1_234_000, "change": 34_000}
    assert result["short"].value == {
        "balance": 123_000,
        "change": 23_000,
        "ratio": Decimal("9.97"),
    }
    assert result["daytrade"].value == {
        "ratio": Decimal("27.95"),
        "volume": 345,
    }
    assert isinstance(result["daytrade"].value["volume"], int)
    assert result["foreign"].value == 100_500
    assert result["investment"].value == -20_000
    assert result["dealer"].value == 3_500
    assert result["pe"].value == Decimal("12.34")
    assert result["pb"].value == Decimal("1.56")
    assert result["date"].value == "2026-07-09"
    assert all(item.source == "TWSE" for item in result.values())
    assert all(item.as_of == "2026-07-09" for item in result.values())
    assert all(item.fetched_at == FETCHED_AT for item in result.values())
    assert all(item.status == "unverified" for item in result.values())


def test_rejects_empty_official_data_explicitly():
    empty = json.dumps({"stat": "OK", "date": "20260709", "fields": [], "data": []})
    with pytest.raises(ProviderDataError, match="price.*no data"):
        _provider({"STOCK_DAY": empty}).fetch("3033", "2026-07-09")


def test_rejects_mismatched_exact_symbol():
    payload = json.loads(_fixture("twse_margin.json"))
    payload["data"][0][0] = "30330"
    with pytest.raises(ProviderDataError, match="margin.*3033"):
        _provider({"MI_MARGN": json.dumps(payload)}).fetch("3033", "2026-07-09")


def test_rejects_dataset_date_different_from_requested_date():
    payload = json.loads(_fixture("twse_institutional.json"))
    payload["date"] = "20260708"
    with pytest.raises(ProviderDataError, match="institutional.*2026-07-08.*2026-07-09"):
        _provider({"T86": json.dumps(payload)}).fetch("3033", "2026-07-09")


def test_rejects_changed_required_official_header():
    payload = json.loads(_fixture("twse_daytrade.json"))
    payload["fields"][3] = "當沖交易量"
    with pytest.raises(ProviderDataError, match="daytrade.*當沖成交股數"):
        _provider({"TWTB4U": json.dumps(payload)}).fetch("3033", "2026-07-09")


def test_zero_margin_balance_makes_short_composite_unavailable():
    payload = json.loads(_fixture("twse_margin.json"))
    payload["data"][0][2] = "0"

    result = _provider({"MI_MARGN": json.dumps(payload)}).fetch(
        "3033", "2026-07-09"
    )

    assert result["margin"].value == {"balance": 0, "change": -1_200_000}
    assert result["short"].value is None
    assert result["short"].status == "unavailable"
