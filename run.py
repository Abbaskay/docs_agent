"""
document_agent/run.py — Entry point for the Document Agent.

Run with:
    python document_agent/run.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app, socketio

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"  Document Agent running at http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)
