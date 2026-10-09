import json, urllib.request, urllib.parse, os, concurrent.futures as cf
DT="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt"
UA={"User-Agent":"Mozilla/5.0"}
uni=json.load(open(os.path.join(DT,"universe.json")))
def f(s):
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?range=5d&interval=1d",headers=UA),timeout=30).read())
        m=d["chart"]["result"][0]["meta"]; return s,{"type":m.get("instrumentType"),"name":m.get("longName") or m.get("shortName"),"first":m.get("firstTradeDate")}
    except Exception as e: return s,{"err":str(e)[:60]}
with cf.ThreadPoolExecutor(8) as ex: meta=dict(ex.map(f,uni))
json.dump(meta,open(os.path.join(DT,"meta.json"),"w"),ensure_ascii=False)
from collections import Counter
print(Counter(v.get("type") for v in meta.values()))
etf=[s for s,v in meta.items() if v.get("type")=="ETF"]
print("ETF:"," ".join(etf))
