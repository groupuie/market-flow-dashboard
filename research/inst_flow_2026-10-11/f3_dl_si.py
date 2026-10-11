# FINRA 合併短倉(consolidatedShortInterest,公開資料集、免金鑰)— 每檔一個 POST,存原始 JSON
import json, os, sys, time, urllib.request, concurrent.futures as cf
OUT = "/home/claude/work/finra_si/raw"
U = sorted(s for s, v in json.load(open('/home/claude/work/t30/meta.json')).items() if v.get('type') == 'EQUITY')
URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
H = {"User-Agent": "curl/8.5.0", "Accept": "application/json", "Content-Type": "application/json"}
F = ["settlementDate", "symbolCode", "marketClassCode", "daysToCoverQuantity", "currentShortPositionQuantity",
     "averageDailyVolumeQuantity", "previousShortPositionQuantity", "revisionFlag", "stockSplitFlag"]
def get(s):
    fn = os.path.join(OUT, s + ".json")
    if os.path.exists(fn): return s, "cached"
    body = json.dumps({"compareFilters": [{"compareType": "EQUAL", "fieldName": "symbolCode", "fieldValue": s}],
                       "limit": 5000, "fields": F}).encode()
    err = ""
    for a in range(5):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=H, method="POST"), timeout=60)
            txt = r.read().decode()
            d = json.loads(txt) if txt.strip() else []
            json.dump(d, open(fn, "w")); return s, len(d)
        except Exception as e:
            err = str(e)[:60]; time.sleep(2 + 4 * a)
    return s, "ERR " + err
t0 = time.time(); res = []
with cf.ThreadPoolExecutor(3) as ex:
    for r in ex.map(get, U): res.append(r)
bad = [r for r in res if isinstance(r[1], str) and r[1] != "cached"]
print("done", len(res), "%.0fs" % (time.time() - t0), "bad", len(bad), bad[:10])
print("zero", [r[0] for r in res if r[1] == 0][:30])
