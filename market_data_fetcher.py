from __future__ import annotations

import argparse
import csv
import json
import re
import ssl
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.parse import urljoin
from urllib.request import Request, urlopen


GOODINFO_URL = "https://goodinfo.tw/tw/ShowK_Chart.asp"
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
TPEX_STOCK_DAY_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
DEFAULT_OUTPUT_DIR = Path("data/market_data")
DEFAULT_AUDIT_LOG_DIR = Path("logs/market_validation")
DATA_VALIDATION_FAILED = "DATA_VALIDATION_FAILED"
VALIDATION_SUCCESS = "驗證成功"
CONFIDENCE_CHECKS = ["Goodinfo", "TWSE / TPEx", "股票代號", "交易日期", "收盤價", "成交量"]


@dataclass(frozen=True)
class MarketDataRecord:
    symbol: str
    name: str
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    previous_close: float
    change: float
    change_percent: float
    volume: int


@dataclass(frozen=True)
class OfficialRecord:
    source: str
    symbol: str
    trade_date: str
    close_price: float
    volume: int


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    status: str
    mismatches: list[str]
    confidence_score: int
    checks: dict[str, bool]


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[dict[str, Any]] = []
        self._table_stack: list[dict[str, Any]] = []
        self._current_cell: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_stack.append({"caption": "", "rows": [], "current_row": []})
        elif tag == "tr" and self._table_stack:
            self._table_stack[-1]["current_row"] = []
        elif tag in {"td", "th", "caption"} and self._table_stack:
            self._current_cell = {"tag": tag, "text": []}

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th", "caption"} and self._current_cell is not None and self._table_stack:
            text = clean_text("".join(self._current_cell["text"]))
            if tag == "caption":
                self._table_stack[-1]["caption"] += text
            elif text:
                self._table_stack[-1]["current_row"].append(text)
            self._current_cell = None
        elif tag == "tr" and self._table_stack:
            row = self._table_stack[-1]["current_row"]
            if row:
                self._table_stack[-1]["rows"].append(row)
        elif tag == "table" and self._table_stack:
            table = self._table_stack.pop()
            self.tables.append({"caption": table["caption"], "rows": table["rows"]})


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def fetch_text(
    url: str,
    encoding: str | None = None,
    headers: dict[str, str] | None = None,
    verify_ssl: bool = True,
) -> str:
    request_headers = {
        "User-Agent": "Mozilla/5.0 market-data-fetcher/1.0",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        headers=request_headers,
    )
    context = None if verify_ssl else ssl._create_unverified_context()
    with urlopen(request, timeout=20, context=context) as response:
        content = response.read()
        detected_encoding = encoding or response.headers.get_content_charset() or "utf-8"
    try:
        return content.decode(detected_encoding)
    except UnicodeDecodeError:
        return content.decode("big5-hkscs", errors="replace")


def build_goodinfo_url(symbol: str) -> str:
    return f"{GOODINFO_URL}?{urlencode({'STOCK_ID': symbol, 'CHT_CAT': 'DATE'})}"


def fetch_goodinfo_record(symbol: str, trade_date: str) -> MarketDataRecord:
    html = fetch_goodinfo_html(symbol)
    return parse_goodinfo_daily_table(html, symbol, trade_date)


def fetch_goodinfo_html(symbol: str) -> str:
    url = build_goodinfo_url(symbol)
    html = fetch_text(url)
    redirect_url = parse_goodinfo_reinit_url(html)
    if not redirect_url:
        return html

    cookie = build_goodinfo_client_key(html)
    return fetch_text(
        urljoin("https://goodinfo.tw/tw/", redirect_url),
        headers={"Cookie": f"CLIENT_KEY={cookie}"},
    )


def parse_goodinfo_reinit_url(html: str) -> str | None:
    match = re.search(r"window\.location\.replace\('([^']+)'\)", html)
    if not match:
        return None
    return match.group(1)


def build_goodinfo_client_key(html: str) -> str:
    values = dict(re.findall(r"arr\[(\d+)\]\s*=\s*'([^']*)'", html))
    return "|".join(values.get(str(index), "0") if index not in {3, 4, 5, 6, 7} else "0" for index in range(8))


