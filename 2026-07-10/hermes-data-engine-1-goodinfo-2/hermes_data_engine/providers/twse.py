"""Header-driven parsers for official TWSE daily datasets."""

import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable
from urllib.parse import urlencode

from hermes_data_engine.http import fetch_text
from hermes_data_engine.models import Observation
from hermes_data_engine.normalize import lots_to_shares, normalize_number, normalize_roc_date


class ProviderDataError(ValueError):
    """Raised when an official response cannot safely provide requested data."""


def _payload(text: str, dataset: str) -> dict:
    try:
        payload = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProviderDataError(f"TWSE {dataset} response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderDataError(f"TWSE {dataset} response is not an object")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise ProviderDataError(f"TWSE {dataset} response has no data")
    fields = payload.get("fields")
    if not isinstance(fields, list):
        raise ProviderDataError(f"TWSE {dataset} response has no fields")
    return payload


def _dataset_date(value: object, dataset: str) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:])).isoformat()
        except ValueError as exc:
            raise ProviderDataError(f"TWSE {dataset} has invalid date {text!r}") from exc
    if "年" in text:
        text = text.replace("年", "/").replace("月", "/").replace("日", "")
    try:
        normalized = normalize_roc_date(text)
    except ValueError as exc:
        raise ProviderDataError(f"TWSE {dataset} has invalid date {value!r}") from exc
    if normalized is None:
        raise ProviderDataError(f"TWSE {dataset} has no dataset date")
    return normalized


def _indices(payload: dict, dataset: str, required: tuple[str, ...]) -> dict[str, int]:
    fields = payload["fields"]
    missing = [field for field in required if field not in fields]
    if missing:
        raise ProviderDataError(
            f"TWSE {dataset} missing required headers: {', '.join(missing)}"
        )
    return {field: fields.index(field) for field in required}


def _symbol_row(payload: dict, dataset: str, symbol_header: str, symbol: str) -> tuple[list, dict[str, int]]:
    indices = _indices(payload, dataset, (symbol_header,))
    symbol_index = indices[symbol_header]
    for row in payload["data"]:
        if isinstance(row, list) and len(row) > symbol_index and str(row[symbol_index]).strip() == symbol:
            return row, indices
    raise ProviderDataError(f"TWSE {dataset} response has no exact symbol {symbol}")


def _value(row: list, index: int, dataset: str, header: str):
    try:
        value = normalize_number(row[index])
    except (IndexError, ValueError) as exc:
        raise ProviderDataError(f"TWSE {dataset} has invalid {header}") from exc
    if value is None:
        raise ProviderDataError(f"TWSE {dataset} has no usable {header}")
    return value


def _dated(payload: dict, dataset: str, requested_date: str) -> str:
    actual = _dataset_date(payload.get("date"), dataset)
    if actual != requested_date:
        raise ProviderDataError(
            f"TWSE {dataset} dataset date {actual} does not match requested date {requested_date}"
        )
    return actual


def _parse_price(text: str, requested_date: str) -> tuple[str, dict]:
    dataset = "price"
    payload = _payload(text, dataset)
    indices = _indices(payload, dataset, ("日期", "成交股數", "收盤價"))
    row = payload["data"][0]
    actual = _dataset_date(row[indices["日期"]], dataset)
    if actual != requested_date:
        raise ProviderDataError(
            f"TWSE {dataset} dataset date {actual} does not match requested date {requested_date}"
        )
    return actual, {
        "price": _value(row, indices["收盤價"], dataset, "收盤價"),
        "volume": _value(row, indices["成交股數"], dataset, "成交股數"),
    }


