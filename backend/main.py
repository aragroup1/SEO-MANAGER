# backend/main.py - Complete FastAPI Backend with Database and Models
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime, timedelta
import asyncio
import os
import sys
from dotenv import load_dotenv
import json
import secrets
from enum import Enum as PyEnum
from urllib.parse import urlparse

# Database Imports
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# Scheduler Import
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import the audit engine (needed for manual audit triggering)
from audit_engine import SEOAuditEngine
from worker import run_daily_audits # Import the core worker function

load_dotenv()

# --- Initialization ---
app = FastAPI(title="SEO Intelligence Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Setup ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")
# Fix Railway's postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base() # Define Base here, used by all models
    print("Database connection successfully initialized.")
except Exception as e:
    print(f"Database connection error: {e}")
    sys.exit(1) # Exit if essential database connection fails

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Database Models ---
class Website(Base):
    __tablename__ = "websites"
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True, nullable=False)
    api_key = Column(String, unique=True, index=True, default=lambda: secrets.token_urlsafe(16))
    last_audit = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    audits = relationship("AuditReport", back_populates="website", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="website", cascade="all, delete-orphan")

class AuditReport(Base):
    __tablename__ = "audit_reports"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    audit_date = Column(DateTime, default=datetime.utcnow)
    health_score = Column(Float)
    technical_score = Column(Float)
    content_score = Column(Float)
    performance_score = Column(Float)
    mobile_score = Column(Float)
    security_score = Column(Float)
    
    # Issue summary
    total_issues = Column(Integer)
    critical_issues = Column(Integer)
    errors = Column(Integer)
    warnings = Column(Integer)
    
    # JSON field to store detailed, unstructured audit findings (issues, recommendations)
    detailed_findings = Column(JSON, default={
        "issues": [], 
        "recommendations": []
    })

    website = relationship("Website", back_populates="audits")

class ContentItem(Base):
    __tablename__ = "content_calendar"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    title = Column(String, nullable=False)
    content_type = Column(String) # e.g., 'Blog Post', 'Landing Page'
    publish_date = Column(DateTime)
    status = Column(String) # e.g., 'Draft', 'Published', 'Scheduled'
    keywords_target = Column(JSON) # List of target keywords
    ai_generated_content = Column(Text)

    website = relationship("Website", back_populates="content_items")


# --- Pydantic Schemas ---
class WebsiteCreate(BaseModel):
    domain: str = Field(..., example="example.com")

class AuditReportSummary(BaseModel):
    health_score: float
    technical_score: float
    content_score: float
    performance_score: float
    mobile_score: float
    security_score: float
    total_issues: int
    critical_issues: int
    errors: int
    warnings: int
    audit_date: datetime

class AuditFull(BaseModel):
    audit: Dict[str, Any]
    issues: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]

class ContentItemModel(BaseModel):
    id: int
    website_id: int
    title: str
    content_type: str
    publish_date: datetime
    status: str
    keywords_target: List[str]
    ai_generated_content: Optional[str] = None
    
    class Config:
        from_attributes = True

# --- API Endpoints ---

# Add to your main.py

