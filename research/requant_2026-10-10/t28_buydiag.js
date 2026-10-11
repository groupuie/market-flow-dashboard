// t28(Codex v0.3「買點診斷」核對)—— 只讀,在網頁裡執行,用網頁自己的函式(tjSeriesJS / tkSeriesJS / fcSeriesJS /
// htSeriesJS / adSeriesJS / qmAppendPathBuys),事件的建法照抄 renderCockpit 的量化層(與 t26_qmdiag.js 相同)。
// 另外:
//   ① adSeriesJS_noRecentHigh = 正式 adSeriesJS 的原始碼,只把 utAt 那一行換成 Codex v0.3 第 6.1 節的寫法(研究副本,不接到畫面)
//   ② adSeriesJS_dbg = 正式 adSeriesJS 原始碼,只在 return 多回傳內部的 u / ma3 / nh / s50 / s100(拿來拆「穩健上漲」的子條件)
//   ③ qmBuyDay = Codex v0.3 第 8 節的只讀診斷函式(逐字,另檔注入)
(function () {
  const src = adSeriesJS.toString();
  const OLD = "const utAt=k=>{if(k<0||!u[k]||!ma3[k])return false;for(let q=Math.max(0,k-39);q<=k;q++)if(nh[q])return true;return false;};";
  const NEW = "const utAt=k=>k>=0&&u[k]&&ma3[k];";
  if (src.split(OLD).length !== 2) throw new Error('utAt 原文找不到或不只一處');
  const RET = "return {n,D,C,s200,lo,rsi,v20,ut,rsiX,lbT,mk,raw,sig,";
  if (src.split(RET).length !== 2) throw new Error('adSeriesJS return 原文找不到或不只一處');
  (0, eval)(src.replace(OLD, NEW).replace(/^function adSeriesJS\(/, 'function adSeriesJS_noRecentHigh('));
  (0, eval)(src.replace(RET, "return {u,ma3,nh,s50,s100,n,D,C,s200,lo,rsi,v20,ut,rsiX,lbT,mk,raw,sig,").replace(/^function adSeriesJS\(/, 'function adSeriesJS_dbg('));
})();

function qm28Build(sym, variant, cut) {   // cut = 只用 ≤cut 的日K與⑦(截斷檢查用);variant = 'orig' | 'nohigh'
  const lastDone = tjLastDone(), end = cut || lastDone;
  const B = (chipBars(sym, 'd') || []).filter(b => b[0] <= lastDone && b[0] <= end);
  const D0 = chipDaily(), FM = {};
  Object.keys(D0 || {}).forEach(dd => { const e = (D0[dd] || {})[sym]; if (e && e.m != null && dd <= lastDone && dd <= end) FM[dd] = +e.m; });
  const T = tjSeriesJS(B, FM), TK = tkSeriesJS(B), FT = FCL ? fcSeriesJS(B) : null;
  const E = [];
  for (let j = 0; j < TK.n; j++) { if (TK.tk[j]) E.push({ w: '頂K', j, d: TK.D[j] }); if (TK.cf[j]) E.push({ w: '減碼', j, d: TK.D[j] }); }
  if (FT) FT.ev.forEach(e => E.push({ w: e.k === 'trim' ? '出' : '抄底', j: e.i, d: e.d }));
  qmAppendPathBuys(E, T);
  const QD = {};
  if (QQQK) { const ds = Object.keys(QQQK).filter(d => d <= lastDone).sort(); let s0 = 0;
    ds.forEach((d, i) => { s0 += +QQQK[d]; if (i >= 20) s0 -= +QQQK[ds[i - 20]]; if (i >= 19) QD[d] = (+QQQK[d]) < s0 / 20; }); }
  const qdOf = d => { if (d in QD) return QD[d]; if (QQQK) return null; const v = fcMktOf(d); return (v != null && FCL && FCL._mkd && d <= FCL._mkd) ? !!(v & QM.QB) : null; };
  const chuB = new Array(B.length).fill(false); E.forEach(x => { if (x.w === '出') chuB[x.j] = true; });
  const AD = (variant === 'nohigh' ? adSeriesJS_noRecentHigh : adSeriesJS)(B, qdOf, chuB);
  for (let j = 0; j < AD.n; j++) if (AD.sig[j]) E.push({ w: '加', j, d: AD.D[j] });
  E.sort((a, b) => a.j - b.j);
  return { B, FM, T, TK, FT, AD, E, qdOf, chuB, QD };
}

function qm28Window(sym, from, to) {   // 正式與研究副本在期間內的事件 + 每天的診斷
  const O = qm28Build(sym, 'orig'), N = qm28Build(sym, 'nohigh');
  const DBG = adSeriesJS_dbg(O.B, O.qdOf, O.chuB);
  const ev = (X, ws) => X.E.filter(x => x.d >= from && x.d <= to && ws.includes(x.w)).map(x => x.w + '|' + x.d);
  const days = [];
  for (let i = 0; i < O.B.length; i++) {
    const d = O.B[i][0]; if (d < from || d > to) continue;
    const k = i - 1, T = O.T, A = DBG;
    let nh40 = false, nhLast = null;
    for (let q = Math.max(0, k - 39); q <= k; q++) if (A.nh[q]) { nh40 = true; nhLast = O.B[q][0]; }
    let lastNH = null; for (let q = k; q >= 0; q--) if (A.nh[q]) { lastNH = O.B[q][0]; break; }
    let td10 = 0, a2 = false, a3 = false;
    for (let j = Math.max(0, i - 9); j <= i; j++) { td10 = Math.max(td10, T.tdb[j]); if ((T.pb[j] != null && T.pb[j] <= 0.35) || T.sqz[j]) a2 = true;
      const f = T.f20n(j); if (T.fok(j) && f != null && f > 0) a3 = true; }
    const day = qmBuyDay({ B: O.B, T: O.T, AD: O.AD, events: O.E, index: i });
    days.push({ d, i, close: +O.B[i][4],
      s50: T.s50a(i), s50_10ago: i >= 10 ? T.s50a(i - 10) : null, reg: T.reg[i], td10max: td10, lowOrSqz10: a2, posFlow10: a3,
      passT: T.passT[i], passTprev: i > 0 ? T.passT[i - 1] : null, passC: T.passC[i], passD: T.passD[i],
      cov20: T.cov20(i), f20r: T.f20r(i),
      prev: k >= 0 ? { d: O.B[k][0], c: +O.B[k][4], s50: A.s50[k], s100: A.s100[k], s200: A.s200[k], s200_20ago: k >= 20 ? A.s200[k - 20] : null,
        cAbove200: A.s200[k] != null && +O.B[k][4] > A.s200[k], s50gt200: A.s200[k] != null && A.s50[k] > A.s200[k],
        s200up: k >= 20 && A.s200[k] != null && A.s200[k - 20] != null && A.s200[k] > A.s200[k - 20],
        s50gt100: A.s50[k] != null && A.s100[k] != null && A.s50[k] > A.s100[k], s100gt200: A.s100[k] != null && A.s200[k] != null && A.s100[k] > A.s200[k],
        u: A.u[k], ma3: A.ma3[k], newHighIn40: nh40, lastNewHighIn40: nhLast, lastNewHighEver: lastNH } : null,
      ut: O.AD.ut[i], utNoHigh: N.AD.ut[i], rsi: O.AD.rsi[i], rsiX: O.AD.rsiX[i], lbT: O.AD.lbT[i], qqqBelow20: O.AD.mk[i], chu10: O.chuB.slice(Math.max(0, i - 10), i + 1).some(Boolean),
      rawOrig: O.AD.raw[i], sigOrig: O.AD.sig[i], rawNoHigh: N.AD.raw[i], sigNoHigh: N.AD.sig[i],
      diag: { buy: day.buy, add: { gates: day.add.gates, failed: day.add.failed, unknown: day.add.unknown, official: day.add.official,
                vs: day.add.reconstructedVsOfficial, rawVs: day.add.rawReconstructedVsOfficial },
              trend: { failed: day.trend.failed, unknown: day.trend.unknown, vs: day.trend.reconstructedVsOfficial, firstDay: day.trend.firstDay },
              cycle: { failed: day.cycle.failed, unknown: day.cycle.unknown, vs: day.cycle.reconstructedVsOfficial, firstDay: day.cycle.firstDay },
              disaster: { failed: day.disaster.failed, unknown: day.disaster.unknown, vs: day.disaster.reconstructedVsOfficial, firstDay: day.disaster.firstDay },
              obs: day.observations } });
  }
  return { sym, lastDone: tjLastDone(), bars: O.B.length, first: O.B[0][0], last: O.B[O.B.length - 1][0], fmDays: Object.keys(O.FM).length,
    qqqLast: QQQK ? Object.keys(QQQK).sort().pop() : null,
    eventsOrig: ev(O, ['買', '加', '出', '抄底', '頂K', '減碼']), eventsNoHigh: ev(N, ['買', '加', '出', '抄底', '頂K', '減碼']),
    addAllOrig: O.E.filter(x => x.w === '加').map(x => x.d), addAllNoHigh: N.E.filter(x => x.w === '加').map(x => x.d), days };
}

function qm28Prefix(sym, from, to, variant) {   // 截斷檢查:只用 ≤ 某天的資料重算,那天(含)以前的 買/加 要與全資料相同
  const F = qm28Build(sym, variant), bad = [];
  const key = X => X.E.filter(x => x.w === '買' || x.w === '加').map(x => x.w + '|' + x.d);
  const full = key(F); let n = 0;
  F.B.forEach(b => { const d = b[0]; if (d < from || d > to) return; n++;
    const P = qm28Build(sym, variant, d), a = full.filter(s => s.split('|')[1] <= d).join(','), p = key(P).join(',');
    if (a !== p) bad.push(d); });
  return { sym, variant, cutDates: n, mismatches: bad };
}
