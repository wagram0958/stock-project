from decimal import Decimal
from pathlib import Path

import pytest

from hermes_data_engine.models import Observation
from hermes_data_engine.providers.goodinfo import GoodinfoProvider, parse_goodinfo


FIXTURE = Path(__file__).parent / "fixtures" / "goodinfo_daily.html"
FETCHED_AT = "2026-07-10T08:00:00+08:00"


def test_parse_goodinfo_maps_required_daily_fields():
    result = parse_goodinfo(FIXTURE.read_text(encoding="utf-8"), "1314", FETCHED_AT)

    assert set(result) == {
        "price", "volume", "daytrade", "margin", "short",
        "foreign", "investment", "dealer", "date",
    }
    assert result["price"].value == Decimal("42.50")
    assert result["volume"].value == 12_345_000
    assert result["daytrade"].value == {"ratio": Decimal("18.25"), "volume": 2_253}
    assert result["margin"].value == {"balance": 8_100_000, "change": -120_000}
    assert result["short"].value == {"balance": 95_000, "ratio": Decimal("1.17")}
    assert result["foreign"].value == 1_250_000
    assert result["investment"].value == -80_000
    assert result["dealer"].value == 35_000
    assert result["date"].value == "2026-07-09"
    assert all(isinstance(item, Observation) for item in result.values())
    assert all(item.source == "Goodinfo" for item in result.values())
    assert all(item.as_of == "2026-07-09" for item in result.values())
    assert all(item.fetched_at == FETCHED_AT for item in result.values())
    assert all(item.status == "verified" for item in result.values())


def test_parse_goodinfo_rejects_changed_required_header():
    html = FIXTURE.read_text(encoding="utf-8").replace("收盤價", "最後價格")
    with pytest.raises(ValueError, match="missing required Goodinfo headers: 收盤價"):
        parse_goodinfo(html, "1314", FETCHED_AT)


def test_provider_uses_guarded_http_boundary_and_requested_date():
    calls = []

    def fetcher(url):
        calls.append(url)
        return FIXTURE.read_text(encoding="utf-8")

    result = GoodinfoProvider(fetcher=fetcher, clock=lambda: FETCHED_AT).fetch(
        "1314", "2026-07-09"
    )
    assert "STOCK_ID=1314" in calls[0]
    assert result["date"].value == "2026-07-09"


def test_provider_rejects_response_for_another_trading_date():
    provider = GoodinfoProvider(
        fetcher=lambda url: FIXTURE.read_text(encoding="utf-8"),
        clock=lambda: FETCHED_AT,
    )
    with pytest.raises(ValueError, match="requested trading date"):
        provider.fetch("1314", "2026-07-08")
