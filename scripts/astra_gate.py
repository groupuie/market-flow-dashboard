# astra-data 排程閘門(2026-10-13):有「新的已收盤交易日」才跑
#   = SPY 最後一根已收盤日K(美東 16:15 後當天才算)> astra-data 分支已發布的 asof → run=1
#   舊閘門比「SPY 最後一根 == 美東今天」:GitHub 排程延遲到美東半夜之後(台灣中午)就會誤判成非交易日而跳過;
#   10/13 第一次排程就延遲 4 小時 25 分(原定 22:45 UTC,實際 03:10 UTC),離誤跳過只差 50 分鐘。
#   假日:SPY 沒有新的一根 → 等於已發布 asof → 跳過(同舊閘門)。抓不到資料 → 照跑(fail-open,同舊閘門)。
#   只用標準函式庫、零秘密。用法(workflow):python3 scripts/astra_gate.py >> "$GITHUB_OUTPUT"
import datetime as dt, json, sys, urllib.request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PUB = "https://raw.githubusercontent.com/groupuie/market-flow-dashboard/astra-data/meta.json"
SPY = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=10d&interval=1d"


def decide(now_et, bar_dates, pub_asof):
    """now_et: 美東時間;bar_dates: SPY 日K 日期(date);pub_asof: 已發布的 'YYYY-MM-DD' 或 None → (run, 最後已收盤日)"""
    cut = now_et.date() if (now_et.hour, now_et.minute) >= (16, 15) else now_et.date() - dt.timedelta(days=1)
    done = [d for d in bar_dates if d <= cut]
    if not done: return True, None
    last = max(done).isoformat()
    return (pub_asof is None or last > pub_asof), last


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}), timeout=20).read())


def main():
    run = True
    try:
        r = get(SPY)["chart"]["result"][0]
        dates = [dt.datetime.fromtimestamp(t, ET).date() for t in r["timestamp"]]
        try: pub = get(PUB).get("asof")
        except Exception as e: pub = None; print("published meta.json unreadable → run:", e, file=sys.stderr)
        now = dt.datetime.now(ET)
        run, last = decide(now, dates, pub)
        print(f"ET now {now:%Y-%m-%d %H:%M}, SPY last closed bar {last}, published asof {pub}", file=sys.stderr)
    except Exception as e:
        print("market-day check failed → fail-open:", e, file=sys.stderr)
    print(f"run={'1' if run else '0'}")


if __name__ == "__main__":
    main()
