#!/usr/bin/env python3
import csv, sys, math
from collections import Counter

NUM_FIELDS=[f"獎號{i}" for i in range(1,7)]
BASE=36/49

def load(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    rows.sort(key=lambda r: str(r["期別"]))
    draws=[]
    for r in rows:
        draws.append((str(r["期別"]), set(int(r[c]) for c in NUM_FIELDS)))
    return draws

def rank_freq(history, window):
    c=Counter(n for d in history[-window:] for n in d)
    return sorted(range(1,50), key=lambda n:(-c[n], n))[:6]

def rank_omission(history):
    last={n:10**9 for n in range(1,50)}
    for lag,d in enumerate(reversed(history), start=1):
        for n in d:
            if last[n]==10**9: last[n]=lag
    return sorted(range(1,50), key=lambda n:(-last[n], n))[:6]

def rank_mix(history):
    c20=Counter(n for d in history[-20:] for n in d)
    c50=Counter(n for d in history[-50:] for n in d)
    last={n:len(history)+1 for n in range(1,50)}
    for lag,d in enumerate(reversed(history), start=1):
        for n in d:
            if last[n]==len(history)+1: last[n]=lag
    # Fixed, preregistered exploratory score. Do not tune on test results.
    vals=[]
    for n in range(1,50):
        score=0.55*(c20[n]/20)+0.35*(c50[n]/50)+0.10*min(last[n],30)/30
        vals.append((score,n))
    return [n for _,n in sorted(vals,key=lambda x:(-x[0],x[1]))[:6]]

def hit(pred, actual):
    return len(set(pred)&actual)

def main(path, min_history=100):
    draws=load(path)
    methods={
        "freq20":lambda h:rank_freq(h,20),
        "freq50":lambda h:rank_freq(h,50),
        "omission":rank_omission,
        "mix_fixed_v0":rank_mix,
    }
    totals={k:0 for k in methods}
    n=0
    for i in range(min_history,len(draws)):
        issue,actual=draws[i]
        hist=[d for _,d in draws[:i]]
        for name,fn in methods.items():
            totals[name]+=hit(fn(hist),actual)
        n+=1

    print(f"evaluated_draws={n}")
    print(f"uniform_expected_mean_K={BASE:.10f}")
    for name,total in totals.items():
        mean=total/n if n else float("nan")
        print(f"{name}: total_hits={total}, mean_K={mean:.6f}, delta_vs_uniform={mean-BASE:.6f}")
    print("NOTE: These are exploratory walk-forward results only, not forward evidence.")

if __name__=="__main__":
    if len(sys.argv)<2:
        raise SystemExit("usage: walk_forward_backtest.py official.csv [min_history]")
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv)>2 else 100)