def parse_goodinfo_daily_table(html: str, symbol: str, trade_date: str) -> MarketDataRecord:
    parsed_symbol, name = parse_symbol_and_name(html, symbol)
    if parsed_symbol != symbol:
        raise ValueError(f"Goodinfo symbol mismatch: expected {symbol}, got {parsed_symbol}")

    parser = TableParser()
    parser.feed(html)
    target_date = normalize_date(trade_date)

    for table in parser.tables:
        rows = table["rows"]
        if not rows or not is_daily_trade_table(table["caption"], rows):
            continue

        headers, subheaders, data_rows = split_goodinfo_rows(rows)
        indexes = map_headers(headers, subheaders)
        for row in data_rows:
            if len(row) <= max(indexes.values()):
                continue
            row_date = normalize_date(row[indexes["trade_date"]])
            if row_date != target_date:
                continue
            close_price = parse_float(row[indexes["close_price"]])
            change = parse_float(row[indexes["change"]])
            previous_close = (
                parse_float(row[indexes["previous_close"]])
                if "previous_close" in indexes
                else round(close_price - change, 2)
            )
            return MarketDataRecord(
                symbol=symbol,
                name=name,
                trade_date=row_date,
                open_price=parse_float(row[indexes["open_price"]]),
                high_price=parse_float(row[indexes["high_price"]]),
                low_price=parse_float(row[indexes["low_price"]]),
                close_price=close_price,
                previous_close=previous_close,
                change=change,
                change_percent=parse_percent(row[indexes["change_percent"]]),
                volume=parse_volume(row[indexes["volume"]], volume_header(headers, subheaders, indexes["volume"])),
            )

    raise ValueError(f"Goodinfo daily trading row not found for {symbol} on {trade_date}")


def parse_symbol_and_name(html: str, expected_symbol: str) -> tuple[str, str]:
    text = clean_text(re.sub(r"<[^>]+>", " ", html))
    pattern = rf"\b({re.escape(expected_symbol)})\s+([^\s,，:：\-|]+)"
    match = re.search(pattern, text)
    if match:
        return match.group(1), match.group(2)

    any_symbol = re.search(r"\b(\d{4})\s+([^\s,，:：\-|]+)", text)
    if any_symbol:
        return any_symbol.group(1), any_symbol.group(2)

    return expected_symbol, ""


def is_daily_trade_table(caption: str, rows: list[list[str]]) -> bool:
    return "每日成交行情" in caption


def split_goodinfo_rows(rows: list[list[str]]) -> tuple[list[str], list[str], list[list[str]]]:
    headers = rows[0]
    if len(rows) > 1 and not looks_like_data_row(rows[1]):
        return headers, rows[1], rows[2:]
    return headers, [], rows[1:]


def looks_like_data_row(row: list[str]) -> bool:
    if not row:
        return False
    return bool(re.match(r"^'?\d{2,4}[/.-]\d{1,2}[/.-]\d{1,2}$", row[0]))


def map_headers(headers: list[str], subheaders: list[str] | None = None) -> dict[str, int]:
    subheaders = subheaders or []
    aliases = {
        "trade_date": ["日期"],
        "open_price": ["開盤"],
        "high_price": ["最高"],
        "low_price": ["最低"],
        "close_price": ["收盤"],
        "previous_close": ["昨收"],
        "change": ["漲跌"],
        "change_percent": ["漲跌幅", "漲跌 (%)", "漲跌(%)"],
        "volume": ["成交張數", "成交量"],
    }
    mapped: dict[str, int] = {}
    for field, names in aliases.items():
        for index, header in enumerate(headers):
            if any(name in header for name in names):
                mapped[field] = index
                break
        if field == "volume" and field not in mapped:
            for index, header in enumerate(headers):
                if "成交資料" in header and subheaders and "張數" in subheaders[0]:
                    mapped[field] = index
                    break
        if field == "volume" and field not in mapped:
            for index, subheader in enumerate(subheaders):
                if "張數" in subheader or "成交" in subheader:
                    mapped[field] = len(headers) - 1 + index
                    break
        if field == "previous_close" and field not in mapped:
            continue
        if field not in mapped:
            raise ValueError(f"Goodinfo daily table missing column: {field}")
    return mapped


def volume_header(headers: list[str], subheaders: list[str], index: int) -> str:
    if index < len(headers):
        header = headers[index]
        if "成交資料" in header and subheaders:
            return subheaders[0]
        return header
    subheader_index = index - (len(headers) - 1)
    if 0 <= subheader_index < len(subheaders):
        return subheaders[subheader_index]
    return ""


def normalize_date(value: str) -> str:
    cleaned = clean_text(value).lstrip("'").replace(".", "/").replace("-", "/")
    parts = cleaned.split("/")
    if len(parts) != 3:
        raise ValueError(f"Unsupported date format: {value}")

    year = int(parts[0])
    if year < 100:
        year += 2000
    elif year < 1000:
        year += 1911

    return f"{year:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def parse_float(value: str) -> float:
    cleaned = clean_text(value).replace(",", "").replace("%", "").replace("+", "")
    if cleaned in {"", "-", "--"}:
        raise ValueError(f"Cannot parse number: {value}")
    return float(cleaned)


