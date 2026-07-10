"""Field-level provider precedence and stale recovery orchestration."""

from __future__ import annotations

import re
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from hermes_data_engine.models import DATA_FIELDS, Observation, build_document


YAHOO_FIELDS = frozenset({"price", "volume", "pe", "pb"})
MOPS_FIELDS = frozenset({"revenue", "eps", "cashflow"})


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _clean_error(message: str) -> str:
    redacted = re.sub(r"\?[^)\]\s]+", "?<redacted>", message)
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*)(bearer\s+)?[^\s,;\]\)]+",
        r"\1<redacted>",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(cookie\s*:\s*)[^\]\)]+",
        r"\1<redacted>",
        redacted,
    )
    return redacted


def _copy_observation(observation: Observation, *, status: str) -> Observation:
    return Observation(
        observation.value,
        observation.source,
        observation.as_of,
        observation.fetched_at,
        status,
        observation.period,
    )


def _provenance(observation: Observation) -> dict[str, Any]:
    provenance = {
        "source": observation.source,
        "as_of": observation.as_of,
        "fetched_at": observation.fetched_at,
        "status": observation.status,
    }
    if observation.period is not None:
        provenance["period"] = observation.period
    return provenance


def _from_value_and_provenance(value: Any, provenance: Mapping[str, Any]) -> Observation:
    return Observation(
        value,
        str(provenance["source"]),
        str(provenance["as_of"]),
        str(provenance["fetched_at"]),
        str(provenance["status"]),
        str(provenance["period"]) if provenance.get("period") is not None else None,
    )


def _previous_observation(
    field: str, previous: Mapping[str, Any] | None, fetched_at: str
) -> Observation | None:
    if not previous or field not in previous:
        return None
    sources = previous.get("sources")
    if not isinstance(sources, Mapping) or field not in sources:
        return None
    provenance = sources[field]
    if not isinstance(provenance, Mapping):
        return None
    source = provenance.get("source")
    as_of = provenance.get("as_of")
    if not isinstance(source, str) or not isinstance(as_of, str):
        return None
    return Observation(
        previous[field],
        source,
        as_of,
        fetched_at,
        "stale",
        provenance.get("period") if isinstance(provenance.get("period"), str) else None,
    )


def _unavailable(field: str, requested_date: str, fetched_at: str) -> Observation:
    del field
    return Observation(None, "Unavailable", requested_date, fetched_at, "unavailable")


def _difference(left: Any, right: Any) -> Any:
    if isinstance(left, (int, float, Decimal)) and isinstance(right, (int, float, Decimal)):
        return right - left
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        diff = {}
        for key in sorted(set(left) & set(right)):
            member_difference = _difference(left[key], right[key])
            if member_difference is not None:
                diff[key] = member_difference
        return diff or None
    return None


def resolve_field(
    field: str,
    goodinfo: Observation | None,
    official: Observation | None,
    yahoo: Observation | None,
    previous: Observation | None,
) -> tuple[Any, dict[str, Any] | None, list[dict[str, Any]]]:
    """Resolve a market field using Goodinfo, TWSE, Yahoo, then previous data."""
    issues: list[dict[str, Any]] = []
    good_value = goodinfo.value if goodinfo and goodinfo.status != "unavailable" else None
    official_value = (
        official.value if official and official.status != "unavailable" else None
    )

    if goodinfo and good_value is not None and official and official_value is not None:
        if good_value == official_value:
            resolved = _copy_observation(goodinfo, status="verified")
            return resolved.value, _provenance(resolved), issues
        issues.append(
            {
                "field": field,
                "goodinfo": good_value,
                "official": official_value,
                "difference": _difference(good_value, official_value),
            }
        )
        resolved = _copy_observation(official, status="mismatch")
        return resolved.value, _provenance(resolved), issues

    if goodinfo and good_value is not None:
        resolved = _copy_observation(goodinfo, status=goodinfo.status)
        return resolved.value, _provenance(resolved), issues
    if official and official_value is not None:
        resolved = _copy_observation(official, status="fallback")
        return resolved.value, _provenance(resolved), issues
    if (
        field in YAHOO_FIELDS
        and yahoo
        and yahoo.status != "unavailable"
        and yahoo.value is not None
    ):
        resolved = _copy_observation(yahoo, status="fallback")
        return resolved.value, _provenance(resolved), issues
    if previous is not None:
        return previous.value, _provenance(previous), issues
    return None, None, issues


class HermesPipeline:
    """Run all providers and produce one canonical Hermes data document."""

    def __init__(self, goodinfo, official, mops, yahoo, clock=None, reporter=None):
        self.goodinfo = goodinfo
        self.official = official
        self.mops = mops
        self.yahoo = yahoo
        self.clock = clock or _now
        self.reporter = reporter or (lambda message: print(message, file=sys.stderr, flush=True))

    def _safe_fetch(self, name: str, provider, *args) -> tuple[dict[str, Observation], dict | None]:
        self.reporter(f"{name} start")
        try:
            values = provider.fetch(*args)
        except Exception as exc:  # noqa: BLE001 - providers must not abort the batch.
            self.reporter(f"{name} failed: {_clean_error(str(exc))}")
            return {}, {"provider": name, "error": _clean_error(str(exc))}
        if not isinstance(values, dict):
            self.reporter(f"{name} failed: provider returned non-object data")
            return {}, {"provider": name, "error": "provider returned non-object data"}
        self.reporter(f"{name} done")
        return values, None

    def run(
        self, symbol: str, requested_date: str, previous: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        generated_at = self.clock()
        goodinfo, goodinfo_error = self._safe_fetch(
            "Goodinfo", self.goodinfo, symbol, requested_date
        )
        official, official_error = self._safe_fetch(
            "TWSE", self.official, symbol, requested_date
        )
        mops, mops_error = self._safe_fetch("MOPS", self.mops, symbol)
        yahoo, yahoo_error = self._safe_fetch("Yahoo(Fallback)", self.yahoo, symbol, requested_date)

        observations: dict[str, Observation] = {}
        issues: list[dict[str, Any]] = []
        for field in DATA_FIELDS:
            previous_field = _previous_observation(field, previous, generated_at)
            if field in MOPS_FIELDS:
                mops_observation = mops.get(field)
                if (
                    mops_observation
                    and mops_observation.status != "unavailable"
                    and mops_observation.value is not None
                ):
                    observations[field] = mops_observation
                elif previous_field is not None:
                    observations[field] = previous_field
                else:
                    observations[field] = _unavailable(field, requested_date, generated_at)
                continue

            value, provenance, field_issues = resolve_field(
                field,
                goodinfo.get(field),
                official.get(field),
                yahoo.get(field),
                previous_field,
            )
            issues.extend(field_issues)
            observations[field] = (
                _from_value_and_provenance(value, provenance)
                if provenance is not None
                else _unavailable(field, requested_date, generated_at)
            )

        document = build_document(symbol, observations, generated_at)
        document["quality"]["issues"].extend(issues)
        if issues:
            document["quality"]["status"] = "mismatch"
        document["errors"].extend(
            error
            for error in (goodinfo_error, official_error, mops_error, yahoo_error)
            if error is not None
        )
        return document
