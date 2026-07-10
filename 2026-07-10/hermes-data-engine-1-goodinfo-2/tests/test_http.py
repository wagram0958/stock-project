from urllib.error import HTTPError

import pytest

from hermes_data_engine.http import fetch_text


class Response:
    def __init__(self, text="ok"):
        self.text = text

    def read(self):
        return self.text.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_fetch_text_sets_descriptive_user_agent():
    requests = []

    def transport(request, timeout):
        requests.append((request, timeout))
        return Response()

    assert fetch_text("https://example.test/data", transport=transport) == "ok"
    assert "HermesDataEngine" in requests[0][0].get_header("User-agent")
    assert requests[0][1] == 20


def test_fetch_text_retries_transient_http_status_only():
    calls = 0

    def transport(request, timeout):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        return Response("recovered")

    assert fetch_text("https://example.test/data", transport=transport) == "recovered"
    assert calls == 3


def test_fetch_text_does_not_retry_permanent_http_status_and_redacts_query_values():
    calls = 0

    def transport(request, timeout):
        nonlocal calls
        calls += 1
        raise HTTPError(request.full_url, 403, "forbidden", {}, None)

    with pytest.raises(RuntimeError) as error:
        fetch_text(
            "https://example.test/data?symbol=1314&token=very-secret",
            transport=transport,
        )
    assert calls == 1
    assert "symbol=REDACTED" in str(error.value)
    assert "token=REDACTED" in str(error.value)
    assert "1314" not in str(error.value)
    assert "very-secret" not in str(error.value)
    assert error.value.__cause__ is None
    chain = []
    current = error.value
    while current is not None:
        chain.append(str(current))
        current = current.__cause__ or current.__context__
    assert "very-secret" not in " ".join(chain)
