"""Read-only CLI readiness gate tests (no live provider calls)."""

import json

from hermes_data_engine.cli import main
from hermes_data_engine.models import DATA_FIELDS, Observation, build_document


DATE = "2026-07-10"
AFTER_CLOSE = "2026-07-10T16:30:00+08:00"


def sample():
    observations = {
        field: Observation(1, "TWSE", DATE, AFTER_CLOSE, "verified")
        for field in DATA_FIELDS
    }
    observations["date"] = Observation(DATE, "TWSE", DATE, AFTER_CLOSE, "verified")
    observations["price"] = Observation(42.5, "TWSE", DATE, AFTER_CLOSE, "verified")
    observations["volume"] = Observation(1000000, "TWSE", DATE, AFTER_CLOSE, "verified")
    return build_document("3033", observations, AFTER_CLOSE)


def invoke(path, *extra):
    return main([
        "readiness",
        "--expected-trading-date", DATE,
        *extra,
        str(path),
    ])


def test_readiness_requires_independently_confirmed_session(tmp_path, capsys):
    p = tmp_path / "3033.json"
    p.write_text(json.dumps(sample()), encoding="utf-8")
    assert invoke(p) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] is False
    assert "official_trading_session_not_independently_confirmed" in result["issues"]


def test_verified_core_document_is_accepted_with_explicit_attestation(tmp_path, capsys):
    p = tmp_path / "3033.json"
    p.write_text(json.dumps(sample()), encoding="utf-8")
    assert invoke(
        p, "--official-session-confirmed",
        "--official-session-source", "Test fixture independent session proof",
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] is True


def test_schema_valid_but_empty_market_data_is_rejected(tmp_path, capsys):
    doc = sample()
    for field in ("date", "price", "volume"):
        doc[field] = None
        doc["sources"][field]["status"] = "unavailable"
        doc["sources"][field]["source"] = "Unavailable"
    doc["quality"]["status"] = "partial"
    p = tmp_path / "3033.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    assert invoke(
        p, "--official-session-confirmed",
        "--official-session-source", "Synthetic CI fixture, NOT live evidence",
    ) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] is False
    assert "price_missing_or_invalid" in result["issues"]


def test_missing_file_fails_closed(tmp_path, capsys):
    assert invoke(tmp_path / "not-found.json") == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] is False
