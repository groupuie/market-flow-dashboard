# t18(2026-10-13):scripts/astra_gate.py 的 decide() — 排程閘門「有新的已收盤交易日才跑」
#   起因:10/13 第一次排程延遲 4 小時 25 分(22:45 → 03:10 UTC);舊閘門比「SPY 最後一根 == 美東今天」,延遲過美東半夜就會誤跳過
#   用法:python3 t18_gate_test.py(不連網;最後一行 ALL OK)
import os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import astra_gate as G
ET = G.ET; D = dt.date
def t(y, m, d, h, mi): return dt.datetime(y, m, d, h, mi, tzinfo=ET)
bars_1012 = [D(2026, 10, d) for d in (5, 6, 7, 8, 9, 12)]
bars_1013p = bars_1012 + [D(2026, 10, 13)]   # 隔天盤中:Yahoo 已有今天這根(還沒收)
CASES = [
    ("一般:週一 18:45 收盤後", t(2026, 10, 12, 18, 45), bars_1012, "2026-10-09", (True, "2026-10-12")),
    ("延遲到美東半夜 01:00(舊閘門會跳過)", t(2026, 10, 13, 1, 0), bars_1012, "2026-10-09", (True, "2026-10-12")),
    ("延遲到隔天開盤 10:00(有盤中棒)", t(2026, 10, 13, 10, 0), bars_1013p, "2026-10-09", (True, "2026-10-12")),
    ("已經發布過了", t(2026, 10, 13, 1, 0), bars_1012, "2026-10-12", (False, "2026-10-12")),
    ("假日(感恩節 11/26)", t(2026, 11, 26, 18, 45), [D(2026, 11, 24), D(2026, 11, 25)], "2026-11-25", (False, "2026-11-25")),
    ("週五延遲到週六 02:00", t(2026, 10, 17, 2, 0), [D(2026, 10, 15), D(2026, 10, 16)], "2026-10-15", (True, "2026-10-16")),
    ("讀不到已發布的 asof", t(2026, 10, 12, 18, 45), bars_1012, None, (True, "2026-10-12")),
]
ok = True
for name, now, bars, pub, want in CASES:
    got = G.decide(now, bars, pub); ok &= got == want
    print(("OK  " if got == want else "FAIL"), name, got)
print("ALL OK" if ok else "SOME FAIL")
sys.exit(0 if ok else 1)
