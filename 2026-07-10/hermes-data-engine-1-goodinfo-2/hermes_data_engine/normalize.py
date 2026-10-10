"""Normalization helpers for Taiwan market data."""

from datetime import date
from decimal import Decimal, InvalidOperation


NULL_MARKERS = frozenset({"", "-", "--", "---", "N/A", "NA", "null", "None"})


def normalize_number(value: object) -> int | Decimal | None:
    """Parse a market number without introducing binary floating-point error."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a market number")
    text = str(value).strip()
    if text in NULL_MARKERS:
        return None
    text = text.replace(",", "").replace("％", "%")
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"invalid market number: {value!r}") from exc
    return int(parsed) if parsed == parsed.to_integral_value() else parsed


def lots_to_shares(value: object) -> int | Decimal | None:
    """Convert Taiwan exchange lots to shares."""
    lots = normalize_number(value)
    return None if lots is None else lots * 1_000


def normalize_roc_date(value: object) -> str | None:
    """Convert an ROC or Gregorian slash-separated date to ISO format."""
    if value is None:
        return None
    text = str(value).strip()
    if text in NULL_MARKERS:
        return None
    parts = text.replace("-", "/").split("/")
    if len(parts) != 3:
        raise ValueError(f"invalid date: {value!r}")
    try:
        year, month, day = (int(part) for part in parts)
        if year < 1911:
            year += 1911
        return date(year, month, day).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid date: {value!r}") from exc
