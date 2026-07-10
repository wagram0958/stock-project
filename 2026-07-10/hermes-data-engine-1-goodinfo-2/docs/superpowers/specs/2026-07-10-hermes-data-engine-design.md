# Hermes Data Engine Design

## Objective

Build a Python data pipeline that runs daily before stock research, collects and cross-validates market and financial data for `3033`, `6214`, `6753`, `1314`, and `2002`, and writes one JSON document per symbol under `data/`.

The engine is research infrastructure only and does not provide investment advice.

## Architecture

Use a per-field provider chain rather than switching an entire symbol between providers. Goodinfo is the preferred convenience source for daily market fields. TWSE is the authoritative cross-validation and fallback source for exchange data. MOPS is the authoritative source for monthly revenue and financial statements. Yahoo is a last-resort fallback only for fields it can reliably supply.

The daily flow is:

1. A scheduled GitHub Actions workflow starts after the Taiwan market close.
2. The CLI processes the five configured symbols.
3. Provider modules download and normalize data into a canonical model.
4. The pipeline compares Goodinfo with official data field by field.
5. The pipeline applies fallback and last-known-good rules.
6. Storage atomically writes `data/<symbol>.json`.
7. Tests and output validation run before the workflow commits and pushes changed JSON files.

## Components

- `hermes_data_engine/providers/goodinfo.py`: downloads and parses Goodinfo market, day-trading, margin, short, and institutional data without bypassing access controls.
- `hermes_data_engine/providers/twse.py`: downloads and parses official TWSE price, volume, day-trading, credit-trading, institutional, and valuation datasets.
- `hermes_data_engine/providers/mops.py`: downloads and parses the latest published monthly revenue and financial statement values.
- `hermes_data_engine/providers/yahoo.py`: provides last-resort price, volume, PE, and PB data only.
- `hermes_data_engine/models.py`: defines normalized values, units, dates, provenance, and output schema.
- `hermes_data_engine/pipeline.py`: orchestrates provider calls, cross-validation, fallback, stale-value recovery, and quality reporting.
- `hermes_data_engine/storage.py`: reads last-known-good output and performs atomic JSON replacement.
- `hermes_data_engine/cli.py`: processes the default five symbols or caller-supplied symbols and dates.
- `.github/workflows/hermes-data-engine.yml`: runs tests, executes the engine on a Taipei-time schedule, and commits changed output.

## Canonical Field Semantics

- `price`: unadjusted closing price in TWD.
- `volume`: traded volume in shares.
- `margin`: object containing end-of-day margin balance and daily change, both in shares.
- `short`: object containing end-of-day short balance and daily change, both in shares; it also contains the short-to-margin ratio.
- `daytrade`: object containing the day-trading ratio and day-trading volume in lots.
- `foreign`: foreign-investor daily net buy/sell in shares.
- `investment`: investment-trust daily net buy/sell in shares.
- `dealer`: dealer daily net buy/sell in shares.
- `revenue`: latest published monthly revenue, including its year-month period and TWD unit.
- `eps`: cumulative basic EPS from the latest published financial report, including the reporting period.
- `cashflow`: cumulative operating cash flow for the same latest published financial-report period, in TWD.
- `pb`: price-to-book ratio with observation date.
- `pe`: price-to-earnings ratio with observation date; it is `null` when the earnings basis is non-positive.
- `date`: actual market-data trading date, never the workflow execution date when the market is closed.

The JSON also contains `schema_version`, `symbol`, `market`, `currency`, `generated_at`, `sources`, `quality`, and `errors`. Each entry in `sources` records at least `source`, `as_of`, `fetched_at`, and `status`. Financial fields additionally record their reporting period where applicable.

## Source and Fallback Rules

Fallback is performed independently for each field.

1. Goodinfo is attempted for supported daily fields.
2. TWSE data is always fetched for official cross-validation and supplies a field when Goodinfo is unavailable.
3. MOPS directly supplies monthly revenue, EPS, and operating cash flow.
4. Yahoo may supply only price, volume, PE, and PB if the preferred and official sources cannot supply them.
5. If every compatible source fails, the previous successful field value is retained with `status: "stale"` and its original `as_of` date.
6. If no historical value exists, the value is `null` with `status: "unavailable"`.

