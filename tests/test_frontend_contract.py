from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class CNFrontendContractTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.index=(ROOT/"site/index.html").read_text(encoding="utf-8");cls.app=(ROOT/"site/assets/app.js").read_text(encoding="utf-8")
  cls.media=(ROOT/"site/assets/css/full-screen-dynamic.css").read_text(encoding="utf-8");cls.module_css=(ROOT/"site/assets/css/v6-modules.css").read_text(encoding="utf-8");cls.tf_host=(ROOT/"site/assets/modules/timeframe-switch/host.css").read_text(encoding="utf-8")
  cls.logo=(ROOT/"site/assets/modules/logo/logo.js").read_text(encoding="utf-8");cls.tf=(ROOT/"site/assets/modules/timeframe-switch/index.html").read_text(encoding="utf-8")
  cls.ticker=(ROOT/"site/assets/modules/signal-ticker/ticker.js").read_text(encoding="utf-8");cls.kline=(ROOT/"site/assets/kline/tencent-kline-controller.js").read_text(encoding="utf-8")
  cls.scanner=(ROOT/"scripts/a_share_cache.py").read_text(encoding="utf-8")
  cls.live_quotes=(ROOT/"site/assets/quotes/tencent-live-quotes.js").read_text(encoding="utf-8")
  cls.kline_controller=(ROOT/"site/assets/kline/tencent-kline-controller.js").read_text(encoding="utf-8")
 def test_seven_systems_are_hosted(self):
  for x in ('id="kline-host"','id="logo-frame"','id="timeframe-frame"','id="rolling-cards-frame"','id="signal-ticker"'):self.assertIn(x,self.index)
  for x in ("createV6KlineView","createSignalTicker","createTencentKlineController","VEGAS_LOGO_SET_SYMBOL","window.setCardOrder"):self.assertIn(x,self.app)
  self.assertIn("full-screen-dynamic.css",self.index)
 def test_media_viewport_and_gesture_system_is_present(self):
  self.assertIn("100dvh",self.media);self.assertIn("safe-area-inset-bottom",self.media)
  self.assertIn("pointerdown",(ROOT/"site/assets/kline/v6-kline-view.js").read_text(encoding="utf-8"))
  self.assertIn("createKlineRotationPause",self.app)
  self.assertIn("rotationPause?.destroy()",self.app)
  self.assertIn("cn-kline-viewport",(ROOT/"site/assets/kline/v6-viewport-state.js").read_text(encoding="utf-8"))
 def test_cn_viewport_storage_is_isolated(self):
  view=(ROOT/"site/assets/kline/v6-kline-view.js").read_text(encoding="utf-8")
  state=(ROOT/"site/assets/kline/v6-viewport-state.js").read_text(encoding="utf-8")
  self.assertIn("cn-kline-viewport-v1",state)
  self.assertNotIn("migrateLegacyViewportKey",view)
  self.assertNotIn("vegas-v6-viewport:",view)
  self.assertNotIn("vegas-v6-viewport:",state)
  self.assertNotIn("removeLegacyViewportState",state)
 def test_legacy_viewport_unit_fallback_is_complete(self):
  for marker in ("max-height:45vh!important","height:clamp(20px,3vh,26px)!important","height:clamp(18px,5vh,23px)!important","calc(100vh - var(--v6-safe-bottom)"):
   self.assertIn(marker,self.media)

 def test_viewport_fallback_supports_syntax_and_migration_order(self):
  for source in (self.media,):
   self.assertIn("@supports not (height: 100dvh)",source)
   self.assertNotIn("@supports not(height:100dvh)",source)
  controller=self.kline
  select=controller[controller.index("async function select("):]
  self.assertLess(select.index("await read(key)"),select.index('render(candles,token,historyComplete,"cache-loaded")'))
  view=(ROOT/"site/assets/kline/v6-kline-view.js").read_text(encoding="utf-8")
  self.assertIn("overlay.setView(viewport())",view)
 def test_tencent_qfq_daily_is_configured(self):
  self.assertIn("stock_zh_a_hist_tx",self.scanner);self.assertIn("Tencent qt.gtimg.cn",self.scanner)
  self.assertIn('TIMEFRAME="1D"',self.kline);self.assertIn('DB_NAME="cn-market-cache"',self.kline)
 def test_daily_timeframe_and_logo_linkage(self):
  self.assertIn('<span class="period">1D</span>',self.tf);self.assertIn('timeframe:"1D"',self.app)
  self.assertIn("VEGAS_LOGO_SET_SYMBOL",self.logo);self.assertIn("VEGAS_LOGO_SET_SYMBOL",self.app)
 def test_cards_and_signal_flow(self):
  self.assertIn("confirmation_date!==summary.market_date",self.app);self.assertIn("VEGAS_CARD_SELECT",self.app);self.assertIn("No change",self.ticker)
 def test_daily_signal_snapshot_is_shared_and_persistent(self):
  for marker in ('SIGNAL_SNAPSHOT_KEY="cn-daily-signal-snapshot-v1"',"readSignalSnapshot()","persistSignalSnapshot(snapshot)","summary.market_date<activeSignalDate","activeSignalSnapshot","JSON.stringify(snapshot)===JSON.stringify(activeSignalSnapshot)","applySignalSnapshot(snapshot)","confirmation_date!==summary.market_date"):
   self.assertIn(marker,self.app)
  self.assertIn('cn-batch-20261116-1',self.index)
  self.assertIn(r"/^\d{4}-\d{2}-\d{2}$/",self.app)
  self.assertIn('if(!activeSignalDate)ticker.render([],"unavailable")',self.app)
  self.assertIn('"signals.previous.json"',self.app)
  self.assertIn("ticker.render(next.length?next:snapshot.previous_signals",self.app)
  self.assertIn('next.length?"ready":"previous"',self.app)
  self.assertIn('"▰ 上次扫描 ▰   "',self.ticker)
  self.assertIn("cn-live-market-20261117-5",self.index)
  self.assertIn("cn-signal-previous-20261117-1",self.app)
  self.assertIn("value.checked_on!==chinaCalendarDate()",self.app)
 def test_fullscreen_panel_geometry(self):
  for x in ("#kline-host","#rolling-cards-frame","#signal-ticker","safe-area-inset-bottom"):self.assertIn(x,self.media)
 def test_single_fullscreen_geometry_authority(self):
  self.assertFalse((ROOT/"site/assets/full-screen.css").exists())
  self.assertNotIn("full-screen.css",self.index)
  self.assertIn("html.page-hidden",self.module_css)
 def test_fullscreen_rules_are_centralized(self):
  self.assertNotIn("full-screen-dynamic.css",self.tf)
  self.assertNotIn("responsive.css",self.index)
  self.assertNotIn("scroll-snap",self.tf)
  self.assertNotIn("VEGAS_TIMEFRAME_SELECT",self.tf)
  self.assertNotIn("VEGAS_TIMEFRAME_SET",self.tf)
  self.assertNotIn("<script>",self.tf)
  self.assertNotIn("button",self.tf)
  self.assertNotIn("VEGAS_TIMEFRAME_SELECT",self.app)
  self.assertNotIn("VEGAS_TIMEFRAME_SET",self.app)
  self.assertIn("pointer-events:none!important",self.tf_host)
  self.assertIn("clip-path:inset(68.83% 0 0 0)",self.tf_host)
  self.assertIn("height:calc(100vh - var(--v6-safe-bottom, 0px))!important",self.tf_host)
  self.assertIn("100dvh",self.media)
  self.assertIn("safe-area-inset-bottom",self.media)
  self.assertIn("?v=cn-batch-20261116-1",self.index)
 def test_browser_kline_cache_is_bounded(self):
  self.assertIn("MAX_CACHED_CANDLES=1200",self.kline_controller)
  self.assertIn("CACHE_SCHEMA=5",self.kline_controller)
  self.assertIn('"ema_schema":2',self.scanner)
  self.assertIn("web_ema_policy",self.scanner)
  self.assertIn('chart.get("ema_schema") != 2', (ROOT/"scripts/validate_pages_payload.py").read_text(encoding="utf-8"))
  self.assertIn("EMA_PERIODS=[12,144,169,576,676]",self.kline_controller)
  self.assertIn('candle["ema"+period]',self.kline_controller)
  self.assertIn("hasSource", (ROOT/"site/assets/kline/v6-vegas-ema.js").read_text(encoding="utf-8"))
  self.assertIn("MAX_CACHE_SYMBOLS=64",self.kline_controller)
  self.assertIn("slice(-MAX_CACHED_CANDLES)",self.kline_controller)
  self.assertIn("current.slice(MAX_CACHE_SYMBOLS)",self.kline_controller)
  self.assertIn("schemaVersion===CACHE_SCHEMA",self.kline_controller)
  self.assertIn('"history_complete":len(chart_bars)==x["valid_bars"]',self.scanner)
 def test_no_second_pages_publisher(self):self.assertFalse((ROOT/".github/workflows/pages.yml").exists())

 def test_ema_rules_have_only_the_three_a_share_groups(self):
  ema=(ROOT/"site/assets/kline/v6-vegas-ema.js").read_text(encoding="utf-8")
  spec=(ROOT/"Charts/ema-colors.json").read_text(encoding="utf-8")
  tokens=(ROOT/"UI/visual-tokens.json").read_text(encoding="utf-8")
  for period in (12,144,169,576,676):self.assertIn("period:"+str(period),ema)
  self.assertNotIn("period:36",ema);self.assertNotIn("period:43",ema)
  self.assertNotIn('"EMA36":',spec);self.assertNotIn('"EMA43":',spec)
  self.assertNotIn("ema36",tokens);self.assertNotIn("ema43",tokens)
 def test_common_rotation_pause_and_cache_capacity(self):
  pause=(ROOT/"site/assets/kline/rotation-pause.js").read_text(encoding="utf-8")
  self.assertIn("lastTapAt",pause);self.assertIn("now-lastTapAt<=320",pause)
  self.assertIn("createKlineRotationPause",self.app)
  self.assertIn("rotationPaused",self.app)
  self.assertIn("MAX_CACHE_SYMBOLS=64",self.kline_controller)


 def test_tencent_cache_uses_media_resilience_mechanisms(self):
  for marker in ("MEMORY_MAX_PER_SYMBOL=1200","MEMORY_MAX_SYMBOLS=8","mode:\"memory-fallback\"","dbRetryAt=Date.now()+15000","navigator.storage?.estimate","usageRatio:ratio","attempt<3","retryDelay(350*Math.pow(2,attempt)"):
   self.assertIn(marker,self.kline_controller)

 def test_residual_asset_cache_is_busted_across_page_and_modules(self):
  logo_html=(ROOT/"site/assets/modules/logo/logo.html").read_text(encoding="utf-8")
  view=(ROOT/"site/assets/kline/v6-kline-view.js").read_text(encoding="utf-8")
  for content in (self.index,logo_html):
   self.assertNotIn("cn-viewport-20261110-1",content)
   self.assertIn("cn-batch-20261116-1",content)
  self.assertIn("?v=cn-ema-snapshot-20261116-1",self.app)
  self.assertIn("?v=cn-viewport-isolated-20261116-1",view)
 def test_cards_share_one_initial_snapshot_request(self):
  cards=(ROOT/"site/assets/rolling-cards.js").read_text(encoding="utf-8")
  self.assertIn("__CN_CARD_DATA_READY__=fetch(\"./data/cards.json\"",cards)
  self.assertIn("window.__CN_CARD_DATA__=rows",cards)
  self.assertIn("window.__CN_CARD_DATA_READY__",self.app)
  self.assertIn("refreshCards({force:true})",self.app)
  self.assertIn("if(force||!Array.isArray(rows))",self.app)
  self.assertIn("dailyRefreshTimer=setTimeout(",self.app)
  self.assertIn("millisecondsUntilDailyRefresh()",self.app)
  self.assertIn("chinaMinutesOfDay()<995",self.app)
  self.assertNotIn("lifecycle.interval(",self.app)
  self.assertNotIn("60000)",self.app)
  self.assertIn("isTodayPublishedSnapshot(summary)",self.app)
  self.assertIn("summary.generated_at_utc",self.app)
  self.assertIn("scheduleDailyRetry()",self.app)
  self.assertIn("},300000)",self.app)
  self.assertIn("daily scan is not published yet",self.app)
  self.assertNotIn("if(summary&&chinaMinutesOfDay()>=995)markDailyCheckCompleted()",self.app)
 def test_five_minute_live_market_refresh_only_updates_signal_carousel_symbols(self):
  for marker in ("setTimeout(()=>{marketRefreshTimer=null;void refreshLiveMarket().finally(()=>scheduleMarketRefresh())},millisecondsUntilNextMarketRefresh())","signalStocks.map(item=>item.symbol)","liveQuotes.read(symbol)","liveQuoteBySymbol.set(symbol,datedQuote)","controller.updateLiveQuote(datedQuote)","isChinaTradingSession()","function millisecondsUntilNextMarketRefresh()","if(isChinaTradingSession())return 300000","[[9,30],[13,0]]"):
   self.assertIn(marker,self.app)
  self.assertIn("millisecondsUntilNextMarketRefresh()",self.app[self.app.index("function scheduleMarketRefresh()"):self.app.index("function startForegroundTimers()")])
  self.assertIn("liveQuoteBySymbol.get(item.symbol)",self.app)
  self.assertNotIn("const symbol=controller.state.symbol",self.app)
  self.assertNotIn("window.updateQuotes(updates)",self.app)
  self.assertNotIn("refreshCards(",self.app[self.app.index("async function refreshLiveMarket()"):self.app.index("function scheduleMarketRefresh()")])
  for marker in ('ENDPOINT="https://qt.gtimg.cn/q="',"window[\"v_\"+symbol]","f[3]","f[4]","f[34]","f[35]","ENDPOINT+symbol"):
   self.assertIn(marker,self.live_quotes)
  self.assertNotIn("BATCH_SIZE",self.live_quotes)
  self.assertIn("updateLiveQuote(quote)",self.kline_controller)
  self.assertIn('"live-quote"',self.kline_controller)
 def test_kline_controller_destroy_is_safe_before_indexeddb_opens(self):
  self.assertIn("if(dbp)dbp.then(db=>db?.close()).catch(()=>{});",self.kline_controller)

 def test_timeframe_font_path_resolves_to_shared_media_font(self):
  module=ROOT/"site/assets/modules/timeframe-switch"
  self.assertIn("url('../../fonts/ChakraPetch-Bold.ttf')",self.tf)
  self.assertTrue((module/"../../fonts/ChakraPetch-Bold.ttf").resolve().is_file())
  self.assertNotIn("../../assets/fonts/ChakraPetch-Bold.ttf",self.tf)
  self.assertIn("cn-timeframe-static-20261116-4",self.index)

 def test_logo_and_timeframe_use_media_load_gate_and_dark_first_paint(self):
  self.assertIn('<style id="cn-first-paint-guard">',self.index)
  self.assertIn('html,body{background:#101010;color-scheme:dark}',self.index)
  self.assertIn('#logo-frame,#timeframe-frame{background:#101010;opacity:0}',self.index)
  self.assertIn('html,body{background:#101010',self.module_css)
  self.assertNotIn("function revealFrame(",self.app)
  self.assertNotIn("revealFrame(logoFrame)",self.app)
  self.assertIn("onload=\"this.classList.add('is-ready')\"",self.index)
  self.assertIn('lifecycle.listen(logoFrame,"load",()=>{if(',self.app)
  self.assertIn('if(logoFrame.contentDocument?.readyState==="complete")syncFrames()',self.app)
  self.assertNotIn('lifecycle.listen(timeframeFrame,"load"',self.app)


if __name__=="__main__":unittest.main()
