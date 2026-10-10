# Hermes Data Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a scheduled, tested Python pipeline that creates provenance-rich daily JSON for five Taiwan-listed stocks using Goodinfo, TWSE, MOPS, and Yahoo fallback data.

**Architecture:** Provider modules return canonical field observations; a pipeline validates Goodinfo against TWSE, applies per-field fallbacks, and merges last-known-good values. A CLI writes validated JSON atomically, while GitHub Actions tests, runs, validates, commits, and pushes daily output.

**Tech Stack:** Python 3.12, standard library HTTP/HTML/JSON utilities, pytest 8, GitHub Actions.

## Global Constraints

- Default symbols are exactly `3033`, `6214`, `6753`, `1314`, and `2002`.
- Output files are exactly `data/<symbol>.json` and contain every field required by the approved design.
- Fallback and provenance are per field; compatible TWSE fallback is labeled `TWSE`, and compatible Yahoo fallback is labeled `Yahoo(Fallback)`.
- Missing values are never converted to zero; last-known-good values become `stale`, and first-run missing values become `null`/`unavailable`.
- Yahoo supplies only price, volume, PE, and PB.
- Provider access controls, CAPTCHA, robots restrictions, and terms must not be bypassed.
- Tests are offline and fixture-based; live smoke tests are opt-in.
- Production code is written only after the corresponding test has failed for the expected reason.

---

## File Map

- `pyproject.toml`: package metadata, Python floor, pytest configuration, CLI entry point.
- `hermes_data_engine/__init__.py`: public version.
- `hermes_data_engine/models.py`: canonical observation, provenance, document builder, and validation.
- `hermes_data_engine/normalize.py`: dates, numbers, percentages, and unit conversion.
- `hermes_data_engine/http.py`: bounded HTTP fetch with user agent, timeout, retry, and injectable transport.
- `hermes_data_engine/providers/goodinfo.py`: Goodinfo response parsing and fetch adapter.
- `hermes_data_engine/providers/twse.py`: TWSE official dataset parsing and fetch adapter.
- `hermes_data_engine/providers/mops.py`: MOPS monthly revenue and financial parsing and fetch adapter.
- `hermes_data_engine/providers/yahoo.py`: Yahoo-compatible market/valuation fallback parsing and fetch adapter.
- `hermes_data_engine/pipeline.py`: cross-validation, precedence, fallback, and stale merge.
- `hermes_data_engine/storage.py`: last-known-good reads and atomic validated writes.
- `hermes_data_engine/cli.py`: batch execution and document validation commands.
- `tests/fixtures/`: minimal provider samples with no credentials or tracking data.
- `tests/test_*.py`: unit and integration coverage.
- `.github/workflows/hermes-data-engine.yml`: scheduled execution and safe push.
- `README.md`: operation, schema, sources, limitations, and research disclaimer.

### Task 1: Canonical Model and Normalization

**Files:**
- Create: `pyproject.toml`
- Create: `hermes_data_engine/__init__.py`
- Create: `hermes_data_engine/models.py`
- Create: `hermes_data_engine/normalize.py`
- Test: `tests/test_models.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Produces: `Observation(value, source, as_of, fetched_at, status, period=None)`.
- Produces: `normalize_number(value)`, `normalize_roc_date(value)`, `lots_to_shares(value)`, and `build_document(symbol, observations, generated_at)`.
- Produces: `validate_document(document)` which raises `ValueError` for missing or invalid schema fields.

- [ ] **Step 1: Write failing normalization tests**

```python
from hermes_data_engine.normalize import lots_to_shares, normalize_number, normalize_roc_date

def test_normalizes_taiwan_market_values():
    assert normalize_number("-1,234") == -1234
    assert normalize_number("--") is None
    assert lots_to_shares("1,234") == 1_234_000
    assert normalize_roc_date("115/07/10") == "2026-07-10"
