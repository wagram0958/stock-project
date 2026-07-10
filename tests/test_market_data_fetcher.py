from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from market_data_fetcher import (
    MarketDataRecord,
    OfficialRecord,
    build_report,
    fetch_goodinfo_record,
    parse_official_table,
    parse_goodinfo_daily_table,
    save_report,
    validate_market_data,
)


GOODINFO_HTML = """
<html>
  <head><title>Goodinfo!台灣股市資訊網 - 1314 中石化</title></head>
  <body>
    <table id="summary">
      <tr><th>收盤價</th><td>99.99</td></tr>
    </table>
    <table id="daily">
      <caption>每日成交行情</caption>
      <tr>
        <th>日期</th><th>開盤</th><th>最高</th><th>最低</th><th>收盤</th>
        <th>昨收</th><th>漲跌</th><th>漲跌幅</th><th>成交張數</th>
      </tr>
      <tr>
        <td>26/07/10</td><td>10.20</td><td>10.70</td><td>10.00</td><td>10.15</td>
        <td>10.05</td><td>+0.10</td><td>+1.00%</td><td>12,345</td>
      </tr>
      <tr>
        <td>26/07/09</td><td>10.00</td><td>10.70</td><td>9.95</td><td>10.05</td>
        <td>10.10</td><td>-0.05</td><td>-0.50%</td><td>8,765</td>
      </tr>
    </table>
  </body>
</html>
"""


GOODINFO_REALISTIC_DETAIL_HTML = """
<html>
  <head><title>Goodinfo!台灣股市資訊網 - 1314 中石化</title></head>
  <body>
    <table id="tblDetail">
      <caption>1314 中石化 每日成交行情、法人買賣及融資券詳細資料</caption>
      <thead>
        <tr>
          <th rowspan="2">交易<br>日期</th><th rowspan="2">開盤</th>
          <th rowspan="2">最高</th><th rowspan="2">最低</th>
          <th rowspan="2">收盤</th><th rowspan="2">漲跌</th>
          <th rowspan="2">漲跌<br>(%)</th><th rowspan="2">振幅<br>(%)</th>
          <th colspan="4">成交資料</th>
        </tr>
        <tr><th>張數</th><th>筆數</th><th>均張</th><th>億元</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>'26/07/09</td><td>9.6</td><td>9.61</td><td>8.83</td><td>8.9</td>
          <td>-0.8</td><td>-8.25</td><td>8.04</td><td>155,533</td><td>37,958</td>
          <td>4.1</td><td>14.1</td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""


GOODINFO_WITH_SUMMARY_BEFORE_DAILY_HTML = """
<html>
  <head><title>Goodinfo!台灣股市資訊網 - 1314 中石化</title></head>
  <body>
    <table>
      <caption>1314 中石化 當日及昨日交易資料</caption>
      <tr>
        <th>成交價</th><th>昨收</th><th>漲跌價</th><th>漲跌幅</th>
        <th>開盤</th><th>最高</th><th>最低</th>
      </tr>
      <tr><td>99.99</td><td>9.70</td><td>+90.29</td><td>999%</td><td>9.60</td><td>99.99</td><td>8.83</td></tr>
    </table>
    <table>
      <caption>1314 中石化 每日成交行情、法人買賣及融資券詳細資料</caption>
      <tr>
        <th>交易日期</th><th>開盤</th><th>最高</th><th>最低</th><th>收盤</th>
        <th>漲跌</th><th>漲跌 (%)</th><th>振幅 (%)</th><th>成交資料</th>
      </tr>
      <tr><th>張數</th><th>筆數</th><th>均張</th><th>億元</th></tr>
      <tr>
        <td>'26/07/09</td><td>9.6</td><td>9.61</td><td>8.83</td><td>8.9</td>
        <td>-0.8</td><td>-8.25</td><td>8.04</td><td>155,533</td><td>37,958</td>
        <td>4.1</td><td>14.1</td>
      </tr>
    </table>
  </body>
