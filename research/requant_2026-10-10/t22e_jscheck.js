// 熱(htSeriesJS)JS↔pandas 對拍:把 index.html 的 periodKey 存成 pk.js、htSeriesJS 那段存成 ht.js,kline_<代號>.json(資料 gist)放同資料夾 → node t22e_jscheck.js ht.js
const fs=require('fs');
eval(fs.readFileSync(__dirname+'/pk.js','utf8')+'\n'+fs.readFileSync(process.argv[2],'utf8')+'\nglobalThis.htSeriesJS=htSeriesJS;');
const out={};
for(const s of ['TSM','NVDA','AAPL','MU','BE','AVGO','LITE','PLTR']){
  const B=JSON.parse(fs.readFileSync(__dirname+'/kline_'+s+'.json','utf8')).bars;
  const H=htSeriesJS(B);out[s]=[];
  for(let i=0;i<H.n;i++)if(H.sig[i])out[s].push(H.D[i]+'|'+H.tdD[i]+'|'+H.tdW[i]);
  out[s+'_raw']=H.raw.filter(Boolean).length;
}
console.log(JSON.stringify(out));
