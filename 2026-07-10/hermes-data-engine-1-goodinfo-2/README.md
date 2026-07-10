# Hermes Data Engine

Hermes Data Engine builds daily, provenance-rich JSON snapshots for Taiwan stock research. It collects Goodinfo data first, cross-checks compatible fields with TWSE, reads revenue and financial data from MOPS, and uses Yahoo only for supported market fallback fields.

This tool is for research automation, not investment advice.

## Setup

Use Python 3.12 or newer.

```bash
python -m pip install -e . pytest
python -m pytest -q
```

## CLI

Generate the default five files:

```bash
hermes-data-engine run --date 2026-07-10 --output-dir data
```

Generate a subset:

```bash
hermes-data-engine run --date 2026-07-10 --output-dir data --symbols 3033,6214
```

Validate existing output:

```bash
hermes-data-engine validate data/3033.json data/6214.json data/6753.json data/1314.json data/2002.json
```

## Output

Default outputs are:

- `data/3033.json`
- `data/6214.json`
- `data/6753.json`
- `data/1314.json`
- `data/2002.json`

Each document includes:

- `price`: closing price, TWD.
- `volume`: trading volume, shares.
- `margin`: financing balance and daily change, shares.
- `short`: securities lending balance and daily change in shares; short-to-margin ratio in percent.
- `daytrade`: day-trade volume in lots and ratio in percent.
- `foreign`, `investment`, `dealer`: institutional net flows, shares.
- `revenue`: latest published monthly revenue in TWD.
- `eps`: latest published cumulative basic EPS.
- `cashflow`: latest published cumulative operating cash flow in TWD.
- `pb`, `pe`: valuation fields.
- `date`: actual data date, not fabricated from the requested date.

Every field also has `sources.<field>` with source, data date, fetch timestamp, status, and period when applicable.

## Source Precedence

Goodinfo is the preferred source for compatible daily fields. TWSE is used to cross-check credit, day-trade, institutional, price, volume, PE, and PB fields. If Goodinfo is missing or fails for a compatible field, TWSE becomes the field-level fallback and is labeled `TWSE`.

MOPS supplies `revenue`, `eps`, and `cashflow` directly because those are financial reporting fields, not daily trading fields.

Yahoo is only allowed for `price`, `volume`, `pe`, and `pb`. When used, the source label is exactly `Yahoo(Fallback)`.

## Stale Behavior

Missing values are never converted to zero. If a current run cannot obtain a field but a prior valid JSON document exists, the prior value is reused with status `stale` and its original data date. On a first run with no prior value, the field is `null` and status `unavailable`.

## GitHub Actions

`.github/workflows/hermes-data-engine.yml` runs on weekdays after the Taiwan market close. It installs the package, runs tests, generates the five JSON files, validates them, and only then commits and pushes changed `data/*.json` files. The workflow requires `contents: write` permission.

When no date is supplied, the CLI uses the current Taipei business day and rolls weekend executions back to the previous Friday. If providers cannot supply that candidate date, stale recovery keeps the last valid field-level `as_of` values, including the prior actual market date.

## Provider Limits

Hermes does not bypass provider access controls, CAPTCHA, robots restrictions, or terms. Offline tests use fixtures. Live provider behavior can change, so the workflow validates every generated document before writing it to the repository.
