from hermes_data_engine.normalize import (
    lots_to_shares,
    normalize_number,
    normalize_roc_date,
)


def test_normalizes_taiwan_market_values():
    assert normalize_number("-1,234") == -1234
    assert normalize_number("--") is None
    assert lots_to_shares("1,234") == 1_234_000
    assert normalize_roc_date("115/07/10") == "2026-07-10"
