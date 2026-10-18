"""WSGI entry point for production servers.

    gunicorn -w 2 -b 127.0.0.1:8765 wsgi:app
    waitress-serve --listen=127.0.0.1:8765 wsgi:app

Run the scheduler separately: `python main.py --daemon`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import db  # noqa: E402
from web import create_app  # noqa: E402

db.configure(Path(os.getenv("DB_PATH", Path(__file__).parent / "trending_history.db")))
db.init_db()
app = create_app()
