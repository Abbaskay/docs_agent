import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gevent import monkey
monkey.patch_all()

import re

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url and _db_url.startswith("postgres://"):
    os.environ["DATABASE_URL"] = re.sub(r"^postgres://", "postgresql://", _db_url)

from app import app, socketio

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"  Document Agent running at http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
