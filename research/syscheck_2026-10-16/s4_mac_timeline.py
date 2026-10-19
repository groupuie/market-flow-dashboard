# s4:Mac 採集器時間線(只讀 gist 的 git 歷史;不碰 token、不寫 gist)
#   ① 10/01 起 Mac 推送中斷 >45 分的空窗
#   ② 10/16 早上恢復後的推送順序(快輪 market_data → 日K分批 → 全量輪 futu_snapshot)與 market_data 裡報價區塊的新舊
#   ③ 美東晚上 20:00–22:00(Yahoo 把當天日K暫時清成 null 的時段)Mac 報價退回前一天收盤的證據(10/13 晚)
#   用法:python3 s4_mac_timeline.py <gist 的 git clone 路徑>
import json, subprocess, sys, datetime as dt
G = sys.argv[1]
def git(*a): return subprocess.run(["git", "-C", G] + list(a), capture_output=True, text=True).stdout
def md_at(h):
    try: return json.loads(git("show", f"{h}:market_data.json"))
    except Exception: return None
TW = dt.timezone(dt.timedelta(hours=8))
print("① Mac 推送空窗 >45 分(10/01 起,台灣時間)")
ts = [int(x) for x in git("log", "--format=%ct", "--since=2026-10-01T00:00:00+08:00", "--", "market_data.json").split()][::-1]
for a, b in zip(ts, ts[1:]):
    if b - a > 45 * 60:
        f = lambda t: dt.datetime.fromtimestamp(t, TW).strftime("%m/%d %H:%M")
        print(f"   {f(a)} → {f(b)}  停 {(b - a) / 3600:.1f} 小時")
print("\n② 10/16 早上恢復後的推送(台灣時間;opt=期權時間戳,cached=期權沿用快取)")
for line in git("log", "--reverse", "--format=%h %cI", "--since=2026-10-16T07:30:00+08:00", "--until=2026-10-16T08:20:00+08:00").splitlines():
    h, t = line.split()
    files = [x for x in git("show", "--name-only", "--format=", h).split() if not x.endswith(".gz64")]
    extra = ""
    if "market_data.json" in files:
        d = md_at(h)
        extra = f"ts={d['ts_utc'][11:]} opt={d.get('_options_ts')} cached={d.get('_options_cached')} NVDA={d['stocks']['NVDA']['last']}"
    kl = [x for x in files if x.startswith("kline_")]
    print(f"   {t[11:19]} {h} " + (f"日K {len(kl)} 檔({kl[0]}…{kl[-1]})" if kl else ",".join(files)) + (" " + extra if extra else ""))
print("\n③ 美東 10/13 晚上 20:00–22:00(UTC 10/14 00:00–02:00)全量輪的 NVDA 報價(10/13 收 228.52、10/12 收 226.32)")
for line in git("log", "--reverse", "--format=%h", "--since=2026-10-13T23:30:00Z", "--until=2026-10-14T03:00:00Z", "--", "futu_snapshot.json").splitlines():
    d = md_at(line.strip())
    if d: print(f"   {d['ts_utc']} UTC  NVDA {d['stocks']['NVDA']['last']}(單日 {d['stocks']['NVDA'].get('chg1d')}%)  SPY {d['market']['SPY']['last']}")
