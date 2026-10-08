# Official Data Acquisition

Updated: 2026-10-08 Asia/Taipei

## Verified machine-readable primary source

- Taiwan Lottery official JSON API:
  https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result
- Fetch script: `../scripts/fetch_official_history.py`.
- Raw archive: `raw/lotto649_official.json`.
- Raw SHA-256: `raw/lotto649_official.sha256`.
- Retrieval time, source, span and any skipped months: `raw/fetch_metadata.json`.
- Validated clean data: `cleaned/lotto649_official.csv`.
- Historical feature rows: `cleaned/features.csv`.

## Verified current run

GitHub Actions: https://github.com/wagram0958/stock-project/actions/runs/37758839589

- Retrieved 2026-10-08T17:49:24+08:00.
- History 2004-01 through 2026-10, 2,176 cleaned draw rows.
- No fetch month exceptions (`skipped_months=[]`).
- Source raw SHA-256:
  `698f92e81e0b6a82300d30f3b7e5aca10e3051a4148de85187b5ffe79768b2d5`.
- Cleaned data validation and historical backtest passed; source and reports were written to the repository.

## Required safeguards

1. Never change an already frozen prediction based on later draw data.
2. A monthly fetch exception fails the entire job. Do not publish a partial new history snapshot.
3. Duplicate issue IDs with conflicting data fail the job.
4. Reject invalid/mixed game, date or draw-number rows using the validation script.
5. Retain original API payloads with SHA-256 and retrieval timestamps before interpreting results.
6. Use only previous draws for features or predictions at target t; never include t's target values.
7. Preserve exploratory backtests separately from genuinely pre-draw frozen forecast results.
8. If official data are amended later, stop before silently overwriting previously scored draws; investigate and retain an audit trail.

## Additional official cross-check source

- Taiwan Lottery historical-result annual download page:
  https://www.taiwanlottery.com/lotto/history/result_download/

The annual download file has not been separately obtained through the current connector. This is an *independent corroboration gap*, not a statement that no official data exist: the official API raw history and its checksum are archived above. A previously used third-party mirror remains exploratory only.

## Scheduled updates

- GitHub Actions workflow: `.github/workflows/dk-lotto-pipeline.yml`.
- Tuesdays and Fridays 22:30 Asia/Taipei (14:30 UTC).
- Official result publication may be later than the broadcast; do not interpret a missing result before publication as a failed prediction.
