# backend/main.py - SEO Intelligence Platform Backend
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv
import json
import io
import secrets
import hashlib
import time
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text

load_dotenv()

# ─── Simple In-Memory Rate Limiter ───
# Tracks requests per IP per endpoint. Resets every minute.
# Production: replace with Redis-based limiter.
_rate_limit_store: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
_RATE_LIMIT_DEFAULT = 60   # requests per minute
_RATE_LIMIT_AI = 10        # AI endpoints (content gen, research, etc.)
_RATE_LIMIT_AUDIT = 3      # audit runs per minute

def _check_rate_limit(client_ip: str, endpoint: str, limit: int) -> bool:
    now = time.time()
    window = 60  # 1 minute window
    # Clean old entries
    _rate_limit_store[client_ip][endpoint] = [
        t for t in _rate_limit_store[client_ip][endpoint] if now - t < window
    ]
    if len(_rate_limit_store[client_ip][endpoint]) >= limit:
        return False
    _rate_limit_store[client_ip][endpoint].append(now)
    return True

def _get_rate_limit(endpoint: str) -> int:
    if any(x in endpoint for x in ["/generate", "/research", "/strategy", "/content/", "/audit"]):
        if "/audit" in endpoint:
            return _RATE_LIMIT_AUDIT
        return _RATE_LIMIT_AI
    return _RATE_LIMIT_DEFAULT

# Import shared database objects
from database import (
    Base, engine, SessionLocal, get_db, DATABASE_URL,
    User, Website, AuditReport, ContentItem, Integration, ProposedFix, KeywordSnapshot, TrackedKeyword,
    CoreWebVitalsSnapshot, NotificationChannel, NotificationLog, ImageAudit, MetaABTest,
    LocalSEOPresence, UserRole, DatabaseBackup, BrokenLink, IndexStatus
)

# Import sitemap generator
from sitemap_generator import generate_sitemap, get_sitemap, submit_to_gsc, validate_sitemap

# Import robots.txt generator
from robots_generator import (
    generate_robots_txt, validate_robots_txt, check_existing_robots,
    get_robots_txt, update_robots_txt
)

app = FastAPI(title="SEO Intelligence Platform")

# CORS: Use FRONTEND_URL env var for production, fallback to common dev origins
_CORS_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:3000,https://localhost:3000").split(",") if o.strip()]
# Reject wildcards in origins
_ALLOWED_ORIGINS = [o for o in _CORS_ORIGINS if "*" not in o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# ─── Simple Auth System ───
# Set these in Railway env vars:
#   AUTH_USERNAME=arman
#   AUTH_PASSWORD=your_secure_password
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

# In-memory session store (survives within a single deployment)
active_sessions: Dict[str, datetime] = {}
SESSION_EXPIRY_HOURS = 72  # 3 days

# Public routes that don't need auth
PUBLIC_ROUTES = {"/health", "/api/auth/login", "/api/auth/check", "/docs", "/openapi.json"}

# OAuth callback routes (exact match only)
OAUTH_CALLBACKS = {"/api/integrations/oauth/google/callback", "/api/integrations/oauth/shopify/callback"}


def _get_client_ip(request: Request) -> str:
    """Get client IP, preferring the last trusted proxy hop."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        # Use the rightmost IP (closest to the server, hardest to spoof)
        return xff.split(",")[-1].strip()
    return request.client.host or "unknown"


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check auth token + rate limit on all API requests (except public routes)."""
    path = request.url.path

    # ─── Rate Limiting ───
    client_ip = _get_client_ip(request)
    limit = _get_rate_limit(path)
    if not _check_rate_limit(client_ip, path, limit):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Try again in a minute. (Limit: {limit}/min)"}
        )

    # Allow public routes
    if path in PUBLIC_ROUTES:
        return await call_next(request)

    # Allow OAuth callbacks (exact match only — prevents bypass)
    if path in OAUTH_CALLBACKS:
        return await call_next(request)

    # Allow CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    # Check for auth token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if not token or token not in active_sessions:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    # Check expiry
    if active_sessions[token] < datetime.utcnow():
        del active_sessions[token]
        return JSONResponse(status_code=401, content={"detail": "Session expired"})

    response = await call_next(request)

    # ─── Add cache headers for GET requests ───
    if request.method == "GET":
        # Cache overview and summary data for 2 minutes (stale-while-revalidate)
        if "/overview" in path or "/full-summary" in path or "/summary" in path:
            response.headers["Cache-Control"] = "private, max-age=120, stale-while-revalidate=300"
        # Cache static data (websites list) for 5 minutes
        elif path == "/websites" or path.startswith("/api/websites/") and path.endswith("/automation-summary"):
            response.headers["Cache-Control"] = "private, max-age=300"
        # Cache audit history for 1 hour
        elif "/history" in path:
            response.headers["Cache-Control"] = "private, max-age=3600"
        # Default: no cache for everything else
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    return response


@app.post("/api/auth/login")
async def login(request: Request):
    """Login with username + password, returns a session token."""
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")

    if not AUTH_PASSWORD:
        # No password set = auth disabled, give a token
        token = secrets.token_urlsafe(32)
        active_sessions[token] = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        return {"success": True, "token": token, "message": "Auth disabled — no password set"}

    if username == AUTH_USERNAME and password == AUTH_PASSWORD:
        token = secrets.token_urlsafe(32)
        active_sessions[token] = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        print(f"[Auth] Login successful for '{username}'")
        return {"success": True, "token": token}

    print(f"[Auth] Login FAILED for '{username}'")
    return JSONResponse(status_code=401, content={"success": False, "message": "Invalid username or password"})


@app.get("/api/auth/check")
async def check_auth(request: Request):
    """Check if a token is still valid."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if not AUTH_PASSWORD:
        return {"authenticated": True, "auth_required": False}

    if token and token in active_sessions and active_sessions[token] > datetime.utcnow():
        return {"authenticated": True, "auth_required": True}

    return {"authenticated": False, "auth_required": True}


@app.post("/api/auth/logout")
async def logout(request: Request):
    """Invalidate a session token."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token in active_sessions:
        del active_sessions[token]
    return {"success": True}

# --- Pydantic Schemas ---
class WebsiteCreate(BaseModel):
    domain: str = Field(..., example="example.com")
    user_id: Optional[int] = 1
    site_type: Optional[str] = "custom"
    shopify_store_url: Optional[str] = None
    shopify_access_token: Optional[str] = None
    monthly_traffic: Optional[int] = None

# --- Core Endpoints ---

@app.get("/health")
async def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "database": db_status, "version": "1.0.0"}