</html>
"""


def goodinfo_html_for(symbol: str, name: str, date: str, close: str, volume_lots: str) -> str:
    roc_date = f"{int(date[:4]) - 2000}/{date[5:7]}/{date[8:10]}"
    return f"""
    <html>
      <head><title>Goodinfo!台灣股市資訊網 - {symbol} {name}</title></head>
      <body>
        <table>
          <caption>每日成交行情</caption>
          <tr>
            <th>日期</th><th>開盤</th><th>最高</th><th>最低</th><th>收盤</th>
            <th>昨收</th><th>漲跌</th><th>漲跌幅</th><th>成交張數</th>
          </tr>
          <tr>
            <td>{roc_date}</td><td>10.00</td><td>10.50</td><td>9.90</td><td>{close}</td>
            <td>10.00</td><td>+0.05</td><td>+0.50%</td><td>{volume_lots}</td>
          </tr>
        </table>
      </body>
    </html>
    """


class MarketDataFetcherTests(unittest.TestCase):
    def test_goodinfo_fetch_follows_reinit_page_before_parsing(self) -> None:
        init_html = """
        <html><body></body><script>
          arr[0] = '4.7'; arr[1] = '39142.8'; arr[2] = '46920.6';
          window.location.replace('ShowK_Chart.asp?STOCK_ID=1314&CHT_CAT=DATE&REINIT=123');
        </script></html>
        """
        responses = [
            Mock(read=Mock(return_value=init_html.encode("utf-8")), headers=Mock(get_content_charset=Mock(return_value="utf-8"))),
            Mock(read=Mock(return_value=GOODINFO_HTML.encode("utf-8")), headers=Mock(get_content_charset=Mock(return_value="utf-8"))),
        ]
        for response in responses:
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=None)

        with patch("market_data_fetcher.urlopen", side_effect=responses):
            record = fetch_goodinfo_record("1314", "2026-07-09")

        self.assertEqual(record.symbol, "1314")
        self.assertEqual(record.close_price, 10.05)

    def test_goodinfo_parser_handles_real_two_row_detail_header(self) -> None:
        record = parse_goodinfo_daily_table(GOODINFO_REALISTIC_DETAIL_HTML, "1314", "2026-07-09")

        self.assertEqual(record.trade_date, "2026-07-09")
        self.assertEqual(record.open_price, 9.6)
        self.assertEqual(record.high_price, 9.61)
        self.assertEqual(record.low_price, 8.83)
        self.assertEqual(record.close_price, 8.9)
        self.assertEqual(record.previous_close, 9.7)
        self.assertEqual(record.change, -0.8)
        self.assertEqual(record.change_percent, -8.25)
        self.assertEqual(record.volume, 155_533)

    def test_goodinfo_parser_ignores_summary_tables_before_daily_detail(self) -> None:
        record = parse_goodinfo_daily_table(GOODINFO_WITH_SUMMARY_BEFORE_DAILY_HTML, "1314", "2026-07-09")

        self.assertEqual(record.close_price, 8.9)
        self.assertEqual(record.high_price, 9.61)
        self.assertEqual(record.volume, 155_533)

    def test_goodinfo_parser_uses_requested_date_not_summary_or_latest_row(self) -> None:
        record = parse_goodinfo_daily_table(GOODINFO_HTML, "1314", "2026-07-09")

        self.assertEqual(record.symbol, "1314")
        self.assertEqual(record.name, "中石化")
        self.assertEqual(record.trade_date, "2026-07-09")
        self.assertEqual(record.close_price, 10.05)
        self.assertEqual(record.high_price, 10.70)
        self.assertEqual(record.volume, 8_765)

    def test_goodinfo_parser_rejects_other_stock_data(self) -> None:
        html = goodinfo_html_for("1216", "統一", "2026-07-09", "80.10", "1,000")

        with self.assertRaises(ValueError):
            parse_goodinfo_daily_table(html, "1314", "2026-07-09")

    def test_validation_failure_suppresses_prices(self) -> None:
        goodinfo = MarketDataRecord(
            symbol="1314",
            name="中石化",
            trade_date="2026-07-09",
            open_price=10.00,
            high_price=10.70,
            low_price=9.95,
            close_price=10.05,
            previous_close=10.10,
            change=-0.05,
            change_percent=-0.50,
            volume=8_765,
        )
        official = OfficialRecord(
            source="TWSE",
            symbol="1314",
            trade_date="2026-07-09",
            close_price=10.10,
            volume=8_765,
        )

        validation = validate_market_data(goodinfo, official)
        report = build_report(goodinfo, official, validation, datetime(2026, 7, 10, 9, 30, 0))

        self.assertFalse(validation.is_valid)
        self.assertIn("資料驗證失敗", validation.status)
        self.assertNotIn("goodinfo_raw", report)
        self.assertNotIn("official_raw", report)
        self.assertEqual(report["validation_status"], "資料驗證失敗")

    def test_six_target_symbols_validate_against_official_records(self) -> None:
        cases = [
            ("2002", "中鋼", "22.80", "12,000"),
            ("6214", "精誠", "143.50", "2,100"),
            ("6753", "龍德造船", "148.00", "950"),
            ("1314", "中石化", "10.05", "8,765"),
            ("1216", "統一", "80.10", "3,333"),
            ("2327", "國巨", "620.00", "1,234"),
        ]

        for symbol, name, close, volume_lots in cases:
            with self.subTest(symbol=symbol):
                goodinfo = parse_goodinfo_daily_table(
                    goodinfo_html_for(symbol, name, "2026-07-09", close, volume_lots),
                    symbol,
                    "2026-07-09",
                )
                official = OfficialRecord(
                    source="TWSE",
                    symbol=symbol,
                    trade_date="2026-07-09",
                    close_price=float(close),
                    volume=int(volume_lots.replace(",", "")),
                )

                validation = validate_market_data(goodinfo, official)

                self.assertTrue(validation.is_valid)
                self.assertEqual(validation.status, "驗證成功")

    def test_official_share_volume_is_rounded_to_lots_for_goodinfo_comparison(self) -> None:
        record = parse_official_table(
            "TWSE",
            "2002",
            "2026-07-09",
            ["日期", "成交股數", "收盤價"],
            [["115/07/09", "25,520,693", "18.55"]],
        )

        self.assertEqual(record.volume, 25_521)

    def test_save_report_does_not_overwrite_history(self) -> None:
        report = {"symbol": "2002", "trade_date": "2026-07-09", "validation_status": "驗證成功"}

        with tempfile.TemporaryDirectory() as temp_dir:
            first = save_report(report, Path(temp_dir))
            second = save_report(report, Path(temp_dir))

            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertEqual(json.loads(first.read_text(encoding="utf-8"))["symbol"], "2002")


if __name__ == "__main__":
    unittest.main()
