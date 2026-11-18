from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "ashare" / "data"
CACHE_DIR = DATA_DIR / "cache"
UNIVERSE_FILE = DATA_DIR / "cn500.csv"
PUBLIC_DIR = ROOT / "public" / "data"

HISTORY_YEARS = 10
REQUEST_SEGMENT_DAYS = 730
EMA_PERIODS = (12, 144, 169, 576, 676)
SCAN_TIME_SHANGHAI = "15:35"
EXPECTED_UNIVERSE_SIZE = 500
