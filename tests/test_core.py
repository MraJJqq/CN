import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import pandas as pd
from cn_core import ema,validate_bars,scan_symbol,chart_rows
class CoreTests(unittest.TestCase):
 def bars(self,n=800):
  dates=pd.bdate_range("2022-01-03",periods=n);close=[100+i*.02 for i in range(n)]
  return pd.DataFrame({"date":dates,"open":close,"high":[x+1 for x in close],"low":[x-1 for x in close],"close":close,"volume":1000,"amount":100000})
 def test_ema_warmup_and_formula(self):
  x=pd.Series([1.,2.,3.,4.]);self.assertTrue(ema(x,12).isna().all())
  values=pd.Series(range(1,20),dtype=float);self.assertTrue(ema(values,12).equals(values.ewm(span=12,adjust=False,min_periods=12).mean()))
 def test_invalid_ohlc_removed(self):
  x=self.bars(20);x.loc[3,"high"]=1;self.assertEqual(len(validate_bars(x)),19)
 def test_observation_candle_never_confirms_itself(self):
  x=self.bars(800);x.loc[700,"low"]=float(x.loc[700,"close"])-100
  signals=scan_symbol(x,"600000","浦发银行");self.assertTrue(signals)
  self.assertTrue(all(s["observation_date"]<s["confirmation_date"] for s in signals))
 def test_long_ema_history_is_present(self):
  x=chart_rows(self.bars(800));self.assertIsNotNone(x[-1]["ema576"]);self.assertIsNotNone(x[-1]["ema676"])
 def test_cn500_universe_is_exact(self):
  from daily_scan import symbols
  self.assertEqual(len(symbols(str(Path(__file__).resolve().parents[1]/"config/cn500.codes.gz.b64"))),500)
if __name__=="__main__":unittest.main()