@app.get("/health/env")
async def env_check(request: Request):
    """Check which API keys/env vars are configured. Requires auth."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if not token or token not in active_sessions:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    return {
        "GOOGLE_GEMINI_API_KEY": "set" if os.getenv("GOOGLE_GEMINI_API_KEY") else "MISSING",
        "DATAFORSEO_LOGIN": "set" if os.getenv("DATAFORSEO_LOGIN") else "MISSING",
        "DATAFORSEO_PASSWORD": "set" if os.getenv("DATAFORSEO_PASSWORD") else "MISSING",
        "GOOGLE_CLIENT_ID": "set" if os.getenv("GOOGLE_CLIENT_ID") else "MISSING",
        "GOOGLE_CLIENT_SECRET": "set" if os.getenv("GOOGLE_CLIENT_SECRET") else "MISSING",
        "ANTHROPIC_API_KEY": "set" if os.getenv("ANTHROPIC_API_KEY") else "MISSING",
        "GOOGLE_PAGESPEED_API_KEY": "set" if os.getenv("GOOGLE_PAGESPEED_API_KEY") else "MISSING",
    }

@app.get("/")
async def root():
    return {"message": "SEO Intelligence Platform API", "version": "1.0.0"}

# --- Website Management ---

import re

_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$')
_MAX_DOMAIN_LEN = 253

@app.post("/websites")
async def create_website(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        domain_raw = data.get('domain', '').strip()
        if not domain_raw:
            raise HTTPException(status_code=400, detail="Domain is required")

        # Sanitize domain
        domain = domain_raw.replace('http://', '').replace('https://', '').split('/')[0].rstrip('/').lower()
        if len(domain) > _MAX_DOMAIN_LEN or not _DOMAIN_RE.match(domain):
            raise HTTPException(status_code=400, detail="Invalid domain format")

        existing = db.query(Website).filter(Website.domain == domain).first()
        if existing:
            raise HTTPException(status_code=400, detail="Domain already registered")

        website = Website(
            user_id=data.get('user_id', 1),
            domain=domain,
            site_type=data.get('site_type', 'custom'),
            shopify_store_url=data.get('shopify_store_url'),
            shopify_access_token=data.get('shopify_access_token'),
            monthly_traffic=data.get('monthly_traffic')
        )
        db.add(website)
        db.commit()
        db.refresh(website)

        # Trigger initial audit in the background
        background_tasks.add_task(_run_audit_task, website.id)

        return {
            "id": website.id, "domain": website.domain, "site_type": website.site_type,
            "created_at": website.created_at.isoformat() if website.created_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")

@app.get("/websites")
async def get_websites(user_id: Optional[int] = None, db: Session = Depends(get_db)):
    try:
        query = db.query(Website)
        if user_id:
            query = query.filter(Website.user_id == user_id)
        websites = query.all()
        result = []
        for w in websites:
            latest_audit = db.query(AuditReport).filter(AuditReport.website_id == w.id).order_by(AuditReport.audit_date.desc()).first()
            result.append({
                "id": w.id, "domain": w.domain, "site_type": w.site_type,
                "monthly_traffic": w.monthly_traffic,
                "autonomy_mode": w.autonomy_mode,
                "health_score": latest_audit.health_score if latest_audit else None,
                "created_at": w.created_at.isoformat() if w.created_at else None
            })
        return result
    except Exception as e:
        print(f"[Website] Error fetching websites: {e}")
        return []

@app.delete("/websites/{website_id}")
async def delete_website(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    try:
        # Manually delete related records to avoid FK constraint errors
        db.query(Integration).filter(Integration.website_id == website_id).delete()
        db.query(ProposedFix).filter(ProposedFix.website_id == website_id).delete()
        db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).delete()
        db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).delete()
        db.query(AuditReport).filter(AuditReport.website_id == website_id).delete()
        db.query(ContentItem).filter(ContentItem.website_id == website_id).delete()
        db.delete(website)
        db.commit()
        return {"message": "Website deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting website: {str(e)}")

@app.put("/websites/{website_id}")
async def update_website(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    if 'domain' in data: website.domain = data['domain']
    if 'monthly_traffic' in data: website.monthly_traffic = data['monthly_traffic']
    if 'site_type' in data: website.site_type = data['site_type']
    if 'autonomy_mode' in data:
        mode = data['autonomy_mode']
        if mode not in ["manual", "smart", "ultra"]:
            raise HTTPException(status_code=400, detail="autonomy_mode must be 'manual', 'smart', or 'ultra'")
        website.autonomy_mode = mode
    db.commit()
    db.refresh(website)
    return {"id": website.id, "domain": website.domain, "site_type": website.site_type, "monthly_traffic": website.monthly_traffic, "autonomy_mode": website.autonomy_mode}

# --- Audit Background Task ---

async def _run_audit_async(website_id: int):
    """Run the audit engine asynchronously."""
    from audit_engine import SEOAuditEngine
    audit_engine = SEOAuditEngine(website_id)
    return await audit_engine.run_comprehensive_audit()

def _run_audit_task(website_id: int):
    """Background task wrapper that runs the async audit."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_audit_async(website_id))
        loop.close()
        print(f"[Background] Audit completed for website {website_id}: score {result.get('health_score', 'N/A')}")
    except Exception as e:
        print(f"[Background] Audit failed for website {website_id}: {e}")
        import traceback
        traceback.print_exc()

# --- Audit Endpoints ---

@app.post("/api/audit/{website_id}/start")
async def start_new_audit(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a new SEO audit for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    background_tasks.add_task(_run_audit_task, website_id)
    return {
        "status": "success",
        "message": f"Audit started for {website.domain}. Results will appear in 10-30 seconds."
    }

@app.get("/api/audit/{website_id}")
async def get_latest_audit_report(website_id: int, db: Session = Depends(get_db)):
    """Get the latest audit report for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    latest_report = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .first()

    # Get previous report for score comparison
    previous_report = None
    if latest_report:
        previous_report = db.query(AuditReport)\
            .filter(AuditReport.website_id == website_id)\
            .filter(AuditReport.id != latest_report.id)\
            .order_by(AuditReport.audit_date.desc())\
            .first()

    if not latest_report:
        return {
            "audit": None,
            "issues": [],
            "recommendations": [],
            "message": "No audit has been run yet. Click 'Run New Audit' to start your first SEO analysis."
        }

    previous_score = previous_report.health_score if previous_report else latest_report.health_score
    score_change = round(latest_report.health_score - previous_score, 1)

    findings = latest_report.detailed_findings or {"issues": [], "recommendations": []}

    raw_data = findings.get("raw_data", {})
    cwv_data = raw_data.get("core_web_vitals", {})

    return {
        "audit": {
            "id": latest_report.id,
            "health_score": latest_report.health_score,
            "previous_score": previous_score,
            "score_change": score_change,
            "technical_score": latest_report.technical_score,
            "content_score": latest_report.content_score,
            "performance_score": latest_report.performance_score,
            "mobile_score": latest_report.mobile_score,
            "desktop_score": latest_report.desktop_score,
            "security_score": latest_report.security_score,
            "total_issues": latest_report.total_issues,
            "critical_issues": latest_report.critical_issues,
            "errors": latest_report.errors,
            "warnings": latest_report.warnings,
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0,
            "fixed_issues": 0,
            "audit_date": latest_report.audit_date.isoformat(),
            "domain": website.domain,
            "core_web_vitals": cwv_data,
        },
        "issues": findings.get("issues", []),
        "recommendations": findings.get("recommendations", [])
    }

@app.get("/api/audit/{website_id}/history")
async def get_audit_history(website_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get audit history for a website."""
    reports = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .limit(limit)\
        .all()

    return [
        {
            "id": r.id,
            "health_score": r.health_score,
            "technical_score": r.technical_score,
            "content_score": r.content_score,
            "performance_score": r.performance_score,
            "mobile_score": r.mobile_score,
            "desktop_score": r.desktop_score,
            "security_score": r.security_score,
            "total_issues": r.total_issues,
            "critical_issues": r.critical_issues,
            "errors": r.errors,
            "warnings": r.warnings,
            "audit_date": r.audit_date.isoformat()
        }
        for r in reports
    ]

# --- Content Calendar ---

@app.get("/api/content-calendar/{website_id}")
async def get_content_calendar(website_id: int, db: Session = Depends(get_db)):
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).all()
    if not content_items:
        return []
    return [
        {"id": item.id, "website_id": item.website_id, "title": item.title, "content_type": item.content_type,
         "publish_date": item.publish_date.isoformat() if item.publish_date else None,
         "status": item.status, "keywords_target": item.keywords_target or [],
         "ai_generated_content": item.ai_generated_content}
        for item in content_items
    ]

