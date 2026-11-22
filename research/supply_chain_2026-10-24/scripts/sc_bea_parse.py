"""BEA NAICS Codes 表解析(只用表格結構,不碰報酬)"""
import re, openpyxl

def norm(c):
    if c is None: return ""
    if isinstance(c, float) and c.is_integer(): c = int(c)
    return str(c).strip()

def parse_spec(spec):
    """'11111-2' → ['11111','11112'];'1122, 1124-5' → ['1122','1124','1125'];'23*' → ['23'];'n.a.' → []"""
    s = norm(spec)
    if s in ("", "n.a."): return []
    out = []
    for part in re.split(r"[,\n]+", s):
        p = part.strip().rstrip("*").strip()
        if not p: continue
        if "-" in p:
            a, b = [x.strip() for x in p.split("-")]
            assert a.isdigit() and b.isdigit() and len(b) <= len(a), (spec, p)
            pre, st = a[:len(a) - len(b)], int(a[len(a) - len(b):])
            for x in range(st, int(b) + 1):
                out.append(pre + str(x).zfill(len(b)))
        else:
            assert p.isdigit(), (spec, p)
            out.append(p)
    return out

def naics_sheet(fn):
    wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
    ws = wb["NAICS Codes"]
    rows = list(ws.iter_rows(min_row=6, max_col=8, values_only=True))
    summ = None; det = []; summaries = {}
    for r in rows:
        a, b, c, d, e, f, g = (norm(x) for x in r[:7])
        if b and c and not d:            # Summary 列:B = 代碼、C = 名稱
            summ = b; summaries[summ] = c; continue
        if d and e:                       # Detail 列:D = 代碼、E = 名稱、F = 註、G = NAICS
            det.append({"summary": summ, "detail": d, "title": e, "note": f, "spec": g, "prefixes": parse_spec(g)})
    return summaries, det
