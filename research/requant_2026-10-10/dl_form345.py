# 下載 SEC Form 3/4/5 季度資料集(2007Q1–2026Q3)— 只下載,不解析;失敗的季度記錄後略過
import json, os, sys, time, urllib.request
DL="/tmp/claude-0/-home-claude/d0a676e0-fcd7-5eae-bc26-2609f6d7a033/scratchpad/dl/form345"
UA="market-flow-research "+json.load(open("/home/claude/tracker/config.json")).get("sec_contact","")
qs=[(y,q) for y in range(2007,2027) for q in (1,2,3,4) if (y,q)<=(2026,3)]
for y,q in qs:
    fn=f"{DL}/{y}q{q}_form345.zip"
    if os.path.exists(fn) and os.path.getsize(fn)>100000: continue
    url=f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"
    for a in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA})
            with urllib.request.urlopen(req,timeout=180) as r, open(fn+".part","wb") as f:
                while True:
                    b=r.read(1<<20)
                    if not b: break
                    f.write(b)
            os.replace(fn+".part",fn); print(time.strftime("%H:%M:%S"),"ok",y,q,os.path.getsize(fn),flush=True); break
        except Exception as e:
            print(time.strftime("%H:%M:%S"),"fail",y,q,a,str(e)[:120],flush=True); time.sleep(3)
    time.sleep(0.5)
print("DONE",flush=True)
