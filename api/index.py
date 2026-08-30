"""
Vercel entrypoint — exposes the FastAPI backend as a single Python serverless function.
vercel.json rewrites every /api/* request here. The app itself lives in backend/app.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# No resident process on serverless — Vercel Cron calls /api/v1/jobs/* instead.
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("LOG_FORMAT", "json")

from app.main import app  # noqa: E402,F401  (Vercel looks for an ASGI `app`)
