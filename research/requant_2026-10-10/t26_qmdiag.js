// t26(Codex v0.2 第 3 節):📊量化 漏標診斷 —— 只讀,在網頁裡執行,用網頁自己的序列函式(tkSeriesJS / fcSeriesJS /
// adSeriesJS / htSeriesJS / tjSeriesJS / qmAppendPathBuys / qGrade),不另寫指標公式、不改事件、不用未來報酬。
// 每一天、每一種記號,把每一道條件的結果都留下來:true = 通過、false = 擋下(blocked)、null = 資料不足(unknown)。
// 出/抄底 的冷卻要重播 fcSeriesJS 的迴圈才看得到(冷卻由「候選轉折」啟動,資金不符也會啟動 —— 照實記錄,沒有改);
// 重播結果會和 fcSeriesJS 自己的事件逐筆比對(replayMatches 必須為 true)。
function qmDiag(sym, from, to) {
  const lastDone = tjLastDone(), sb = chipBars(sym, 'd') || [], B = sb.filter(b => b[0] <= lastDone);
  const n = B.length, D = B.map(b => b[0]);
  const D0 = chipDaily(), FM = {};
  Object.keys(D0 || {}).forEach(dd => { const e = (D0[dd] || {})[sym]; if (e && e.m != null && dd <= lastDone) FM[dd] = +e.m; });
  const T = tjSeriesJS(B, FM), TK = tkSeriesJS(B), FT = FCL ? fcSeriesJS(B) : null, HT = htSeriesJS(B);
  const th = (FCL && FCL.th) || { trim: 0.35, trim_strong: 0.20, buy: 0.80, ext: 0.15, dip: 0.15, cool: 20 };
  // ---- 事件:與網頁量化層同一個順序與規則 ----
  const E = [];
  for (let j = 0; j < TK.n; j++) { if (TK.tk[j]) E.push({ w: '頂K', j, d: TK.D[j] }); if (TK.cf[j]) E.push({ w: '減碼', j, d: TK.D[j] }); }
  if (FT) FT.ev.forEach(e => E.push({ w: e.k === 'trim' ? '出' : '抄底', j: e.i, d: e.d }));
  qmAppendPathBuys(E, T);
  const QD = {};
  if (QQQK) { const ds = Object.keys(QQQK).filter(d => d <= lastDone).sort(); let s0 = 0;
    ds.forEach((d, i) => { s0 += +QQQK[d]; if (i >= 20) s0 -= +QQQK[ds[i - 20]]; if (i >= 19) QD[d] = (+QQQK[d]) < s0 / 20; }); }
  const qdOf = d => { if (d in QD) return QD[d]; if (QQQK) return null; const v = fcMktOf(d); return (v != null && FCL && FCL._mkd && d <= FCL._mkd) ? !!(v & QM.QB) : null; };
  const chuB = new Array(n).fill(false); E.forEach(x => { if (x.w === '出') chuB[x.j] = true; });
  const AD = adSeriesJS(B, qdOf, chuB);
  for (let j = 0; j < AD.n; j++) if (AD.sig[j]) E.push({ w: '加', j, d: AD.D[j] });
  for (let j = 0; j < HT.n; j++) if (HT.sig[j]) E.push({ w: '熱', j, d: HT.D[j] });
  const isAI = TK_AI.has(sym);
  // ---- 出/抄底:重播冷卻 ----
  const fc = new Array(n).fill(null); let lt = -999, lb = -999; const repT = [], repB = [];
  if (FT) for (let i = 0; i < n; i++) {
    const s20 = FT.s20, C = FT.C, ok = i >= 1 && s20[i] != null && s20[i - 1] != null;
    const dn = ok ? (C[i] < s20[i] && C[i - 1] >= s20[i - 1]) : null, up = ok ? (C[i] > s20[i] && C[i - 1] <= s20[i - 1]) : null;
    const cl = fcClimOf(D[i]);
    const r = { dn, up, ext: FT.ext[i], dip: FT.dip[i], coolT: i - lt > th.cool, coolB: i - lb > th.cool, cl,
      extOk: FT.ext[i] == null ? null : FT.ext[i] >= th.ext, dipCand: FT.dip[i] == null ? null : FT.dip[i] <= -0.10,
      dipDeep: FT.dip[i] == null ? null : FT.dip[i] <= -th.dip, climT: cl == null ? null : cl <= th.trim, climB: cl == null ? null : cl >= th.buy,
      candT: false, accT: false, candB: false, accB: false };
    if (ok) {
      if (dn && r.extOk && r.coolT) { r.candT = true; lt = i; if (r.climT) { r.accT = true; repT.push(i); } }
      if (up && r.dipCand && r.coolB) { r.candB = true; lb = i; if (r.climB && r.dipDeep) { r.accB = true; repB.push(i); } }
    }
    fc[i] = r;
  }
  const evT = FT ? FT.ev.filter(e => e.k === 'trim').map(e => e.i) : [], evB = FT ? FT.ev.filter(e => e.k === 'buy').map(e => e.i) : [];
  const replayMatches = JSON.stringify(repT) === JSON.stringify(evT) && JSON.stringify(repB) === JSON.stringify(evB);
  // ---- 每天每種記號的條件 ----
  const fin = Number.isFinite, b = v => v === null || v === undefined ? null : !!v;
  const rows = [];
  for (let i = 0; i < n; i++) {
    if (D[i] < from || D[i] > to) continue;
    const hotG = TK.hot[i] ? true : [TK.r20[i], TK.dA[i], TK.ext[i]].every(fin) ? false : null;
    const f = fc[i] || {};
    const c10 = (() => { for (let q = Math.max(0, i - 10); q <= i; q++) if (chuB[q]) return true; return false; })();
    const rawPrev = (() => { for (let q = Math.max(0, i - AD_TH.gap); q < i; q++) if (AD.raw[q]) return true; return false; })();
    const htRawPrev = (() => { for (let q = Math.max(0, i - HT_TH.gap); q < i; q++) if (HT.raw[q]) return true; return false; })();
    const pathFirst = i >= 1 && ((T.passT[i] && !T.passT[i - 1]) || (T.passC[i] && !T.passC[i - 1]) || (T.passD[i] && !T.passD[i - 1]));
    const bottomNear = E.some(x => x.w === '抄底' && x.j <= i && i - x.j <= 3);
    rows.push({
      d: D[i], i,
      '頂K': { hot: hotG, touch: fin(TK.up[i]) ? !!TK.touch[i] : null, off: fin(TK.off[i]) ? TK.off[i] >= TK_TH.off : null, mark: !!TK.tk[i],
        r20: TK.r20[i], ext50: TK.ext[i], dA: TK.dA[i], offPct: fin(TK.off[i]) ? +(TK.off[i] * 100).toFixed(4) : null },
      '減碼': { prevTopK: i >= 1 ? !!TK.tk[i - 1] : null, breakLow: i >= 1 ? B[i][4] < B[i - 1][3] : null, mark: !!TK.cf[i] },
      '出': { crossDown: f.dn ?? null, ext15: f.extOk ?? null, cool: f.coolT ?? null, climate: f.climT ?? null, candidate: !!f.candT, mark: !!f.accT,
        extPct: fin(f.ext) ? +(f.ext * 100).toFixed(2) : null, climPct: fin(f.cl) ? Math.round(f.cl * 100) : null },
      '抄底': { crossUp: f.up ?? null, dip10: f.dipCand ?? null, dip15: f.dipDeep ?? null, cool: f.coolB ?? null, climate: f.climB ?? null,
        candidate: !!f.candB, mark: !!f.accB, dipPct: fin(f.dip) ? +(f.dip * 100).toFixed(2) : null },
      '加': { steadyUp: b(AD.ut[i]), trigger: !!(AD.rsiX[i] || AD.lbT[i]), rsi40: !!AD.rsiX[i], lowerBand: !!AD.lbT[i],
        qqqBelow20: AD.mk[i] == null ? null : AD.mk[i] === true, noChu: !c10, notRepeat: !rawPrev, mark: !!AD.sig[i] },
      '熱': { tdD9to13: HT.tdD[i] == null ? null : (HT.tdD[i] >= HT_TH.tdLo && HT.tdD[i] <= HT_TH.tdHi), touch: b(HT.touch[i]),
        tdW9: HT.tdW[i] == null ? null : HT.tdW[i] >= HT_TH.tdW, touchW: b(HT.touchW[i]), notRepeat: !htRawPrev, mark: !!HT.sig[i],
        tdD: HT.tdD[i], tdW: HT.tdW[i] },
      '買': { pathFirstDay: pathFirst, pathT: !!T.passT[i], pathC: !!T.passC[i], pathD: !!T.passD[i], flowCoverageOK: b(T.fok ? T.fok(i) : null),
        noBottomNear: !bottomNear, mark: E.some(x => x.w === '買' && x.j === i) }
    });
  }
  // 狀態列「仍有效」:照抄網頁量化層的 valid()(i9 = 最後一根已收盤K)
  const i9 = n - 1, Cj = k => +B[k][4], Hj = k => +B[k][2];
  const valid = x => { const j = x.j; if (i9 - j > 10) return false; if (x.w === '頂K') return j === i9; if (x.w === '買') return i9 - j <= 5;
    if (x.w === '加') { if (i9 - j > 5) return false; for (let k = j + 1; k <= i9; k++) { const m = AD.s200[k]; if (m != null && Cj(k) < m) return false; } return true; }
    for (let k = j + 1; k <= i9; k++) { const c = Cj(k), m = T.s20a(k);
      if (x.w === '減碼' && c > Hj(j - 1)) return false;
      if (x.w === '抄底' && m != null && c < m) return false; }
    return true; };
  const evInWin = E.filter(x => x.d >= from && x.d <= to).map(x => {
    const g = (x.w === '買' || x.w === '加' || x.w === '熱') ? { g: null } : qGrade(x.w, x.j, TK.C, TK.tk, fcMktOf(x.d), isAI);
    return { w: x.w, d: x.d, j: x.j, grade: g.g, gray: g.g === 'w', barsAgo: n - 1 - x.j, validNow: x.w === '熱' ? null : valid(x) };
  });
  return { sym, lastDone, bars: n, first: D[0], last: D[n - 1], fmDays: Object.keys(FM).length, fmLast: Object.keys(FM).sort().pop() || null,
    qqqLast: QQQK ? Object.keys(QQQK).sort().pop() : null, climateLast: FCL && FCL._ld ? FCL._ld : null, replayMatches, isAI, rows, events: evInWin };
}

