# Claude(2026-10-14):同一檔股票、兩份下載,底/回/頂訊號哪一天不同、差多少(只描述)
#   用法:python3 c3_signal_flip.py <資料夾A> <資料夾B> <代號,代號,...>
#   訊號 = vendor/scripts/astra_data.py:sw_series(和 v0.5.0 研究釘住的同一份,研究模式:全歷史、不四捨五入)
import json, os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, '..', '..', 'astra_v0.5.0_2026-10-13', 'vendor', 'scripts', 'astra_data.py')
spec = importlib.util.spec_from_file_location('astra_data_pinned', V); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
def load(d, s):
    m = json.load(open(os.path.join(d, 'manifest.json')))['symbols'][s]
    return json.load(open(os.path.join(d, m['adjustedFile'])))['bars']
def sig(b):
    r = ad.sw_series(b); D = r['D']
    return {k: {D[i] for i in r[k]} for k in ('bot', 'b2', 'top')}, r
out = {}
for s in sys.argv[3].split(','):
    ba, bb = load(sys.argv[1], s), load(sys.argv[2], s)
    sa, ra = sig(ba); sb, rb = sig(bb)
    out[s] = {}
    for k in ('bot', 'b2', 'top'):
        only_a, only_b = sorted(sa[k] - sb[k]), sorted(sb[k] - sa[k])
        out[s][k] = {'onlyA': only_a, 'onlyB': only_b}
        for d in only_a + only_b:
            i = ra['D'].index(d)
            C = ra['C']; Cb = rb['C']
            mn_a = min(C[i-6:i+1]); mn_b = min(Cb[i-6:i+1])
            print(s, k, d, '只在', 'A' if d in only_a else 'B',
                  f"收盤A={C[i]!r} B={Cb[i]!r} 7日最低A={mn_a!r} B={mn_b!r} 昨高A={ra['H'][i-1]!r} B={rb['H'][i-1]!r}")
    print(s, {k: (len(v['onlyA']), len(v['onlyB'])) for k, v in out[s].items()})
if len(sys.argv) > 4: json.dump(out, open(sys.argv[4], 'w'), indent=1)