def parse_percent(value: str) -> float:
    return parse_float(value)


def parse_volume(value: str, header: str) -> int:
    volume = int(parse_float(value))
    if "股" in header:
        return (volume + 500) // 1000
    return volume


def fetch_official_record(symbol: str, trade_date: str) -> OfficialRecord:
    try:
        return fetch_twse_record(symbol, trade_date)
    except ValueError:
        return fetch_tpex_record(symbol, trade_date)


def fetch_twse_record(symbol: str, trade_date: str) -> OfficialRecord:
    query = urlencode({"date": trade_date.replace("-", ""), "stockNo": symbol, "response": "json"})
    payload = json.loads(fetch_text(f"{TWSE_STOCK_DAY_URL}?{query}", verify_ssl=False))
    fields = payload.get("fields", [])
    rows = payload.get("data", [])
    if not rows:
        raise ValueError(f"TWSE returned no data for {symbol} on {trade_date}")
    return parse_official_table("TWSE", symbol, trade_date, fields, rows)


def fetch_tpex_record(symbol: str, trade_date: str) -> OfficialRecord:
    query = urlencode({"code": symbol, "date": trade_date.replace("-", "/"), "response": "json"})
    payload = json.loads(fetch_text(f"{TPEX_STOCK_DAY_URL}?{query}", verify_ssl=False))
    fields = payload.get("fields") or payload.get("tables", [{}])[0].get("fields", [])
    rows = payload.get("data") or payload.get("tables", [{}])[0].get("data", [])
    if not rows:
        raise ValueError(f"TPEx returned no data for {symbol} on {trade_date}")
    return parse_official_table("TPEx", symbol, trade_date, fields, rows)


def parse_official_table(source: str, symbol: str, trade_date: str, fields: list[str], rows: list[list[str]]) -> OfficialRecord:
    close_index = find_field(fields, ["收盤價", "收盤"])
    volume_index = find_field(fields, ["成交股數", "成交股數(股)", "成交量"])
    date_index = find_field(fields, ["日期"])
    target_date = normalize_date(trade_date)

    for row in rows:
        if normalize_date(row[date_index]) == target_date:
            return OfficialRecord(
                source=source,
                symbol=symbol,
                trade_date=target_date,
                close_price=parse_float(row[close_index]),
                volume=parse_volume(row[volume_index], fields[volume_index]),
            )

    raise ValueError(f"{source} row not found for {symbol} on {trade_date}")


def find_field(fields: list[str], candidates: list[str]) -> int:
    for index, field in enumerate(fields):
        if any(candidate in field for candidate in candidates):
            return index
    raise ValueError(f"Official data missing field: {', '.join(candidates)}")


def validate_market_data(goodinfo: MarketDataRecord, official: OfficialRecord) -> ValidationResult:
    checks = {
        "Goodinfo": goodinfo is not None,
        "TWSE / TPEx": official.source in {"TWSE", "TPEx"},
        "股票代號": goodinfo.symbol == official.symbol,
        "交易日期": goodinfo.trade_date == official.trade_date,
        "收盤價": round(goodinfo.close_price, 2) == round(official.close_price, 2),
        "成交量": goodinfo.volume == official.volume,
    }
    mismatches = [name for name, passed in checks.items() if not passed]
    confidence_score = calculate_confidence_score(checks)

    if confidence_score != 100:
        return ValidationResult(False, DATA_VALIDATION_FAILED, mismatches, confidence_score, checks)
    return ValidationResult(True, VALIDATION_SUCCESS, [], confidence_score, checks)


def failed_validation_result(error_check: str) -> ValidationResult:
    checks = {name: False for name in CONFIDENCE_CHECKS}
    if error_check in checks:
        checks[error_check] = False
    return ValidationResult(False, DATA_VALIDATION_FAILED, list(checks), 0, checks)


def calculate_confidence_score(checks: dict[str, bool]) -> int:
    if not checks:
        return 0
    passed = sum(1 for passed_check in checks.values() if passed_check)
    return round(passed / len(checks) * 100)


def build_report(
    goodinfo: MarketDataRecord,
    official: OfficialRecord,
    validation: ValidationResult,
    fetched_at: datetime,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "symbol": goodinfo.symbol,
        "name": goodinfo.name,
        "trade_date": goodinfo.trade_date,
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "session": classify_session(fetched_at),
        "validation_status": validation.status,
        "confidence_score": validation.confidence_score,
        "confidence_checks": validation.checks,
        "hermes_analysis_allowed": validation.confidence_score == 100,
        "is_delayed": True,
    }
    if validation.mismatches:
        report["mismatches"] = validation.mismatches

    if validation.is_valid:
        report["goodinfo_raw"] = asdict(goodinfo)
        report["official_raw"] = asdict(official)
    return report