@app.post("/api/content-calendar/{website_id}/generate")
async def generate_content_calendar(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    async def create_sample_content():
        for i in range(3):
            content = ContentItem(
                website_id=website_id, title=f"AI-Generated Content Idea {i+1}", content_type="Blog Post",
                publish_date=datetime.utcnow() + timedelta(days=(i+1)*7), status="Draft",
                keywords_target=["AI SEO", "content marketing", "automation"],
                ai_generated_content="AI-generated content would go here..."
            )
            db.add(content)
        db.commit()
    background_tasks.add_task(create_sample_content)
    return {"status": "success", "message": "Content generation initiated"}

# --- Error Monitoring (pulls from real audit data) ---

@app.get("/api/errors/{website_id}")
async def get_errors(website_id: int, db: Session = Depends(get_db)):
    """Get errors from the latest audit."""
    latest_report = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .first()

    if not latest_report or not latest_report.detailed_findings:
        return []

    issues = latest_report.detailed_findings.get("issues", [])

    return [
        {
            "id": issue.get("id", i+1),
            "title": issue.get("title", issue.get("issue_type", "Unknown")),
            "severity": issue.get("severity", "Warning").lower(),
            "description": issue.get("how_to_fix", ""),
            "page": issue.get("affected_pages", ["/"])[0] if issue.get("affected_pages") else "/",
            "category": issue.get("category", "Technical"),
            "auto_fixed": False,
            "affected_urls": issue.get("affected_pages", []),
        }
        for i, issue in enumerate(issues)
    ]

@app.post("/api/errors/{error_id}/fix")
async def fix_error(error_id: int):
    await asyncio.sleep(1)
    return {"status": "success", "message": f"Error {error_id} fix initiated"}

# --- Content Writer ---

@app.post("/api/content/{website_id}/generate")
async def generate_content_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate AI content — blog post, product description, landing page, etc."""
    data = await request.json()
    from content_writer import generate_content
    result = await generate_content(
        website_id=website_id,
        content_type=data.get("content_type", "blog_post"),
        topic=data.get("topic", ""),
        target_keywords=data.get("target_keywords", []),
        word_count=data.get("word_count", 800),
        tone=data.get("tone", "professional"),
        additional_instructions=data.get("instructions", ""),
    )
    return result

@app.post("/api/content/{website_id}/ideas")
async def suggest_content_ideas_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Get AI-suggested content ideas based on keyword gaps."""
    from content_writer import suggest_content_ideas
    result = await suggest_content_ideas(website_id)
    return result

@app.get("/api/content/{website_id}/list")
async def list_content(website_id: int, db: Session = Depends(get_db)):
    """List all generated content for a website."""
    items = db.query(ContentItem).filter(ContentItem.website_id == website_id).order_by(ContentItem.id.desc()).all()
    return {
        "content": [
            {
                "id": item.id, "title": item.title, "content_type": item.content_type,
                "status": item.status, "keywords": item.keywords_target or [],
                "created_at": item.publish_date.isoformat() if item.publish_date else None,
                "has_content": bool(item.ai_generated_content),
            }
            for item in items
        ]
    }

@app.get("/api/content/{website_id}/{content_id}")
async def get_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    """Get a specific content item with full generated content."""
    item = db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.website_id == website_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    content_data = {}
    if item.ai_generated_content:
        try:
            content_data = json.loads(item.ai_generated_content)
        except Exception:
            content_data = {"content_html": item.ai_generated_content}
    return {"id": item.id, "title": item.title, "content_type": item.content_type, "status": item.status, "keywords": item.keywords_target, "content": content_data}

@app.post("/api/content/{website_id}/{content_id}/publish")
async def publish_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    """Publish a content item to the connected platform."""
    from content_writer import publish_content
    result = await publish_content(website_id, content_id)
    return result


@app.post("/api/content/{website_id}/{content_id}/schedule")
async def schedule_content_item(website_id: int, content_id: int, request: Request, db: Session = Depends(get_db)):
    """Schedule a content item for publishing."""
    data = await request.json()
    publish_date_str = data.get("publish_date")
    if not publish_date_str:
        raise HTTPException(status_code=400, detail="publish_date is required")
    try:
        publish_date = datetime.fromisoformat(publish_date_str.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid publish_date format. Use ISO 8601.")

    from content_writer import schedule_content
    result = await schedule_content(website_id, content_id, publish_date)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/content/{website_id}/queue")
async def get_content_queue(website_id: int, db: Session = Depends(get_db)):
    """Get the publishing queue for a website."""
    from content_writer import get_publishing_queue
    result = await get_publishing_queue(website_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/content/{website_id}/{content_id}/cancel")
async def cancel_scheduled_content(website_id: int, content_id: int, db: Session = Depends(get_db)):
    """Cancel a scheduled content item."""
    from content_writer import cancel_scheduled
    result = await cancel_scheduled(website_id, content_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.delete("/api/content/{website_id}/{content_id}")
async def delete_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    """Delete a content item."""
    item = db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.website_id == website_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    db.delete(item)
    db.commit()
    return {"deleted": True}

# --- Competitor Analysis ---

@app.post("/api/competitors/{website_id}/research")
async def research_competitor(website_id: int, request: Request, db: Session = Depends(get_db)):
    """AI-powered competitor research — crawls competitor and compares with your data."""
    data = await request.json()
    competitor_domain = data.get("competitor_domain", "").strip()
    if not competitor_domain:
        return {"error": "Competitor domain is required"}

    competitor_domain = competitor_domain.replace("https://", "").replace("http://", "").rstrip("/")

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        return {"error": "Website not found"}

    # Get tracked keywords for context
    tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
    tracked_kws = [{"keyword": tk.keyword, "position": tk.current_position, "url": tk.target_url} for tk in tracked]

    # Get latest keyword snapshot
    latest_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).order_by(KeywordSnapshot.snapshot_date.desc()).first()
    top_keywords = []
    if latest_snap and latest_snap.keyword_data:
        top_keywords = [{"query": kw.get("query",""), "position": kw.get("position",0), "clicks": kw.get("clicks",0)} for kw in latest_snap.keyword_data[:20]]

    # Crawl competitor homepage + top pages
    competitor_content = ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(f"https://{competitor_domain}")
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.string if soup.title else ""
                meta_desc = ""
                meta_tag = soup.find("meta", attrs={"name": "description"})
                if meta_tag:
                    meta_desc = meta_tag.get("content", "")
                headings = [h.get_text(strip=True) for h in soup.find_all(['h1','h2','h3'])[:20]]
                links = [a.get('href','') for a in soup.find_all('a', href=True) if competitor_domain in a.get('href','')][:30]
                competitor_content = f"Title: {title}\nMeta: {meta_desc}\nHeadings: {', '.join(headings)}\nInternal pages: {len(links)}"
    except Exception as e:
        competitor_content = f"Could not crawl: {e}"

    # Use AI to analyze
    GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not GEMINI_API_KEY:
        return {"error": "AI API key not configured"}

    prompt = f"""You are an SEO competitive analyst. Analyze this competitor and provide actionable intelligence.

YOUR WEBSITE: {website.domain}
Your top keywords: {json.dumps(top_keywords[:10])}
Your tracked keywords (Road to #1): {json.dumps(tracked_kws)}

COMPETITOR: {competitor_domain}
Competitor page data: {competitor_content[:2000]}

Provide:
1. COMPETITOR OVERVIEW: What they do, their apparent SEO strategy, strengths
2. CONTENT GAPS: Topics/keywords they cover that {website.domain} doesn't
3. THEIR WEAKNESSES: Where {website.domain} already beats them or could easily beat them
4. KEYWORD OPPORTUNITIES: Keywords they rank for that {website.domain} should target
5. ACTION PLAN: 5 specific things to do this week to gain ground against them

Be specific, actionable, and reference actual data. Format with clear sections."""

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.4}}
            )
            if resp.status_code == 200:
                analysis = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {"competitor_analysis": analysis, "competitor_domain": competitor_domain, "your_domain": website.domain}
            elif resp.status_code == 429:
                return {"error": "AI rate limited. Try again in a minute or enable Gemini billing."}
            else:
                return {"error": f"AI error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# --- Legacy Google Auth ---

@app.get("/auth/google/init")
async def init_google_auth(user_id: int = 1, integration_type: str = "search_console"):
    return {"authorization_url": f"https://accounts.google.com/oauth/authorize?client_id=xxx&redirect_uri=xxx&scope={integration_type}"}

# --- Database Migrations (lightweight, run at startup) ---
def _run_migrations():
    """Add missing columns that may not exist in older databases."""
    db = SessionLocal()
    try:
        # Check if desktop_score column exists in audit_reports
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

# --- Include Routers ---
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

# --- New Feature Routes ---

# Hub & Spoke Internal Linking
@app.post("/api/linking/{website_id}/analyze")
async def analyze_linking(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Analyze internal link structure and generate link suggestions."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from linking_engine import analyze_internal_linking
    raw = await analyze_internal_linking(website_id)
    if isinstance(raw, dict) and not raw.get("error"):
        domain = raw.get("domain", "")
        def _abs(path: str) -> str:
            if not path: return ""
            if path.startswith("http"): return path
            return f"https://{domain}{path}" if domain else path
        hubs = [{
            "url": _abs(h.get("path", "")),
            "title": h.get("path", ""),
            "inbound": h.get("inbound_links", 0),
            "outbound": 0,
            "is_hub": True, "is_orphan": False,
        } for h in raw.get("hub_pages", [])]
        orphans = [{
            "url": _abs(o.get("path", "")),
            "title": o.get("title", ""),
            "inbound": o.get("inbound", 0),
            "outbound": 0,
            "is_hub": False, "is_orphan": True,
        } for o in raw.get("orphan_pages", [])]
        suggestions = [{
            "from_url": _abs(s.get("source_page", "")),
            "to_url": _abs(s.get("target_page", "")),
            "anchor_text": s.get("anchor_text", ""),
            "reason": s.get("reason", ""),
        } for s in raw.get("link_suggestions", [])]
        result = {
            "total_pages": raw.get("pages_analyzed", 0),
            "total_internal_links": raw.get("total_internal_links", 0),
            "avg_links_per_page": raw.get("avg_internal_links", 0),
            "hubs": hubs,
            "orphans": orphans,
            "suggestions": suggestions,
            "analyzed_at": raw.get("analyzed_at"),
        }
        try:
            from database import StrategistResult
            from datetime import datetime as _dt
            row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
            if not row:
                row = StrategistResult(website_id=website_id)
                db.add(row); db.flush()
            row.linking = result
            row.linking_generated_at = _dt.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Linking] persist failed: {e}")
            db.rollback()
        return result
    return raw


@app.get("/api/linking/{website_id}/graph")
async def get_linking_graph(website_id: int, db: Session = Depends(get_db)):
    """Return the internal link graph as nodes and edges for visualization."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from linking_engine import get_link_graph
    result = get_link_graph(website_id)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# Content Decay Detection
@app.post("/api/decay/{website_id}/analyze")
async def analyze_decay(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Detect content decay — check freshness vs competitors."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from content_decay import detect_content_decay
    raw = await detect_content_decay(website_id)
    if isinstance(raw, dict) and not raw.get("error"):
        def _bucket(score):
            if score < 40: return "high"
            if score < 65: return "medium"
            return "low"
        from datetime import datetime as _dt2
        def _days_since(signals):
            for k in ("modified_date", "schema_date_modified", "last_modified", "published_date", "schema_date_published"):
                v = signals.get(k) if signals else None
                if not v: continue
                try:
                    dt = _dt2.fromisoformat(str(v).replace("Z", "+00:00").split("+")[0])
                    return max(0, (_dt2.utcnow() - dt).days)
                except Exception: pass
            return 0
        items = []
        for p in raw.get("own_pages", []):
            score = p.get("freshness_score", 50)
            signals = p.get("signals", {}) or {}
            last_mod = (signals.get("modified_date") or signals.get("schema_date_modified")
                        or signals.get("last_modified") or signals.get("published_date") or "")
            days = _days_since(signals)
            items.append({
                "url": p.get("url", ""),
                "title": p.get("title", ""),
                "last_modified": last_mod,
                "days_since_update": days,
                "decay_risk": _bucket(score),
                "recommendation": (
                    "Refresh content — very stale" if score < 40 else
                    "Consider updating soon" if score < 65 else
                    "Fresh enough — monitor"
                ),
            })
        comp_map = {c.get("our_page", ""): c for c in raw.get("competitor_comparison", [])}
        for it in items:
            c = comp_map.get(it["url"])
            if c:
                it["current_position"] = c.get("position")
                it["competitor_freshness"] = (
                    f"Gap {c.get('freshness_gap', 0):+d} vs top competitor"
                )
        high = [i for i in items if i["decay_risk"] == "high"]
        med = [i for i in items if i["decay_risk"] == "medium"]
        low = [i for i in items if i["decay_risk"] == "low"]
        result = {
            "total_pages_analyzed": raw.get("pages_checked", len(items)),
            "high_risk": high,
            "medium_risk": med,
            "low_risk": low,
            "refresh_recommendations": [
                (r if isinstance(r, str) else
                 f"[{r.get('priority','med').upper()}] {r.get('action','')} — {r.get('reason','')}".strip(" —"))
                for r in (raw.get("recommendations") or [])
            ],
            "analyzed_at": raw.get("analyzed_at"),
        }
        try:
            from database import StrategistResult
            from datetime import datetime as _dt
            row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
            if not row:
                row = StrategistResult(website_id=website_id)
                db.add(row); db.flush()
            row.decay = result
            row.decay_generated_at = _dt.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Decay] persist failed: {e}")
            db.rollback()
        return result
    return raw


# GA4 Traffic Data
@app.get("/api/ga4/{website_id}/traffic")
async def get_ga4_traffic(website_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Fetch traffic data from Google Analytics 4."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ga4_data import fetch_ga4_traffic
    result = await fetch_ga4_traffic(website_id, days=days)
    return result

# --- AI Overseer ---

@app.post("/api/overseer/{website_id}/run")
async def run_overseer(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Run the AI Overseer for a specific website. Does: audit → keywords → GEO scan → fixes → strategy refresh."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ai_overseer import run_overseer_background
    background_tasks.add_task(run_overseer_background, website_id)

    return {
        "status": "running",
        "message": f"AI Overseer started for {website.domain}. Running: audit → keywords → GEO scan → fixes → strategy refresh. Check Issues & Fixes for results."
    }

@app.post("/api/overseer/run-all")
async def run_overseer_all(background_tasks: BackgroundTasks):
    """Run the AI Overseer for ALL websites."""
    from ai_overseer import run_overseer_background
    background_tasks.add_task(run_overseer_background, None)
    return {"status": "running", "message": "AI Overseer started for all websites."}


@app.get("/api/overseer/status")
async def overseer_status(website_id: Optional[int] = None):
    """Return current AI Overseer phase. Reflects real backend activity (no fake messages)."""
    from ai_overseer import get_overseer_status
    return get_overseer_status(website_id)


@app.get("/api/websites/{website_id}/automation-summary")
async def get_automation_summary(website_id: int, days: int = 7):
    """Get automation summary for a website (auto-approved/applied fixes)."""
    from reporting import generate_automation_summary
    result = await generate_automation_summary(website_id, days)
    return result


@app.get("/api/websites/{website_id}/full-summary")
async def get_full_website_summary(website_id: int, db: Session = Depends(get_db)):
    """Get a comprehensive unified summary for a single website — all modules in one call."""
    website = db.query(Website).filter(Website.id == website_id, Website.is_active == True).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    # ─── 1. Audit History (for trend charts) ───
    audit_history = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .limit(30).all()
    audit_history_reversed = list(reversed(audit_history))

    latest_audit = audit_history[0] if audit_history else None
    prev_audit = audit_history[1] if len(audit_history) > 1 else None

    # ─── 2. Keyword Snapshot History ───
    keyword_history = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc())\
        .limit(30).all()
    keyword_history_reversed = list(reversed(keyword_history))

    latest_snap = keyword_history[0] if keyword_history else None

    # ─── 3. Fixes Summary ───
    pending_fixes = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id, ProposedFix.status == "pending"
    ).count()
    approved_fixes = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id, ProposedFix.status == "approved"
    ).count()
    applied_fixes = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id, ProposedFix.status == "applied"
    ).count()
    auto_approved_count = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id, ProposedFix.auto_approved_at != None
    ).count()
    auto_applied_count = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id, ProposedFix.auto_applied == True
    ).count()

    # ─── 4. Tracked Keywords (Road to #1) ───
    tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
    tracked_keywords = []
    for tk in tracked:
        tracked_keywords.append({
            "id": tk.id,
            "keyword": tk.keyword,
            "current_position": tk.current_position,
            "target_position": tk.target_position,
            "status": tk.status,
            "current_clicks": tk.current_clicks,
            "current_impressions": tk.current_impressions,
        })

    # ─── 5. Strategist Cache ───
    strategist = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()

    # ─── 6. Content Items ───
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).order_by(ContentItem.id.desc()).limit(5).all()

    # ─── 7. GEO Audit ───
    geo_audit = None
    if strategist and strategist.geo_audit:
        geo_audit = strategist.geo_audit

    return {
        "website": {
            "id": website.id,
            "domain": website.domain,
            "site_type": website.site_type,
            "autonomy_mode": website.autonomy_mode,
            "created_at": website.created_at.isoformat() if website.created_at else None,
        },
        "audit": {
            "latest": {
                "health_score": latest_audit.health_score if latest_audit else None,
                "technical_score": latest_audit.technical_score if latest_audit else None,
                "content_score": latest_audit.content_score if latest_audit else None,
                "performance_score": latest_audit.performance_score if latest_audit else None,
                "mobile_score": latest_audit.mobile_score if latest_audit else None,
                "desktop_score": latest_audit.desktop_score if latest_audit else None,
                "security_score": latest_audit.security_score if latest_audit else None,
                "total_issues": latest_audit.total_issues if latest_audit else 0,
                "critical_issues": latest_audit.critical_issues if latest_audit else 0,
                "errors": latest_audit.errors if latest_audit else 0,
                "warnings": latest_audit.warnings if latest_audit else 0,
                "audit_date": latest_audit.audit_date.isoformat() if latest_audit else None,
                "score_change": round(latest_audit.health_score - (prev_audit.health_score if prev_audit else latest_audit.health_score), 1) if latest_audit else 0,
            },
            "history": [
                {
                    "date": a.audit_date.isoformat(),
                    "health_score": a.health_score,
                    "technical_score": a.technical_score,
                    "content_score": a.content_score,
                    "performance_score": a.performance_score,
                    "total_issues": a.total_issues,
                }
                for a in audit_history_reversed
            ],
        },
        "keywords": {
            "latest": {
                "total_keywords": latest_snap.total_keywords if latest_snap else 0,
                "total_clicks": latest_snap.total_clicks if latest_snap else 0,
                "total_impressions": latest_snap.total_impressions if latest_snap else 0,
                "avg_position": latest_snap.avg_position if latest_snap else 0,
                "avg_ctr": latest_snap.avg_ctr if latest_snap else 0,
                "snapshot_date": latest_snap.snapshot_date.isoformat() if latest_snap else None,
            },
            "history": [
                {
                    "date": s.snapshot_date.isoformat(),
                    "total_keywords": s.total_keywords,
                    "total_clicks": s.total_clicks,
                    "total_impressions": s.total_impressions,
                    "avg_position": s.avg_position,
                }
                for s in keyword_history_reversed
            ],
            "tracked": tracked_keywords,
            "tracked_count": len(tracked_keywords),
        },
        "fixes": {
            "pending": pending_fixes,
            "approved": approved_fixes,
            "applied": applied_fixes,
            "auto_approved": auto_approved_count,
            "auto_applied": auto_applied_count,
        },
        "strategist": {
            "has_strategy": bool(strategist and strategist.strategy),
            "has_weekly": bool(strategist and strategist.weekly_plan),
            "has_portfolio": bool(strategist and strategist.portfolio),
            "has_linking": bool(strategist and strategist.linking),
            "has_decay": bool(strategist and strategist.decay),
            "strategy_generated_at": strategist.strategy_generated_at.isoformat() if strategist and strategist.strategy_generated_at else None,
            "weekly_generated_at": strategist.weekly_generated_at.isoformat() if strategist and strategist.weekly_generated_at else None,
        },
        "geo": {
            "has_audit": bool(geo_audit),
            "overall_score": geo_audit.get("scores", {}).get("overall") if geo_audit else None,
            "pages_analyzed": geo_audit.get("pages_analyzed") if geo_audit else None,
            "audit_date": strategist.geo_audit_at.isoformat() if strategist and strategist.geo_audit_at else None,
        },
        "content": {
            "recent_count": len(content_items),
            "recent": [
                {"id": c.id, "title": c.title, "content_type": c.content_type, "status": c.status}
                for c in content_items
            ],
        },
    }


# --- Overview Summary ---

@app.get("/api/overview")
async def get_overview_summary(db: Session = Depends(get_db)):
    """Get a quick summary for all websites — health, keywords, changes."""
    websites = db.query(Website).filter(Website.is_active == True).all()
    summaries = []

    for w in websites:
        summary = {"id": w.id, "domain": w.domain, "site_type": w.site_type}

        # Latest audit
        latest_audit = db.query(AuditReport).filter(AuditReport.website_id == w.id).order_by(AuditReport.audit_date.desc()).first()
        prev_audit = None
        if latest_audit:
            prev_audit = db.query(AuditReport).filter(AuditReport.website_id == w.id, AuditReport.id != latest_audit.id).order_by(AuditReport.audit_date.desc()).first()

        if latest_audit:
            prev_score = prev_audit.health_score if prev_audit else latest_audit.health_score
            summary["health_score"] = latest_audit.health_score
            summary["score_change"] = round(latest_audit.health_score - prev_score, 1)
            summary["total_issues"] = latest_audit.total_issues
            summary["critical_issues"] = latest_audit.critical_issues
            summary["issues_change"] = latest_audit.total_issues - (prev_audit.total_issues if prev_audit else latest_audit.total_issues)
            summary["last_audit"] = latest_audit.audit_date.isoformat()
        else:
            summary["health_score"] = None
            summary["score_change"] = 0
            summary["total_issues"] = 0
            summary["critical_issues"] = 0
            summary["issues_change"] = 0
            summary["last_audit"] = None

        # Latest keywords
        latest_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == w.id).order_by(KeywordSnapshot.snapshot_date.desc()).first()
        prev_snap = None
        if latest_snap:
            prev_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == w.id, KeywordSnapshot.id != latest_snap.id).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest_snap:
            summary["total_keywords"] = latest_snap.total_keywords
            summary["total_clicks"] = latest_snap.total_clicks
            summary["total_impressions"] = latest_snap.total_impressions
            summary["avg_position"] = latest_snap.avg_position
            summary["keywords_change"] = latest_snap.total_keywords - (prev_snap.total_keywords if prev_snap else 0)
            summary["clicks_change"] = latest_snap.total_clicks - (prev_snap.total_clicks if prev_snap else 0)
        else:
            summary["total_keywords"] = 0
            summary["total_clicks"] = 0
            summary["total_impressions"] = 0
            summary["avg_position"] = 0
            summary["keywords_change"] = 0
            summary["clicks_change"] = 0

        # Fixes
        summary["pending_fixes"] = db.query(ProposedFix).filter(ProposedFix.website_id == w.id, ProposedFix.status == "pending").count()
        summary["applied_fixes"] = db.query(ProposedFix).filter(ProposedFix.website_id == w.id, ProposedFix.status == "applied").count()
        summary["autonomy_mode"] = w.autonomy_mode

        # Tracked keywords
        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == w.id).all()
        summary["tracked_count"] = len(tracked)
        summary["tracked_keywords"] = [{"keyword": tk.keyword, "position": tk.current_position, "clicks": tk.current_clicks} for tk in tracked[:5]]

        summaries.append(summary)

    return {"websites": summaries}

# --- Daily Audit Scheduler ---

_daily_audit_running = False

async def _run_daily_audits():
    """Run audits for all active websites. Called once per day."""
    global _daily_audit_running
    if _daily_audit_running:
        print("[DailyAudit] Already running, skipping")
        return
    _daily_audit_running = True
    try:
        db = SessionLocal()
        websites = db.query(Website).filter(Website.is_active == True).all()
        db.close()

        print(f"[DailyAudit] Starting daily audits for {len(websites)} websites")
        for w in websites:
            try:
                from audit_engine import SEOAuditEngine
                engine = SEOAuditEngine(w.id)
                result = await engine.run_comprehensive_audit()
                print(f"[DailyAudit] {w.domain}: score {result.get('health_score', 'N/A')}")

                # ─── Auto-fix scan for Smart/Ultra mode sites ───
                if w.autonomy_mode in ["smart", "ultra"] and w.site_type in ["shopify", "wordpress"]:
                    try:
                        print(f"[DailyAudit] {w.domain}: auto-fix scan (mode: {w.autonomy_mode})")
                        from fix_engine import generate_fixes_for_website
                        fix_result = await generate_fixes_for_website(w.id)
                        print(f"[DailyAudit] {w.domain}: {fix_result.get('total_fixes', 0)} fixes generated, {fix_result.get('auto_applied', 0)} auto-applied")
                    except Exception as e:
                        print(f"[DailyAudit] {w.domain}: auto-fix scan failed: {e}")

                await asyncio.sleep(5)  # Pause between sites
            except Exception as e:
                print(f"[DailyAudit] {w.domain} failed: {e}")
        print("[DailyAudit] All daily audits complete")
    except Exception as e:
        print(f"[DailyAudit] Error: {e}")
    finally:
        _daily_audit_running = False

def _schedule_daily_audits():
    """Schedule daily audits and weekly overseer runs."""
    import threading

    def _daily_loop():
        import time
        while True:
            # Wait until 3 AM UTC
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Next daily audit in {wait_seconds/3600:.1f} hours (3 AM UTC)")
            time.sleep(wait_seconds)

            # Run daily audits
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_daily_audits())
                loop.close()
            except Exception as e:
                print(f"[Scheduler] Daily audit error: {e}")

    def _weekly_loop():
        """Run full overseer cycle every Monday at 4 AM UTC."""
        import time
        while True:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            # Find next Monday
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 4:
                days_until_monday = 7
            target = (now + timedelta(days=days_until_monday)).replace(
                hour=4, minute=0, second=0, microsecond=0)
            wait_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Next weekly overseer in {wait_seconds/3600:.1f} hours (Monday 4 AM UTC)")
            time.sleep(wait_seconds)

            # Run full overseer for all websites
            try:
                from ai_overseer import run_overseer_background
                run_overseer_background(None)  # All websites
                print("[Scheduler] Weekly overseer cycle complete")
            except Exception as e:
                print(f"[Scheduler] Weekly overseer error: {e}")

    # Start both scheduler threads
    daily_thread = threading.Thread(target=_daily_loop, daemon=True)
    daily_thread.start()
    print("[Scheduler] Daily audit scheduler started (runs at 3 AM UTC)")

    weekly_thread = threading.Thread(target=_weekly_loop, daemon=True)
    weekly_thread.start()
    print("[Scheduler] Weekly overseer scheduler started (runs Monday 4 AM UTC)")

# --- Startup ---

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
                # Performance indexes
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
                # New tables for missing features
                """CREATE TABLE IF NOT EXISTS core_web_vitals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL,
                    url VARCHAR DEFAULT '/',
                    lcp FLOAT,
                    inp FLOAT,
                    cls FLOAT,
                    fcp FLOAT,
                    ttfb FLOAT,
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
                    config JSON,
                    events JSON,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS notification_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER NOT NULL,
                    website_id INTEGER NOT NULL,
                    event_type VARCHAR NOT NULL,
                    status VARCHAR DEFAULT 'pending',
                    message TEXT,
                    response TEXT,
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
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    winner VARCHAR,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS local_seo_presence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    website_id INTEGER NOT NULL UNIQUE,
                    business_name VARCHAR,
                    address VARCHAR,
                    city VARCHAR,
                    postcode VARCHAR,
                    country VARCHAR DEFAULT 'GB',
                    phone VARCHAR,
                    category VARCHAR,
                    gbp_url VARCHAR,
                    gbp_status VARCHAR DEFAULT 'not_claimed',
                    review_count INTEGER DEFAULT 0,
                    avg_rating FLOAT,
                    last_checked TIMESTAMP
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

    # Start daily audit scheduler
    _schedule_daily_audits()


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: BACKUP / EXPORT / DATA RECOVERY
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
from datetime import datetime

# Railway DB check endpoint removed — exposed internal connection details.


@app.post("/api/admin/db/backup")
async def create_backup():
    """Create a JSON backup of the entire database."""
    from export_engine import export_database_to_json
    import os
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"seo_backup_{timestamp}_{uuid.uuid4().hex[:8]}.json"
    filepath = os.path.join(_BACKUP_DIR, filename)
    data = export_database_to_json()
    with open(filepath, "w") as f:
        f.write(data)
    size = os.path.getsize(filepath)
    db = SessionLocal()
    try:
        websites_count = db.query(Website).count()
        backup = DatabaseBackup(
            backup_type="manual", format="json", file_path=filepath,
            size_bytes=size, websites_count=websites_count
        )
        db.add(backup)
        db.commit()
        return {"success": True, "file": filename, "size_bytes": size, "websites": websites_count}
    finally:
        db.close()


@app.get("/api/admin/db/backups")
async def list_backups():
    """List all database backups."""
    db = SessionLocal()
    try:
        backups = db.query(DatabaseBackup).order_by(DatabaseBackup.created_at.desc()).all()
        return [{"id": b.id, "type": b.backup_type, "file": b.file_path,
                 "size": b.size_bytes, "websites": b.websites_count,
                 "created_at": b.created_at.isoformat() if b.created_at else None}
                for b in backups]
    finally:
        db.close()


import uuid

_BACKUP_DIR = os.path.abspath("backups")

@app.post("/api/admin/db/restore")
async def restore_from_backup(request: Request):
    """Restore websites from a JSON backup file."""
    data = await request.json()
    filepath_raw = data.get("file", "")
    # Prevent path traversal — only allow files in the backups directory
    filepath = os.path.abspath(os.path.join(_BACKUP_DIR, os.path.basename(filepath_raw)))
    if not filepath.startswith(_BACKUP_DIR) or not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="Backup file not found or invalid path")
    try:
        with open(filepath, "r") as f:
            backup = json.load(f)
    except (json.JSONDecodeError, OSError):
        raise HTTPException(status_code=400, detail="Invalid backup file")
    db = SessionLocal()
    restored = 0
    try:
        for w_data in backup.get("websites", []):
            domain = w_data.get("domain", "")
            if not domain or not _DOMAIN_RE.match(domain):
                continue
            existing = db.query(Website).filter(Website.domain == domain).first()
            if existing:
                continue
            website = Website(
                domain=domain,
                site_type=w_data.get("site_type", "custom"),
                monthly_traffic=w_data.get("monthly_traffic"),
                autonomy_mode=w_data.get("autonomy_mode", "manual"),
            )
            db.add(website)
            db.commit()
            db.refresh(website)
            restored += 1
            for a in w_data.get("audits", []):
                audit = AuditReport(
                    website_id=website.id,
                    health_score=a.get("health_score", 0),
                    technical_score=a.get("technical_score", 0),
                    content_score=a.get("content_score", 0),
                    performance_score=a.get("performance_score", 0),
                    mobile_score=a.get("mobile_score", 0),
                    security_score=a.get("security_score", 0),
                    total_issues=a.get("total_issues", 0),
                    critical_issues=a.get("critical_issues", 0),
                    errors=a.get("errors", 0),
                    warnings=a.get("warnings", 0),
                    detailed_findings=a.get("findings", {}),
                )
                db.add(audit)
            for c in w_data.get("content", []):
                item = ContentItem(
                    website_id=website.id,
                    title=c.get("title", "")[:500],
                    content_type=c.get("content_type", "Blog Post"),
                    status=c.get("status", "Draft"),
                    keywords_target=c.get("keywords_target", []),
                )
                db.add(item)
            for tk in w_data.get("tracked_keywords", []):
                tk_obj = TrackedKeyword(
                    website_id=website.id,
                    keyword=tk.get("keyword", "")[:500],
                    current_position=tk.get("current_position"),
                    target_position=tk.get("target_position", 1),
                    status=tk.get("status", "tracking"),
                )
                db.add(tk_obj)
            db.commit()
        return {"success": True, "restored": restored, "total_in_backup": len(backup.get("websites", []))}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: CSV/JSON EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse

