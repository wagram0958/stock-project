#!/usr/bin/env python3
import csv, sys
from datetime import datetime

NUM_FIELDS=[f"獎號{i}" for i in range(1,7)]
REQUIRED=["遊戲名稱","期別","開獎日期",*NUM_FIELDS,"特別號"]

def fail(msg):
    raise SystemExit(msg)

def main(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if not rows: fail("empty dataset")
    missing=[c for c in REQUIRED if c not in rows[0]]
    if missing: fail("missing columns: "+",".join(missing))

    seen=set()
    prev_date=None
    errors=[]
    for i,r in enumerate(rows, start=2):
        issue=str(r["期別"]).strip()
        if issue in seen: errors.append((i,"duplicate_issue",issue))
        seen.add(issue)

        try:
            nums=[int(r[c]) for c in NUM_FIELDS]
            special=int(r["特別號"])
        except Exception:
            errors.append((i,"non_integer_number",""))
            continue

        if len(set(nums))!=6: errors.append((i,"duplicate_main_number",nums))
        if any(n<1 or n>49 for n in nums): errors.append((i,"main_out_of_range",nums))
        if special<1 or special>49: errors.append((i,"special_out_of_range",special))
        if special in nums: errors.append((i,"special_mixed_or_duplicate",special))

        raw_date=str(r["開獎日期"]).strip()
        parsed=None
        for fmt in ("%Y/%m/%d","%Y-%m-%d","%Y%m%d"):
            try:
                parsed=datetime.strptime(raw_date,fmt).date()
                break
            except ValueError:
                pass
        if parsed is None:
            errors.append((i,"bad_date",raw_date))
        elif prev_date and parsed < prev_date:
            errors.append((i,"date_not_ascending",raw_date))
        if parsed: prev_date=parsed

        game=str(r["遊戲名稱"])
        if "大樂透" not in game:
            errors.append((i,"wrong_game",game))

    print(f"rows={len(rows)}")
    print(f"unique_issues={len(seen)}")
    print(f"errors={len(errors)}")
    for e in errors[:100]:
        print(e)
    if errors:
        raise SystemExit(2)

if __name__=="__main__":
    if len(sys.argv)!=2:
        fail("usage: validate_history.py official.csv")
    main(sys.argv[1])
