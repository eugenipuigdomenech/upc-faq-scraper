import sys
from pathlib import Path


# Allow imports like `from scraper.scraping import ...`
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
