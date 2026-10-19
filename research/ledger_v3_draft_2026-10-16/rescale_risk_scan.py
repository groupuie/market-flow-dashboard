#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""換尺度重播的風險掃描(Claude 2026-10-17;回應 Astra v0.7.4 附錄四 §4)
問題:持有期間遇到配息 / 分割,結案時抓的資料(帳本拿來算出場)在除息日以前會整段換尺度、再四捨五入;
v3 重播只能用「鎖定時的快照 × 比例(不再四捨五入)」重建歷史 → 兩者在第 3 位小數可能差一點點,
極少數情況會讓頂的判斷不同 → 出場對不上 → 這一筆算「無法重現」(缺漏規則:同意填 −100%、不同意 → 資訊不足)。這支程式量它多常發生。
做法:268 檔真實日K(d266),2023-01 ~ 2026-07 的每一個買點(凍結引擎),假設進場後第 2 個交易日除息 / 分割:
  帳本版 = 除息日以前 rp(價格 × f)、之後 rp(價格) 的完整歷史 → 凍結賣法算出場
  重播版 = 鎖定時快照 rp(價格) × f̂(f̂ 用重疊兩根 8 個價格估)+ 帳本版的之後 K 線 → 用 v3_verify.replay() 的同一套邏輯
  f = 0.999、0.995、0.98(配息)、0.5、0.25(分割);兩邊都用最後 400 根(同長度)
用法:python3 -I rescale_risk_scan.py <repo> <astra_v050_data> <輸出 json>
"""
import datetime as dt, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_verify as V
REPO, DATA, OUT = sys.argv[1:4]
man = json.loads(V.Git(REPO).show('origin/astra-ledger', 'engine_manifest.json')); V.load_engine(V.Git(REPO), man['main_commit'], man['files'])
AD, AT = V.AD, V.AT
dm = json.load(open(os.path.join(DATA, 'manifest.json')))['symbols']
FS = (0.999, 0.995, 0.98, 0.5, 0.25); HIST = 400; t0 = time.time()
res = {f: {'n': 0, 'mismatch': 0, 'overlap_rejected': 0, 'examples': []} for f in FS}
for s in sorted(dm):
    raw = [[b[0]] + [float(x) for x in b[1:5]] + [int(b[5] or 0)] for b in json.load(open(os.path.join(DATA, dm[s]['adjustedFile'])))['bars']]
    if len(raw) < HIST + 60: continue
    pb = [[b[0], AD.rp(b[1]), AD.rp(b[2]), AD.rp(b[3]), AD.rp(b[4]), b[5]] for b in raw]
    W0 = AD.sw_series(pb); sty = AT.style_of(s)
    nxt = {pb[j][0]: pb[j + 1][0] for j in range(len(pb) - 1)}
    V.next_session = lambda d, nxt=nxt: dt.date.fromisoformat(nxt[d if isinstance(d, str) else d.isoformat()])   # 歷史資料用自己的交易日
    for i, k in AT.buy_points(W0):
        if not ('2023-01-01' <= pb[i][0] <= '2026-07-31') or i < HIST or i + 45 >= len(pb): continue
        snap = pb[i - HIST + 1:i + 1]                                         # 鎖定時的快照(原尺度)
        for f in FS:
            E = i + 3                                                           # 進場(i+1)之後第 2 根除息 / 分割
            j0, j1 = i - HIST + 1, min(len(raw), i + 61)
            Bl = [[raw[j][0]] + [AD.rp(x * f) if (j < E or f < 0.9) else AD.rp(x) for x in raw[j][1:5]] + [raw[j][5]] for j in range(j0, j1)]; il = HIST - 1   # 帳本版:同樣 400 根歷史 + 之後
            Wl = AD.sw_series(Bl[:il + 60]); Ol = [b[1] for b in Bl[:il + 60]]
            d, why = AT.exit_of(Wl, Ol, il, sty)
            if d is None or d + 1 >= il + 60: continue
            rec = {'status': 'closed', 'entry': Bl[il + 1][0], 'exit': Bl[d + 1][0], 'exit_why': why, 'ret': AT.ret(Ol, il + 1, d + 1, 0.001),
                   'entry_open': Ol[il + 1], 'exit_open': Ol[d + 1], 'bars_used': Bl[il - 1:d + 2], 'closed_utc': Bl[d + 1][0] + 'T21:00:00Z'}
            m = {'date': pb[i][0], 'style': sty['key']}
            # replay() 用官方日曆檢查之後的 K 線;歷史資料的休市日不在 2026–2028 表裡 → 只把「下一個交易日」換成這檔自己的日期,其餘是同一支函式
            r = V.replay(m, rec, snap, V.SPEC)
            res[f]['n'] += 1
            if r[0] != 'closed':
                key = 'overlap_rejected' if '共同比例' in r[2] else 'mismatch'; res[f][key] += 1
                if len(res[f]['examples']) < 8: res[f]['examples'].append({'sym': s, 'date': pb[i][0], 'why': r[2][:160]})
    print(s, {f: (res[f]['n'], res[f]['mismatch'], res[f]['overlap_rejected']) for f in FS}, round(time.time() - t0), flush=True) if s[:1] in 'AFKPU' and s[1:2] == 'A' else None
out = {'scope': '假設每個買點進場後第 2 根除息 / 分割;不是實際發生率,是「發生時對不上的比例」', 'hist_bars': HIST, 'by_factor': {str(f): v for f, v in res.items()},
       'seconds': round(time.time() - t0)}
json.dump(out, open(OUT, 'w'), ensure_ascii=False, indent=1)
print(json.dumps({f: {k: v for k, v in r.items() if k != 'examples'} for f, r in out['by_factor'].items()}, ensure_ascii=False))
