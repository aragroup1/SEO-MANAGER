# Shared in-memory state used by routers and middleware.
import os
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

# Auth sessions: token -> expiry datetime
active_sessions: Dict[str, datetime] = {}
SESSION_EXPIRY_HOURS = 72

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

# sync-all background jobs: job_id -> dict
sync_all_jobs: Dict[str, Dict] = {}

# Rate limiter (per-IP, per-endpoint)
rate_limit_store: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
RATE_LIMIT_DEFAULT = 60
RATE_LIMIT_AI = 10
RATE_LIMIT_AUDIT = 3
