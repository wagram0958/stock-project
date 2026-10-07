# Exploratory Mirror Backtest — 2026-10-07

Status: EXPLORATORY ONLY — NOT DK FORWARD EVIDENCE

## Data

Mirror source:
Albertyoung22/lotto `lotto649_history.csv`

The mirror project states that its history is fetched from Taiwan Lottery's official API. This copy is used only to unblock exploratory model screening. It is not a substitute for the official raw file required by the CGC data gate.

Coverage observed:
- first: 113000001 / 2024-01-02
- last: 115000087 / 2026-09-11
- rows: 323

Official-source cross-check remains required.

## Walk-forward rule

For each target draw t:
- only draws before t were used
- minimum history: 100 draws
- evaluated draws: 223
- one formal pick set of six per method per historical target
- scoring: intersection count K with six main numbers only

Fair baseline:
E[K] = 36/49 = 0.7346938776

## Candidate results

| Method | Total hits | Mean K | Delta vs fair |
|---|---:|---:|---:|
| freq20 | 168 | 0.753363 | +0.018669 |
| freq50 | 193 | 0.865471 | +0.130777 |
| omission | 174 | 0.780269 | +0.045575 |
| mix_fixed_v0 | 170 | 0.762332 | +0.027638 |

For freq50, the fair-baseline one-tail probability for total hits >= 193 over 223 independent draws is approximately 0.00652. This is NOT a confirmatory p-value because multiple candidate rules were examined and the data are exploratory.

## Temporal stress check for freq50

- first half: 97 / 111 = 0.873874
- second half: 96 / 112 = 0.857143
- 2024 evaluated segment: 14 / 18 = 0.777778
- 2025: 105 / 118 = 0.889831
- 2026 through mirror cutoff: 74 / 87 = 0.850575
- last 50 evaluated draws: 44 / 50 = 0.880000
- last 20 evaluated draws: 19 / 20 = 0.950000

## Audit interpretation

This is a candidate signal, not proof.

Reasons it cannot be promoted yet:
1. Mirror data rather than archived official raw file.
2. The candidate was selected after examining exploratory results.
3. Multiple windows/rules were compared.
4. Language-model/public-history contamination remains possible.
5. No future frozen validation has been completed.

## Required next test

- Obtain official raw history and SHA-256.
- Independently reproduce freq50 exactly.
- Freeze the rule before using future draws:
  score(n) = count of number n in the previous 50 draws.
  Select the six highest counts; ties resolved by ascending number.
- Do not adjust the 50-draw window based on future outcomes.
- Compare future frozen mean K against 0.7346938776.
- Any improved model must be versioned separately and evaluated only on later draws.
