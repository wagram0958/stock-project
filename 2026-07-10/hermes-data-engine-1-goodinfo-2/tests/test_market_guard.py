"""Offline, network-free end-to-end tests of guarded Hermes CLI execution."""

import json
from datetime import date
from pathlib import Path

from hermes_data_engine.cli import main
from hermes_data_engine.models import DATA_FIELDS, Observation, build_document


def official_calendar():
    dates = [
        ("1150101", "中華民國開國紀念日", "放假"),
        ("1150102", "國曆新年開始交易日", "開始交易"),
        ("1150211", "農曆春節前最後交易日", "最後交易"),
        ("1150212", "市場無交易，僅辦理結算交割作業", ""),
        ("1150213", "市場無交易，僅辦理結算交割作業", ""),
        ("1150216", "春節", "放假"),
        ("1150219", "春節", "放假"),
        ("1150220", "春節", "補假"),
        ("1150223", "農曆春節後開始交易日", "開始交易"),
        ("1150928", "教師節", "放假"),
        ("1151009", "國慶日", "補假"),
        ("1151026", "臺灣光復日", "補假"),
        ("1151225", "行憲紀念日", "放假"),
    ]
    return json.dumps([{"Date": value, "Name": name, "Description": description}
                       for value, name, description in dates])


class ReadyPipeline:
    def __init__(self, price=45.5):
        self.calls = []
        self.price = price

    def run(self, symbol, requested_date, previous=None):
        self.calls.append((symbol, requested_date))
        stamp = requested_date + "T16:00:00+08:00"
        values = {field: 1 for field in DATA_FIELDS}
        values.update(date=requested_date, price=self.price, volume=100000)
        observations = {
            field: Observation(
                value, "TWSE", requested_date, stamp,
                "unavailable" if value is None else "verified",
            ) for field, value in values.items()
        }
        return build_document(symbol, observations, stamp)


def run_guard(monkeypatch, tmp_path, pipeline, chosen="2026-10-08"):
    monkeypatch.setattr(
        "hermes_data_engine.cli.fetch_text",
        lambda url, *, timeout, attempts: official_calendar()
    )
    return main(
        ["run", "--market-guard", "--date", chosen,
         "--output-dir", str(tmp_path), "--symbols", "3033"],
        pipeline_factory=lambda **kwargs: pipeline,
    )


def test_holiday_does_not_call_providers_or_overwrite(monkeypatch, tmp_path, capsys):
    p = tmp_path / "3033.json"
    p.write_text("PRESERVE_ORIGINAL", encoding="utf-8")
    pipeline = ReadyPipeline()
    result = run_guard(monkeypatch, tmp_path, pipeline, "2026-10-09")
    assert result == 0
    assert pipeline.calls == []
    assert p.read_text() == "PRESERVE_ORIGINAL"
    assert "MARKET_CLOSED_NO_WRITE" in capsys.readouterr().out


def test_open_market_and_ready_data_writes_approved_snapshot(monkeypatch, tmp_path):
    pipeline = ReadyPipeline()
    result = run_guard(monkeypatch, tmp_path, pipeline)
    assert result == 0
    assert pipeline.calls == [("3033", "2026-10-08")]
    assert json.loads((tmp_path / "3033.json").read_text())["price"] == 45.5


def test_bad_market_data_cannot_overwrite_previous_snapshot(monkeypatch, tmp_path):
    path = tmp_path / "3033.json"
    original = ReadyPipeline().run("3033", "2026-10-07")
    original_bytes = json.dumps(original, ensure_ascii=False).encode("utf-8")
    path.write_bytes(original_bytes)
    pipeline = ReadyPipeline(price=None)
    assert run_guard(monkeypatch, tmp_path, pipeline) == 1
    assert pipeline.calls == [("3033", "2026-10-08")]
    assert path.read_bytes() == original_bytes


def test_unusable_new_market_document_is_not_written(monkeypatch, tmp_path):
    pipeline = ReadyPipeline(price=None)
    assert run_guard(monkeypatch, tmp_path, pipeline) == 1
    assert not (tmp_path / "3033.json").exists()


def test_calendar_outage_fails_before_provider_or_write(monkeypatch, tmp_path):
    def unavailable(url, *, timeout, attempts):
        raise RuntimeError("official calendar API unavailable")
    monkeypatch.setattr("hermes_data_engine.cli.fetch_text", unavailable)
    pipeline = ReadyPipeline()
    result = main(
        ["run", "--market-guard", "--date", "2026-10-08",
         "--output-dir", str(tmp_path), "--symbols", "3033"],
        pipeline_factory=lambda **kwargs: pipeline,
    )
    assert result == 1
    assert pipeline.calls == []
    assert list(tmp_path.iterdir()) == []


def test_calendar_year_mismatch_blocks_before_any_write(monkeypatch, tmp_path):
    pipeline = ReadyPipeline()
    assert run_guard(monkeypatch, tmp_path, pipeline, "2027-10-08") == 1
    assert pipeline.calls == []
