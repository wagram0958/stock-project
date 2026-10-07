#!/usr/bin/env python3
import csv, sys
from collections import Counter, defaultdict

NUM_FIELDS=[f"獎號{i}" for i in range(1,7)]

def load(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    rows.sort(key=lambda r: str(r["期別"]))
    return rows

def main(path, out_path):
    rows=load(path)
    history=[]
    out=[]
    for r in rows:
        nums=sorted(int(r[c]) for c in NUM_FIELDS)
        counts20=Counter(n for draw in history[-20:] for n in draw)
        counts50=Counter(n for draw in history[-50:] for n in draw)
        counts100=Counter(n for draw in history[-100:] for n in draw)

        last_seen={n:None for n in range(1,50)}
        for lag,draw in enumerate(reversed(history), start=1):
            for n in draw:
                if last_seen[n] is None:
                    last_seen[n]=lag

        prev=set(history[-1]) if history else set()
        for n in range(1,50):
            out.append({
                "target_issue":r["期別"],
                "number":n,
                "freq20":counts20[n],
                "freq50":counts50[n],
                "freq100":counts100[n],
                "omission":last_seen[n] if last_seen[n] is not None else "",
                "in_prev_draw":int(n in prev),
                "target_y":int(n in nums),
                "history_n":len(history)
            })
        history.append(nums)

    fields=["target_issue","number","freq20","freq50","freq100","omission","in_prev_draw","target_y","history_n"]
    with open(out_path,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader(); w.writerows(out)
    print(f"feature_rows={len(out)}")

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("usage: build_features.py official.csv features.csv")
    main(sys.argv[1],sys.argv[2])
