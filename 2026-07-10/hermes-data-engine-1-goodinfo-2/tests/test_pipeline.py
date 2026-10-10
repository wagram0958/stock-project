from hermes_data_engine.models import DATA_FIELDS, Observation, build_document
from hermes_data_engine.pipeline import HermesPipeline, resolve_field


NOW = "2026-07-10T09:00:00+00:00"
DAY = "2026-07-10"


class FakeProvider:
    def __init__(self, values=None, error=None):
        self.values = values or {}
        self.error = error

    def fetch(self, *args):
        if self.error:
            raise self.error
        return self.values


def obs(value, source, status="unverified", as_of=DAY, period=None):
    return Observation(value, source, as_of, NOW, status, period)


def run(good=None, official=None, mops=None, yahoo=None, previous=None):
    return HermesPipeline(
        FakeProvider(good), FakeProvider(official), FakeProvider(mops),
        FakeProvider(yahoo), clock=lambda: NOW,
    ).run("3033", DAY, previous)


def test_verifies_matches_and_uses_official_mismatch():
    document = run(
        {"price": obs(10, "Goodinfo"), "volume": obs(1000, "Goodinfo")},
        {"price": obs(10, "TWSE"), "volume": obs(1200, "TWSE")},
    )
    assert document["price"] == 10
    assert document["sources"]["price"]["source"] == "Goodinfo"
    assert document["sources"]["price"]["status"] == "verified"
    assert document["volume"] == 1200
    assert document["sources"]["volume"]["status"] == "mismatch"
    assert document["quality"]["issues"][0]["field"] == "volume"


def test_structured_mismatch_reports_member_differences():
    document = run(
        {"margin": obs({"balance": 1000, "change": 100}, "Goodinfo")},
        {"margin": obs({"balance": 1200, "change": -50}, "TWSE")},
    )

    assert document["quality"]["issues"][0]["difference"] == {
        "balance": 200,
        "change": -150,
    }


def test_resolve_field_returns_value_provenance_and_issues():
    value, provenance, issues = resolve_field(
        "price",
        obs(10, "Goodinfo"),
        obs(10, "TWSE"),
        None,
        None,
    )
    assert value == 10
    assert provenance["source"] == "Goodinfo"
    assert provenance["status"] == "verified"
    assert issues == []


def test_uses_per_field_fallbacks_and_yahoo_allowlist():
    document = run(
        official={"margin": obs({"balance": 1, "change": 1}, "TWSE")},
        yahoo={"price": obs(9, "Yahoo(Fallback)"), "foreign": obs(999, "Yahoo(Fallback)")},
    )
    assert document["margin"]["balance"] == 1
    assert document["sources"]["margin"]["status"] == "fallback"
    assert document["price"] == 9
    assert document["sources"]["price"]["source"] == "Yahoo(Fallback)"
    assert document["foreign"] is None


def test_preserves_mops_periods_and_stale_previous_values():
    previous_observations = {field: obs(1, "TWSE", "verified", "2026-07-09") for field in DATA_FIELDS}
    previous_observations["date"] = obs("2026-07-09", "TWSE", "verified", "2026-07-09")
    previous = build_document("3033", previous_observations, NOW)
    document = run(
        mops={
            "revenue": obs(500, "MOPS", as_of="2026-07-08", period="2026-06"),
            "eps": obs(2.5, "MOPS", as_of="2026-05-15", period="2026-Q1"),
            "cashflow": obs(700, "MOPS", as_of="2026-05-15", period="2026-Q1"),
        },
        previous=previous,
    )
    assert document["revenue"] == 500
    assert document["sources"]["revenue"]["period"] == "2026-06"
    assert document["sources"]["eps"]["as_of"] == "2026-05-15"
    assert document["price"] == 1
    assert document["sources"]["price"]["status"] == "stale"
    assert document["date"] == "2026-07-09"


def test_captures_provider_errors_without_query_secrets():
    pipeline = HermesPipeline(
        FakeProvider(
            error=RuntimeError(
                "failed https://x.test/a?token=secret Authorization: Bearer abc Cookie: sid=123"
            )
        ),
        FakeProvider(), FakeProvider(), FakeProvider(), clock=lambda: NOW,
    )
    document = pipeline.run("3033", DAY)
    assert document["price"] is None
    assert document["sources"]["price"]["status"] == "unavailable"
    assert "secret" not in str(document["errors"])
    assert "Bearer abc" not in str(document["errors"])
    assert "sid=123" not in str(document["errors"])


def test_reports_provider_progress_and_continues_after_failure():
    events = []
    pipeline = HermesPipeline(
        FakeProvider(error=TimeoutError("Goodinfo timed out")),
        FakeProvider({"price": obs(9, "TWSE")}),
        FakeProvider(),
        FakeProvider(),
        clock=lambda: NOW,
        reporter=events.append,
    )

    document = pipeline.run("3033", DAY)

    assert document["price"] == 9
    assert document["sources"]["price"]["source"] == "TWSE"
    assert any("Goodinfo start" in event for event in events)
    assert any("Goodinfo failed" in event for event in events)
    assert any("TWSE start" in event for event in events)
    assert any("TWSE done" in event for event in events)
