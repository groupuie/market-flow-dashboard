# -*- coding: utf-8 -*-
"""FS1 往前封存:共用函式(路徑、French 資料、時間、雜湊)。協定見 ../PROTOCOL_FS1.md。"""
import os, io, re, json, time, hashlib, zipfile, subprocess, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("FS1_BASE") or os.path.dirname(HERE)            # forward/fs1(自我測試可改到暫存資料夾)
CARDS, PACKETS, SCORES, PENDING = (os.path.join(BASE, x) for x in ("cards", "packets", "scores", "pending"))
LEDGER = os.path.join(BASE, "ledger.jsonl")
IND = json.load(open(os.path.join(os.path.dirname(HERE), "industries49.json"), encoding="utf-8"))
CODES = [x["code"] for x in IND]
FRENCH = {"ind49": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_CSV.zip",
          "ff": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"}
ET = ZoneInfo("America/New_York"); UTC = dt.timezone.utc
RULES = {"max_weight": 0.15, "max_searches": 15, "min_claims": 5, "over_calls": [3, 10], "under_calls": [0, 5], "top_n": 10, "note_max_chars": 60}
BRANCH = "sector-forward-ledger"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(open(p, "rb").read())


def now_utc():
    return dt.datetime.now(UTC).replace(microsecond=0)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s):
    """ISO 日期或日期時間 → UTC datetime;只有日期 = 該日 00:00 UTC"""
    s = str(s).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def month_str(p):
    return f"{p.year:04d}-{p.month:02d}"


def last_weekday(year, month):
    d = (pd.Period(f"{year}-{month:02d}", "M").end_time.normalize()).date()
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def first_weekday(year, month):
    d = dt.date(year, month, 1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def decision_month(t_utc):
    """決定月 t = 最近一個「最後一個平日 16:00(美東)已經過去」的月份(假日不另外處理 → 偏保守)"""
    e = t_utc.astimezone(ET); p = pd.Period(f"{e.year}-{e.month:02d}", "M")
    for cand in (p, p - 1):
        lw = last_weekday(cand.year, cand.month)
        if e >= dt.datetime(lw.year, lw.month, lw.day, 16, 0, tzinfo=ET):
            return cand
    return p - 2


def first_open_utc(t):
    """月 t+1 第一個平日 09:30(美東)= 封存期限(假日不另外處理 → 偏保守)"""
    n = t + 1; d = first_weekday(n.year, n.month)
    return dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET).astimezone(UTC)


def fetch(url, dest, tries=3):
    err = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fs1-ledger/1.0"}), timeout=120) as r:
                b = r.read()
            os.makedirs(os.path.dirname(dest), exist_ok=True); open(dest, "wb").write(b)
            return b
        except Exception as e:                       # noqa: BLE001
            err = e; time.sleep(5 * (k + 1))
    raise RuntimeError(f"下載失敗:{url}:{err}")


def french_monthly(zip_bytes, anchor):
    """French CSV zip → (月報酬 DataFrame(小數), 檔頭的 CRSP 版本 YYYYMM)。anchor = 那一段之前的標題行開頭"""
    z = zipfile.ZipFile(io.BytesIO(zip_bytes)); text = z.read(z.namelist()[0]).decode("latin-1"); lines = text.splitlines()
    m = re.search(r"using the (\d{6}) CRSP database", text)
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(anchor))
    hdr = None; rows = []
    for l in lines[i + 1:]:
        s = l.strip()
        if not s:
            if rows:
                break
            continue
        if s.startswith(","):
            if rows:
                break
            hdr = [c.strip() for c in s.split(",")[1:]]; continue
        parts = [p.strip() for p in l.split(",")]
        if not (parts[0].isdigit() and len(parts[0]) == 6):
            break
        rows.append([parts[0]] + [float(x) for x in parts[1:]])
    df = pd.DataFrame([r[1:] for r in rows], columns=hdr, index=pd.PeriodIndex([f"{r[0][:4]}-{r[0][4:]}" for r in rows], freq="M"))
    return df.mask(df <= -99.99) / 100, (m.group(1) if m else None)


def load_french(workdir):
    """抓 49 產業(市值加權)與 F-F 因子;回傳 dict(R, MKT, RF, 版本, 指紋)"""
    b49 = fetch(FRENCH["ind49"], os.path.join(workdir, "49_Industry_Portfolios_CSV.zip"))
    bff = fetch(FRENCH["ff"], os.path.join(workdir, "F-F_Research_Data_Factors_CSV.zip"))
    R, v49 = french_monthly(b49, "Average Value Weighted Returns -- Monthly")
    FF, vff = french_monthly(bff, "The annual TBill return")
    assert list(R.columns) == CODES, "French 49 產業欄位和 industries49.json 不同"
    return {"R": R, "MKT": FF["Mkt-RF"] + FF["RF"], "RF": FF["RF"], "ind49_vintage": v49, "ff_vintage": vff,
            "ind49_sha256": sha256_bytes(b49), "ff_sha256": sha256_bytes(bff)}


def s0_scores(R, end):
    """S0_fwd:月 end−10 ~ end 共 11 個月的累計報酬(缺任何一個月 → NaN)"""
    win = R[(R.index >= end - 10) & (R.index <= end)]
    if len(win) != 11:
        raise ValueError("S0 視窗不足 11 個月")
    return np.expm1(np.log1p(win).sum(min_count=11)).where(win.notna().all())


def rank_codes(scores):
    """分數高 → 前;同分照欄位順序;缺值排最後(照欄位順序)"""
    pos = {c: j for j, c in enumerate(CODES)}
    have = [c for c in CODES if pd.notna(scores.get(c))]; miss = [c for c in CODES if c not in have]
    return sorted(have, key=lambda c: (-float(scores[c]), pos[c])) + miss


def read_ledger(path=None):
    p = path or LEDGER
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd or BASE, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失敗:{r.stderr.strip()[:300]}")
    return r.stdout.strip()


def git_commit_push(paths, msg, push=True):
    root = git("rev-parse", "--show-toplevel")
    br = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if br != BRANCH:
        raise RuntimeError(f"目前分支是 {br},不是 {BRANCH};不提交")
    git("add", *paths, cwd=root)
    if not git("diff", "--cached", "--name-only", cwd=root):
        return "沒有變更"
    git("commit", "-q", "-m", msg, cwd=root)
    if push:
        for k in range(3):
            try:
                git("push", "-q", "origin", f"HEAD:{BRANCH}", cwd=root); break
            except RuntimeError:
                if k == 2:
                    raise
                git("pull", "-q", "--rebase", "origin", BRANCH, cwd=root); time.sleep(3)
    return git("rev-parse", "HEAD", cwd=root)
