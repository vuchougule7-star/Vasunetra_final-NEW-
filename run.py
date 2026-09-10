import os, sys
from pathlib import Path
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn


def open_browser():
    webbrowser.open("http://127.0.0.1:8000/")


if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()

    uvicorn.run(
        'backend.main:app',
        host='127.0.0.1',
        port=8000,
        reload=False
    )
