from decimal import Decimal
from pathlib import Path

import pytest

from hermes_data_engine.providers.mops import MopsProvider


FIXTURES = Path(__file__).parent / "fixtures"
FETCHED_AT = "2026-07-10T08:00:00+08:00"


def _fetcher(url):
    name = "mops_revenue.json" if "revenue" in url else "mops_financial.json"
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_mops_selects_latest_published_periods_with_publication_as_as_of():
    result = MopsProvider(fetcher=_fetcher, clock=lambda: FETCHED_AT).fetch("1314")

    assert set(result) == {"revenue", "eps", "cashflow"}
    assert result["revenue"].value == 1250
    assert result["revenue"].period == "2026-05"
    assert result["revenue"].as_of == "2026-06-10"
    assert result["eps"].value == Decimal("0.55")
    assert result["cashflow"].value == 320
    assert result["eps"].period == result["cashflow"].period == "2026-Q1"
    assert result["eps"].as_of == result["cashflow"].as_of == "2026-05-15"
    assert all(item.source == "MOPS" for item in result.values())
    assert all(item.fetched_at == FETCHED_AT for item in result.values())
    assert all(item.status == "unverified" for item in result.values())
    assert all(item.as_of != item.period for item in result.values())


@pytest.mark.parametrize("payload", ["null", "{}", '{"data": []}', "not-json"])
def test_mops_malformed_or_empty_responses_fail_closed(payload):
    provider = MopsProvider(fetcher=lambda url: payload, clock=lambda: FETCHED_AT)
    with pytest.raises(ValueError, match="MOPS"):
        provider.fetch("1314")


def test_mops_requires_exact_symbol():
    provider = MopsProvider(fetcher=_fetcher, clock=lambda: FETCHED_AT)
    with pytest.raises(ValueError, match="exact symbol"):
        provider.fetch("9999")


def test_mops_fails_when_symbol_has_no_records_published_by_fetch_date():
    provider = MopsProvider(
        fetcher=_fetcher, clock=lambda: "2026-01-01T08:00:00+08:00"
    )
    with pytest.raises(ValueError, match="no published exact symbol"):
        provider.fetch("1314")
