# Score data/ai_marks.json (Claude discretionary forward marks) with Yahoo daily bars.
# usage: python3 w0_score_ai_marks.py <dir with Yahoo chart JSON per symbol> <cutoff YYYY-MM-DD>
# entry = first open strictly after the mark date; horizons = 20/40 bars from entry (close); SPY same window.
import json, sys, datetime as dt, subprocess
YH = sys.argv[1]; CUTOFF = sys.argv[2]
marks = json.loads(subprocess.check_output(['git','-C','/home/claude/market-flow-dashboard','show','origin/main:data/ai_marks.json']))['marks']
def load(s):
    j = json.load(open(f'{YH}/{s}.json'))['chart']['result'][0]
    ts = j['timestamp']; q = j['indicators']['quote'][0]
    tz = j['meta'].get('gmtoffset', -14400)
    out = []
    for i,t in enumerate(ts):
        o,c,l = q['open'][i], q['close'][i], q['low'][i]
        if o is None or c is None: continue
        d = (dt.datetime.fromtimestamp(t + tz, dt.timezone.utc)).date().isoformat()
        if d <= CUTOFF: out.append((d,o,c,l))
    return out
spy = load('SPY'); spyd = {b[0]:b for b in spy}
def fwd(bars, i0, h):
    j = i0 + h - 1
    return bars[j] if j < len(bars) else None
import re
rows = []
for sym, lst in marks.items():
    for m in lst:
        bars = load(sym)
        d = m['d']
        i0 = next(i for i,b in enumerate(bars) if b[0] > d)   # first bar strictly after issue date
        ent = bars[i0]
        r = {'sym':sym,'d':d,'k':m['k'],'conf':m['conf'],'px':m['px'],'entry_date':ent[0],'entry_open':round(ent[1],2)}
        # reference close on/just before d (sanity vs px)
        ref = [b for b in bars if b[0] <= d][-1]
        r['ref_close'] = round(ref[2],2); r['ref_date']=ref[0]
        sp0 = spyd[ent[0]][1]
        for h in (20,40):
            b = fwd(bars, i0, h)
            if b:
                ret = b[2]/ent[1]-1
                sret = spyd[b[0]][2]/sp0-1
                r[f'r{h}'] = round(100*ret,2); r[f'spy{h}'] = round(100*sret,2); r[f'x{h}'] = round(100*(ret-sret),2); r[f'd{h}']=b[0]
            else:
                r[f'r{h}'] = None
        last = bars[-1]
        r['last_date']=last[0]; r['r_last']=round(100*(last[2]/ent[1]-1),2); r['spy_last']=round(100*(spyd[last[0]][2]/sp0-1),2)
        r['bars_held_to_last'] = len(bars)-i0
        # max adverse / favorable excursion to horizon 40 (or last)
        seg = bars[i0:i0+40]
        r['min_close_40'] = round(100*(min(b[2] for b in seg)/ent[1]-1),2)
        r['max_close_40'] = round(100*(max(b[2] for b in seg)/ent[1]-1),2)
        # invalidation
        inv = m.get('invalid','')
        mm = re.search(r'跌破\s*([0-9.]+)', inv) or re.search(r'跌回\s*([0-9.]+)', inv)
        if m['k']=='抄底' and mm:
            lvl = float(mm.group(1)); r['stop']=lvl
            hit = next((b for b in bars[i0:] if b[2] < lvl), None)
            if hit: r['stop_hit']=hit[0]; r['stop_ret']=round(100*(hit[2]/ent[1]-1),2)
        rows.append(r)
json.dump(rows, open('w0_ai_marks_score.json','w'), ensure_ascii=False, indent=1)
for r in rows:
    print(r)
