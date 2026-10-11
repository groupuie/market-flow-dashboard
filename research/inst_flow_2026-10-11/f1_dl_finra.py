# FINRA Reg SHO 每日放空量(CNMS = 全部場外 TRF 合併),只留研究名單的股票;每個交易日一個 csv
import urllib.request, time, os, sys, json, concurrent.futures as cf, pandas as pd, io
OUT="days"; os.makedirs(OUT,exist_ok=True)
U=set(s for s,v in json.load(open('/home/claude/work/t30/meta.json')).items() if v.get('type')=='EQUITY')|{'SPY','QQQ'}
cal=pd.read_pickle('/home/claude/work/t30/yh/SPY.pkl').index
days=[d for d in cal if d>=pd.Timestamp(sys.argv[1] if len(sys.argv)>1 else '2018-08-01')]
H={"User-Agent":"curl/8.5.0","Accept":"*/*"}
def get(d):
    fn=os.path.join(OUT,d.strftime('%Y%m%d')+'.csv')
    if os.path.exists(fn): return d,'cached'
    u=f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d.strftime('%Y%m%d')}.txt"
    err=''
    for a in range(4):
        try:
            b=urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60).read().decode('utf-8','replace')
            rows=[ln for ln in b.splitlines() if ln and ln.split('|')[1:2] and ln.split('|')[1] in U]
            hdr=b.splitlines()[0]
            open(fn,'w').write(hdr+'\n'+'\n'.join(rows)+'\n'); return d,len(rows)
        except Exception as e:
            err=str(e)[:50]; time.sleep(2+3*a)
    return d,'ERR '+err
t0=time.time(); res=[]
with cf.ThreadPoolExecutor(4) as ex:
    for r in ex.map(get,days): res.append(r)
bad=[(str(d.date()),r) for d,r in res if isinstance(r,str) and r!='cached']
print('done',len(res),'%.0fs'%(time.time()-t0),'bad',len(bad),bad[:10])
