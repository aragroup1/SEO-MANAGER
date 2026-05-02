# backend/main.py — SEO Intelligence Platform Backend (slim shell)
# All endpoint handlers live in routers/. This file owns: app setup, CORS,
# auth + rate-limit middleware, cache headers, startup migrations, and router wiring.
import os
import time
from datetime import datetime
from typing import Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from database import Base, engine, SessionLocal
from routers.state import (
    active_sessions, rate_limit_store,
    RATE_LIMIT_DEFAULT, RATE_LIMIT_AI, RATE_LIMIT_AUDIT,
)


def _check_rate_limit(client_ip: str, endpoint: str, limit: int) -> bool:
    now = time.time()
    rate_limit_store[client_ip][endpoint] = [
        t for t in rate_limit_store[client_ip][endpoint] if now - t < 60
    ]
    if len(rate_limit_store[client_ip][endpoint]) >= limit:
        return False
    rate_limit_store[client_ip][endpoint].append(now)
    return True


def _get_rate_limit(endpoint: str) -> int:
    if any(x in endpoint for x in ["/generate", "/research", "/strategy", "/content/", "/audit"]):
        if "/audit" in endpoint:
            return RATE_LIMIT_AUDIT
        return RATE_LIMIT_AI
    return RATE_LIMIT_DEFAULT


app = FastAPI(title="SEO Intelligence Platform")

# CORS
_CORS_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:3000,https://localhost:3000").split(",") if o.strip()]
_ALLOWED_ORIGINS = [o for o in _CORS_ORIGINS if "*" not in o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

PUBLIC_ROUTES = {"/health", "/api/auth/login", "/api/auth/check", "/docs", "/openapi.json"}
OAUTH_CALLBACKS = {"/api/integrations/oauth/google/callback", "/api/integrations/oauth/shopify/callback"}


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host or "unknown"


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    client_ip = _get_client_ip(request)
    limit = _get_rate_limit(path)
    if not _check_rate_limit(client_ip, path, limit):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Try again in a minute. (Limit: {limit}/min)"}
        )

    if path in PUBLIC_ROUTES:
        return await call_next(request)
    if path in OAUTH_CALLBACKS:
        return await call_next(request)
    if request.method == "OPTIONS":
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if not token or token not in active_sessions:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    if active_sessions[token] < datetime.utcnow():
        del active_sessions[token]
        return JSONResponse(status_code=401, content={"detail": "Session expired"})

    response = await call_next(request)

    if request.method == "GET":
        if "/overview" in path or "/full-summary" in path or "/summary" in path:
            response.headers["Cache-Control"] = "private, max-age=120, stale-while-revalidate=300"
        elif path == "/websites" or (path.startswith("/api/websites/") and path.endswith("/automation-summary")):
            response.headers["Cache-Control"] = "private, max-age=300"
        elif "/history" in path:
            response.headers["Cache-Control"] = "private, max-age=3600"
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


# ─── Lightweight migrations (legacy) ───
def _run_migrations():
    db = SessionLocal()
    try:
        try:
            db.execute(text("SELECT desktop_score FROM audit_reports LIMIT 1"))
            db.commit()
        except Exception:
            db.rollback()
            print("[Migration] Adding desktop_score column to audit_reports...")
            db.execute(text("ALTER TABLE audit_reports ADD COLUMN IF NOT EXISTS desktop_score FLOAT DEFAULT 0"))
            db.commit()
            print("[Migration] desktop_score column added successfully.")
    except Exception as e:
        db.rollback()
        print(f"[Migration] Migration check failed (non-critical): {e}")
    finally:
        db.close()


_run_migrations()


# ─── Routers (refactored from main.py — Phase 5) ───
from routers.auth import router as auth_router
from routers.admin import router as admin_router
from routers.audit import router as audit_router
from routers.websites import router as websites_router
from routers.content import router as content_router
from routers.competitors import router as competitors_router
from routers.export import router as export_router
from routers.monitoring import router as monitoring_router
from routers.overseer import router as overseer_router, schedule_daily_audits

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(audit_router)
app.include_router(websites_router)
app.include_router(content_router)
app.include_router(competitors_router)
app.include_router(export_router)
app.include_router(monitoring_router)
app.include_router(overseer_router)

# ─── Existing routers (pre-Phase 5) ───
from integrations import router as integrations_router
app.include_router(integrations_router)
from fix_routes import router as fix_router
app.include_router(fix_router)
from keyword_routes import router as keyword_router
app.include_router(keyword_router)
from geo_routes import router as geo_router
app.include_router(geo_router)
from strategist_routes import router as strategist_router
app.include_router(strategist_router)
from report_routes import router as report_router
app.include_router(report_router)


