import {createV6KlineView} from "./media/v6-kline-view.js";
const $=s=>document.querySelector(s);
const state={signals:[],charts:{},index:0,view:null,quoteTimer:0,rotationTimer:0,quotes:new Map(),calendar:null};
const host=$("#kline-host");state.view=createV6KlineView({host,onInteractionChange:()=>{}});
function setStatus(t){$("#refresh-state").textContent=t}
function candlesFor(rows){return rows.map(r=>({t:new Date(r.date+"T00:00:00+08:00").getTime(),o:r.open,h:r.high,l:r.low,c:r.close}))}
function showChart(code){const rows=state.charts[code]||[],candles=candlesFor(rows);state.view.setCandles(candles);state.view.setVegasEmaCandles(candles)}
function chinaNow(){const p=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Shanghai",weekday:"short",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date());return Object.fromEntries(p.filter(x=>x.type!=="literal").map(x=>[x.type,x.value]))}
function marketOpen(){const t=chinaNow(),minutes=Number(t.hour)*60+Number(t.minute),weekend=t.weekday==="Sat"||t.weekday==="Sun";return state.calendar?.date===t.year+"-"+t.month+"-"+t.day&&state.calendar.is_trading_day===true&&!weekend&&((minutes>=570&&minutes<=690)||(minutes>=780&&minutes<=900))}
function renderSignals(){
 const root=$("#signal-list");root.replaceChildren();
 if(!state.signals.length){root.textContent="今日暂无正式信号";$("#ticker-text").textContent="▰ No change ▰";$("#chart-empty").style.display="grid";return}
 $("#chart-empty").style.display="none";
 state.signals.forEach((s,i)=>{const card=document.createElement("button");card.className="signal-card";card.type="button";const title=document.createElement("strong");title.textContent=s.name;const meta=document.createElement("small");meta.textContent=s.code+" · "+s.confirmation_date;const side=document.createElement("span");side.className="side";side.textContent=s.side+" · "+s.zones.join("/");card.append(title,meta,side);card.addEventListener("click",()=>select(i));root.append(card)});
 $("#ticker-text").textContent=state.signals.map(s=>`▰ ${s.name} ▰`).join("　")||"▰ No change ▰";select(0);
}
function select(i){if(!state.signals.length)return;state.index=(i+state.signals.length)%state.signals.length;const s=state.signals[state.index];$("#stock-name").textContent=s.name;$("#stock-code").textContent=s.code;$("#quote-state").textContent="腾讯日线 / 盘中报价";showChart(s.code)}
function tencentQuote(code){return new Promise(resolve=>{const market=code.startsWith("6")||code.startsWith("9")?"sh":code.startsWith("4")||code.startsWith("8")?"bj":"sz",variable="v_"+market+code,script=document.createElement("script"),timer=setTimeout(()=>{script.remove();resolve(null)},10000);script.src="https://qt.gtimg.cn/q="+market+code+"&_="+Date.now();window[variable]=undefined;script.onload=()=>{clearTimeout(timer);const raw=window[variable];script.remove();if(typeof raw!=="string"){resolve(null);return}const f=raw.split("~"),price=Number(f[3]),high=Number(f[33]),low=Number(f[34]);resolve(price>0?{price,high,low}:null)};script.onerror=()=>{clearTimeout(timer);script.remove();resolve(null)};document.head.append(script)})}
async function refreshSignalQuotes(){
 if(document.hidden||!state.signals.length||!marketOpen())return;
 const codes=[...new Set(state.signals.map(s=>s.code))],results=await Promise.all(codes.map(async code=>[code,await tencentQuote(code)]));
 for(const [code,q] of results)if(q)state.quotes.set(code,q);
 const s=state.signals[state.index],q=state.quotes.get(s?.code);
 if(q){$("#quote-state").textContent="腾讯盘中 "+q.price.toFixed(2);const rows=(state.charts[s.code]||[]).map(r=>({...r}));if(rows.length){const last=rows[rows.length-1];last.high=Math.max(last.high,q.high||q.price);last.low=Math.min(last.low,q.low||q.price);last.close=q.price;state.view.setCandles(candlesFor(rows))}}
 setStatus("K线报价已刷新 "+new Date().toLocaleTimeString("zh-CN",{hour12:false}));
}
async function boot(){
 try{
  const [summary,signals,charts,calendar]=await Promise.all(["summary.json","signals.json","charts.json","trading-calendar.json"].map(n=>fetch("./data/"+n,{cache:"no-store"}).then(r=>{if(!r.ok)throw Error(n+" HTTP "+r.status);return r.json()})));
  if(summary.data_status!=="complete"||summary.symbols_ok!==500||summary.universe_total!==500)throw Error("CN500数据未通过完整性校验");
  state.calendar=calendar;state.signals=signals.filter(s=>s.confirmation_date===summary.market_date);state.charts=charts;$("#market-date").textContent=summary.market_date+" · 1D";renderSignals();setStatus("数据完整 500/500");
  state.quoteTimer=setInterval(refreshSignalQuotes,300000);refreshSignalQuotes();
  if(state.signals.length>1)state.rotationTimer=setInterval(()=>select(state.index+1),7000);
 }catch(e){setStatus("数据不可用："+e.message);$("#chart-empty").textContent="数据未通过校验";$("#chart-empty").style.display="grid"}
}
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshSignalQuotes()});
window.addEventListener("pagehide",()=>{clearInterval(state.quoteTimer);clearInterval(state.rotationTimer);state.view.destroy()},{once:true});
boot();