```

- [ ] **Step 2: Run `python -m pytest tests/test_normalize.py -q` and verify collection fails because the package does not exist**
- [ ] **Step 3: Implement the four small normalization functions with `Decimal`-safe parsing and explicit null markers**
- [ ] **Step 4: Run the normalization test and verify it passes**
- [ ] **Step 5: Write failing model tests for all required keys, provenance metadata, negative-EPS PE nulling, and schema rejection**

```python
def test_document_has_required_fields(sample_observations):
    document = build_document("3033", sample_observations, "2026-07-10T09:00:00Z")
    assert set(REQUIRED_FIELDS) <= document.keys()
    assert document["pe"] is None
    assert document["sources"]["price"]["source"] == "TWSE"
    validate_document(document)
```

- [ ] **Step 6: Run `python -m pytest tests/test_models.py -q` and verify the missing model API causes failure**
- [ ] **Step 7: Implement immutable observations, document construction, quality aggregation, and strict validation**
- [ ] **Step 8: Run `python -m pytest tests/test_models.py tests/test_normalize.py -q` and verify all tests pass**
- [ ] **Step 9: Commit `feat: add canonical Hermes data model`**

### Task 2: HTTP Boundary and Goodinfo Provider

**Files:**
- Create: `hermes_data_engine/http.py`
- Create: `hermes_data_engine/providers/__init__.py`
- Create: `hermes_data_engine/providers/goodinfo.py`
- Create: `tests/fixtures/goodinfo_daily.html`
- Test: `tests/test_http.py`
- Test: `tests/test_goodinfo.py`

**Interfaces:**
- Consumes: normalization helpers and `Observation`.
- Produces: `fetch_text(url, transport=None, attempts=3, timeout=20)`.
- Produces: `GoodinfoProvider.fetch(symbol, trading_date) -> dict[str, Observation]`.
- Produces: `parse_goodinfo(html, symbol, fetched_at) -> dict[str, Observation]`.

- [ ] **Step 1: Write failing tests proving the HTTP boundary sets a descriptive user agent, retries transient status errors only, and redacts URL query values from raised errors**
- [ ] **Step 2: Run `python -m pytest tests/test_http.py -q` and verify failure is due to missing HTTP API**
- [ ] **Step 3: Implement bounded retry using injectable transport and no browser/challenge circumvention**
- [ ] **Step 4: Run the HTTP tests and verify they pass**
- [ ] **Step 5: Add a minimal UTF-8 Goodinfo fixture and failing parser tests for price, volume, daytrade ratio/volume, margin balance/change, short balance/ratio, and three institutional net flows**
- [ ] **Step 6: Run `python -m pytest tests/test_goodinfo.py -q` and verify failure is due to missing parser/provider**
- [ ] **Step 7: Implement header-driven table parsing that rejects absent or changed required headers instead of returning fabricated values**
- [ ] **Step 8: Run `python -m pytest tests/test_http.py tests/test_goodinfo.py -q` and verify all tests pass**
- [ ] **Step 9: Commit `feat: add guarded Goodinfo provider`**

### Task 3: TWSE Official Provider and Cross-Validation Inputs

**Files:**
- Create: `hermes_data_engine/providers/twse.py`
- Create: `tests/fixtures/twse_price.json`
- Create: `tests/fixtures/twse_margin.json`
- Create: `tests/fixtures/twse_daytrade.json`
- Create: `tests/fixtures/twse_institutional.json`
- Create: `tests/fixtures/twse_valuation.json`
- Test: `tests/test_twse.py`

**Interfaces:**
- Consumes: HTTP boundary, normalization helpers, and `Observation`.
- Produces: `TwseProvider.fetch(symbol, trading_date) -> dict[str, Observation]`.
- Produces one observation for each compatible requested field, with source `TWSE` and actual dataset date.

- [ ] **Step 1: Write failing fixture tests for official price/volume, margin/short balances and changes, short-to-margin ratio, daytrade fields, institutional net flows, PE, and PB**
- [ ] **Step 2: Run `python -m pytest tests/test_twse.py -q` and verify the missing provider causes failure**
- [ ] **Step 3: Implement dataset-specific parsers that locate columns by official field name and filter by exact symbol**
- [ ] **Step 4: Add failing tests for ROC dates, empty `data`, mismatched symbols, and share/lot normalization**
- [ ] **Step 5: Implement explicit `ProviderDataError` failures for unusable official responses**
- [ ] **Step 6: Run `python -m pytest tests/test_twse.py -q` and verify all tests pass**
- [ ] **Step 7: Commit `feat: add TWSE official datasets`**

### Task 4: MOPS and Yahoo Providers

**Files:**
- Create: `hermes_data_engine/providers/mops.py`
- Create: `hermes_data_engine/providers/yahoo.py`
- Create: `tests/fixtures/mops_revenue.json`
- Create: `tests/fixtures/mops_financial.json`
- Create: `tests/fixtures/yahoo_chart.json`
- Create: `tests/fixtures/yahoo_quote.json`
- Test: `tests/test_mops.py`
- Test: `tests/test_yahoo.py`

**Interfaces:**
- Produces: `MopsProvider.fetch(symbol) -> dict[str, Observation]` containing revenue, cumulative basic EPS, and cumulative operating cash flow with periods.
- Produces: `YahooProvider.fetch(symbol, trading_date) -> dict[str, Observation]` containing only price, volume, PE, and PB.

- [ ] **Step 1: Write failing MOPS fixture tests selecting the latest published month and the latest financial period without equating publication date to market date**
- [ ] **Step 2: Run `python -m pytest tests/test_mops.py -q` and verify the provider is missing**
- [ ] **Step 3: Implement MOPS parsing with explicit period, publication metadata, cumulative basic EPS, and cumulative operating cash flow**
- [ ] **Step 4: Run the MOPS tests and verify they pass**
- [ ] **Step 5: Write failing Yahoo tests for chart price/volume and quote PE/PB, including the invariant that no unsupported fields are returned**
- [ ] **Step 6: Run `python -m pytest tests/test_yahoo.py -q` and verify the provider is missing**
- [ ] **Step 7: Implement Yahoo parsing with the exact source label `Yahoo(Fallback)` and no credit, institutional, or MOPS-domain fields**
- [ ] **Step 8: Run `python -m pytest tests/test_mops.py tests/test_yahoo.py -q` and verify all tests pass**
- [ ] **Step 9: Commit `feat: add MOPS and Yahoo providers`**

### Task 5: Pipeline Precedence, Mismatch, and Stale Recovery

**Files:**
- Create: `hermes_data_engine/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: providers exposing `fetch(...) -> dict[str, Observation]` and an optional prior document.
- Produces: `HermesPipeline.run(symbol, requested_date, previous=None) -> dict`.
- Produces: `resolve_field(field, goodinfo, official, yahoo, previous) -> tuple[value, provenance, issues]`.

