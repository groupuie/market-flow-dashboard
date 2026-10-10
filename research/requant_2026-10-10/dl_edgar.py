# EDGAR 公司申報清單(submissions API):為 259 檔找 CIK,下載全部申報索引(含較舊分頁)— 只存 JSON
import json, os, sys, time, urllib.request
DL="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dl/edgar"
UA="market-flow-research "+json.load(open("/home/claude/tracker/config.json")).get("sec_contact","")
def get(url):
    for a in range(4):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept-Encoding":"identity"})
            with urllib.request.urlopen(req,timeout=60) as r: return r.read()
        except Exception as e:
            if "404" in str(e): return None
            time.sleep(1.5*(a+1))
    return None
meta=json.load(open("/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dt/meta.json"))
eq=[s for s,v in meta.items() if v.get("type")=="EQUITY"]
ct=json.loads(get("https://www.sec.gov/files/company_tickers.json"))
m={v["ticker"].upper():int(v["cik_str"]) for v in ct.values()}
json.dump(m,open(f"{DL}/ticker_cik.json","w"))
miss=[]
for s in eq:
    cik=m.get(s.replace("-",".")) or m.get(s)
    if not cik: miss.append(s); continue
    fn=f"{DL}/{s}.json"
    if os.path.exists(fn): continue
    j=get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"); time.sleep(0.15)
    if not j: miss.append(s); continue
    d=json.loads(j); out={"cik":cik,"name":d.get("name"),"recent":d["filings"]["recent"],"files":[]}
    for f in d["filings"].get("files",[]):
        jj=get("https://data.sec.gov/submissions/"+f["name"]); time.sleep(0.15)
        if jj: out["files"].append(json.loads(jj))
    json.dump(out,open(fn,"w")); print(time.strftime("%H:%M:%S"),s,cik,len(out["files"]),flush=True)
print("MISSING",miss,flush=True); print("DONE",flush=True)
