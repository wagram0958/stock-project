"""Small, guarded HTTP boundary shared by data providers."""

from time import sleep
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


USER_AGENT = "HermesDataEngine/1.0 (daily Taiwan market data; respectful bounded client)"


def _redacted_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        [(key, "REDACTED") for key, _ in parse_qsl(parts.query, keep_blank_values=True)]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def fetch_text(
    url: str,
    transport: Callable | None = None,
    attempts: int = 3,
    timeout: int = 20,
) -> str:
    """Fetch UTF-8 text, retrying only rate-limit and server HTTP failures."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    opener = transport or urlopen
    request = Request(url, headers={"User-Agent": USER_AGENT})
    failed_status: int | None = None
    for attempt in range(1, attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            transient = exc.code == 429 or 500 <= exc.code <= 599
            if transient and attempt < attempts:
                sleep(0.1 * (2 ** (attempt - 1)))
                continue
            failed_status = exc.code
            break
    if failed_status is not None:
        safe_url = _redacted_url(url)
        raise RuntimeError(f"HTTP {failed_status} fetching {safe_url}") from None
    raise AssertionError("unreachable")