def classify_session(fetched_at: datetime) -> str:
    current_time = fetched_at.time()
    if current_time.hour < 13 or (current_time.hour == 13 and current_time.minute <= 30):
        return "盤中"
    return "收盤"


def save_report(report: dict[str, Any], output_root: Path = DEFAULT_OUTPUT_DIR) -> Path:
    trade_date = str(report["trade_date"])
    symbol = str(report["symbol"])
    fetched_at = str(report.get("fetched_at", datetime.now().isoformat(timespec="seconds")))
    safe_timestamp = fetched_at.replace(":", "").replace("-", "").replace("T", "_")
    output_dir = output_root / trade_date
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate = output_dir / f"{symbol}_{safe_timestamp}.json"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"{symbol}_{safe_timestamp}_{suffix}.json"
        suffix += 1

    candidate.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return candidate


def save_audit_log(
    requested_symbol: str,
    requested_date: str,
    fetched_at: datetime,
    goodinfo: MarketDataRecord | None,
    official: OfficialRecord | None,
    validation: ValidationResult,
    error_message: str = "",
    log_root: Path = DEFAULT_AUDIT_LOG_DIR,
) -> Path:
    audit = {
        "requested_symbol": requested_symbol,
        "requested_date": requested_date,
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "goodinfo_raw": asdict(goodinfo) if goodinfo else None,
        "official_raw": asdict(official) if official else None,
        "confidence_score": validation.confidence_score,
        "confidence_checks": validation.checks,
        "success": validation.is_valid,
        "error_message": error_message,
    }

    safe_timestamp = fetched_at.isoformat(timespec="seconds").replace(":", "").replace("-", "").replace("T", "_")
    log_root.mkdir(parents=True, exist_ok=True)
    candidate = log_root / f"{requested_symbol}_{requested_date}_{safe_timestamp}.json"
    suffix = 1
    while candidate.exists():
        candidate = log_root / f"{requested_symbol}_{requested_date}_{safe_timestamp}_{suffix}.json"
        suffix += 1

    candidate.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return candidate


def build_fail_safe_report(
    symbol: str,
    trade_date: str,
    fetched_at: datetime,
    validation: ValidationResult,
    error_message: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "trade_date": trade_date,
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        "validation_status": DATA_VALIDATION_FAILED,
        "confidence_score": validation.confidence_score,
        "confidence_checks": validation.checks,
        "hermes_analysis_allowed": False,
        "error_message": error_message,
    }


def print_report(report: dict[str, Any]) -> None:
    if report.get("validation_status") == DATA_VALIDATION_FAILED:
        print(DATA_VALIDATION_FAILED)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def fetch_validate_and_save(
    symbol: str,
    trade_date: str,
    output_root: Path = DEFAULT_OUTPUT_DIR,
    audit_log_root: Path = DEFAULT_AUDIT_LOG_DIR,
) -> dict[str, Any]:
    fetched_at = datetime.now()
    goodinfo: MarketDataRecord | None = None
    official: OfficialRecord | None = None
    error_message = ""

    try:
        goodinfo = fetch_goodinfo_record(symbol, trade_date)
        official = fetch_official_record(symbol, trade_date)
        validation = validate_market_data(goodinfo, official)
        report = build_report(goodinfo, official, validation, fetched_at)
        if not validation.is_valid:
            error_message = ", ".join(validation.mismatches)
    except (URLError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        error_message = str(exc)
        validation = failed_validation_result("Goodinfo" if goodinfo is None else "TWSE / TPEx")
        report = build_fail_safe_report(symbol, trade_date, fetched_at, validation, error_message)

    saved_path = save_report(report, output_root)
    audit_path = save_audit_log(symbol, trade_date, fetched_at, goodinfo, official, validation, error_message, audit_log_root)
    report["saved_path"] = str(saved_path)
    report["audit_log_path"] = str(audit_path)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and validate Taiwan stock daily market data.")
    parser.add_argument("--symbol", required=True, help="Taiwan stock symbol, for example 2002.")
    parser.add_argument("--date", required=True, help="Trade date in YYYY-MM-DD format.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output root directory. Default: data/market_data",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = fetch_validate_and_save(args.symbol, args.date, args.output_dir)
    print_report(report)
    return 0 if report["validation_status"] == VALIDATION_SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
