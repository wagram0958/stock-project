# Official Data Acquisition

Primary source:
- Taiwan Lottery historical result download page:
  https://www.taiwanlottery.com/lotto/history/result_download/

Official page states the Lotto 6/49-style fields include:
遊戲名稱, 期別, 開獎日期, 銷售總額, 銷售注數, 總獎金, 獎號1..6, 特別號.

Update cadence shown by Taiwan Lottery:
- Updated on the 5th of each month through the prior month.

## Required ingestion procedure

1. Save original official annual file unchanged under `data/raw/`.
2. Record download timestamp in Asia/Taipei.
3. Compute SHA-256 before any transformation.
4. Filter to 大樂透 only.
5. Run `scripts/validate_history.py`.
6. Preserve original draw order separately from sorted-number representation.
7. Write cleaned data to `data/cleaned/`.
8. Never append future draw results into a training snapshot used for an earlier frozen forecast.

## Current blocker — 2026-10-07

The official download page is reachable, but the current connector does not expose the annual-file download URL and direct container download of the HTML page failed. No annual official file has therefore been stored yet.

Do not replace the missing official file with guessed or silently substituted data.
