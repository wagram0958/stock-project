# CGC-DK-Lab Status

Updated: 2026-10-07 Asia/Taipei

## Completed
- Core SOP v1.1
- Freeze template
- Post-draw audit template
- GitHub project area
- Official source identification
- Historical-data validation script
- Time-safe feature builder skeleton
- Draw scoring script
- Model registry skeleton

## Official-source facts
- Taiwan Lottery publishes historical-result downloads with fields including game, issue, draw date, six main numbers, and special number.
- The official download page states monthly updates on the 5th through the prior month.
- Lotto 6/49 draws are scheduled Tuesday and Friday.
- Official draw activity starts around 20:30; published web results follow later.

## Blocked / incomplete
- The actual official annual data file has not yet been downloaded into the repository.
- The visible official download page does not expose the direct annual-file URL through the current connector.
- Therefore no historical feature values, walk-forward backtest, DK-M1 weights, or claimed hit-rate improvement have been computed yet.

## Next automatic step
Acquire the official annual result file through an accessible direct file endpoint or synchronized NAS/Drive copy, validate it, then generate time-safe features and fit candidate models.
