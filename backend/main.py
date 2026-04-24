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
    User, Website, AuditReport, ContentItem, Integration, ProposedFix, KeywordSnapshot, TrackedKeyword
)

app = FastAPI(title="SEO Intelligence Platform")

# CORS: Use FRONTEND_URL env var for production, fallback to common dev origins
_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_URL", "http://localhost:3000,https://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Check auth token + rate limit on all API requests (except public routes)."""
    path = request.url.path

    # ─── Rate Limiting ───
    client_ip = request.headers.get("X-Forwarded-For", request.client.host or "unknown").split(",")[0].strip()
    limit = _get_rate_limit(path)
    if not _check_rate_limit(client_ip, path, limit):
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Try again in a minute. (Limit: {limit}/min)"}
        )

    # Allow public routes
    if path in PUBLIC_ROUTES or not AUTH_PASSWORD:
        return await call_next(request)

    # Allow OAuth callbacks (Google needs to redirect back)
    if "/oauth/" in path or "/callback" in path:
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

    return await call_next(request)


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
    except:
        db_status = "disconnected"
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "database": db_status, "version": "1.0.0"}

@app.get("/health/env")
async def env_check():
    """Check which API keys/env vars are configured."""
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

@app.post("/websites")
async def create_website(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        if not data.get('domain'):
            raise HTTPException(status_code=400, detail="Domain is required")

        domain = data['domain'].replace('http://', '').replace('https://', '').rstrip('/')

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
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
        print(f"Error fetching websites: {e}")
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
            "security_score": latest_report.security_score,
            "total_issues": latest_report.total_issues,
            "critical_issues": latest_report.critical_issues,
            "errors": latest_report.errors,
            "warnings": latest_report.warnings,
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0,
            "fixed_issues": 0,
            "audit_date": latest_report.audit_date.isoformat(),
            "domain": website.domain
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
        except:
            content_data = {"content_html": item.ai_generated_content}
    return {"id": item.id, "title": item.title, "content_type": item.content_type, "status": item.status, "keywords": item.keywords_target, "content": content_data}

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

@app.post("/api/competitors/{website_id}/analyze")
async def analyze_competitors(website_id: int, background_tasks: BackgroundTasks):
    async def mock_analysis():
        await asyncio.sleep(2)
    background_tasks.add_task(mock_analysis)
    return {"status": "success", "message": "Competitor analysis initiated"}

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
                except: pass
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
                "ALTER TABLE proposed_fixes ADD COLUMN IF NOT EXISTS auto_approved_at TIMESTAMP",
                "ALTER TABLE proposed_fixes ADD COLUMN IF NOT EXISTS auto_applied BOOLEAN DEFAULT FALSE",
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
            ]
            for migration in migrations:
                try:
                    conn.execute(text(migration))
                    conn.commit()
                except:
                    pass
        print("Database schema updated")
    except Exception as e:
        print(f"Migration skipped: {e}")

    # Start daily audit scheduler
    _schedule_daily_audits()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