# ─── Startup: schema migrations + scheduler ───
@app.on_event("startup")
async def startup_event():
    print(f"Starting SEO Intelligence Platform on port {os.getenv('PORT', 8000)}")
    try:
        with engine.connect() as conn:
            migrations = [
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS user_id INTEGER DEFAULT 1",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS site_type VARCHAR DEFAULT 'custom'",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS shopify_store_url VARCHAR",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS shopify_access_token VARCHAR",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS monthly_traffic INTEGER",
                "ALTER TABLE tracked_keywords ADD COLUMN IF NOT EXISTS target_url VARCHAR",
                """CREATE TABLE IF NOT EXISTS serp_ranking_history (
                    id SERIAL PRIMARY KEY,
                    website_id INTEGER NOT NULL REFERENCES websites(id),
                    keyword VARCHAR NOT NULL,
                    position FLOAT,
                    ranking_url VARCHAR,
                    country VARCHAR DEFAULT 'gb',
                    source VARCHAR DEFAULT 'serper',
                    checked_at TIMESTAMP DEFAULT NOW()
                )""",
                "CREATE INDEX IF NOT EXISTS idx_serp_hist_wk ON serp_ranking_history(website_id, keyword)",
                "CREATE INDEX IF NOT EXISTS idx_serp_hist_when ON serp_ranking_history(checked_at)",
                """CREATE TABLE IF NOT EXISTS keyword_volumes (
                    id SERIAL PRIMARY KEY,
                    website_id INTEGER NOT NULL REFERENCES websites(id),
                    keyword VARCHAR NOT NULL,
                    country VARCHAR DEFAULT 'GB',
                    year_month VARCHAR NOT NULL,
                    search_volume INTEGER DEFAULT 0,
                    competition INTEGER DEFAULT 0,
                    cpc FLOAT DEFAULT 0,
                    source VARCHAR DEFAULT 'dataforseo',
                    fetched_at TIMESTAMP DEFAULT NOW()
                )""",
                "CREATE INDEX IF NOT EXISTS idx_kv_wkc ON keyword_volumes(website_id, keyword, country)",
                "CREATE INDEX IF NOT EXISTS idx_kv_month ON keyword_volumes(year_month)",
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_kv_wkcm ON keyword_volumes(website_id, keyword, country, year_month)",
                """CREATE TABLE IF NOT EXISTS strategist_results (
                    id SERIAL PRIMARY KEY,
                    website_id INTEGER NOT NULL UNIQUE REFERENCES websites(id),
                    strategy JSON,
                    strategy_generated_at TIMESTAMP,
                    weekly_plan JSON,
                    weekly_generated_at TIMESTAMP,
                    portfolio JSON,
                    portfolio_generated_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )""",
                "CREATE INDEX IF NOT EXISTS idx_strat_wid ON strategist_results(website_id)",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS linking JSON",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS linking_generated_at TIMESTAMP",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS decay JSON",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS decay_generated_at TIMESTAMP",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS geo_audit JSON",
                "ALTER TABLE strategist_results ADD COLUMN IF NOT EXISTS geo_audit_at TIMESTAMP",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS autonomy_mode VARCHAR DEFAULT 'manual'",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS sitemap_xml TEXT",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS sitemap_generated_at TIMESTAMP",
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS robots_txt TEXT",
                "ALTER TABLE proposed_fixes ADD COLUMN IF NOT EXISTS auto_approved_at TIMESTAMP",
                "ALTER TABLE proposed_fixes ADD COLUMN IF NOT EXISTS auto_applied BOOLEAN DEFAULT FALSE",
                "ALTER TABLE content_calendar ADD COLUMN IF NOT EXISTS scheduled_publish_date TIMESTAMP",
                "ALTER TABLE content_calendar ADD COLUMN IF NOT EXISTS published_at TIMESTAMP",
                "CREATE INDEX IF NOT EXISTS idx_audit_website ON audit_reports(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_reports(audit_date)",
                "CREATE INDEX IF NOT EXISTS idx_content_website ON content_calendar(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_fixes_website ON proposed_fixes(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_fixes_status ON proposed_fixes(status)",
                "CREATE INDEX IF NOT EXISTS idx_fixes_severity ON proposed_fixes(severity)",
                "CREATE INDEX IF NOT EXISTS idx_snapshots_website ON keyword_snapshots(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_snapshots_date ON keyword_snapshots(snapshot_date)",
                "CREATE INDEX IF NOT EXISTS idx_tracked_website ON tracked_keywords(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_integration_website ON integrations(website_id)",
                """CREATE TABLE IF NOT EXISTS core_web_vitals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    url VARCHAR DEFAULT '/',
                    lcp FLOAT, inp FLOAT, cls FLOAT, fcp FLOAT, ttfb FLOAT,
                    device_type VARCHAR DEFAULT 'mobile',
                    source VARCHAR DEFAULT 'pagespeed',
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                "CREATE INDEX IF NOT EXISTS idx_cwv_website ON core_web_vitals(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_cwv_checked ON core_web_vitals(checked_at)",
                """CREATE TABLE IF NOT EXISTS notification_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    channel_type VARCHAR NOT NULL,
                    name VARCHAR NOT NULL,
                    config JSON, events JSON,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS notification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    website_id INTEGER NOT NULL,
                    event_type VARCHAR NOT NULL,
                    status VARCHAR DEFAULT 'pending',
                    message TEXT, response TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                "CREATE INDEX IF NOT EXISTS idx_notif_logs_website ON notification_logs(website_id)",
                """CREATE TABLE IF NOT EXISTS image_audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    page_url VARCHAR NOT NULL,
                    image_url VARCHAR NOT NULL,
                    alt_text VARCHAR,
                    has_dimensions BOOLEAN DEFAULT 0,
                    file_size_kb INTEGER,
                    format VARCHAR,
                    is_lazy_loaded BOOLEAN DEFAULT 0,
                    is_above_fold BOOLEAN DEFAULT 0,
                    issues JSON,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                "CREATE INDEX IF NOT EXISTS idx_imgaudit_website ON image_audits(website_id)",
                """CREATE TABLE IF NOT EXISTS broken_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    page_url VARCHAR NOT NULL,
                    link_url VARCHAR NOT NULL,
                    anchor_text VARCHAR,
                    status_code INTEGER,
                    error_type VARCHAR DEFAULT 'unknown',
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_fixed BOOLEAN DEFAULT 0
                )""",
                "CREATE INDEX IF NOT EXISTS idx_broken_links_website ON broken_links(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_broken_links_checked ON broken_links(checked_at)",
                "CREATE INDEX IF NOT EXISTS idx_broken_links_fixed ON broken_links(is_fixed)",
                """CREATE TABLE IF NOT EXISTS meta_ab_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    page_url VARCHAR NOT NULL,
                    element_type VARCHAR NOT NULL,
                    variant_a TEXT NOT NULL,
                    variant_b TEXT NOT NULL,
                    status VARCHAR DEFAULT 'draft',
                    start_date TIMESTAMP, end_date TIMESTAMP,
                    winner VARCHAR, notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS local_seo_presence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL UNIQUE,
                    business_name VARCHAR, address VARCHAR, city VARCHAR,
                    postcode VARCHAR, country VARCHAR DEFAULT 'GB',
                    phone VARCHAR, category VARCHAR, gbp_url VARCHAR,
                    gbp_status VARCHAR DEFAULT 'not_claimed',
                    review_count INTEGER DEFAULT 0,
                    avg_rating FLOAT, last_checked TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS user_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    website_id INTEGER NOT NULL,
                    role VARCHAR DEFAULT 'admin',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS database_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_type VARCHAR DEFAULT 'manual',
                    format VARCHAR DEFAULT 'json',
                    file_path VARCHAR NOT NULL,
                    size_bytes INTEGER DEFAULT 0,
                    websites_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS index_statuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    url VARCHAR NOT NULL,
                    is_indexed BOOLEAN DEFAULT 0,
                    coverage_state VARCHAR,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    check_method VARCHAR DEFAULT 'unknown',
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                "CREATE INDEX IF NOT EXISTS idx_index_status_website ON index_statuses(website_id)",
                "CREATE INDEX IF NOT EXISTS idx_index_status_url ON index_statuses(url)",
                "CREATE INDEX IF NOT EXISTS idx_index_status_indexed ON index_statuses(is_indexed)",
                "CREATE INDEX IF NOT EXISTS idx_index_status_checked ON index_statuses(last_checked)",
            ]
            for migration in migrations:
                try:
                    conn.execute(text(migration))
                    conn.commit()
                except Exception:
                    pass
        print("Database schema updated")
    except Exception as e:
        print(f"Migration skipped: {e}")

    schedule_daily_audits()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
