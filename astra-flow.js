/* Astra Flow v0.1.0. Original research candidate; no trading API or dependencies. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.AstraFlow = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const VERSION = '0.1.0';
  const P = Object.freeze({warmup:60, cmfEntry:0.08, cmfPositive:0.05,
    persistence:3, minDollarVolume:2e7, minPrice:5, maxAtrFraction:0.12,
    breakoutVolume:1.2, reclaimVolume:1, dryVolume:0.8, baseAtr:4,
    lowToleranceAtr:0.5, maxExtensionAtr:2.5, initialStopAtr:2,
    trailingAtr:3, distributionVolume:1.3, distributionClv:-0.4, cooldown:5});
  const mean = a => a.reduce((s,v) => s+v,0)/a.length;
  const median = a => {const s=a.slice().sort((x,y)=>x-y), n=s.length;
    return n%2?s[(n-1)/2]:(s[n/2-1]+s[n/2])/2;};
  const dateOK = d => typeof d==='string' && /^\d{4}-\d{2}-\d{2}$/.test(d)
    && !Number.isNaN(Date.parse(d+'T00:00:00Z'))
    && new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d;
  function validate(bars, name) {
    if (!Array.isArray(bars)) throw new Error(name+': expected array');
    let prev='';
    bars.forEach((b,i)=>{
      if (!b || !dateOK(b.date) || b.date<=prev) throw new Error(name+': date/order at '+i);
      for (const k of ['open','high','low','close','volume']) {
        if (typeof b[k]!=='number'||!Number.isFinite(b[k])||b[k]<=0)
          throw new Error(name+': invalid '+k+' at '+b.date);
      }
      if (b.high<Math.max(b.open,b.close,b.low)||b.low>Math.min(b.open,b.close))
        throw new Error(name+': inconsistent OHLC at '+b.date);
      prev=b.date;
    });
  }
  function indicators(B) {
    const tr=[], clv=[], sma20=[], sma50=[], atr=[], cmf=[], vr=[], dist=[];
    for(let i=0;i<B.length;i++) {
      const b=B[i], prev=i?B[i-1].close:b.open;
      tr[i]=Math.max(b.high-b.low,Math.abs(b.high-prev),Math.abs(b.low-prev));
      clv[i]=b.high===b.low?0:(2*b.close-b.high-b.low)/(b.high-b.low);
      atr[i]=i>=13?mean(tr.slice(i-13,i+1)):null;
      sma20[i]=i>=19?mean(B.slice(i-19,i+1).map(x=>x.close)):null;
      sma50[i]=i>=49?mean(B.slice(i-49,i+1).map(x=>x.close)):null;
      cmf[i]=i>=19?B.slice(i-19,i+1).reduce((s,x,k)=>s+clv[i-19+k]*x.volume,0)
        /B.slice(i-19,i+1).reduce((s,x)=>s+x.volume,0):null;
      vr[i]=i>=20?b.volume/median(B.slice(i-20,i).map(x=>x.volume)):null;
      dist[i]=i>=20&&b.close<prev&&clv[i]<=P.distributionClv&&vr[i]>=P.distributionVolume;
    }
    return {tr,clv,sma20,sma50,atr,cmf,vr,dist};
  }
  function run(input) {
    const {asOfDate,symbol='',benchmarkSymbol='SPY',researchMode=false,
      meta={},benchmarkMeta={},ablationNoPressure=false}=input||{};
    if (!dateOK(asOfDate)) throw new Error('asOfDate must be a completed session YYYY-MM-DD');
    if (ablationNoPressure&&!researchMode) throw new Error('ablation is research only');
    if (!Array.isArray(input.bars)||!Array.isArray(input.benchmarkBars))
      throw new Error('bars and benchmarkBars are required');
    // Validate only information available by cutoff. Future appends cannot change past events.
    const B=input.bars.filter(b=>!b||!dateOK(b.date)||b.date<=asOfDate);
    const M=input.benchmarkBars.filter(b=>!b||!dateOK(b.date)||b.date<=asOfDate);
    validate(B,'bars'); validate(M,'benchmarkBars');
    const warnings=[];
    for (const [name,m] of [['stock',meta],['benchmark',benchmarkMeta]]) {
      if (!m.source || !m.adjustment || m.volumeBasisVerified!==true)
        warnings.push(name+': source/adjustment/volume basis not fully verified');
      if (!dateOK(m.finalizedThrough)||m.finalizedThrough<asOfDate)
        warnings.push(name+': finalizedThrough not confirmed');
    }
    if (warnings.length&&!researchMode) throw new Error('Data quality blocked: '+warnings.join('; '));
    const events=[], diagnostics=[];
    const provenanceOf=m=>({source:m.source||'unknown',adjustment:m.adjustment||'unverified',
      volumeBasisVerified:m.volumeBasisVerified===true,finalizedThrough:m.finalizedThrough||null,
      updatedUTC:m.updatedUTC||null});
    const result={version:VERSION,params:P,symbol,benchmarkSymbol,asOfDate,
      researchMode,ablationNoPressure,identityEvidence:'UNIDENTIFIED_PRICE_VOLUME_PROXY',
      provenance:{stock:provenanceOf(meta),benchmark:provenanceOf(benchmarkMeta)},
      warnings,events,diagnostics,status:'WARMUP',modelState:'FLAT',
      dataThrough:B.length?B[B.length-1].date:null,benchmarkThrough:M.length?M[M.length-1].date:null};
    if (!B.length) {result.status='NO_DATA';return result;}
    const I=indicators(B), J=indicators(M), mi=new Map(M.map((b,i)=>[b.date,i]));
    let position=null, lastExit=-Infinity, watchActive=false;
    for(let i=0;i<B.length;i++) {
      const b=B[i];
      if(i<P.warmup-1) {diagnostics.push({date:b.date,status:'WARMUP',blockedBy:['WARMUP']});continue;}
      const a=I.atr[i], j=mi.get(b.date), start=mi.get(B[i-20].date);
      const benchmarkReady=j!==undefined&&j>=49&&start!==undefined;
      const rs=benchmarkReady?b.close/B[i-20].close-M[j].close/M[start].close:null;
      const market=benchmarkReady&&M[j].close>=J.sma50[j];
      const dv=median(B.slice(i-20,i).map(x=>x.close*x.volume));
      const liquid=dv>=P.minDollarVolume&&b.close>=P.minPrice;
      const volatility=a>0&&a/b.close<=P.maxAtrFraction;
      const trend=b.close>I.sma50[i]&&I.sma20[i]>=I.sma20[i-5];
      const pressure=I.cmf[i]>=P.cmfEntry&&I.cmf.slice(i-4,i+1).filter(v=>v>=P.cmfPositive).length>=P.persistence;
      const prior5=B.slice(i-5,i), before5=B.slice(i-10,i-5), prior10=B.slice(i-10,i);
      const dryRatio=median(prior5.map(x=>x.volume))/median(B.slice(i-25,i-5).map(x=>x.volume));
      const baseRange=Math.max(...prior10.map(x=>x.high))-Math.min(...prior10.map(x=>x.low));
      const base=dryRatio<=P.dryVolume&&baseRange<=P.baseAtr*I.atr[i-1]
        &&Math.min(...prior5.map(x=>x.low))>=Math.min(...before5.map(x=>x.low))-P.lowToleranceAtr*I.atr[i-1];
      const breakout=b.close>Math.max(...B.slice(i-20,i).map(x=>x.high))&&I.vr[i]>=P.breakoutVolume;
      const reclaim=base&&b.close>Math.max(...prior5.map(x=>x.high))&&I.vr[i]>=P.reclaimVolume;
      const extended=b.close-I.sma20[i]>P.maxExtensionAtr*a;
      const gates={LIQUIDITY:liquid,VOLATILITY:volatility,TREND:trend,
        BENCHMARK_DATA:benchmarkReady,MARKET:market,RELATIVE_STRENGTH:rs!==null&&rs>=0,
        PRESSURE:ablationNoPressure||pressure,EXTENSION:!extended,COOLDOWN:i-lastExit>P.cooldown,
        TRIGGER:breakout||reclaim};
      const metrics={cmf20:I.cmf[i],volumeRatio:I.vr[i],atr14:a,sma20:I.sma20[i],
        sma50:I.sma50[i],rs20:rs,medianDollarVolume20:dv,dryRatio,pressure,base,breakout,reclaim};
      const emit=(kind,label,reason,extra={})=>events.push({date:b.date,kind,label,reason,
        price:b.close,signalAt:b.date+' after regular-session close',
        earliestExecution:'NEXT_SESSION_OPEN',version:VERSION,metrics:{...metrics},...extra});
      let exitReason=null, stop=null, avwap=null;
      if(position) {
        position.pv+=((b.high+b.low+b.close)/3)*b.volume;
        position.vol+=b.volume;
        avwap=position.pv/position.vol;
        position.highClose=Math.max(position.highClose,b.close);
        position.stop=Math.max(position.stop,position.highClose-P.trailingAtr*a);
        stop=position.stop;
        if(b.close<stop) exitReason='CLOSE_BELOW_RISK_LINE';
        else if(b.close<I.sma20[i]&&B[i-1].close<I.sma20[i-1]&&I.cmf[i]<0)
          exitReason='TWO_CLOSES_WEAK_WITH_NEGATIVE_PRESSURE';
        else if(b.close<avwap&&I.dist.slice(Math.max(0,i-4),i+1).filter(Boolean).length>=2)
          exitReason='DISTRIBUTION_BELOW_SIGNAL_AVWAP';
        if(exitReason) {
          emit('EXIT','A出',exitReason,{referenceRiskLine:stop,signalAvwap:avwap,
            entrySignalDate:B[position.index].date});
          position=null;lastExit=i;watchActive=false;
        }
      }
      // A close-confirmed model state; actual fills live only in the backtester/broker.
      if(!position&&!exitReason&&Object.values(gates).every(Boolean)) {
        stop=b.close-P.initialStopAtr*a;
        position={index:i,stop,highClose:b.close,pv:((b.high+b.low+b.close)/3)*b.volume,vol:b.volume};
        emit('ENTRY','A進',breakout?'PERSISTENT_PRESSURE_BREAKOUT':'DRY_BASE_RECLAIM',
          {referenceRiskLine:stop});
        watchActive=false;
      } else if(!position&&!exitReason) {
        const watch=liquid&&volatility&&trend&&(pressure||base);
        if(watch&&!watchActive) emit('WATCH','A候',base?'DRY_BASE_WAIT_CONFIRMATION':'PRESSURE_WAIT_CONFIRMATION');
        watchActive=watch;
      }
      diagnostics.push({date:b.date,status:position?'MODEL_LONG':'MODEL_FLAT',
        blockedBy:Object.entries(gates).filter(([,v])=>!v).map(([k])=>k),metrics,
        referenceRiskLine:position?position.stop:null,signalAvwap:avwap,exitReason});
    }
    result.modelState=position?'LONG':'FLAT';
    result.status=B.length<P.warmup?'WARMUP':(researchMode?'RESEARCH':'READY');
    if(result.dataThrough!==asOfDate||result.benchmarkThrough!==asOfDate) {
      result.warnings.push('STALE_OR_MISSING_LATEST_SESSION');result.status='STALE';
    }
    result.latest=diagnostics[diagnostics.length-1];
    result.lastEvent=events.length?events[events.length-1]:null;
    return result;
  }
  return Object.freeze({VERSION,PARAMS:P,run,indicators});
});
