import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from daily_scan import publish
class PublishTests(unittest.TestCase):
 def test_partial_cn500_is_never_published(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(RuntimeError):publish(__import__("datetime").date(2026,1,5),["600000"],{"600000":"浦发银行"},{},Path(d))
   self.assertFalse((Path(d)/"summary.json").exists())
if __name__=="__main__":unittest.main()
