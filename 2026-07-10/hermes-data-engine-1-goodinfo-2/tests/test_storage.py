import json
import os

import pytest

from hermes_data_engine.models import DATA_FIELDS, Observation, build_document
from hermes_data_engine.storage import atomic_write, load_previous


NOW = "2026-07-10T09:00:00+00:00"


def document(symbol="3033"):
    observations = {
        field: Observation(1, "TWSE", "2026-07-10", NOW, "verified")
        for field in DATA_FIELDS
    }
    observations["date"] = Observation("2026-07-10", "TWSE", "2026-07-10", NOW, "verified")
    return build_document(symbol, observations, NOW)


def test_atomic_write_replaces_with_valid_document(tmp_path):
    path = tmp_path / "3033.json"

    atomic_write(path, document())

    assert load_previous(path)["symbol"] == "3033"
    assert json.loads(path.read_text(encoding="utf-8"))["price"] == 1


def test_atomic_write_preserves_existing_file_when_validation_fails(tmp_path):
    path = tmp_path / "3033.json"
    atomic_write(path, document())
    original = path.read_text(encoding="utf-8")
    invalid = document()
    del invalid["sources"]["price"]["as_of"]

    with pytest.raises(ValueError, match="as_of"):
        atomic_write(path, invalid)

    assert path.read_text(encoding="utf-8") == original


def test_atomic_write_preserves_existing_file_when_replace_fails(tmp_path, monkeypatch):
    path = tmp_path / "3033.json"
    atomic_write(path, document())
    original = path.read_text(encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk full"):
        atomic_write(path, document("6214"))

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp"))
