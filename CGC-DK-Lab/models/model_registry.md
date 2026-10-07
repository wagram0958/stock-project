# DK Model Registry

## DK-M0 — Uniform baseline
Status: baseline only
Purpose: 公平 6/49 對照，不代表 DK 模型。
Expected K: 36/49 = 0.7346938776

## DK-M1 — Candidate multi-window signal model
Status: NOT YET FIT / NOT YET VALIDATED

Candidate feature families:
- freq20 / freq50 / freq100
- omission
- previous-draw repeat
- pair co-occurrence
- odd/even and low/high set-level constraints
- sum / spacing / consecutive-number diagnostics

Rules before promotion:
1. All features for target t must be computed from draws < t only.
2. Weights must be selected without using the held-out test segment.
3. Compare against uniform baseline and at least one simple fixed heuristic.
4. Preserve losing candidate models.
5. Promotion requires a reproducible walk-forward result; this still counts as exploratory evidence.
6. Final success is judged only by frozen future draws.

Current note:
No weights, parameters, or official six-number output have been approved yet.