Required source labels are `Goodinfo`, `TWSE`, `MOPS`, and `Yahoo(Fallback)`. A fallback value from TWSE is therefore explicitly represented in `sources.<field>.source` as `TWSE`; a Yahoo fallback uses `Yahoo(Fallback)`.

Yahoo must never be presented as the source of credit trading, day-trading, institutional, monthly revenue, EPS, or cash-flow fields unless a future documented provider capability and schema revision explicitly allow it.

## Cross-Validation and Data Quality

All comparisons occur after normalization of Gregorian/ROC dates, thousands separators, signs, percentages, and share/lot units.

- Matching Goodinfo and TWSE values retain the Goodinfo output and receive `status: "verified"`.
- Mismatched values use the official TWSE value, receive `status: "mismatch"`, and add both raw normalized values and their difference to `quality.issues`.
- A Goodinfo failure followed by a successful TWSE result receives `status: "fallback"`.
- Missing data is never silently converted to zero.
- Weekend, holiday, and unscheduled closure runs retain the actual most recent trading date.
- `quality.status` is one of `complete`, `partial`, `mismatch`, or `stale`.
- Provider errors are captured in `errors` without credentials, cookies, authorization headers, or tracking data.

Provider requests use a descriptive user agent, low request volume, timeouts, bounded retry with backoff, and caching appropriate for a daily job. The implementation must not bypass CAPTCHA, Cloudflare challenges, robots restrictions, or provider terms. If Goodinfo disallows automated access or blocks the workflow, the engine proceeds with official sources.

## Storage and Failure Safety

JSON output is UTF-8, deterministic, and human-readable. Each document is written to a temporary file in the target directory and atomically replaces the prior file only after schema validation succeeds. A partial provider failure may produce a valid mixed-source document, but a malformed document must never replace the last valid file.

The repository must not contain provider credentials or session data. GitHub workflow permissions are limited to the content write permission needed to commit generated JSON.

## Scheduling and Publishing

GitHub Actions is the sole scheduled runtime in this scope. The cron expression is chosen in UTC for an after-close Asia/Taipei execution on weekdays. The engine itself determines the effective trading date, so holidays and closures do not receive fabricated dates.

The workflow:

1. checks out the branch;
2. sets up the supported Python version;
3. installs pinned dependencies;
4. runs the offline test suite;
5. runs the five-symbol batch;
6. validates all five JSON documents;
7. commits and pushes only when tracked output changed.

Push failures caused by branch protection or concurrent updates must fail visibly rather than force-push.

## Testing Strategy

Tests follow test-driven development and use small saved fixtures rather than live network dependencies.

- Provider parser tests cover valid responses, empty tables, changed headers, malformed numbers, negative values, ROC dates, and encoding.
- Normalization tests cover shares versus lots, percentages, signs, nulls, and reporting periods.
- Pipeline tests cover Goodinfo verified values, TWSE fallback, Yahoo fallback for compatible fields, MOPS financial fields, mismatch precedence, last-known-good stale recovery, and first-run unavailable values.
- Storage tests prove atomic replacement and preservation of the previous valid document on validation failure.
- CLI tests prove default and caller-supplied symbol selection and nonzero exit status for invalid output.
- Workflow validation checks that all five expected files are produced.

A separate opt-in live smoke test may exercise providers manually. Scheduled correctness does not depend on live tests being stable.

## Acceptance Criteria

- A successful batch creates `data/3033.json`, `data/6214.json`, `data/6753.json`, `data/1314.json`, and `data/2002.json`.
- Every document exposes all requested top-level fields: `price`, `volume`, `margin`, `short`, `daytrade`, `foreign`, `investment`, `dealer`, `revenue`, `eps`, `cashflow`, `pb`, `pe`, and `date`.
- Every requested field has per-field provenance and freshness metadata.
- Goodinfo failure falls back to TWSE for compatible official fields and labels those fields `TWSE`.
- Yahoo fallback fields are labeled `Yahoo(Fallback)` and are limited to compatible market/valuation data.
- Unrecoverable fields retain last-known-good values as stale; a first-run absence uses `null`, never a fabricated zero.
- Official mismatches are visible and resolve to the official value.
- Offline tests and JSON validation pass before automated output is pushed.

## Out of Scope

- Investment recommendations, trade execution, portfolio management, alerting, dashboards, and intraday polling.
- Circumventing provider access restrictions.
- Treating Yahoo as an authoritative replacement for TWSE or MOPS datasets.
- Local Windows Task Scheduler setup.
