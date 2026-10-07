#!/usr/bin/env python3
import sys

def parse(s):
    xs=[int(x) for x in s.replace(","," ").split()]
    if len(xs)!=6 or len(set(xs))!=6 or any(x<1 or x>49 for x in xs):
        raise SystemExit("each side must contain 6 unique integers from 1..49")
    return set(xs)

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit('usage: score_draw.py "7 8 11 23 38 41" "1 2 3 4 5 6"')
    pred=parse(sys.argv[1])
    actual=parse(sys.argv[2])
    hit=sorted(pred & actual)
    k=len(hit)
    print("hits=",hit)
    print("K=",k)
    print("misses=",6-k)
