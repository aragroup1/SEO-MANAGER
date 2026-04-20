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
from sqlalchemy.orm import Session
from sqlalchemy import text

load_dotenv()

# Import shared database objects
from database import (
    Base, engine, SessionLocal, get_db, DATABASE_URL,
    User, Website, AuditReport, ContentItem, Integration, ProposedFix, KeywordSnapshot, TrackedKeyword
)

app = FastAPI(title="SEO Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    """Check auth token on all API requests (except public routes)."""
    path = request.url.path

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
    db.commit()
    db.refresh(website)
    return {"id": website.id, "domain": website.domain, "site_type": website.site_type, "monthly_traffic": website.monthly_traffic}

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
    result = await analyze_internal_linking(website_id)
    return result


# Content Decay Detection
@app.post("/api/decay/{website_id}/analyze")
async def analyze_decay(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Detect content decay — check freshness vs competitors."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from content_decay import detect_content_decay
    result = await detect_content_decay(website_id)
    return result


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
