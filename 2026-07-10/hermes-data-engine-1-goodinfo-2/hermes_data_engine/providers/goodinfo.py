"""Goodinfo daily table parser and guarded provider adapter."""

from datetime import datetime
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlencode

from hermes_data_engine.http import fetch_text
from hermes_data_engine.models import Observation
from hermes_data_engine.normalize import lots_to_shares, normalize_number, normalize_roc_date


HEADERS = (
    "日期",
    "收盤價",
    "成交量(張)",
    "當沖比率",
    "當沖量(張)",
    "融資餘額(張)",
    "融資增減(張)",
    "融券餘額(張)",
    "券資比",
    "外資買賣超(張)",
    "投信買賣超(張)",
    "自營商買賣超(張)",
)


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def _daily_row(html: str) -> dict[str, str]:
    parser = _TableParser()
    parser.feed(html)
    seen_headers: set[str] = set()
    for table in parser.tables:
        if not table:
            continue
        headers = table[0]
        seen_headers.update(headers)
        if all(header in headers for header in HEADERS):
            if len(table) < 2:
                raise ValueError("Goodinfo daily table has no data row")
            row = table[1]
            if len(row) != len(headers):
                raise ValueError("Goodinfo daily row does not match its headers")
            return dict(zip(headers, row))
    missing = [header for header in HEADERS if header not in seen_headers]
    raise ValueError(f"missing required Goodinfo headers: {', '.join(missing)}")


def parse_goodinfo(
    html: str, symbol: str, fetched_at: str
) -> dict[str, Observation]:
    """Parse required fields from a header-identified Goodinfo daily table."""
    del symbol  # Reserved for diagnostics as provider formats evolve.
    row = _daily_row(html)
    as_of = normalize_roc_date(row["日期"])
    if as_of is None:
        raise ValueError("Goodinfo daily row has no date")
    values = {
        "price": normalize_number(row["收盤價"]),
        "volume": lots_to_shares(row["成交量(張)"]),
        "daytrade": {
            "ratio": normalize_number(row["當沖比率"]),
            "volume": normalize_number(row["當沖量(張)"]),
        },
        "margin": {
            "balance": lots_to_shares(row["融資餘額(張)"]),
            "change": lots_to_shares(row["融資增減(張)"]),
        },
        "short": {
            "balance": lots_to_shares(row["融券餘額(張)"]),
            "ratio": normalize_number(row["券資比"]),
        },
        "foreign": lots_to_shares(row["外資買賣超(張)"]),
        "investment": lots_to_shares(row["投信買賣超(張)"]),
        "dealer": lots_to_shares(row["自營商買賣超(張)"]),
        "date": as_of,
    }
    return {
        field: Observation(value, "Goodinfo", as_of, fetched_at, "verified")
        for field, value in values.items()
    }


class GoodinfoProvider:
    """Fetch supported Goodinfo data without bypassing access controls."""

    BASE_URL = "https://goodinfo.tw/tw/StockDetail.asp"

    def __init__(
        self,
        fetcher: Callable[[str], str] = fetch_text,
        clock: Callable[[], str] | None = None,
    ):
        self.fetcher = fetcher
        self.clock = clock or (lambda: datetime.now().astimezone().isoformat())

    def fetch(self, symbol: str, trading_date: str) -> dict[str, Observation]:
        url = f"{self.BASE_URL}?{urlencode({'STOCK_ID': symbol})}"
        observations = parse_goodinfo(self.fetcher(url), symbol, self.clock())
        if observations["date"].value != trading_date:
            raise ValueError(
                f"Goodinfo response does not contain requested trading date {trading_date}"
            )
        return observations
