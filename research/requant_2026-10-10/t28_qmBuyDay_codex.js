// Codex v0.3 第 8 節 qmBuyDay(逐字抄自使用者貼上的交班文件)
// Read-only explanation of existing rules; booleans are true/false/null (unknown).
// Call after official events are built. This helper never creates or edits signals.
function qmBuyDay({ B, T, AD, events, index: i }) {
  if (!Number.isInteger(i) || i < 0 || i >= B.length || !Array.isArray(events)) throw new Error('Invalid diagnostic input');
  const finite = Number.isFinite, bool = v => typeof v === 'boolean' ? v : null;
  const and = a => a.includes(false) ? false : a.includes(null) ? null : true;
  const or = a => a.includes(true) ? true : a.includes(null) ? null : false;
  const compare = (a, b) => a == null || b == null ? 'unknown' : a === b ? 'match' : 'mismatch';
  const coverage = j => finite(T.cov20(j)) && T.fok(j) ? true : null;
  const flowPositive = j => coverage(j) === true && finite(T.f20n(j)) ? T.f20n(j) > 0 : null;
  const low = (j, threshold) => finite(T.pb[j]) || finite(T.bw[j])
    ? (finite(T.pb[j]) && T.pb[j] <= threshold) || !!T.sqz[j] : null;
  const td = (j, threshold) => j >= 4 && finite(T.tdb[j]) ? T.tdb[j] >= threshold : null;
  const below = j => finite(T.C[j]) && finite(T.lo[j]) ? T.C[j] < T.lo[j] : null;
  const scan = (n, predicate) => {
    const hits = [], unknownDates = [], values = [];
    for (let j = Math.max(0, i - n + 1); j <= i; j++) {
      const value = predicate(j); values.push(value);
      if (value === true) hits.push(B[j][0]); else if (value == null) unknownDates.push(B[j][0]);
    }
    return { pass: or(values), dates: hits, unknownDates };
  };
  const recent = { td6: scan(10, j => td(j, 6)), td9: scan(10, j => td(j, 9)),
    lowOrSqueeze: scan(10, j => low(j, 0.35)), positiveFlow: scan(10, flowPositive),
    closedBelowLower: scan(10, below), td9Last5: scan(5, j => td(j, 9)) };
  const pack = (gates, official, firstDay = null) => {
    const reconstructed = and(Object.values(gates));
    return { gates, failed: Object.keys(gates).filter(k => gates[k] === false),
      unknown: Object.keys(gates).filter(k => gates[k] == null), reconstructed,
      official, reconstructedVsOfficial: compare(reconstructed, official), firstDay };
  };
  const first = values => i === 0 ? false : bool(values[i]) == null || bool(values[i - 1]) == null
    ? null : values[i] && !values[i - 1];
  const regime = T.reg[i] === 'trend' || T.reg[i] === 'cycle' ? T.reg[i] : null;
  const aboveLower = finite(T.C[i]) && finite(T.lo[i]) ? T.C[i] > T.lo[i] : null;
  const return20 = i >= 20 && T.C[i - 20] > 0 ? T.C[i] / T.C[i - 20] - 1 : null;
  const flow5 = T.sl5(i), cov20 = T.cov20(i);
  const trend = pack({ trendRegime: regime == null ? null : regime === 'trend', td6In10: recent.td6.pass,
    lowOrSqueezeIn10: recent.lowOrSqueeze.pass, positiveFlowIn10: recent.positiveFlow.pass }, bool(T.passT[i]), first(T.passT));
  const cycle = pack({ cycleRegime: regime == null ? null : regime === 'cycle', lowOrSqueezeToday: low(i, 0.2),
    td9In5: recent.td9Last5.pass, flowCoverage20: coverage(i), flow20Positive: flowPositive(i),
    return20AtMost2Percent: finite(return20) ? return20 <= 0.02 : null }, bool(T.passC[i]), first(T.passC));
  const disaster = pack({ td9In10: recent.td9.pass, closedBelowLowerIn10: recent.closedBelowLower.pass,
    nowAboveLower: aboveLower, flowCoverage20: coverage(i), flow5Positive: finite(flow5) ? flow5 > 0 : null }, bool(T.passD[i]), first(T.passD));
  const exitDates = events.filter(e => e.w === '出' && e.j >= i - 10 && e.j <= i).map(e => e.d);
  const rawRecent = AD.raw.slice(Math.max(0, i - 10), i).some(v => v === true);
  const rsiCross = finite(AD.rsi[i]) && finite(AD.rsi[i - 1]) ? bool(AD.rsiX[i]) : null;
  const lowerTouch = i >= 29 && finite(AD.lo[i]) ? bool(AD.lbT[i]) : null;
  const addGates = { stableUptrend: i >= 220 && finite(AD.s200[i - 21]) ? bool(AD.ut[i]) : null,
    rsiCrossOrFirstLowerTouch: or([rsiCross, lowerTouch]), qqqBelow20: bool(AD.mk[i]),
    noExitTodayAndPrevious10: exitDates.length === 0, noRawAddPrevious10: rawRecent ? false : i >= 10 ? true : null };
  const add = pack(addGates, bool(AD.sig[i]));
  const rawReconstructed = and(Object.values(addGates).slice(0, 4));
  Object.assign(add, { rsiCross, firstLowerTouch: lowerTouch, exitDates, rawOfficial: bool(AD.raw[i]),
    rawReconstructed, rawReconstructedVsOfficial: compare(rawReconstructed, bool(AD.raw[i])) });
  const bottomDates = events.filter(e => e.w === '抄底' && e.j <= i && i - e.j <= 3).map(e => e.d);
  const anyPathFirstDay = or([trend.firstDay, cycle.firstDay, disaster.firstDay]);
  const reconstructedBuy = and([anyPathFirstDay, bottomDates.length === 0]);
  const officialBuy = events.some(e => e.w === '買' && e.j === i);
  const meanVolume = (start, end) => {
    if (start < 0) return null;
    const v = B.slice(start, end + 1).map(b => b[5]);
    return v.every(x => finite(x) && x >= 0) ? v.reduce((s, x) => s + x, 0) / v.length : null;
  };
  const v5 = meanVolume(i - 4, i), v20Previous = meanVolume(i - 24, i - 5);
  return { date: B[i][0], index: i, regime, trend, cycle, disaster, add, recent,
    buy: { anyPathFirstDay, suppressedByKnownBottomDates: bottomDates, reconstructed: reconstructedBuy,
      official: officialBuy, reconstructedVsOfficial: compare(reconstructedBuy, officialBuy) },
    observations: { tdBuy: T.tdb[i], percentB: T.pb[i], squeeze: T.sqz[i], coverage20: cov20,
      flow20MillionUSD: T.f20r(i), normalizedFlow20: T.f20n(i), flow5MillionUSD: flow5,
      rsi14: AD.rsi[i], volumeShares: B[i][5], volume5ToPrevious20: finite(v5) && v20Previous > 0 ? v5 / v20Previous : null },
    notes: { rsi: 'RSI不是買的三路徑條件；RSI首次跌至40是加的候選觸發之一。',
      volume: '量比僅供觀察，不是目前買或加的門檻；squeeze是價格帶寬，不是成交量縮。',
      unknown: 'null表示資料或暖機不足；不可當作已證實條件不成立。',
      scope: '只讀診斷，所有買加事件仍以原函式為準。' } };
}
