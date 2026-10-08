# CGC-DK-Lab Status

Updated: 2026-10-08 Asia/Taipei

## Verified implementation

- Official Taiwan Lottery JSON API history pipeline implemented, executed and committed.
- Most recent successful GitHub Actions run: https://github.com/wagram0958/stock-project/actions/runs/37758839589
- Data snapshot retrieved 2026-10-08T17:49:24+08:00: 2,176 official draw rows, skipped_months=[].
- Raw official API archive and SHA-256 committed under `data/raw/`.
- Raw archive SHA-256: `698f92e81e0b6a82300d30f3b7e5aca10e3051a4148de85187b5ffe79768b2d5`.
- Cleaned CSV validated; time-safe features generated; historical exploratory walk-forward backtest completed for 2,076 targets.
- Seven offline scoring regression tests passed in the GitHub Actions run; official dual-track ledger scoring and `reports/forward_scoreboard.md` generation steps passed.
- Workflow protects against partial monthly fetch, conflicting issue data and hidden backtest pipeline failure.
- GitHub Actions schedule: Tuesdays and Fridays 22:30 Asia/Taipei; the ChatGPT dual-track post-draw check is scheduled for 22:15.

## Frozen forecast and pre-draw Gate 0 audit

- Target: `115000095`, scheduled Friday 2026-10-09 at 20:30 Asia/Taipei.
- DK frozen numbers: `01 02 03 04 05 20`, R5H v0.1.
- CGC frozen numbers: `04 12 14 26 29 35`, CGC-FREQ50 v0.1.
- Frozen on 2026-10-07, initially tagged Gate 0 incomplete. Original snapshot preserved.
- On 2026-10-08 **before the draw**, official Taiwan Lottery promotional schedule verified issue/date:
  https://lotto.ctbcbank.com/news1150908.htm
- The frozen R5H and FREQ50 results were independently reproduced using archived official history without seeing the future target draw. Added an append-only verification section to the frozen record and marked the ledger Gate 0 passed on 2026-10-08, not retroactively on original freeze day.
- No future forward result is available as of this update; scoreboard n=0 for both tracks.

## Exploratory history — not verified predictive advantage

From the October 8 official-source exploratory run (2,076 test draws):
- freq20: mean K 0.731696
- freq50: mean K 0.768304
- omission: mean K 0.742293
- mix_fixed_v0: mean K 0.721580
- Uniform fair 6/49 baseline: mean K 36/49 ≈ 0.734694.

These values cannot establish an advantage because candidate methods were screened on retrospective data. No improvement is marked verified. Model changes must apply only to future, not-yet-frozen draws.

## Open constraints and follow-up

- Verify first scheduled post-draw official result capture, recording and data commit after 2026-10-09; this has not happened yet.
- DK does not have a demonstrated direct automated channel to this GitHub workflow. DK forecasts must arrive independently in time to be frozen; missing forecasts must be marked missing, never simulated as DK's output.
- Monitoring/assessment tasks have reached the existing active-task cap; follow-up checks have been combined into the existing Tuesday/Friday dual-track task instead of deleting other tasks.
- External annual-download-file reconciliation remains an optional independent cross-check; official API raw archive is already stored. Do not relabel the historical mirror as official.
- Track separate DK/CGC forward K, mean K, K>=2/3 frequencies and tests after sufficient *valid pre-draw* samples. Make no winning-probability claims based on a single draw.

## Next automatic steps

1. At/after each draw, ingest the official result into versioned raw and cleaned datasets.
2. Match only valid pre-draw frozen forecasts, score DK and CGC separately, update the forward scoreboard.
3. Review any GitHub Action failure, distinguish transient failure from code fault, preserve failing logs, and verify fixes with a new successful run.
4. Only propose model candidates from leakage-safe evidence; never rewrite frozen history.
