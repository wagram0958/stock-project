"""Fixture-testable MOPS financial and monthly revenue provider."""

import json
from datetime import date, datetime
from typing import Callable
from urllib.parse import urlencode

from hermes_data_engine.http import fetch_text
from hermes_data_engine.models import Observation
from hermes_data_engine.normalize import normalize_number


class MopsDataError(ValueError):
    """Raised when MOPS data cannot safely supply the requested observations."""


def _rows(text: str, dataset: str) -> list[dict]:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MopsDataError(f"MOPS {dataset} response is not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise MopsDataError(f"MOPS {dataset} response has no data")
    rows = payload["data"]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise MopsDataError(f"MOPS {dataset} response has no usable data")
    return rows


def _publication_date(row: dict, dataset: str) -> str:
    value = row.get("publication_date")
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise MopsDataError(f"MOPS {dataset} has invalid publication date") from exc


def _latest(text: str, dataset: str, symbol: str, cutoff: date) -> dict:
    matches = [
        row for row in _rows(text, dataset)
        if row.get("symbol") == symbol and _publication_date(row, dataset) <= cutoff.isoformat()
    ]
    if not matches:
        raise MopsDataError(
            f"MOPS {dataset} response has no published exact symbol {symbol} by {cutoff}"
        )
    return max(matches, key=lambda row: _publication_date(row, dataset))


def _required_number(row: dict, key: str, dataset: str):
    try:
        value = normalize_number(row.get(key))
    except ValueError as exc:
        raise MopsDataError(f"MOPS {dataset} has invalid {key}") from exc
    if value is None:
        raise MopsDataError(f"MOPS {dataset} has no usable {key}")
    return value


class MopsProvider:
    """Fetch latest actually published MOPS revenue and cumulative financials."""

    BASE_URL = "https://mops.twse.com.tw/api"

    def __init__(self, fetcher: Callable[[str], str] = fetch_text, clock: Callable[[], str] | None = None):
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now().astimezone().isoformat())

    def _url(self, dataset: str, symbol: str) -> str:
        return f"{self.BASE_URL}/{dataset}?{urlencode({'symbol': symbol})}"

    def fetch(self, symbol: str) -> dict[str, Observation]:
        fetched_at = self.clock()
        try:
            cutoff = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).date()
        except (AttributeError, ValueError) as exc:
            raise MopsDataError("MOPS fetch clock returned an invalid timestamp") from exc
        revenue = _latest(
            self.fetcher(self._url("revenue", symbol)), "revenue", symbol, cutoff
        )
        financial = _latest(
            self.fetcher(self._url("financial", symbol)), "financial", symbol, cutoff
        )
        revenue_period = revenue.get("period")
        financial_period = financial.get("period")
        if not isinstance(revenue_period, str) or not revenue_period.strip():
            raise MopsDataError("MOPS revenue has no reporting period")
        if not isinstance(financial_period, str) or not financial_period.strip():
            raise MopsDataError("MOPS financial has no reporting period")
        definitions = {
            "revenue": (revenue, "revenue", revenue_period, _publication_date(revenue, "revenue")),
            "eps": (financial, "basic_eps_cumulative", financial_period, _publication_date(financial, "financial")),
            "cashflow": (financial, "operating_cash_flow_cumulative", financial_period, _publication_date(financial, "financial")),
        }
        return {
            field: Observation(
                _required_number(row, key, field), "MOPS", published, fetched_at,
                "unverified", period,
            )
            for field, (row, key, period, published) in definitions.items()
        }
