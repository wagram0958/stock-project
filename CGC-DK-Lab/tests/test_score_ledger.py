#!/usr/bin/env python3
"""Offline smoke tests; no actual lottery API calls required."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "score_ledger.py"
spec = importlib.util.spec_from_file_location("score_ledger", SCRIPT)
score = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score)

FIELDS = ["issue", "scheduled_draw", "freeze_time", "status", "dk_model",
          "dk_numbers", "cgc_model", "cgc_numbers", "dk_K", "cgc_K", "winner", "notes"]
OFFICIAL = ["遊戲名稱", "期別", "開獎日期", *[f"獎號{i}" for i in range(1, 7)], "特別號"]


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class ScoreLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.history = root / "official.csv"
        self.ledger = root / "ledger.csv"
        self.out = root / "scoreboard.md"
        self.official = dict(zip(OFFICIAL, [
            "大樂透", "115000095", "2026-10-09", "01", "02", "03",
            "04", "05", "20", "07"]))
        self.entry = dict(zip(FIELDS, [
            "115000095", "2026-10-09T20:30:00+08:00",
            "2026-10-07T20:29:34+08:00", "FROZEN_GATE0_INCOMPLETE",
            "DK-v0", "01 02 03 04 05 20", "CGC-v0",
            "04 12 14 26 29 35", "", "", "", "numbers locked"]))
        self.save()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        write_csv(self.history, OFFICIAL, [self.official])
        write_csv(self.ledger, FIELDS, [self.entry])

    def run_score(self):
        score.process(self.history, self.ledger, self.out)
        return score.read_csv(self.ledger)[1][0]

    def test_provisional_is_scored_but_not_formal(self):
        r = self.run_score()
        self.assertEqual((r["dk_K"], r["cgc_K"], r["winner"]), ("6", "1", "DK"))
        self.assertEqual(r["score_status"], "PROVISIONAL_GATE0_INCOMPLETE")
        self.assertIn("Formal Gate 0 passed issues: 0", self.out.read_text())
        self.assertIn("DK: n=0", self.out.read_text())

    def test_idempotent(self):
        self.run_score()
        before = self.ledger.read_bytes()
        self.run_score()
        self.assertEqual(before, self.ledger.read_bytes())

    def test_formal_tracks_only_gate0_passed(self):
        self.entry["status"] = "FROZEN_GATE0_PASSED"
        self.save()
        r = self.run_score()
        self.assertEqual(r["score_status"], "FORMAL")
        self.assertIn("DK: n=1, mean_K=6.0000", self.out.read_text())

    def test_reject_wrong_draw_date(self):
        self.official["開獎日期"] = "2026-10-10"
        self.save()
        with self.assertRaisesRegex(ValueError, "date mismatch"):
            self.run_score()
        self.assertEqual(self.ledger.read_text().count("actual_numbers"), 0)

    def test_reject_late_freeze(self):
        self.entry["freeze_time"] = "2026-10-10T01:00:00+08:00"
        self.save()
        with self.assertRaisesRegex(ValueError, "freeze not before"):
            self.run_score()

    def test_no_draw_cannot_be_guessed(self):
        self.official["期別"] = "115000094"
        self.save()
        r = self.run_score()
        self.assertFalse(r.get("actual_numbers"))
        self.assertIn("Scored issues (including provisional): 0", self.out.read_text())

    def test_no_silent_official_revision(self):
        self.run_score()
        fields, rows = score.read_csv(self.ledger)
        rows[0]["actual_numbers"] = "01 02 03 04 05 06"
        write_csv(self.ledger, fields, rows)
        with self.assertRaisesRegex(ValueError, "official numbers changed"):
            self.run_score()


if __name__ == "__main__":
    unittest.main()
