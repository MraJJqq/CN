from pathlib import Path
import hashlib
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MediaParityTests(unittest.TestCase):
 def read(self,relative):
  return (ROOT/relative).read_text(encoding="utf-8")
 def git_blob_sha(self,relative):
  content=(ROOT/relative).read_bytes()
  header=b"blob "+str(len(content)).encode("ascii")+b"\0"
  return hashlib.sha1(header+content).hexdigest()
 def test_shared_modules_are_byte_identical_to_media_snapshot(self):
  expected={
   "site/assets/shared/lifecycle.js":"3ac39c9cee24d7bcdc946826e2f745cb3688db83",
   "site/assets/shared/page-lifecycle-v6.js":"2d6822edc3074604092e8ed2e5e242736f5cccc1",
   "site/assets/kline/rotation-pause.js":"1ab93849cfebdd11eb4f957402e9a19e881f6450",
   "site/assets/rolling-cards.css":"44dc3547c3560a062ae94223fdb49c98e65f5b20",
  }
  for path,sha in expected.items():self.assertEqual(self.git_blob_sha(path),sha,path)
 def test_a_share_ema_is_exactly_five_periods(self):
  ema=self.read("site/assets/kline/v6-vegas-ema.js")
  controller=self.read("site/assets/kline/tencent-kline-controller.js")
  for period in (12,144,169,576,676):
   self.assertIn("period:"+str(period),ema)
   self.assertIn(str(period),controller)
  for forbidden in (36,43):self.assertNotIn("period:"+str(forbidden),ema)
 def test_logo_and_kline_transition_are_staged_together(self):
  app=self.read("site/assets/app.js")
  logo=self.read("site/assets/modules/logo/logo.js")
  transition=app[app.index("async function transitionToIndex"):app.index("async function refreshCards")]
  self.assertLess(transition.index("sendLogoTransitionStart()"),transition.index("await waitTransition(1500,token)"))
  self.assertLess(transition.index("await controller.select"),transition.index("sendLogo(item,market)"))
  self.assertIn('d.type==="VEGAS_LOGO_TRANSITION_START"',logo)
  self.assertIn('d.type==="VEGAS_LOGO_TRANSITION_CANCEL"',logo)
  self.assertIn("if(transitionPrepared)",logo)
  self.assertIn("sendLogoTransitionStart();",app[app.index("async function resumeRuntime"):app.index("function teardown")])
  self.assertIn("await controller.resume({refresh:true,nextSymbol:item.symbol",app)
  self.assertIn('lifecycle.listen(window,"unhandledrejection"',app)
  self.assertIn("signalRefreshController?.abort()",app)
  self.assertIn("if(destroyed||isHidden())return null;",app)
  self.assertIn('if($("app").classList.contains("is-symbol-transitioning"))sendTimeframe();else syncFrames()',app)
  self.assertIn("function resume({refresh=true,nextSymbol=symbol",self.read("site/assets/kline/tencent-kline-controller.js"))
 def test_card_rotation_matches_media_baseline(self):
  cn=self.read("site/assets/rolling-cards.js")
  self.assertIn("var SPEED=Math.PI/60",cn)
 def test_ten_year_warmup_is_distinct_from_web_display_cap(self):
  scanner=self.read("scripts/a_share_cache.py")
  self.assertIn("history_start=history_end.replace(year=history_end.year-10",scanner)
  self.assertIn('for p in PERIODS:bars[f"ema{p}"]=ema(bars.close,p)',scanner)
  self.assertIn('chart_bars=x["chart_bars"][-CHART_BAR_LIMIT:]',scanner)
  self.assertIn('"web_ema_policy":"EMA12/144/169/576/676 calculated from the full available 10-year Tencent history',scanner)
 def test_runtime_keeps_cn_specific_data_adapters(self):
  app=self.read("site/assets/app.js")
  controller=self.read("site/assets/kline/tencent-kline-controller.js")
  self.assertIn("createTencentKlineController",app)
  self.assertIn('TIMEFRAME="1D"',controller)
  self.assertIn('DB_NAME="cn-market-cache"',controller)
  self.assertNotIn("gate-kline-controller",app)
  self.assertNotIn("public-signals.json",app)


 def test_all_seven_systems_retain_the_media_behavior_contract(self):
  # K-line + viewport: retain the reusable view/gesture/state mechanisms while
  # the Tencent controller remains the only A-share data adapter.
  view=self.read("site/assets/kline/v6-kline-view.js")
  viewport=self.read("site/assets/kline/v6-viewport-state.js")
  for marker in ("pointerdown","pointermove","pointerup","setPointerCapture","setView","destroy"):
   self.assertIn(marker,view)
  for marker in ("captureViewportState","normalizeViewportState","resolveViewportRight","VIEWPORT_STORAGE_KEY"):
   self.assertIn(marker,viewport)
  for marker in ("migrateLegacyViewportKey","vegas-v6-viewport:"):
   self.assertIn(marker,view)
  controller=self.read("site/assets/kline/tencent-kline-controller.js")
  self.assertIn("migrateLegacyViewportKey?.(key)",controller)

  # Cards: the 500-stock adapter may virtualize DOM nodes, but must retain
  # the Media ring's drag, inertia, selection, pause and lifecycle behavior.
  cards=self.read("site/assets/rolling-cards.js")
  for marker in ("function createCard","function fling(","setPointerCapture","pointerdown","pointermove","pointerup","wheel","VEGAS_CARD_SELECT","VEGAS_CARD_INTERACTION","IntersectionObserver","ResizeObserver","visibilitychange","pagehide","pageshow","window.setCardOrder"):
   self.assertIn(marker,cards)

  # Logo: preserve staged transitions and lifecycle-safe A-share calendar countdown.
  logo=self.read("site/assets/modules/logo/logo.js")
  for marker in ("VEGAS_LOGO_TRANSITION_START","VEGAS_LOGO_TRANSITION_CANCEL","VEGAS_LOGO_SET_SYMBOL","startPreparedTransition","cancelPreparedTransition","1500","refreshCalendar","nextTradingClose","scheduleClock","stopClock","pagehide","pageshow"):
   self.assertIn(marker,logo)

  # Fixed 1D is the A-share adapter; the isolated iframe message contract remains.
  timeframe=self.read("site/assets/modules/timeframe-switch/index.html")
  for marker in ('timeframe==="1D"',"VEGAS_TIMEFRAME_SET","VEGAS_TIMEFRAME_SELECT","VEGAS_TIMEFRAME_READY","event.source!==window.parent","location.origin"):
   self.assertIn(marker,timeframe)

  # Ticker: dynamic A-share signal rows must keep the continuous marquee engine.
  ticker=self.read("site/assets/modules/signal-ticker/ticker.js")
  for marker in ("function layout()","function schedule()","function render(","--signal-distance","--signal-duration","animationPlayState","ResizeObserver","function destroy()","cancelFrame","replaceChildren"):
   self.assertIn(marker,ticker)

  # Full-screen dynamic remains the single owner of outer viewport geometry.
  fullscreen=self.read("site/assets/css/full-screen-dynamic.css")
  for marker in ("100dvh","safe-area-inset-bottom","orientation:landscape","@supports not (height: 100dvh)","#timeframe-frame","#signal-ticker"):
   self.assertIn(marker,fullscreen)


if __name__=="__main__":unittest.main()
