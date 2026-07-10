from dataclasses import FrozenInstanceError

import pytest

from hermes_data_engine.models import (
    REQUIRED_FIELDS,
    Observation,
    build_document,
    validate_document,
)


def sample_observations():
    fetched_at = "2026-07-10T08:00:00Z"
    values = {
        "price": 42.5,
        "volume": 1_000_000,
        "margin": {"balance": 100_000, "change": -1_000},
        "short": {"balance": 10_000, "change": 100, "ratio": 10},
        "daytrade": {"ratio": 12.5, "volume": 100},
        "foreign": 5_000,
        "investment": -2_000,
        "dealer": 300,
        "revenue": 123_000_000,
        "eps": -0.25,
        "cashflow": 9_000_000,
        "pb": 1.5,
        "pe": 12.0,
        "date": "2026-07-10",
    }
    return {
        field: Observation(
            value=value,
            source="TWSE" if field not in {"revenue", "eps", "cashflow"} else "MOPS",
            as_of="2026-07-10",
            fetched_at=fetched_at,
            status="verified",
            period="2026-Q1" if field in {"eps", "cashflow"} else None,
        )
        for field, value in values.items()
    }


def test_document_has_required_fields_and_provenance():
    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )

    assert set(REQUIRED_FIELDS) <= document.keys()
    assert document["pe"] is None
    assert document["sources"]["pe"]["status"] == "unavailable"
    assert document["sources"]["price"] == {
        "source": "TWSE",
        "as_of": "2026-07-10",
        "fetched_at": "2026-07-10T08:00:00Z",
        "status": "verified",
    }
    assert document["sources"]["eps"]["period"] == "2026-Q1"
    assert document["quality"] == {"status": "partial", "issues": []}
    validate_document(document)


def test_observation_is_immutable():
    observation = sample_observations()["price"]
    with pytest.raises(FrozenInstanceError):
        observation.status = "stale"


def test_quality_aggregates_worst_observation_status():
    observations = sample_observations()
    observations["volume"] = Observation(
        None, "TWSE", "2026-07-10", "2026-07-10T08:00:00Z", "unavailable"
    )
    document = build_document("3033", observations, "2026-07-10T09:00:00Z")
    assert document["quality"]["status"] == "partial"


def test_unverified_non_null_observation_is_valid_and_partial():
    observations = sample_observations()
    observations["price"] = Observation(
        42.5, "Goodinfo", "2026-07-10", "2026-07-10T08:00:00Z", "unverified"
    )
    document = build_document("3033", observations, "2026-07-10T09:00:00Z")

    assert document["quality"]["status"] == "partial"
    validate_document(document)


@pytest.mark.parametrize("status", ["mismatch", "stale"])
def test_negative_eps_preserves_worse_quality_status(status):
    observations = sample_observations()
    observations["volume"] = Observation(
        1_000_000, "TWSE", "2026-07-10", "2026-07-10T08:00:00Z", status
    )
    document = build_document("3033", observations, "2026-07-10T09:00:00Z")
    assert document["sources"]["pe"]["status"] == "unavailable"
    assert document["quality"]["status"] == status


def test_schema_rejects_missing_and_invalid_fields():
    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )
    del document["sources"]["price"]["as_of"]
    with pytest.raises(ValueError, match="as_of"):
        validate_document(document)

    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )
    document["quality"]["status"] = "excellent"
    with pytest.raises(ValueError, match="quality.status"):
        validate_document(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2.0"),
        ("symbol", ""),
        ("market", "NASDAQ"),
        ("currency", "USD"),
        ("generated_at", "yesterday"),
    ],
)
def test_schema_rejects_invalid_document_metadata(field, value):
    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )
    document[field] = value
    with pytest.raises(ValueError, match=field):
        validate_document(document)


@pytest.mark.parametrize("key", ["source", "as_of", "fetched_at"])
def test_schema_rejects_empty_or_invalid_provenance(key):
    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )
    document["sources"]["price"][key] = "" if key != "fetched_at" else "later"
    with pytest.raises(ValueError, match=key):
        validate_document(document)


@pytest.mark.parametrize(
    ("status", "value"),
    [
        ("unavailable", 42.5),
        ("verified", None),
        ("fallback", None),
        ("mismatch", None),
        ("stale", None),
        ("unverified", None),
    ],
)
def test_schema_rejects_value_status_inconsistency(status, value):
    document = build_document(
        "3033", sample_observations(), "2026-07-10T09:00:00Z"
    )
    document["price"] = value
    document["sources"]["price"]["status"] = status
    with pytest.raises(ValueError, match="sources.price.status"):
        validate_document(document)
