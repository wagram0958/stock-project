#!/usr/bin/env python3
"""Append-only-minded scoring of pre-draw frozen DK/CGC predictions.

Only official-history rows can supply actual numbers. The original frozen
numbers, models and freeze times are never modified. Gate 0 incomplete
records are scored descriptively but excluded from formal forward metrics.
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = 36 / 49
EXTRA = ["actual_numbers", "special_number", "result_source", "score_status"]
FORMAL = {"FROZEN_GATE0_PASSED", "FROZEN_GATE0_COMPLETE"}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def six(value):
    nums = [int(s) for s in str(value).replace(",", " ").split()]
    if len(nums) != 6 or len(set(nums)) != 6 or any(not 1 <= n <= 49 for n in nums):
        raise ValueError("Invalid six-number prediction/result: " + str(value))
    return set(nums)


def when(value):
    d = datetime.fromisoformat(str(value))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("Timezone-aware time required: " + str(value))
    return d


def official_index(history):
    _, draws = read_csv(history)
    result = {}
    for row in draws:
        issue = row["期別"].strip()
        if issue in result:
            raise ValueError("Duplicate official issue: " + issue)
        nums = six(" ".join(row[f"獎號{i}"] for i in range(1, 7)))
        special = int(row["特別號"])
        if not 1 <= special <= 49 or special in nums:
            raise ValueError("Invalid special number for " + issue)
        result[issue] = (row["開獎日期"].replace("/", "-"), nums, special)
    return result


def metrics(rows, track):
    items = [int(r[f"{track}_K"]) for r in rows
             if r.get("score_status") == "FORMAL" and r.get(f"{track}_K", "") != ""]
    c = Counter(items)
    def avg(vals):
        return f"{sum(vals) / len(vals):.4f}" if vals else "N/A"
    return (f"{track.upper()}: n={len(items)}, mean_K={avg(items)}, "
            f"last20={avg(items[-20:]) if len(items)>=20 else 'N/A'}, "
            f"last50={avg(items[-50:]) if len(items)>=50 else 'N/A'}, "
            f"K_distribution=" + "/".join(str(c[k]) for k in range(7)) +
            f", K>=2={sum(k>=2 for k in items)}, K>=3={sum(k>=3 for k in items)}")


def process(history, ledger_path, summary_path):
    official = official_index(history)
    fields, ledger = read_csv(ledger_path)
    required = {"issue", "scheduled_draw", "freeze_time", "status",
                "dk_numbers", "cgc_numbers", "dk_K", "cgc_K", "winner"}
    if not required.issubset(fields):
        raise ValueError("Missing ledger fields: " + str(required - set(fields)))
    all_fields = fields + [name for name in EXTRA if name not in fields]
    changed = False
    for row in ledger:
        issue = row["issue"].strip()
        if issue not in official:
            continue
        if not row["status"].startswith("FROZEN_"):
            continue
        draw_date, nums, special = official[issue]
        target_time = when(row["scheduled_draw"])
        frozen_time = when(row["freeze_time"])
        if frozen_time >= target_time:
            raise ValueError(f"{issue}: freeze not before draw")
        if target_time.date().isoformat() != draw_date:
            raise ValueError(f"{issue}: official draw date mismatch: {draw_date}")
        expected = " ".join(f"{n:02d}" for n in sorted(nums))
        if row.get("actual_numbers") and row["actual_numbers"] != expected:
            raise ValueError(f"{issue}: official numbers changed; manual review required")
        if row.get("special_number") and row["special_number"] != f"{special:02d}":
            raise ValueError(f"{issue}: official special changed; manual review required")
        quality = "FORMAL" if row["status"] in FORMAL else "PROVISIONAL_GATE0_INCOMPLETE"
        values = {"actual_numbers": expected, "special_number": f"{special:02d}",
                  "result_source": "Taiwan Lottery official history", "score_status": quality}
        for track in ("dk", "cgc"):
            if row.get(f"{track}_numbers", "").strip():
                k = len(six(row[f"{track}_numbers"]) & nums)
                prior = row.get(f"{track}_K", "")
                if prior != "" and int(prior) != k:
                    raise ValueError(f"{issue}: recorded {track} K mismatch; review required")
                values[f"{track}_K"] = str(k)
        if "dk_K" in values and "cgc_K" in values:
            a, b = int(values["dk_K"]), int(values["cgc_K"])
            values["winner"] = "DK" if a > b else "CGC" if b > a else "TIE"
        for key, val in values.items():
            if row.get(key, "") != val:
                row[key] = val
                changed = True
    if changed:
        with open(ledger_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=all_fields)
            w.writeheader()
            w.writerows(ledger)
    scored = [r for r in ledger if r.get("actual_numbers")]
    formal_n = sum(r.get("score_status") == "FORMAL" for r in scored)
    report = [
        "# DK / CGC Official Draw Scoreboard",
        "",
        "Source: Taiwan Lottery official data (see raw fetch metadata and checksum).",
        "Only Gate 0 passed pre-draw freezes enter formal forward metrics.",
        "Gate 0 incomplete records retain descriptive K but are not official validation samples.",
        "No historical/exploratory backtest is counted as forward evidence.",
        "",
        f"- Scored issues (including provisional): {len(scored)}",
        f"- Formal Gate 0 passed issues: {formal_n}",
        f"- Fair 6/49 expected K per six-number ticket: {BASE:.10f}",
        f"- {metrics(ledger, 'dk')}",
        f"- {metrics(ledger, 'cgc')}",
        "",
        "## Scored draws",
        "| Issue | Official main numbers | Special | DK K | CGC K | Better track | Gate |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for r in scored:
        report.append("| " + " | ".join([
            r["issue"], r["actual_numbers"], r["special_number"],
            r.get("dk_K", ""), r.get("cgc_K", ""),
            r.get("winner", ""), r.get("score_status", "")]) + " |")
    summary_path = Path(summary_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"scored={len(scored)} formal={formal_n} modified_ledger={changed}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: score_ledger.py official.csv dual_track_ledger.csv scoreboard.md")
    process(*sys.argv[1:])
