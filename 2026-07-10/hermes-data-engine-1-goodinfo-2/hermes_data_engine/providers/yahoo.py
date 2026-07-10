"""Narrow Yahoo market-data fallback with an explicit field allowlist."""

import json
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlencode

from hermes_data_engine.http import fetch_text
from hermes_data_engine.models import Observation
from hermes_data_engine.normalize import normalize_number


class YahooDataError(ValueError):
    """Raised when a Yahoo response cannot safely provide fallback data."""


def _object(text: str, dataset: str) -> dict:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise YahooDataError(f"Yahoo {dataset} response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise YahooDataError(f"Yahoo {dataset} response is not an object")
    return payload


def _chart_values(text: str, trading_date: str) -> dict:
    payload = _object(text, "chart")
    try:
        result = payload["chart"]["result"]
        record = result[0]
        timestamps = record["timestamp"]
        quote = record["indicators"]["quote"][0]
        closes, volumes = quote["close"], quote["volume"]
    except (KeyError, IndexError, TypeError) as exc:
        raise YahooDataError("Yahoo chart response has no usable result") from exc
    for index, timestamp in enumerate(timestamps):
        try:
            actual = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError) as exc:
            raise YahooDataError("Yahoo chart has an invalid timestamp") from exc
        if actual == trading_date:
            try:
                price = normalize_number(closes[index])
                volume = normalize_number(volumes[index])
            except (IndexError, TypeError, ValueError) as exc:
                raise YahooDataError("Yahoo chart has invalid price or volume") from exc
            if price is None or volume is None:
                raise YahooDataError("Yahoo chart has no usable price or volume")
            return {"price": price, "volume": volume}
    raise YahooDataError(f"Yahoo chart has no requested trading date {trading_date}")


def _quote_values(text: str, expected_symbol: str) -> dict:
    payload = _object(text, "quote")
    try:
        records = payload["quoteResponse"]["result"]
        record = records[0]
    except (KeyError, IndexError, TypeError) as exc:
        raise YahooDataError("Yahoo quote response has no usable result") from exc
    if record.get("symbol") != expected_symbol:
        raise YahooDataError(f"Yahoo quote response has no exact symbol {expected_symbol}")
    values = {}
    for field, key in (("pe", "trailingPE"), ("pb", "priceToBook")):
        try:
            values[field] = normalize_number(record.get(key))
        except ValueError as exc:
            raise YahooDataError(f"Yahoo quote has invalid {key}") from exc
    try:
        earnings = normalize_number(record.get("epsTrailingTwelveMonths"))
    except ValueError as exc:
        raise YahooDataError("Yahoo quote has invalid epsTrailingTwelveMonths") from exc
    if earnings is None or earnings <= 0:
        values["pe"] = None
    return values


class YahooProvider:
    """Return only price, volume, PE, and PB as Yahoo fallbacks."""

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance"

    def __init__(self, fetcher: Callable[[str], str] = fetch_text, clock: Callable[[], str] | None = None):
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now().astimezone().isoformat())

    def fetch(self, symbol: str, trading_date: str) -> dict[str, Observation]:
        yahoo_symbol = f"{symbol}.TW"
        chart_url = f"{self.BASE_URL}/chart/{yahoo_symbol}?{urlencode({'interval': '1d', 'range': '1mo'})}"
        quote_url = f"{self.BASE_URL}/quote?{urlencode({'symbols': yahoo_symbol})}"
        values = _chart_values(self.fetcher(chart_url), trading_date)
        values.update(_quote_values(self.fetcher(quote_url), yahoo_symbol))
        fetched_at = self.clock()
        return {
            field: Observation(
                value, "Yahoo(Fallback)", trading_date, fetched_at,
                "unavailable" if value is None else "fallback",
            )
            for field, value in values.items()
        }
