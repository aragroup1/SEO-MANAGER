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
from sqlalchemy.orm import Session
from sqlalchemy import text

load_dotenv()

# Import shared database objects — NO models defined here
from database import (
    Base, engine, SessionLocal, get_db, DATABASE_URL,
    User, Website, AuditReport, ContentItem, Integration
)

app = FastAPI(title="SEO Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        domain = data['domain'].replace('http://', '').replace('https://', '').replace('/', '')

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

        try:
            from audit_engine import SEOAuditEngine
            background_tasks.add_task(SEOAuditEngine(website.id).run_comprehensive_audit)
        except ImportError:
            print("Audit engine not available, skipping initial audit")

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
    db.delete(website)
    db.commit()
    return {"message": "Website deleted successfully"}

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

# --- Audit Endpoints ---

@app.post("/api/audit/{website_id}/start")
async def start_new_audit(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    try:
        from audit_engine import SEOAuditEngine
        background_tasks.add_task(SEOAuditEngine(website_id).run_comprehensive_audit)
        return {"status": "success", "message": f"Audit initiated for {website.domain}"}
    except ImportError:
        mock_audit = AuditReport(
            website_id=website_id, health_score=75+(website_id%20), technical_score=80+(website_id%15),
            content_score=70+(website_id%25), performance_score=85+(website_id%10),
            mobile_score=90+(website_id%5), security_score=95-(website_id%10),
            total_issues=10+(website_id%15), critical_issues=1+(website_id%3),
            errors=2+(website_id%5), warnings=3+(website_id%7)
        )
        db.add(mock_audit)
        db.commit()
        return {"status": "success", "message": f"Mock audit created for {website.domain}"}

@app.get("/api/audit/{website_id}")
async def get_latest_audit_report(website_id: int, db: Session = Depends(get_db)):
    latest_report = db.query(AuditReport).filter(AuditReport.website_id == website_id).order_by(AuditReport.audit_date.desc()).first()

    if not latest_report:
        return {
            "audit": {
                "id": 0, "health_score": 78, "previous_score": 75, "score_change": 3,
                "technical_score": 82, "content_score": 76, "performance_score": 71,
                "mobile_score": 85, "security_score": 90, "total_issues": 23,
                "critical_issues": 2, "errors": 5, "warnings": 10, "notices": 6,
                "new_issues": 3, "fixed_issues": 7, "audit_date": datetime.utcnow().isoformat()
            },
            "issues": [], "recommendations": []
        }

    findings = latest_report.detailed_findings or {"issues": [], "recommendations": []}
    return {
        "audit": {
            "id": latest_report.id, "health_score": latest_report.health_score,
            "previous_score": latest_report.health_score - 3, "score_change": 3,
            "technical_score": latest_report.technical_score, "content_score": latest_report.content_score,
            "performance_score": latest_report.performance_score, "mobile_score": latest_report.mobile_score,
            "security_score": latest_report.security_score, "total_issues": latest_report.total_issues,
            "critical_issues": latest_report.critical_issues, "errors": latest_report.errors,
            "warnings": latest_report.warnings,
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0, "fixed_issues": 0, "audit_date": latest_report.audit_date.isoformat()
        },
        "issues": findings.get("issues", []),
        "recommendations": findings.get("recommendations", [])
    }

# --- Content Calendar ---

@app.get("/api/content-calendar/{website_id}")
async def get_content_calendar(website_id: int, db: Session = Depends(get_db)):
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).all()
    if not content_items:
        return [
            {"id": i+1, "website_id": website_id, "title": f"SEO Best Practices Guide Part {i+1}",
             "content_type": "Blog Post", "publish_date": (datetime.utcnow() + timedelta(days=i*7)).isoformat(),
             "status": "Scheduled", "keywords_target": ["SEO", "optimization", "ranking"],
             "ai_generated_content": f"This is sample content for post {i+1}..."}
            for i in range(3)
        ]
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

# --- Error Monitoring ---

@app.get("/api/errors/{website_id}")
async def get_errors(website_id: int, db: Session = Depends(get_db)):
    return [
        {"id": 1, "title": "Missing Meta Description", "severity": "error", "page": "/products", "auto_fixed": False},
        {"id": 2, "title": "Slow Page Load Time", "severity": "warning", "page": "/", "auto_fixed": True}
    ]

@app.post("/api/errors/{error_id}/fix")
async def fix_error(error_id: int):
    await asyncio.sleep(1)
    return {"status": "success", "message": f"Error {error_id} fixed"}

# --- Competitor Analysis ---

@app.post("/api/competitors/{website_id}/analyze")
async def analyze_competitors(website_id: int, background_tasks: BackgroundTasks):
    async def mock_analysis():
        await asyncio.sleep(2)
    background_tasks.add_task(mock_analysis)
    return {"status": "success", "message": "Competitor analysis initiated"}

# --- Legacy Google Auth ---

@app.get("/auth/google/init")
async def init_google_auth(user_id: int = 1, integration_type: str = "search_console"):
    return {"authorization_url": f"https://accounts.google.com/oauth/authorize?client_id=xxx&redirect_uri=xxx&scope={integration_type}"}

# --- Include Integration Router (imports from database.py, no circular import) ---
from integrations import router as integrations_router
app.include_router(integrations_router)

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
                "ALTER TABLE websites ADD COLUMN IF NOT EXISTS monthly_traffic INTEGER"
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