// 摘要:每種記號先取「核心觸發日」當底,再依固定順序找第一道沒過的條件(各類加總 = 底);null = 資料不足。
function qmDiagSummary(r) {
  const S = {}, add = (w, k) => { S[w] = S[w] || {}; S[w][k] = (S[w][k] || 0) + 1; };
  const firstFail = (o, order) => { for (const [k, lab] of order) { if (o[k] === null || o[k] === undefined) return '資料不足:' + lab; if (o[k] === false) return '擋在 ' + lab; } return null; };
  for (const row of r.rows) {
    const t = row['頂K'];
    if (t.hot === true && t.touch === true) add('頂K', t.mark ? '標出' : (t.off === null ? '資料不足:離高' : '擋在 收盤離高<5%'));
    if (t.hot === false && t.touch === true && t.off === true) add('頂K', '(另)只差 漲多');
    if (t.hot === true && t.touch === false && t.off === true) add('頂K', '(另)只差 碰上緣');
    const c = row['減碼'];
    if (c.prevTopK === true) add('減碼', c.mark ? '標出' : '擋在 沒跌破頂K低點');
    const o = row['出'];
    if (o.crossDown === true) add('出', o.mark ? '標出' : (firstFail(o, [['ext15', '20日內沒漲到50日線上15%'], ['cool', '冷卻中(20根內有候選轉折)'], ['climate', '資金不夠緊(>35%)']]) || '其他'));
    const u = row['抄底'];
    if (u.crossUp === true) add('抄底', u.mark ? '標出' : (firstFail(u, [['dip10', '20日內沒跌到50日線下10%'], ['cool', '冷卻中'], ['dip15', '跌幅10–15%(要≥15%)'], ['climate', '資金不夠寬鬆(<80%)']]) || '其他'));
    const a = row['加'];
    if (a.trigger === true) add('加', a.mark ? '標出' : (firstFail(a, [['steadyUp', '不是穩健上漲'], ['qqqBelow20', 'QQQ 沒在20日線下'], ['noChu', '當天或前10根有出'], ['notRepeat', '同一段已標過']]) || '其他'));
    const h = row['熱'];
    if (h.tdD9to13 === true && h.touch === true) add('熱', h.mark ? '標出' : (firstFail(h, [['tdW9', '週K TD<9'], ['touchW', '沒碰週布林上緣'], ['notRepeat', '同一段已標過']]) || '其他'));
    const m = row['買'];
    if (m.pathFirstDay === true) add('買', m.mark ? '標出' : (m.noBottomNear === false ? '擋在 3根內有抄底' : '其他'));
    if (m.flowCoverageOK === false) add('買', '(另)⑦資金流覆蓋不足的天');
  }
  return S;
}