@app.get("/api/export/{website_id}/audit.csv")
async def export_audit_csv(website_id: int):
    from export_engine import export_audit_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_audit_to_csv(website_id)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit-{domain}.csv"}
    )


@app.get("/api/export/{website_id}/keywords.csv")
async def export_keywords_csv(website_id: int):
    from export_engine import export_keywords_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_keywords_to_csv(website_id)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=keywords-{domain}.csv"}
    )


@app.get("/api/export/{website_id}/fixes.csv")
async def export_fixes_csv(website_id: int):
    from export_engine import export_fixes_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_fixes_to_csv(website_id)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fixes-{domain}.csv"}
    )


@app.get("/api/export/{website_id}/full-report.json")
async def export_full_report_json(website_id: int):
    from export_engine import export_full_report_to_json
    json_str = export_full_report_to_json(website_id)
    return StreamingResponse(
        io.BytesIO(json_str.encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=report-{website_id}.json"}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: CORE WEB VITALS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/cwv/{website_id}/check")
async def check_cwv(website_id: int):
    from cwv_monitor import check_cwv_for_website
    result = await check_cwv_for_website(website_id)
    return result


@app.get("/api/cwv/{website_id}/latest")
async def get_latest_cwv_endpoint(website_id: int):
    from cwv_monitor import get_latest_cwv
    return get_latest_cwv(website_id)


@app.get("/api/cwv/{website_id}/history")
async def get_cwv_history_endpoint(website_id: int, days: int = 30, device: str = "mobile"):
    from cwv_monitor import get_cwv_history
    return {"history": get_cwv_history(website_id, days, device)}


@app.get("/api/cwv/{website_id}/trends")
async def get_cwv_trends_endpoint(website_id: int):
    from cwv_monitor import get_cwv_trends
    return get_cwv_trends(website_id)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/notifications/{website_id}/channels")
async def add_notification_channel(website_id: int, request: Request):
    data = await request.json()
    db = SessionLocal()
    try:
        channel = NotificationChannel(
            website_id=website_id,
            channel_type=data.get("channel_type"),
            name=data.get("name"),
            config=data.get("config", {}),
            events=data.get("events", []),
            is_active=data.get("is_active", True),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return {"id": channel.id, "name": channel.name, "channel_type": channel.channel_type, "events": channel.events}
    finally:
        db.close()


@app.get("/api/notifications/{website_id}/channels")
async def list_notification_channels(website_id: int):
    from notifications import get_notification_channels
    return {"channels": get_notification_channels(website_id)}


@app.delete("/api/notifications/channels/{channel_id}")
async def delete_notification_channel(channel_id: int):
    db = SessionLocal()
    try:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        db.delete(channel)
        db.commit()
        return {"success": True}
    finally:
        db.close()


@app.post("/api/notifications/channels/{channel_id}/test")
async def test_notification_channel(channel_id: int):
    from notifications import notify_event
    db = SessionLocal()
    try:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        results = await notify_event(
            channel.website_id, "test",
            "Test Notification",
            f"This is a test notification from your {channel.name} channel. If you see this, your setup is working! 🎉",
            {"test": True}
        )
        return {"success": True, "results": results}
    finally:
        db.close()


@app.get("/api/notifications/{website_id}/logs")
async def get_notification_logs(website_id: int, limit: int = 50):
    from notifications import get_notification_logs
    return {"logs": get_notification_logs(website_id, limit)}


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: SCHEMA.ORG GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/schema/{website_id}/generate")
async def generate_schema_endpoint(website_id: int, request: Request):
    from schema_generator import generate_schema
    data = await request.json()
    schema_type = data.get("schema_type", "Organization")
    result = await generate_schema(schema_type, data.get("data", {}))
    return result


@app.post("/api/schema/{website_id}/validate")
async def validate_schema_endpoint(request: Request):
    from schema_generator import validate_schema
    data = await request.json()
    schema = data.get("schema", {})
    return validate_schema(schema)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: IMAGE OPTIMIZATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/images/{website_id}/audit")
async def run_image_audit(website_id: int):
    from image_optimizer import ImageOptimizer
    optimizer = ImageOptimizer(website_id)
    result = await optimizer.analyze_images()
    return result


@app.get("/api/images/{website_id}/stats")
async def get_image_stats_endpoint(website_id: int):
    from image_optimizer import get_image_stats
    return get_image_stats(website_id)


@app.get("/api/images/{website_id}/issues")
async def get_image_issues_endpoint(website_id: int, severity: str = None, limit: int = 100):
    from image_optimizer import get_image_issues
    return {"issues": get_image_issues(website_id, severity, limit)}


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: A/B TESTING
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/ab-test/{website_id}/create")
async def create_ab_test(website_id: int, request: Request):
    from ab_testing import create_test
    data = await request.json()
    result = await create_test(
        website_id=website_id,
        page_url=data.get("page_url", ""),
        element_type=data.get("element_type", "title"),
        variant_a=data.get("variant_a", ""),
        keywords=data.get("keywords", [])
    )
    return result


@app.get("/api/ab-test/{website_id}/list")
async def list_ab_tests(website_id: int):
    from ab_testing import list_tests
    return {"tests": list_tests(website_id)}


@app.post("/api/ab-test/{test_id}/start")
async def start_ab_test(test_id: int):
    from ab_testing import start_test
    return start_test(test_id)


@app.post("/api/ab-test/{test_id}/end")
async def end_ab_test(test_id: int, request: Request):
    from ab_testing import end_test
    data = await request.json()
    return end_test(test_id, data.get("winner", "tie"), data.get("notes"))


@app.get("/api/ab-test/{test_id}/results")
async def get_ab_test_results(test_id: int):
    from ab_testing import get_test_results
    return get_test_results(test_id)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: LOCAL SEO
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/local-seo/{website_id}/setup")
async def setup_local_seo(website_id: int, request: Request):
    from local_seo import update_local_seo
    data = await request.json()
    return update_local_seo(website_id, data)


@app.get("/api/local-seo/{website_id}/status")
async def get_local_seo_endpoint(website_id: int):
    from local_seo import get_local_seo_status
    return get_local_seo_status(website_id)


@app.post("/api/local-seo/{website_id}/check-citations")
async def check_local_citations(website_id: int):
    from local_seo import check_citations
    return await check_citations(website_id)


@app.get("/api/local-seo/{website_id}/schema")
async def get_local_schema_endpoint(website_id: int):
    from local_seo import generate_local_schema
    return generate_local_schema(website_id)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: SITEMAP GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/sitemap/{website_id}/generate")
async def generate_sitemap_endpoint(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate a sitemap for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await generate_sitemap(website_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/sitemap/{website_id}")
async def get_sitemap_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Get the current sitemap for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    return await get_sitemap(website_id)


@app.post("/api/sitemap/{website_id}/submit")
async def submit_sitemap_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Submit sitemap to Google Search Console."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    data = await request.json()
    sitemap_url = data.get("sitemap_url", "")
    if not sitemap_url:
        # Default to domain/sitemap.xml
        sitemap_url = f"https://{website.domain}/sitemap.xml"

    result = await submit_to_gsc(website_id, sitemap_url)
    return result


@app.get("/api/sitemap/{website_id}/validate")
async def validate_sitemap_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Validate the current sitemap."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    if not website.sitemap_xml:
        return {"valid": False, "error": "No sitemap generated yet"}

    validation = validate_sitemap(website.sitemap_xml)
    return {
        "valid": validation["valid"],
        "url_count": validation["url_count"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: ROBOTS.TXT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/robots/{website_id}/generate")
async def generate_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Generate an optimized robots.txt for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    result = generate_robots_txt(website_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/robots/{website_id}")
async def get_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Get the current stored robots.txt for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    return get_robots_txt(website_id)


@app.post("/api/robots/{website_id}/validate")
async def validate_robots_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Validate robots.txt content (uses stored or provided content)."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    data = await request.json()
    content = data.get("content", website.robots_txt or "")

    if not content:
        return {"valid": False, "error": "No robots.txt content to validate"}

    result = validate_robots_txt(content, website_id)
    return result


@app.get("/api/robots/{website_id}/check")
async def check_existing_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Check the existing robots.txt on the live website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    result = await check_existing_robots(website_id)
    return result


@app.put("/api/robots/{website_id}")
async def update_robots_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Update the stored robots.txt with edited content."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    data = await request.json()
    content = data.get("content", "")
    result = update_robots_txt(website_id, content)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# NEW ENDPOINTS: MULTI-USER
# ═══════════════════════════════════════════════════════════════════════════════

# User registration and listing endpoints removed for security.
# This is a single-user application. Users are managed via database directly.


# Multi-user member endpoints disabled for security.
# This is a single-user application.


# ═══════════════════════════════════════════════════════════════════════════════
# BROKEN LINK CHECKER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/links/{website_id}/scan")
async def start_link_scan(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start a broken link scan for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    async def _run_scan():
        from link_checker import scan_broken_links
        await scan_broken_links(website_id)

    background_tasks.add_task(_run_scan)
    return {
        "status": "success",
        "message": f"Broken link scan started for {website.domain}. Results will appear shortly."
    }


@app.get("/api/links/{website_id}/broken")
async def get_broken_links_endpoint(
    website_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get broken links for a website, optionally filtered by error type."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from link_checker import get_broken_links
    results = get_broken_links(website_id, status_filter=status)
    return {"broken_links": results, "count": len(results)}


@app.get("/api/links/{website_id}/summary")
async def get_link_summary_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Get link health summary for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from link_checker import get_link_health_summary
    return get_link_health_summary(website_id)


@app.post("/api/links/{link_id}/mark-fixed")
async def mark_link_fixed_endpoint(link_id: int, db: Session = Depends(get_db)):
    """Mark a broken link as fixed."""
    from link_checker import mark_link_fixed
    result = mark_link_fixed(link_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# INDEX TRACKER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/index/{website_id}/sync")
async def sync_index_status_endpoint(
    website_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Sync index status for all known URLs of a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    async def _run_sync():
        from index_tracker import sync_index_status
        result = await sync_index_status(website_id)
        print(f"[IndexTracker] Sync complete for {website.domain}: {result.get('checked', 0)} URLs checked")

    background_tasks.add_task(_run_sync)
    return {
        "status": "syncing",
        "message": f"Index status sync started for {website.domain}. Results will appear shortly."
    }


@app.get("/api/index/{website_id}")
async def get_index_statuses_endpoint(
    website_id: int,
    indexed: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get all index statuses for a website with optional filter."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from index_tracker import get_index_statuses
    return get_index_statuses(website_id, indexed=indexed, limit=limit, offset=offset)


@app.get("/api/index/{website_id}/summary")
async def get_index_summary_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Get index summary stats for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from index_tracker import get_index_summary
    return get_index_summary(website_id)


@app.get("/api/index/{website_id}/trends")
async def get_index_trends_endpoint(
    website_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get index trends over time for a website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from index_tracker import get_index_trends
    return get_index_trends(website_id, days=days)


# ═══════════════════════════════════════════════════════════════════════════════
# SYNC ALL — Run every audit, sync, and scan for a website
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/sync-all/{website_id}")
async def sync_all(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Run all audits, syncs, and scans for a website in the background.
    Returns immediately with a job ID. Poll /api/sync-all/{website_id}/status for progress."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    job_id = f"syncall_{website_id}_{int(time.time())}"
    _sync_all_jobs[job_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "steps": [],
        "current_step": None,
        "error": None,
    }

    background_tasks.add_task(_run_sync_all, website_id, job_id)
    return {"job_id": job_id, "status": "started", "message": "Full sync started. This will take 5-15 minutes."}


# In-memory job tracker (per-deployment)
_sync_all_jobs: Dict[str, Dict] = {}


async def _run_sync_all(website_id: int, job_id: str):
    """Background worker that runs every sync/audit sequentially."""
    from geo_engine import run_geo_audit
    from geo_fix_engine import scan_geo_fixes
    from fix_engine import AIFixGenerator
    from linking_engine import analyze_internal_links
    from content_decay import analyze_content_decay
    from cwv_monitor import check_cwv
    from image_optimizer import ImageOptimizer
    from local_seo import check_gbp_presence
    from ab_testing import get_ab_tests
    from schema_generator import generate_schema

    def _step(name: str):
        _sync_all_jobs[job_id]["current_step"] = name
        _sync_all_jobs[job_id]["steps"].append({"step": name, "at": datetime.utcnow().isoformat(), "status": "running"})
        print(f"[SyncAll] {job_id}: {name}")

    def _step_done(name: str, result: str = "ok"):
        for s in _sync_all_jobs[job_id]["steps"]:
            if s["step"] == name and s.get("status") == "running":
                s["status"] = result
        print(f"[SyncAll] {job_id}: {name} → {result}")

    try:
        db = SessionLocal()
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            _sync_all_jobs[job_id]["status"] = "failed"
            _sync_all_jobs[job_id]["error"] = "Website not found"
            return

        domain = website.domain
        base_url = f"https://{domain}"

        # 1. Site Audit
        _step("Site Audit")
        try:
            from audit_engine import SEOAuditEngine
            audit_engine = SEOAuditEngine(website_id)
            await audit_engine.run_comprehensive_audit()
            _step_done("Site Audit", "done")
        except Exception as e:
            _step_done("Site Audit", f"error: {e}")

        # 2. Keyword Sync (GSC)
        _step("Keyword Sync")
        try:
            from search_console import sync_gsc_keywords
            await sync_gsc_keywords(website_id)
            _step_done("Keyword Sync", "done")
        except Exception as e:
            _step_done("Keyword Sync", f"error: {e}")

        # 3. GEO Audit
        _step("GEO Audit")
        try:
            geo_result = await run_geo_audit(website_id)
            # Persist to StrategistResult
            sr = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
            if not sr:
                sr = StrategistResult(website_id=website_id)
                db.add(sr)
            sr.geo_audit = geo_result
            sr.geo_audit_at = datetime.utcnow()
            db.commit()
            _step_done("GEO Audit", "done")
        except Exception as e:
            _step_done("GEO Audit", f"error: {e}")

        # 4. GEO Fix Scan
        _step("GEO Fix Scan")
        try:
            await scan_geo_fixes(website_id)
            _step_done("GEO Fix Scan", "done")
        except Exception as e:
            _step_done("GEO Fix Scan", f"error: {e}")

        # 5. Fix Scan (AI fixes)
        _step("Fix Scan")
        try:
            fix_gen = AIFixGenerator(website_id)
            await fix_gen.scan_and_generate_fixes()
            _step_done("Fix Scan", "done")
        except Exception as e:
            _step_done("Fix Scan", f"error: {e}")

        # 6. Internal Linking Analysis
        _step("Linking Analysis")
        try:
            await analyze_internal_links(website_id)
            _step_done("Linking Analysis", "done")
        except Exception as e:
            _step_done("Linking Analysis", f"error: {e}")

        # 7. Content Decay Analysis
        _step("Content Decay")
        try:
            await analyze_content_decay(website_id)
            _step_done("Content Decay", "done")
        except Exception as e:
            _step_done("Content Decay", f"error: {e}")

        # 8. Core Web Vitals
        _step("Core Web Vitals")
        try:
            await check_cwv(website_id, base_url, "mobile")
            await check_cwv(website_id, base_url, "desktop")
            _step_done("Core Web Vitals", "done")
        except Exception as e:
            _step_done("Core Web Vitals", f"error: {e}")

        # 9. Image Audit
        _step("Image Audit")
        try:
            optimizer = ImageOptimizer(website_id)
            await optimizer.analyze_images()
            _step_done("Image Audit", "done")
        except Exception as e:
            _step_done("Image Audit", f"error: {e}")

        # 10. Local SEO Check
        _step("Local SEO")
        try:
            await check_gbp_presence(website_id)
            _step_done("Local SEO", "done")
        except Exception as e:
            _step_done("Local SEO", f"error: {e}")

        # 11. Sitemap Generation
        _step("Sitemap Generation")
        try:
            from sitemap_generator import generate_sitemap
            await generate_sitemap(website_id)
            _step_done("Sitemap Generation", "done")
        except Exception as e:
            _step_done("Sitemap Generation", f"error: {e}")

        # 12. Broken Link Scan
        _step("Broken Link Scan")
        try:
            from link_checker import scan_broken_links
            await scan_broken_links(website_id)
            _step_done("Broken Link Scan", "done")
        except Exception as e:
            _step_done("Broken Link Scan", f"error: {e}")

        # 13. Index Status Sync
        _step("Index Status Sync")
        try:
            from index_tracker import sync_index_status
            await sync_index_status(website_id)
            _step_done("Index Status Sync", "done")
        except Exception as e:
            _step_done("Index Status Sync", f"error: {e}")

        _sync_all_jobs[job_id]["status"] = "completed"
        _sync_all_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        print(f"[SyncAll] {job_id}: ALL DONE")

    except Exception as e:
        _sync_all_jobs[job_id]["status"] = "failed"
        _sync_all_jobs[job_id]["error"] = str(e)
        print(f"[SyncAll] {job_id}: FAILED — {e}")
    finally:
        db.close()


@app.get("/api/sync-all/{website_id}/status")
async def sync_all_status(website_id: int, job_id: str):
    """Get the status of a running sync-all job."""
    job = _sync_all_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
