import json

from datetime import date

from hermes_data_engine.cli import DEFAULT_SYMBOLS, _configured_fetcher, effective_trading_date, main
from hermes_data_engine.models import DATA_FIELDS, Observation, build_document


NOW = "2026-07-10T09:00:00+00:00"


class FakePipeline:
    def __init__(self, failing_symbol=None):
        self.failing_symbol = failing_symbol
        self.calls = []

    def run(self, symbol, requested_date, previous=None):
        if symbol == self.failing_symbol:
            raise RuntimeError("provider failed")
        self.calls.append((symbol, requested_date, previous))
        observations = {
            field: Observation(1, "TWSE", requested_date, NOW, "verified")
            for field in DATA_FIELDS
        }
        observations["date"] = Observation(
            requested_date, "TWSE", requested_date, NOW, "verified"
        )
        return build_document(symbol, observations, NOW)


def test_run_writes_exact_default_symbol_files(tmp_path):
    pipeline = FakePipeline()

    result = main(
        ["run", "--date", "2026-07-10", "--output-dir", str(tmp_path)],
        pipeline_factory=lambda: pipeline,
    )

    assert result == 0
    assert sorted(path.name for path in tmp_path.glob("*.json")) == sorted(
        f"{symbol}.json" for symbol in DEFAULT_SYMBOLS
    )
    assert [call[0] for call in pipeline.calls] == list(DEFAULT_SYMBOLS)


def test_default_effective_trading_date_skips_weekends():
    assert effective_trading_date(date(2026, 7, 11)) == "2026-07-10"
    assert effective_trading_date(date(2026, 7, 12)) == "2026-07-10"
    assert effective_trading_date(date(2026, 7, 13)) == "2026-07-13"


def test_configured_fetcher_passes_timeout_and_attempts(monkeypatch):
    calls = []

    def fake_fetch_text(url, *, attempts, timeout):
        calls.append((url, attempts, timeout))
        return "ok"

    monkeypatch.setattr("hermes_data_engine.cli.fetch_text", fake_fetch_text)
    fetcher = _configured_fetcher(timeout=5, attempts=1)

    assert fetcher("https://example.test") == "ok"
    assert calls == [("https://example.test", 1, 5)]


def test_run_accepts_custom_symbol_subset(tmp_path):
    result = main(
        [
            "run",
            "--date",
            "2026-07-10",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "3033,6214",
        ],
        pipeline_factory=lambda: FakePipeline(),
    )

    assert result == 0
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "3033.json",
        "6214.json",
    ]


def test_run_returns_nonzero_when_a_symbol_fails(tmp_path):
    result = main(
        ["run", "--date", "2026-07-10", "--output-dir", str(tmp_path)],
        pipeline_factory=lambda: FakePipeline(failing_symbol="6214"),
    )

    assert result == 1
    assert (tmp_path / "3033.json").exists()
    assert not (tmp_path / "6214.json").exists()


def test_validate_accepts_json_document_paths(tmp_path):
    pipeline = FakePipeline()
    doc = pipeline.run("3033", "2026-07-10")
    path = tmp_path / "3033.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert main(["validate", str(path)]) == 0

    doc["quality"]["status"] = "wrong"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