@app.delete("/websites/{website_id}")
async def delete_website(
    website_id: int,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    db.delete(website)
    db.commit()
    return {"message": "Website deleted successfully"}

@app.put("/websites/{website_id}")
async def update_website(
    website_id: int,
    domain: Optional[str] = None,
    monthly_traffic: Optional[int] = None,
    industry: Optional[str] = None,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    if domain:
        website.domain = domain
    if monthly_traffic:
        website.monthly_traffic = monthly_traffic
    if industry:
        website.industry = industry
    
    website.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(website)
    
    return website

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")

@app.post("/api/websites")
async def register_website(new_website: WebsiteCreate, db: Session = Depends(get_db)):
    # Basic domain validation
    if not urlparse(f"http://{new_website.domain}").netloc:
        raise HTTPException(status_code=400, detail="Invalid domain format")
    
    # Check if exists
    if db.query(Website).filter(Website.domain == new_website.domain).first():
        raise HTTPException(status_code=409, detail="Website already registered")

    db_website = Website(domain=new_website.domain)
    db.add(db_website)
    db.commit()
    db.refresh(db_website)
    
    # Trigger an immediate first audit in the background
    BackgroundTasks().add_task(SEOAuditEngine(db_website.id).run_comprehensive_audit)
    
    return {"message": "Website registered and first audit initiated.", "id": db_website.id, "domain": db_website.domain}

@app.get("/api/websites", response_model=List[Dict[str, Any]])
async def get_websites(db: Session = Depends(get_db)):
    websites = db.query(Website).all()
    # Simple serialization for the endpoint
    return [
        {
            "id": w.id, 
            "domain": w.domain, 
            "last_audit": w.last_audit.isoformat() if w.last_audit else None,
            "api_key": w.api_key # Should be hidden in production, but useful for testing
        } for w in websites
    ]


@app.post("/api/audit/{website_id}/start")
async def start_new_audit(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    # Check if an audit is already running (simplified check)
    # In a real system, you'd use Redis/database flags for this
    
    # Add the audit task to run in the background
    background_tasks.add_task(SEOAuditEngine(website_id).run_comprehensive_audit)
    
    return {"status": "success", "message": f"Comprehensive audit initiated for {website.domain}"}

@app.get("/api/audit/{website_id}", response_model=AuditFull)
async def get_latest_audit_report(website_id: int, db: Session = Depends(get_db)):
    # Get the latest audit report
    latest_report = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .first()

    if not latest_report:
        # Fallback to mock data if no real audit exists
        # In a real app, this should be a 404 or a 'loading' status
        mock_data = {
            "audit": {
                "id": 0,
                "health_score": 78,
                "previous_score": 75,
                "score_change": 3,
                "technical_score": 82,
                "content_score": 76,
                "performance_score": 71,
                "mobile_score": 85,
                "security_score": 90,
                "total_issues": 23,
                "critical_issues": 2,
                "errors": 5,
                "warnings": 10,
                "notices": 6,
                "new_issues": 3,
                "fixed_issues": 7,
                "audit_date": datetime.utcnow().isoformat()
            },
            "issues": [],
            "recommendations": []
        }
        return mock_data

    # Deserialize the detailed findings
    findings = latest_report.detailed_findings or {"issues": [], "recommendations": []}

    return {
        "audit": {
            "id": latest_report.id,
            "health_score": latest_report.health_score,
            # Placeholder for change tracking, which would need more reports
            "previous_score": latest_report.health_score - 3, 
            "score_change": 3, 
            "technical_score": latest_report.technical_score,
            "content_score": latest_report.content_score,
            "performance_score": latest_report.performance_score,
            "mobile_score": latest_report.mobile_score,
            "security_score": latest_report.security_score,
            "total_issues": latest_report.total_issues,
            "critical_issues": latest_report.critical_issues,
            "errors": latest_report.errors,
            "warnings": latest_report.warnings,
            # These are simplified for the model
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0,
            "fixed_issues": 0,
            "audit_date": latest_report.audit_date.isoformat()
        },
        "issues": findings.get("issues", []),
        "recommendations": findings.get("recommendations", [])
    }


@app.get("/api/errors/{website_id}")
async def get_errors(website_id: int, db: Session = Depends(get_db)):
    # In a real implementation, this would query issues from the latest audit report
    # For now, we return mock errors based on the audit
    
    # Re-use the audit data logic to get issues
    audit_data = await get_latest_audit_report(website_id, db)
    
    errors = [
        issue for issue in audit_data['issues'] 
        if issue.get('severity', '').lower() in ['critical', 'error', 'high']
    ]

    # Add a mock 'auto_fixed' status for demonstration in the frontend
    for i, error in enumerate(errors):
        error['auto_fixed'] = (i % 3 == 0) # Example: every third error is auto-fixed

    return errors

@app.post("/api/errors/{error_id}/fix")
async def fix_error(error_id: int):
    # This is a placeholder for the AI auto-fix logic
    await asyncio.sleep(2) # Simulate work
    return {"status": "success", "message": f"Error {error_id} auto-fix attempted."}

@app.get("/api/content-calendar/{website_id}", response_model=List[ContentItemModel])
async def get_content_calendar(website_id: int, db: Session = Depends(get_db)):
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).all()
    if not content_items:
        # Generate mock data if none exist
        return [
            ContentItemModel(
                id=i+1,
                website_id=website_id,
                title=f"The AI Revolution in SEO: A 2024 Guide {i+1}",
                content_type="Blog Post",
                publish_date=datetime.utcnow() + timedelta(days=i),
                status="Scheduled",
                keywords_target=["AI SEO", "SEO Automation"],
                ai_generated_content=f"This is the draft content for the post {i+1}. It discusses how artificial intelligence is transforming search engine optimization by automating complex tasks and improving content quality..."
            ) for i in range(3)
        ]
        
    return content_items

@app.post("/api/content-calendar/{website_id}/generate")
async def generate_content_calendar(website_id: int, background_tasks: BackgroundTasks):
    # This would trigger an LLM call to generate new content ideas
    async def run_generation(website_id: int):
        print(f"Starting content generation for website {website_id}...")
        await asyncio.sleep(5) # Simulate LLM generation time
        print(f"Content generation complete for website {website_id}.")
    
    background_tasks.add_task(run_generation, website_id)
    return {"status": "success", "message": "Content generation initiated in the background."}


@app.post("/api/competitors/{website_id}/analyze")
async def analyze_competitors(website_id: int, background_tasks: BackgroundTasks):
    # This is a placeholder for the actual API call in the background
    async def run_competitor_analysis(website_id: int):
        print(f"Starting competitor analysis for website {website_id}...")
        # In a real app, this would call RealSEODataProvider.get_competitor_keyword_gap
        await asyncio.sleep(10) # Simulate API call time
        print(f"Competitor analysis complete for website {website_id}.")

    background_tasks.add_task(run_competitor_analysis, website_id)
    return {"status": "success", "message": "Competitor analysis initiated."}


# --- Command Line Tooling ---
def create_db():
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

# Startup event (The scheduler is handled by the separate worker service now)
@app.on_event("startup")
async def startup_event():
    print(f"Starting SEO Intelligence Platform (API Service) on port {os.getenv('PORT', 8000)}")
    
# Main execution for command line
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create_db":
        create_db()
    else:
        # For local development without Docker compose, use uvicorn main:app --reload
        print("Run 'uvicorn main:app --reload' or use the Docker setup.")
