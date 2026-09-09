import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn

if __name__ == '__main__':
    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000, reload=False)
