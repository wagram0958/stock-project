## Task 5 Report: Pipeline Precedence, Mismatch, and Stale Recovery

Status: complete

RED evidence:
- `python -m pytest tests/test_pipeline.py -q` failed with `ModuleNotFoundError: No module named 'hermes_data_engine.pipeline'`.
- Added public contract coverage for `resolve_field(...) -> value, provenance, issues`; focused test failed with `ValueError: not enough values to unpack`.

GREEN evidence:
- `python -m pytest tests/test_pipeline.py -q`: 5 passed.
- `python -m pytest -q`: 61 passed.

Implemented:
- `HermesPipeline.run(symbol, requested_date, previous=None)`.
- `resolve_field(field, goodinfo, official, yahoo, previous)` returning value, provenance, and issues.
- Goodinfo/TWSE verification, TWSE mismatch selection, per-field fallback, Yahoo allowlist, MOPS period preservation, stale previous values, unavailable first-run values, and redacted provider errors.

Commit: deferred per user instruction to commit only after all remaining tests and integration checks pass.