- [ ] **Step 1: Write failing tests where matching Goodinfo/TWSE values retain Goodinfo with `verified` status**
- [ ] **Step 2: Run the focused test and verify failure is due to missing pipeline**
- [ ] **Step 3: Implement verified-field resolution only and make the test pass**
- [ ] **Step 4: Write failing tests where mismatches select TWSE and preserve both normalized inputs in `quality.issues`**
- [ ] **Step 5: Implement mismatch resolution and make the focused test pass**
- [ ] **Step 6: Write failing tests for Goodinfo failure to TWSE, compatible Yahoo fallback, and Yahoo rejection for unsupported fields**
- [ ] **Step 7: Implement ordered per-field fallback and make the focused tests pass**
- [ ] **Step 8: Write failing tests for stale previous values, first-run unavailable nulls, mixed financial dates, and weekend actual trading dates**
- [ ] **Step 9: Implement stale/unavailable merging and document-level quality aggregation**
- [ ] **Step 10: Run `python -m pytest tests/test_pipeline.py -q` and verify all pipeline tests pass**
- [ ] **Step 11: Commit `feat: orchestrate field-level data fallback`**

### Task 6: Atomic Storage and Batch CLI

**Files:**
- Create: `hermes_data_engine/storage.py`
- Create: `hermes_data_engine/cli.py`
- Test: `tests/test_storage.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `validate_document` and `HermesPipeline`.
- Produces: `load_previous(path) -> dict | None`.
- Produces: `atomic_write(path, document) -> None`.
- Produces CLI commands `hermes-data-engine run` and `hermes-data-engine validate`.

- [ ] **Step 1: Write failing storage tests proving valid atomic replacement and preservation of the original file after validation or replacement failure**
- [ ] **Step 2: Run `python -m pytest tests/test_storage.py -q` and verify missing storage functions cause failure**
- [ ] **Step 3: Implement same-directory temporary writes, flush/fsync, validation, and `os.replace` cleanup**
- [ ] **Step 4: Run storage tests and verify they pass**
- [ ] **Step 5: Write failing CLI tests for the exact five default files, a custom symbol subset, nonzero provider/validation failure, and `validate data/*.json`**
- [ ] **Step 6: Run `python -m pytest tests/test_cli.py -q` and verify missing CLI behavior causes failure**
- [ ] **Step 7: Implement argparse commands, provider construction, previous-data loading, per-symbol execution, and deterministic JSON formatting**
- [ ] **Step 8: Run `python -m pytest tests/test_storage.py tests/test_cli.py -q` and verify all tests pass**
- [ ] **Step 9: Commit `feat: add atomic batch CLI`**

### Task 7: GitHub Actions, Documentation, and End-to-End Verification

**Files:**
- Create: `.github/workflows/hermes-data-engine.yml`
- Create: `README.md`
- Test: `tests/test_workflow_contract.py`

**Interfaces:**
- Consumes: `python -m pytest`, `hermes-data-engine run`, and `hermes-data-engine validate`.
- Produces: weekday scheduled workflow with `contents: write`, concurrency control, explicit test/run/validate gates, and non-force push.

- [ ] **Step 1: Write a failing workflow contract test that requires weekday cron, Python 3.12, `contents: write`, concurrency, pytest before run, validation before commit, the five output paths, and no force push**
- [ ] **Step 2: Run `python -m pytest tests/test_workflow_contract.py -q` and verify failure because the workflow is absent**
- [ ] **Step 3: Implement the workflow with UTC cron corresponding to after-close Asia/Taipei, `workflow_dispatch`, pip cache, and changed-output commit guard**
- [ ] **Step 4: Run the workflow contract test and verify it passes**
- [ ] **Step 5: Write README sections for setup, CLI use, schema, exact field units, source precedence, stale behavior, GitHub permissions, provider limitations, and the non-investment-advice disclaimer**
- [ ] **Step 6: Run `python -m pytest -q` and verify the complete offline suite has zero failures**
- [ ] **Step 7: Run `python -m hermes_data_engine.cli --help` and both CLI command help screens; verify exit code 0**
- [ ] **Step 8: Run an injected-fixture batch into a temporary directory and run `hermes-data-engine validate` over all five generated documents**
- [ ] **Step 9: Review `git diff --check`, confirm no credentials/cookies/query tokens are present, and inspect the requirements checklist against the approved design**
- [ ] **Step 10: Ask Reviewer to challenge source semantics, fallback boundaries, dates, units, and workflow safety; address every actionable finding with a failing test first**
- [ ] **Step 11: Re-run `python -m pytest -q`, CLI smoke tests, fixture batch validation, and `git diff --check` immediately before completion**
- [ ] **Step 12: Commit `feat: automate daily Hermes data generation`**
- [ ] **Step 13: Push the current branch to its configured GitHub remote without force**

## Plan Self-Review

- Every approved design requirement maps to a task: schema/normalization (Task 1), Goodinfo (Task 2), TWSE (Task 3), MOPS/Yahoo (Task 4), fallback/quality (Task 5), atomic output/CLI (Task 6), and schedule/publish/docs (Task 7).
- Provider interfaces consistently return `dict[str, Observation]`; pipeline and storage consume the same canonical document type.
- The plan contains no deferred implementation placeholders; live network access remains an explicit opt-in smoke test rather than an offline test dependency.
- Push is last and occurs only after fresh verification and Reviewer feedback.
