/* Astra dashboard adapter v0.1.0. No network calls or persistence. */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./astra-flow.js'));
  } else {
    root.AstraDashboard = factory(root.AstraFlow);
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (AstraFlow) {
  'use strict';

  const VERSION = '0.1.0';
  const KINDS = ['ENTRY', 'EXIT', 'WATCH'];
  const STYLE = {
    ENTRY: { color: '#22d3ee', symbol: 'triangle-up', label: 'A進', position: 'bottom center' },
    EXIT: { color: '#f472b6', symbol: 'triangle-down', label: 'A出', position: 'top center' },
    WATCH: { color: '#fbbf24', symbol: 'diamond-open', label: 'A候', position: 'top center' }
  };
  const REASONS = {
    PERSISTENT_PRESSURE_BREAKOUT: '持續買壓突破', DRY_BASE_RECLAIM: '量縮守穩轉強',
    CLOSE_BELOW_RISK_LINE: '收盤跌破風險線',
    TWO_CLOSES_WEAK_WITH_NEGATIVE_PRESSURE: '連續轉弱且壓力負向',
    DISTRIBUTION_BELOW_SIGNAL_AVWAP: '跌破訊號日起成交均價並出現賣壓',
    DRY_BASE_WAIT_CONFIRMATION: '量縮守穩，等待轉強確認',
    PRESSURE_WAIT_CONFIRMATION: '買壓持續，等待其他條件確認'
  };
  const GATES = { LIQUIDITY: '成交金額／股價', VOLATILITY: '波動範圍', TREND: '股價趨勢',
    BENCHMARK_DATA: 'SPY資料', MARKET: '大盤條件', RELATIVE_STRENGTH: '相對強勢',
    PRESSURE: '持續買壓', EXTENSION: '追價限制', COOLDOWN: '冷卻期', TRIGGER: '轉強觸發', WARMUP: '歷史長度' };

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function validDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function convert(rawBars, asOfDate, name) {
    if (!Array.isArray(rawBars)) throw new TypeError(name + ' must be an array');
    return rawBars.map(function (bar, i) {
      if (!Array.isArray(bar) || bar.length < 6 || !validDate(bar[0])) {
        throw new TypeError(name + '[' + i + '] must be [YYYY-MM-DD, open, high, low, close, volume]');
      }
      // Do not coerce null, empty strings, or NaN to zero. Core validates OHLCV.
      const numeric = function (value) {
        return value === null || value === '' || typeof value === 'boolean' ? NaN : Number(value);
      };
      return {
        date: bar[0], open: numeric(bar[1]), high: numeric(bar[2]), low: numeric(bar[3]),
        close: numeric(bar[4]), volume: numeric(bar[5])
      };
    }).filter(function (bar) { return bar.date <= asOfDate; });
  }

  function evaluate(options) {
    const opts = options || {};
    const instrumentType = (opts.meta || {}).instrumentType;
    if (['leveraged-or-inverse', 'leveraged-etf', 'inverse-etf', 'leveraged-inverse-etf'].includes(instrumentType)) {
      return { status: 'UNSUPPORTED_INSTRUMENT', events: [], diagnostics: { message: 'v0.1不適用槓桿／反向ETF，亦不以正股替代。' } };
    }
    if ((opts.period || 'd') !== 'd') {
      return { status: 'unsupported-period', events: [], diagnostics: { message: 'v0.1 僅支援已收盤日K；週／月／年K不產生標記。' } };
    }
    try {
      if (!AstraFlow || typeof AstraFlow.run !== 'function') throw new Error('AstraFlow core is not loaded');
      if (!validDate(opts.asOfDate)) throw new TypeError('asOfDate must be YYYY-MM-DD');
      return AstraFlow.run({
        bars: convert(opts.rawBars, opts.asOfDate, 'rawBars'),
        benchmarkBars: convert(opts.rawBenchmarkBars, opts.asOfDate, 'rawBenchmarkBars'),
        asOfDate: opts.asOfDate,
        symbol: opts.symbol,
        benchmarkSymbol: opts.benchmarkSymbol || 'SPY',
        researchMode: opts.researchMode !== false,
        meta: Object.assign({}, opts.meta || {}),
        benchmarkMeta: Object.assign({}, opts.benchmarkMeta || {})
      });
    } catch (error) {
      return {
        status: 'error', events: [],
        diagnostics: { message: error && error.message ? String(error.message) : 'Astra evaluation failed' }
      };
    }
  }

  function rowDate(row) { return row && (row.d || row.date); }
  function rowValue(row, shortName, longName) {
    const value = row && (row[shortName] == null ? row[longName] : row[shortName]);
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
  }

  function traces(result, rows, x) {
    if (!result || !Array.isArray(result.events) || !Array.isArray(rows) || !Array.isArray(x) || rows.length !== x.length) return [];
    const dateIndex = new Map();
    rows.forEach(function (row, i) { dateIndex.set(rowDate(row), i); });
    const majorIndexes = result.events.filter(function (event) {
      return event && (event.kind === 'ENTRY' || event.kind === 'EXIT') && dateIndex.has(event.date);
    }).map(function (event) { return dateIndex.get(event.date); });
    const provenance = result.provenance || {};
    const stockSource = provenance.stock || {}, benchmarkSource = provenance.benchmark || {};
    const sourceText = '<br>價量來源 ' + escapeHtml(stockSource.source || '未提供')
      + ' · ' + escapeHtml(result.benchmarkSymbol || 'SPY') + ' ' + escapeHtml(benchmarkSource.source || '未提供')
      + '<br>資料截止 ' + escapeHtml(result.dataThrough || '未提供') + ' · 評估截止 ' + escapeHtml(result.asOfDate || '未提供')
      + '<br>來源更新(UTC) ' + escapeHtml(stockSource.updatedUTC || '未提供')
      + '<br>定稿截止 ' + escapeHtml(stockSource.finalizedThrough || '尚未驗證');
    const output = [];
    KINDS.forEach(function (kind) {
      const style = STYLE[kind];
      const trace = {
        type: 'scatter', mode: 'markers+text', name: 'Astra ' + kind, meta: 'astra-flow',
        x: [], y: [], text: [], customdata: [], showlegend: false,
        xaxis: 'x', yaxis: 'y', cliponaxis: false,
        marker: { color: style.color, symbol: style.symbol, size: 9, line: { color: '#14171d', width: 1 } },
        textfont: { color: style.color, size: 10 }, textposition: style.position,
        hoverlabel: { bgcolor: '#14171d', bordercolor: style.color, font: { color: '#e6e9ef', size: 12 }, align: 'left' },
        hovertemplate: '%{customdata}<extra></extra>'
      };
      result.events.forEach(function (event) {
        if (!event || event.kind !== kind || !dateIndex.has(event.date)) return;
        const i = dateIndex.get(event.date);
        const y = kind === 'ENTRY' ? rowValue(rows[i], 'l', 'low') : rowValue(rows[i], 'h', 'high');
        if (y === null || y <= 0) return;
        const translateReason = function (value) { return REASONS[value] || value; };
        const reason = Array.isArray(event.reason) ? event.reason.map(translateReason).join('；') : translateReason(event.reason);
        const reference = typeof event.price === 'number' && Number.isFinite(event.price) ? event.price.toFixed(2) : '—';
        const metrics = event.metrics || {};
        const metricText = [['cmf20', 'CMF20'], ['volumeRatio', '量比'], ['rs20', '20日相對強度']]
          .filter(function (entry) { return typeof metrics[entry[0]] === 'number' && Number.isFinite(metrics[entry[0]]); })
          .map(function (entry) { return entry[1] + ' ' + metrics[entry[0]].toFixed(3); }).join(' · ');
        trace.x.push(x[i]);
        // Marker anchors remain inside observed H/L, so existing zoom autoscale needs no change.
        trace.y.push(y);
        // Preserve every marker and hover; suppress WATCH text crowding a nearby entry/exit.
        const crowded = kind === 'WATCH' && majorIndexes.some(function (index) { return Math.abs(index - i) <= 3; });
        trace.text.push(crowded ? '' : style.label);
        trace.customdata.push('Astra ' + escapeHtml(event.label || style.label) + '<br>' + escapeHtml(event.date)
          + '<br>事件參考價 ' + reference + '<br>' + escapeHtml(reason || '查看研究規則')
          + (metricText ? '<br>' + metricText : '')
          + sourceText
          + '<br>研究模型事件；不代表實際成交或真實持倉');
      });
      if (trace.x.length) output.push(trace);
    });
    return output;
  }

  function panelText(result) {
    if (!result) return 'Astra資金｜等待日K與SPY資料。';
    if (result.status === 'UNSUPPORTED_INSTRUMENT') return 'Astra資金｜v0.1不適用槓桿／反向ETF；不以正股替代。';
    if (result.status === 'unsupported-period') return 'Astra資金｜v0.1僅支援已收盤日K。';
    if (result.status === 'error') return 'Astra資金｜資料或引擎錯誤，暫停判斷：' + String((result.diagnostics || {}).message || '未知原因');
    const events = Array.isArray(result.events) ? result.events : [];
    const last = events.length ? events[events.length - 1] : null;
    const status = { RESEARCH: '候選研究', READY: '資料條件通過', STALE: '資料未到齊', WARMUP: '歷史長度不足', NO_DATA: '尚無資料' }[result.status] || String(result.status || 'unknown');
    const state = result.modelState === 'LONG' ? '策略模擬持有' : result.modelState === 'FLAT' ? '策略模擬空手' : '';
    const missing = (result.latest && Array.isArray(result.latest.blockedBy) ? result.latest.blockedBy : [])
      .map(function (gate) { return GATES[gate] || gate; });
    const warnings = Array.isArray(result.warnings) ? result.warnings.length : 0;
    return 'Astra資金｜' + status + (state ? '｜' + state : '')
      + '｜評估截止 ' + String(result.asOfDate || '未提供') + '／資料截至 ' + String(result.dataThrough || '未提供')
      + (warnings ? '｜資料口徑待核實（' + warnings + '項警示）' : '')
      + (last ? '｜最近事件 ' + String(last.date) + ' ' + String(last.label || last.kind) : '｜未出現事件')
      + (missing.length && result.modelState !== 'LONG' ? '｜進場尚缺：' + missing.join('、') : '')
      + '｜不代表真實持倉；訊號不代表實際成交。';
  }

  // Exact, non-cryptographic cache identity. Keep it in memory, not a DOM attribute.
  // Including every OHLCV catches historical volume/revision changes at an unchanged close.
  function inputKey(options) {
    const opts = options || {};
    return JSON.stringify([
      VERSION, AstraFlow && (AstraFlow.VERSION || AstraFlow.version) || '', opts.symbol,
      opts.benchmarkSymbol || 'SPY', opts.period || 'd', opts.asOfDate,
      opts.researchMode !== false, opts.meta || {}, opts.benchmarkMeta || {},
      opts.rawBars || [], opts.rawBenchmarkBars || []
    ]);
  }

  return Object.freeze({ VERSION: VERSION, evaluate: evaluate, traces: traces, panelText: panelText, inputKey: inputKey });
}));
