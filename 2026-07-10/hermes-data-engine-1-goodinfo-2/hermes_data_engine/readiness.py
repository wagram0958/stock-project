"""Fail-closed *market-data* readiness, separate from JSON schema validation.

A schema-valid document may contain only unavailable or stale observations.
An independent caller must confirm the trading session and retain the
authoritative calendar/result reference. This module does NOT verify that
reference or fetch live data. Until independently verified, readiness is false.
"""

from __future__ import annotations

from datetime import date, datetime, time
from math import isfinite
from numbers import Real
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from hermes_data_engine.models import validate_document


_TAIPEI = ZoneInfo("Asia/Taipei")
_REQUIRED = ("date", "price", "volume")
_CLOSE = time(13, 30)


def _session_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if value == parsed.isoformat() else None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None and stamp.utcoffset() is not None else None


def assess_market_readiness(
    document: Mapping[str, Any],
    expected_trading_date: str,
    *,
    session_confirmed: bool = False,
    session_source: str | None = None,
) -> dict[str, Any]:
    """Return a diagnostic; never treat a schema PASS as a data-ready PASS.

    The caller's confirmation must come from independently checked official
    trading-session evidence. A source label alone is not authentication.
    """
    issues: list[str] = []
    result: dict[str, Any] = {
        "symbol": document.get("symbol") if isinstance(document, Mapping) else None,
        "expected_trading_date": expected_trading_date,
        "ready": False,
        "issues": issues,
        "session_source": session_source,
    }

    try:
        validate_document(document)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        issues.append(f"invalid_schema: {exc}")
        return result

    target = _session_date(expected_trading_date)
    if target is None:
        issues.append("invalid_expected_trading_date")
        return result

    if session_confirmed is not True or not isinstance(session_source, str) or not session_source.strip():
        issues.append("official_trading_session_not_independently_confirmed")

    if document.get("quality", {}).get("status") in {"mismatch", "stale"}:
        issues.append("document_quality_conflict_or_stale")

    generated = _timestamp(document.get("generated_at"))
    if generated is None or generated.astimezone(_TAIPEI).date() < target:
        issues.append("generation_timestamp_not_current")

    if document.get("date") != expected_trading_date:
        issues.append("trading_date_missing_or_mismatch")

    price = document.get("price")
    if (isinstance(price, bool) or not isinstance(price, (Real, Decimal))
            or not isfinite(float(price)) or price <= 0):
        issues.append("price_missing_or_invalid")

    volume = document.get("volume")
    if (isinstance(volume, bool) or not isinstance(volume, (Real, Decimal))
            or not isfinite(float(volume)) or volume < 0 or volume != int(volume)):
        issues.append("volume_missing_or_invalid")

    sources = document["sources"]
    for field in _REQUIRED:
        provenance = sources[field]
        if provenance["as_of"] != expected_trading_date:
            issues.append(f"{field}_provenance_date_mismatch")

        provider, status = provenance["source"], provenance["status"]
        accepted = (
            (provider == "TWSE" and status in {"verified", "fallback"})
            or (provider == "Goodinfo" and status == "verified")
        )
        if not accepted:
            issues.append(f"{field}_source_not_official_or_cross_verified")

        fetched = _timestamp(provenance["fetched_at"])
        if fetched is None:
            issues.append(f"{field}_fetch_timestamp_invalid")
        else:
            local = fetched.astimezone(_TAIPEI)
            if local.date() < target or (local.date() == target and local.time() < _CLOSE):
                issues.append(f"{field}_fetched_before_session_closed")

    result["ready"] = not issues
    return result
