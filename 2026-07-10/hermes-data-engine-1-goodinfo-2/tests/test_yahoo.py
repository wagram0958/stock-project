import json
from decimal import Decimal
from pathlib import Path

import pytest

from hermes_data_engine.providers.yahoo import YahooProvider


FIXTURES = Path(__file__).parent / "fixtures"
FETCHED_AT = "2026-07-10T08:00:00+08:00"


def _fetcher(url):
    name = "yahoo_chart.json" if "/chart/" in url else "yahoo_quote.json"
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_yahoo_returns_exact_supported_allowlist_and_source():
    result = YahooProvider(fetcher=_fetcher, clock=lambda: FETCHED_AT).fetch(
        "1314", "2026-07-09"
    )

    assert set(result) == {"price", "volume", "pe", "pb"}
    assert result["price"].value == Decimal("42.5")
    assert result["volume"].value == 12_345_000
    assert result["pe"].value == Decimal("12.5")
    assert result["pb"].value == Decimal("1.75")
    assert all(item.source == "Yahoo(Fallback)" for item in result.values())
    assert all(item.as_of == "2026-07-09" for item in result.values())
    assert all(item.status == "fallback" for item in result.values())


def test_yahoo_negative_earnings_does_not_fabricate_pe():
    quote = json.loads((FIXTURES / "yahoo_quote.json").read_text(encoding="utf-8"))
    quote["quoteResponse"]["result"][0]["trailingPE"] = 99.0
    quote["quoteResponse"]["result"][0]["epsTrailingTwelveMonths"] = -2.0

    def fetcher(url):
        return json.dumps(quote) if "/quote" in url else _fetcher(url)

    result = YahooProvider(fetcher=fetcher, clock=lambda: FETCHED_AT).fetch(
        "1314", "2026-07-09"
    )
    assert result["pe"].value is None
    assert result["pe"].status == "unavailable"


def test_yahoo_missing_earnings_fails_pe_closed():
    quote = json.loads((FIXTURES / "yahoo_quote.json").read_text(encoding="utf-8"))
    del quote["quoteResponse"]["result"][0]["epsTrailingTwelveMonths"]

    def fetcher(url):
        return json.dumps(quote) if "/quote" in url else _fetcher(url)

    result = YahooProvider(fetcher=fetcher, clock=lambda: FETCHED_AT).fetch(
        "1314", "2026-07-09"
    )
    assert result["pe"].value is None
    assert result["pe"].status == "unavailable"


@pytest.mark.parametrize("payload", ["null", "{}", "not-json"])
def test_yahoo_malformed_responses_fail_closed(payload):
    provider = YahooProvider(fetcher=lambda url: payload, clock=lambda: FETCHED_AT)
    with pytest.raises(ValueError, match="Yahoo"):
        provider.fetch("1314", "2026-07-09")


def test_yahoo_rejects_chart_without_requested_trading_date():
    provider = YahooProvider(fetcher=_fetcher, clock=lambda: FETCHED_AT)
    with pytest.raises(ValueError, match="requested trading date"):
        provider.fetch("1314", "2026-07-07")
