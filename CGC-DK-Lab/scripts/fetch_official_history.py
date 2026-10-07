#!/usr/bin/env python3
"""Fetch Taiwan Lotto 6/49 history from Taiwan Lottery's official JSON API.

Source:
https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result

For each target month:
  ?period=&month=YYYY-MM&pageSize=31

Writes:
- data/raw/lotto649_official.json
- data/cleaned/lotto649_official.csv
- data/raw/lotto649_official.sha256
- data/raw/fetch_metadata.json
"""
from __future__ import annotations
import csv, hashlib, json, ssl, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

BASE="https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result"
START="2004-01"
TW=timezone(timedelta(hours=8))
UA="Mozilla/5.0 CGC-DK-Lab/1.1"
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"data"/"raw"
CLEAN=ROOT/"data"/"cleaned"

def months(start,end):
    sy,sm=map(int,start.split("-")); ey,em=map(int,end.split("-"))
    y,m=sy,sm
    while (y,m)<=(ey,em):
        yield f"{y:04d}-{m:02d}"
        m+=1
        if m==13: y,m=y+1,1

def sslctx():
    ctx=ssl.create_default_context()
    if hasattr(ssl,"VERIFY_X509_STRICT"):
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx

def get_month(month,retries=4):
    url=f"{BASE}?period=&month={month}&pageSize=31"
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
    last=None
    for attempt in range(1,retries+1):
        try:
            with urllib.request.urlopen(req,timeout=30,context=sslctx()) as r:
                payload=json.loads(r.read().decode("utf-8"))
            return payload,url
        except Exception as e:
            last=e
            if attempt<retries: time.sleep(1.5*attempt)
    raise RuntimeError(f"{month}: {last}")

def rows_from(payload):
    c=payload.get("content") or {}
    arr=c.get("lotto649Res")
    if arr is None:
        arr=next((v for v in c.values() if isinstance(v,list)),[])
    out=[]
    for r in arr:
        nums=list(r.get("drawNumberSize") or [])
        if len(nums)<7:
            continue
        main=nums[:6]; special=nums[6]
        out.append({
            "遊戲名稱":"大樂透",
            "期別":str(r.get("period","")),
            "開獎日期":str(r.get("lotteryDate",""))[:10],
            "獎號1":main[0],"獎號2":main[1],"獎號3":main[2],
            "獎號4":main[3],"獎號5":main[4],"獎號6":main[5],
            "特別號":special,
        })
    return out

def validate(rows):
    seen=set(); errs=[]
    for r in rows:
        p=r["期別"]
        if not p: errs.append([p,"missing_period"])
        if p in seen: errs.append([p,"duplicate_period"])
        seen.add(p)
        nums=[int(r[f"獎號{i}"]) for i in range(1,7)]
        sp=int(r["特別號"])
        if len(set(nums))!=6: errs.append([p,"duplicate_main"])
        if any(n<1 or n>49 for n in nums): errs.append([p,"main_range"])
        if sp<1 or sp>49: errs.append([p,"special_range"])
        if sp in nums: errs.append([p,"special_duplicates_main"])
    return errs

def main():
    RAW.mkdir(parents=True,exist_ok=True); CLEAN.mkdir(parents=True,exist_ok=True)
    today=datetime.now(TW).date()
    end=f"{today.year:04d}-{today.month:02d}"
    all_rows=[]; raw_months=[]; skipped=[]
    for month in months(START,end):
        try:
            payload,url=get_month(month)
            raw_months.append({"month":month,"url":url,"payload":payload})
            all_rows.extend(rows_from(payload))
        except Exception as e:
            skipped.append({"month":month,"error":str(e)})
        time.sleep(0.15)
    # Dedupe by period, sort numerically. Keep last identical source row.
    by_period={r["期別"]:r for r in all_rows if r["期別"]}
    rows=sorted(by_period.values(),key=lambda r:int(r["期別"]))
    errors=validate(rows)
    if errors:
        print(json.dumps(errors[:20],ensure_ascii=False,indent=2))
        raise SystemExit("validation failed")
    raw_bytes=json.dumps(raw_months,ensure_ascii=False,sort_keys=True).encode()
    (RAW/"lotto649_official.json").write_bytes(raw_bytes)
    sha=hashlib.sha256(raw_bytes).hexdigest()
    (RAW/"lotto649_official.sha256").write_text(sha+"\n",encoding="utf-8")
    meta={
        "source":BASE,
        "retrieved_at_asia_taipei":datetime.now(TW).isoformat(),
        "start_month":START,"end_month":end,
        "rows":len(rows),"skipped_months":skipped,"sha256_raw_json":sha,
    }
    (RAW/"fetch_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    fields=["遊戲名稱","期別","開獎日期","獎號1","獎號2","獎號3","獎號4","獎號5","獎號6","特別號"]
    with open(CLEAN/"lotto649_official.csv","w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(json.dumps(meta,ensure_ascii=False,indent=2))
    if skipped:
        print(f"WARNING skipped_months={len(skipped)}",file=sys.stderr)

if __name__=="__main__":
    main()
