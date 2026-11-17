const ENDPOINT="https://qt.gtimg.cn/q=";
const BATCH_SIZE=50;
function parse(symbol){
 const raw=window["v_"+symbol];if(typeof raw!=="string")return null;
 const f=raw.split("~"),price=Number(f[3]),previousClose=Number(f[4]),open=Number(f[5]);
 if(!(price>0)||!(previousClose>0))return null;
 const high=Number(f[34]),low=Number(f[35]);
 return {symbol,price,previousClose,open:open>0?open:previousClose,high:high>0?high:price,low:low>0?low:price};
}
function loadBatch(symbols){
 return new Promise((resolve,reject)=>{
  const script=document.createElement("script");let settled=false;
  const finish=error=>{if(settled)return;settled=true;clearTimeout(timer);script.onload=script.onerror=null;script.remove();if(error)reject(error);else resolve(symbols.map(parse).filter(Boolean))};
  const timer=setTimeout(()=>finish(new Error("Tencent quote request timed out")),15000);
  script.async=true;script.charset="gbk";script.onload=()=>finish(null);script.onerror=()=>finish(new Error("Tencent quote script failed to load"));
  script.src=ENDPOINT+symbols.join(",")+"&_="+Date.now();document.head.appendChild(script);
 });
}
export function createTencentLiveQuotes(){
 let sequence=0;
 async function read(rows){
  if(!Array.isArray(rows))return [];
  const token=++sequence,symbols=rows.map(row=>String(row?.symbol||"")).filter(s=>/^(sh|sz|bj)\d{6}$/.test(s)),quotes=[];
  for(let i=0;i<symbols.length;i+=BATCH_SIZE){quotes.push(...await loadBatch(symbols.slice(i,i+BATCH_SIZE)));if(token!==sequence)return []}
  const bySymbol=new Map(quotes.map(row=>[row.symbol,row])),updates=[];
  for(let i=0;i<rows.length;i++){const quote=bySymbol.get(rows[i]?.symbol);if(quote)updates.push([i,quote.price,quote.previousClose,quote.open,quote.high,quote.low])}
  return updates;
 }
 return Object.freeze({read});
}