def _parse_margin(text: str, symbol: str, requested_date: str) -> tuple[str, dict]:
    dataset = "margin"
    payload = _payload(text, dataset)
    actual = _dated(payload, dataset, requested_date)
    required = ("股票代號", "融資前日餘額", "融資今日餘額", "融券前日餘額", "融券今日餘額")
    row, _ = _symbol_row(payload, dataset, "股票代號", symbol)
    indices = _indices(payload, dataset, required)
    margin_previous = _value(row, indices["融資前日餘額"], dataset, "融資前日餘額")
    margin_balance = _value(row, indices["融資今日餘額"], dataset, "融資今日餘額")
    short_previous = _value(row, indices["融券前日餘額"], dataset, "融券前日餘額")
    short_balance = _value(row, indices["融券今日餘額"], dataset, "融券今日餘額")
    ratio = (Decimal(short_balance) * 100 / Decimal(margin_balance)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    ) if margin_balance else None
    return actual, {
        "margin": {"balance": lots_to_shares(margin_balance), "change": lots_to_shares(margin_balance - margin_previous)},
        "short": {"balance": lots_to_shares(short_balance), "change": lots_to_shares(short_balance - short_previous), "ratio": ratio},
    }


def _parse_symbol_dataset(text, dataset, symbol, requested_date, symbol_header, value_headers):
    payload = _payload(text, dataset)
    actual = _dated(payload, dataset, requested_date)
    row, _ = _symbol_row(payload, dataset, symbol_header, symbol)
    indices = _indices(payload, dataset, (symbol_header, *value_headers))
    return actual, {header: _value(row, indices[header], dataset, header) for header in value_headers}


class TwseProvider:
    """Fetch the five official TWSE datasets used for cross-validation."""

    BASE_URL = "https://www.twse.com.tw/rwd/zh"

    def __init__(self, fetcher: Callable[[str], str] = fetch_text, clock: Callable[[], str] | None = None):
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now().astimezone().isoformat())

    def _url(self, dataset: str, query: dict) -> str:
        return f"{self.BASE_URL}/{dataset}?{urlencode({**query, 'response': 'json'})}"

    def fetch(self, symbol: str, trading_date: str) -> dict[str, Observation]:
        compact_date = trading_date.replace("-", "")
        fetched_at = self.clock()
        dates_and_values = [
            _parse_price(self.fetcher(self._url("afterTrading/STOCK_DAY", {"date": compact_date, "stockNo": symbol})), trading_date),
            _parse_margin(self.fetcher(self._url("marginTrading/MI_MARGN", {"date": compact_date, "selectType": "ALL"})), symbol, trading_date),
        ]
        actual, daytrade = _parse_symbol_dataset(
            self.fetcher(self._url("dayTrading/TWTB4U", {"date": compact_date, "selectType": "All"})),
            "daytrade", symbol, trading_date, "證券代號", ("當沖成交股數", "當沖成交比率"),
        )
        dates_and_values.append((actual, {"daytrade": {"volume": daytrade["當沖成交股數"], "ratio": daytrade["當沖成交比率"]}}))
        actual, institutional = _parse_symbol_dataset(
            self.fetcher(self._url("fund/T86", {"date": compact_date, "selectType": "ALLBUT0999"})),
            "institutional", symbol, trading_date, "證券代號",
            ("外陸資買賣超股數(不含外資自營商)", "投信買賣超股數", "自營商買賣超股數"),
        )
        dates_and_values.append((actual, {
            "foreign": institutional["外陸資買賣超股數(不含外資自營商)"],
            "investment": institutional["投信買賣超股數"],
            "dealer": institutional["自營商買賣超股數"],
        }))
        actual, valuation = _parse_symbol_dataset(
            self.fetcher(self._url("afterTrading/BWIBBU", {"date": compact_date, "selectType": "ALL"})),
            "valuation", symbol, trading_date, "證券代號", ("本益比", "股價淨值比"),
        )
        dates_and_values.append((actual, {"pe": valuation["本益比"], "pb": valuation["股價淨值比"]}))
        values = {}
        for _, parsed in dates_and_values:
            values.update(parsed)
        values["date"] = trading_date
        return {
            field: Observation(value, "TWSE", trading_date, fetched_at, "unverified")
            for field, value in values.items()
        }
