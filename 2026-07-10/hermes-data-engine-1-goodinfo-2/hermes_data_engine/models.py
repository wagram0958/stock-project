"""Canonical observations and JSON-ready Hermes documents."""

from dataclasses import dataclass
from typing import Any, Mapping


DATA_FIELDS = (
    "price",
    "volume",
    "margin",
    "short",
    "daytrade",
    "foreign",
    "investment",
    "dealer",
    "revenue",
    "eps",
    "cashflow",
    "pb",
    "pe",
    "date",
)

REQUIRED_FIELDS = (
    "schema_version",
    "symbol",
    "market",
    "currency",
    "generated_at",
    *DATA_FIELDS,
    "sources",
    "quality",
    "errors",
)

OBSERVATION_STATUSES = frozenset(
    {"verified", "mismatch", "fallback", "stale", "unavailable"}
)
QUALITY_STATUSES = frozenset({"complete", "partial", "mismatch", "stale"})


@dataclass(frozen=True)
class Observation:
    """A value together with the provenance needed to assess it."""

    value: Any
    source: str
    as_of: str
    fetched_at: str
    status: str
    period: str | None = None


def _quality_status(observations: Mapping[str, Observation]) -> str:
    statuses = {observation.status for observation in observations.values()}
    if "mismatch" in statuses:
        return "mismatch"
    if "stale" in statuses:
        return "stale"
    if statuses - {"verified"}:
        return "partial"
    return "complete"


def build_document(
    symbol: str, observations: Mapping[str, Observation], generated_at: str
) -> dict[str, Any]:
    """Build the canonical JSON-ready document from field observations."""
    missing = [field for field in DATA_FIELDS if field not in observations]
    if missing:
        raise ValueError(f"missing observations: {', '.join(missing)}")

    document: dict[str, Any] = {
        "schema_version": "1.0",
        "symbol": symbol,
        "market": "TWSE",
        "currency": "TWD",
        "generated_at": generated_at,
        "sources": {},
        "quality": {"status": _quality_status(observations), "issues": []},
        "errors": [],
    }
    for field in DATA_FIELDS:
        observation = observations[field]
        document[field] = observation.value
        provenance = {
            "source": observation.source,
            "as_of": observation.as_of,
            "fetched_at": observation.fetched_at,
            "status": observation.status,
        }
        if observation.period is not None:
            provenance["period"] = observation.period
        document["sources"][field] = provenance

    if document["eps"] is not None and document["eps"] <= 0:
        document["pe"] = None
    return document


def validate_document(document: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` when a canonical document violates its schema."""
    for field in REQUIRED_FIELDS:
        if field not in document:
            raise ValueError(f"missing required field: {field}")

    sources = document["sources"]
    if not isinstance(sources, Mapping):
        raise ValueError("sources must be an object")
    for field in DATA_FIELDS:
        if field not in sources:
            raise ValueError(f"missing sources.{field}")
        provenance = sources[field]
        if not isinstance(provenance, Mapping):
            raise ValueError(f"sources.{field} must be an object")
        for key in ("source", "as_of", "fetched_at", "status"):
            if key not in provenance:
                raise ValueError(f"missing sources.{field}.{key}")
        if provenance["status"] not in OBSERVATION_STATUSES:
            raise ValueError(f"invalid sources.{field}.status")

    quality = document["quality"]
    if not isinstance(quality, Mapping):
        raise ValueError("quality must be an object")
    if quality.get("status") not in QUALITY_STATUSES:
        raise ValueError("invalid quality.status")
    if not isinstance(quality.get("issues"), list):
        raise ValueError("quality.issues must be a list")
    if not isinstance(document["errors"], list):
        raise ValueError("errors must be a list")
