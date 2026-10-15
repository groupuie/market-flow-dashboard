# Claude 2026-10-15:下載樣本外 c345 + SPY 的 Yahoo 日K(2004 起、到 2026-10-14 收盤),存成和 Claude 10/13 快照同格式(manifest.json + adjusted/*.json)
#   原始資料不放 repo;結果檔只記 manifest 的 SHA-256
#   用法:python3 -I download_oos.py <名單檔> <輸出資料夾>
import json, os, sys, time, hashlib, datetime as dt
import concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '..', 'scripts'))
import astra_data as AD
ULIST, OUT = sys.argv[1], sys.argv[2]
LAST = '2026-10-14'
syms = [s.strip() for s in open(ULIST) if s.strip() and not s.startswith('#')] + ['SPY']
os.makedirs(os.path.join(OUT, 'adjusted'), exist_ok=True)
p1 = int(dt.datetime(2004, 1, 1, tzinfo=dt.timezone.utc).timestamp()); p2 = int(time.time()) + 86400
def job(s):
    for k in range(3):
        try:
            b = [list(x) for x in AD.yahoo(s, p1, p2) if x[0] <= LAST]
            return s, b, None
        except Exception as e:
            err = str(e)[:120]; time.sleep(2)
    return s, None, err
man, fail = {}, {}
with cf.ThreadPoolExecutor(8) as ex:
    for s, b, err in ex.map(job, syms):
        if not b: fail[s] = err or '沒有資料'; continue
        f = os.path.join('adjusted', s + '.json'); raw = json.dumps({'symbol': s, 'bars': b}, separators=(',', ':'))
        open(os.path.join(OUT, f), 'w').write(raw)
        man[s] = {'adjustedFile': f, 'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'first': b[0][0], 'last': b[-1][0], 'n': len(b)}
json.dump({'created_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'last': LAST, 'source': 'Yahoo chart v8, adjclose/close 比例套用到開高低收(scripts/astra_data.py yahoo())',
           'symbols': man, 'fail': fail}, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=1)
print(json.dumps({'ok': len(man), 'fail': fail, 'last_dates': sorted({v['last'] for v in man.values()})[-3:]}, ensure_ascii=False))
