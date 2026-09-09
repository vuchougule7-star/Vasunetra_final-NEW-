from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "villages.csv"
UPLOAD_DIR = BASE_DIR / "uploads"

# Central place for the settings most useful during the demo.
DEFAULT_PORT = 8000
ADVANCED_MAX_IMAGE_SIDE = 900
CORE_ORB_FEATURES = 2000
