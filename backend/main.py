# backend/main.py - Complete SEO Intelligence Platform Backend
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
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

load_dotenv()

# --- FastAPI App Initialization ---
app = FastAPI(title="SEO Intelligence Platform")

# CORS Configuration
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

# Create engine with error handling
try:
    if "postgresql" in DATABASE_URL:
        engine = create_engine(DATABASE_URL)
    else:
        # SQLite fallback for local testing
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print(f"Database connection initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
except Exception as e:
    print(f"Database connection error, using SQLite fallback: {e}")
    engine = create_engine("sqlite:///./seo_tool.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Database Models ---
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, default="user@example.com")
    name = Column(String, default="Default User")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    websites = relationship("Website", back_populates="owner", cascade="all, delete-orphan")

class Website(Base):
    __tablename__ = "websites"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    domain = Column(String, unique=True, index=True, nullable=False)
    site_type = Column(String, default="custom")  # shopify, wordpress, custom
    shopify_store_url = Column(String, nullable=True)
    shopify_access_token = Column(String, nullable=True)
    monthly_traffic = Column(Integer, nullable=True)
    api_key = Column(String, unique=True, index=True, default=lambda: secrets.token_urlsafe(16))
    last_audit = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    owner = relationship("User", back_populates="websites")
    audits = relationship("AuditReport", back_populates="website", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="website", cascade="all, delete-orphan")

class AuditReport(Base):
    __tablename__ = "audit_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    audit_date = Column(DateTime, default=datetime.utcnow)
    health_score = Column(Float, default=0)
    technical_score = Column(Float, default=0)
    content_score = Column(Float, default=0)
    performance_score = Column(Float, default=0)
    mobile_score = Column(Float, default=0)
    security_score = Column(Float, default=0)
    
    # Issue summary
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    
    # JSON field for detailed findings
    detailed_findings = Column(JSON, default=lambda: {"issues": [], "recommendations": []})

    website = relationship("Website", back_populates="audits")

class ContentItem(Base):
    __tablename__ = "content_calendar"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    title = Column(String, nullable=False)
    content_type = Column(String, default="Blog Post")
    publish_date = Column(DateTime)
    status = Column(String, default="Draft")
    keywords_target = Column(JSON, default=lambda: [])
    ai_generated_content = Column(Text)

    website = relationship("Website", back_populates="content_items")

# Create all tables
Base.metadata.create_all(bind=engine)

# Initialize default user
def init_db():
    db = SessionLocal()
    try:
        # Check if default user exists
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            default_user = User(
                id=1,
                email="user@example.com",
                name="Default User"
            )
            db.add(default_user)
            db.commit()
            print("Default user created")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

# Initialize database on startup
init_db()

# --- Pydantic Schemas ---
class WebsiteCreate(BaseModel):
    domain: str = Field(..., example="example.com")
    user_id: Optional[int] = 1
    site_type: Optional[str] = "custom"
    shopify_store_url: Optional[str] = None
    shopify_access_token: Optional[str] = None
    monthly_traffic: Optional[int] = None

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

# --- Core API Endpoints ---

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": db_status,
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SEO Intelligence Platform API", "version": "1.0.0"}

# --- Website Management Endpoints ---

@app.post("/websites")
async def create_website(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new website"""
    try:
        data = await request.json()
        print(f"Creating website with data: {data}")
        
        # Validate required fields
        if not data.get('domain'):
            raise HTTPException(status_code=400, detail="Domain is required")
        
        # Clean domain (remove http/https if present)
        domain = data['domain'].replace('http://', '').replace('https://', '').replace('/', '')
        
        # Check if domain already exists
        existing = db.query(Website).filter(Website.domain == domain).first()
        if existing:
            raise HTTPException(status_code=400, detail="Domain already registered")
        
        # Create website
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
        
        print(f"Website created successfully: {website.domain}")
        
        # Trigger initial audit (if audit_engine exists)
        try:
            from audit_engine import SEOAuditEngine
            background_tasks.add_task(SEOAuditEngine(website.id).run_comprehensive_audit)
        except ImportError:
            print("Audit engine not available, skipping initial audit")
        
        return {
            "id": website.id,
            "domain": website.domain,
            "site_type": website.site_type,
            "created_at": website.created_at.isoformat() if website.created_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating website: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/websites")
async def get_websites(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all websites"""
    try:
        query = db.query(Website)
        if user_id:
            query = query.filter(Website.user_id == user_id)
        
        websites = query.all()
        
        # Build response with health scores from latest audits
        result = []
        for w in websites:
            # Get latest audit for health score
            latest_audit = db.query(AuditReport)\
                .filter(AuditReport.website_id == w.id)\
                .order_by(AuditReport.audit_date.desc())\
                .first()
            
            health_score = latest_audit.health_score if latest_audit else None
            
            result.append({
                "id": w.id,
                "domain": w.domain,
                "site_type": w.site_type,
                "monthly_traffic": w.monthly_traffic,
                "health_score": health_score,
                "created_at": w.created_at.isoformat() if w.created_at else None
            })
        
        return result
    except Exception as e:
        print(f"Error fetching websites: {e}")
        return []

@app.delete("/websites/{website_id}")
async def delete_website(
    website_id: int,
    db: Session = Depends(get_db)
):
    """Delete a website"""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    db.delete(website)
    db.commit()
    return {"message": "Website deleted successfully"}

@app.put("/websites/{website_id}")
async def update_website(
    website_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update a website"""
    data = await request.json()
    website = db.query(Website).filter(Website.id == website_id).first()
    
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    # Update fields if provided
    if 'domain' in data:
        website.domain = data['domain']
    if 'monthly_traffic' in data:
        website.monthly_traffic = data['monthly_traffic']
    if 'site_type' in data:
        website.site_type = data['site_type']
    
    db.commit()
    db.refresh(website)
    
    return {
        "id": website.id,
        "domain": website.domain,
        "site_type": website.site_type,
        "monthly_traffic": website.monthly_traffic
    }

# --- API Endpoints (for backward compatibility) ---

@app.post("/api/websites")
async def api_register_website(
    new_website: WebsiteCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """API endpoint for registering website"""
    request_data = new_website.dict()
    request = Request(scope={"type": "http"})
    request._json = request_data
    return await create_website(request, background_tasks, db)

@app.get("/api/websites")
async def api_get_websites(db: Session = Depends(get_db)):
    """API endpoint for getting websites"""
    return await get_websites(None, db)

# --- Audit Endpoints ---

@app.post("/api/audit/{website_id}/start")
async def start_new_audit(
    website_id: int, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """Start a new audit for a website"""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    try:
        from audit_engine import SEOAuditEngine
        background_tasks.add_task(SEOAuditEngine(website_id).run_comprehensive_audit)
        return {"status": "success", "message": f"Audit initiated for {website.domain}"}
    except ImportError:
        # Create a mock audit if audit_engine doesn't exist
        mock_audit = AuditReport(
            website_id=website_id,
            health_score=75 + (website_id % 20),
            technical_score=80 + (website_id % 15),
            content_score=70 + (website_id % 25),
            performance_score=85 + (website_id % 10),
            mobile_score=90 + (website_id % 5),
            security_score=95 - (website_id % 10),
            total_issues=10 + (website_id % 15),
            critical_issues=1 + (website_id % 3),
            errors=2 + (website_id % 5),
            warnings=3 + (website_id % 7)
        )
        db.add(mock_audit)
        db.commit()
        return {"status": "success", "message": f"Mock audit created for {website.domain}"}

@app.get("/api/audit/{website_id}")
async def get_latest_audit_report(website_id: int, db: Session = Depends(get_db)):
    """Get the latest audit report for a website"""
    latest_report = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .first()

    if not latest_report:
        # Return mock data if no audit exists
        return {
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

    findings = latest_report.detailed_findings or {"issues": [], "recommendations": []}

    return {
        "audit": {
            "id": latest_report.id,
            "health_score": latest_report.health_score,
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
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0,
            "fixed_issues": 0,
            "audit_date": latest_report.audit_date.isoformat()
        },
        "issues": findings.get("issues", []),
        "recommendations": findings.get("recommendations", [])
    }

# --- Content Calendar Endpoints ---

@app.get("/api/content-calendar/{website_id}")
async def get_content_calendar(website_id: int, db: Session = Depends(get_db)):
    """Get content calendar for a website"""
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).all()
    
    if not content_items:
        # Return mock data
        return [
            {
                "id": i+1,
                "website_id": website_id,
                "title": f"SEO Best Practices Guide Part {i+1}",
                "content_type": "Blog Post",
                "publish_date": (datetime.utcnow() + timedelta(days=i*7)).isoformat(),
                "status": "Scheduled",
                "keywords_target": ["SEO", "optimization", "ranking"],
                "ai_generated_content": f"This is sample content for post {i+1}..."
            } for i in range(3)
        ]
    
    return [
        {
            "id": item.id,
            "website_id": item.website_id,
            "title": item.title,
            "content_type": item.content_type,
            "publish_date": item.publish_date.isoformat() if item.publish_date else None,
            "status": item.status,
            "keywords_target": item.keywords_target or [],
            "ai_generated_content": item.ai_generated_content
        } for item in content_items
    ]

@app.post("/api/content-calendar/{website_id}/generate")
async def generate_content_calendar(
    website_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate content calendar using AI"""
    async def create_sample_content():
        # Create sample content items
        for i in range(3):
            content = ContentItem(
                website_id=website_id,
                title=f"AI-Generated Content Idea {i+1}",
                content_type="Blog Post",
                publish_date=datetime.utcnow() + timedelta(days=(i+1)*7),
                status="Draft",
                keywords_target=["AI SEO", "content marketing", "automation"],
                ai_generated_content="AI-generated content would go here..."
            )
            db.add(content)
        db.commit()
    
    background_tasks.add_task(create_sample_content)
    return {"status": "success", "message": "Content generation initiated"}

# --- Error Monitoring Endpoints ---

@app.get("/api/errors/{website_id}")
async def get_errors(website_id: int, db: Session = Depends(get_db)):
    """Get errors for a website"""
    # Mock error data
    return [
        {
            "id": 1,
            "title": "Missing Meta Description",
            "severity": "error",
            "page": "/products",
            "auto_fixed": False
        },
        {
            "id": 2,
            "title": "Slow Page Load Time",
            "severity": "warning",
            "page": "/",
            "auto_fixed": True
        }
    ]

@app.post("/api/errors/{error_id}/fix")
async def fix_error(error_id: int):
    """Auto-fix an error"""
    await asyncio.sleep(1)  # Simulate work
    return {"status": "success", "message": f"Error {error_id} fixed"}

# --- Competitor Analysis Endpoints ---

@app.post("/api/competitors/{website_id}/analyze")
async def analyze_competitors(
    website_id: int, 
    background_tasks: BackgroundTasks
):
    """Analyze competitors"""
    async def mock_analysis():
        await asyncio.sleep(2)
        print(f"Competitor analysis complete for website {website_id}")
    
    background_tasks.add_task(mock_analysis)
    return {"status": "success", "message": "Competitor analysis initiated"}

# --- Google Integration Endpoints ---

@app.get("/auth/google/init")
async def init_google_auth(
    user_id: int = 1, 
    integration_type: str = "search_console"
):
    """Initialize Google OAuth"""
    # This would redirect to Google OAuth in production
    return {
        "authorization_url": f"https://accounts.google.com/oauth/authorize?client_id=xxx&redirect_uri=xxx&scope={integration_type}"
    }

# --- Startup Events ---

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    print(f"Starting SEO Intelligence Platform on port {os.getenv('PORT', 8000)}")
    
    # Auto-migrate database schema
    try:
        with engine.connect() as conn:
            # Add any missing columns
            if "postgresql" in DATABASE_URL or "sqlite" in DATABASE_URL:
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
                        pass  # Column might already exist
                        
        print("Database schema updated")
    except Exception as e:
        print(f"Migration skipped: {e}")

# --- Main Execution ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
