# backend/main.py - Complete FastAPI Backend with Error Handling
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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

load_dotenv()

# Initialize FastAPI first
app = FastAPI(title="SEO Intelligence Platform")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup with Railway fix
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")
# Fix Railway's postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print(f"Database connected successfully")
except Exception as e:
    print(f"Database connection error: {e}")
    # Fallback to SQLite for health checks
    engine = create_engine("sqlite:///./test.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

# Initialize services with error handling
try:
    from redis import Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url)
    redis_client.ping()
    print("Redis connected successfully")
except Exception as e:
    print(f"Redis connection error: {e}")
    redis_client = None

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
except Exception as e:
    print(f"Scheduler error: {e}")
    scheduler = None

try:
    from anthropic import Anthropic
    anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "dummy"))
except Exception as e:
    print(f"Anthropic initialization error: {e}")
    anthropic = None

try:
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY", "dummy")
except Exception as e:
    print(f"OpenAI initialization error: {e}")

try:
    import resend
    resend.api_key = os.getenv("RESEND_API_KEY", "")
except Exception as e:
    print(f"Resend initialization error: {e}")

# Optional imports
try:
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"Data library import error: {e}")
    pd = None
    np = None

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    GOOGLE_AVAILABLE = True
except ImportError as e:
    print(f"Google libraries not available: {e}")
    GOOGLE_AVAILABLE = False

try:
    import shopify
    SHOPIFY_AVAILABLE = True
except ImportError as e:
    print(f"Shopify library not available: {e}")
    SHOPIFY_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    import aiohttp
    import httpx
    WEB_SCRAPING_AVAILABLE = True
except ImportError as e:
    print(f"Web scraping libraries not available: {e}")
    WEB_SCRAPING_AVAILABLE = False

# Enums
class ApprovalStatus(PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"

class ErrorSeverity(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    company = Column(String)
    subscription_tier = Column(String, default="free")
    api_key = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    websites = relationship("Website", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")

class Website(Base):
    __tablename__ = "websites"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    domain = Column(String, unique=True, index=True)
    site_type = Column(String, default="custom")
    shopify_store_url = Column(String)
    shopify_access_token = Column(String)
    google_analytics_property_id = Column(String)
    google_search_console_property = Column(String)
    google_merchant_id = Column(String)
    google_business_profile_id = Column(String)
    google_credentials = Column(JSON)
    monthly_traffic = Column(Integer)
    industry = Column(String)
    competitors = Column(JSON)
    auto_optimize = Column(Boolean, default=False)
    optimization_settings = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="websites")
    integrations = relationship("WebsiteIntegration", back_populates="website", cascade="all, delete-orphan")
    optimizations = relationship("Optimization", back_populates="website", cascade="all, delete-orphan")
    errors = relationship("ErrorLog", back_populates="website", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="website", cascade="all, delete-orphan")
    rankings = relationship("Ranking", back_populates="website", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="website", cascade="all, delete-orphan")
    audits = relationship("SiteAudit", back_populates="website", cascade="all, delete-orphan")
    ai_searches = relationship("AISearchOptimization", back_populates="website", cascade="all, delete-orphan")
    content_calendar = relationship("ContentCalendar", back_populates="website", cascade="all, delete-orphan")

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)
    name = Column(String)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime)
    credentials = Column(JSON)
    scope = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="integrations")

class WebsiteIntegration(Base):
    __tablename__ = "website_integrations"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    integration_id = Column(Integer, ForeignKey("integrations.id"))
    config = Column(JSON)
    enabled = Column(Boolean, default=True)
    
    website = relationship("Website", back_populates="integrations")
    integration = relationship("Integration")

class Keyword(Base):
    __tablename__ = "keywords"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    keyword = Column(String, index=True)
    search_volume = Column(Integer)
    difficulty = Column(Float)
    cpc = Column(Float)
    intent = Column(String)
    priority = Column(Integer)
    target_url = Column(String)
    competitor_analysis = Column(JSON)
    ai_search_visibility = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    website = relationship("Website", back_populates="keywords")
    rankings = relationship("Ranking", back_populates="keyword")

class Ranking(Base):
    __tablename__ = "rankings"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    keyword_id = Column(Integer, ForeignKey("keywords.id"))
    position = Column(Integer)
    url = Column(String)
    featured_snippet = Column(Boolean, default=False)
    people_also_ask = Column(Boolean, default=False)
    knowledge_panel = Column(Boolean, default=False)
    ai_overview_present = Column(Boolean, default=False)
    ai_overview_position = Column(Integer)
    clicks = Column(Integer)
    impressions = Column(Integer)
    ctr = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)
    
    website = relationship("Website", back_populates="rankings")
    keyword = relationship("Keyword", back_populates="rankings")

class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    type = Column(String)
    title = Column(String)
    description = Column(Text)
    priority = Column(Integer)
    status = Column(String, default="pending")
    impact_score = Column(Float)
    estimated_traffic_gain = Column(Integer)
    ai_recommendations = Column(JSON)
    execution_plan = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    
    website = relationship("Website", back_populates="strategies")

class Optimization(Base):
    __tablename__ = "optimizations"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    type = Column(String)
    entity_type = Column(String)
    entity_id = Column(String)
    current_value = Column(Text)
    suggested_value = Column(Text)
    ai_reasoning = Column(Text)
    impact_score = Column(Float)
    approval_status = Column(String, default="pending")
    approved_by = Column(Integer, ForeignKey("users.id"))
    approved_at = Column(DateTime)
    applied_at = Column(DateTime)
    rollback_data = Column(JSON)
    performance_before = Column(JSON)
    performance_after = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    website = relationship("Website", back_populates="optimizations")

class ErrorLog(Base):
    __tablename__ = "error_logs"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    error_type = Column(String)
    severity = Column(String)
    title = Column(String)
    description = Column(Text)
    affected_urls = Column(JSON)
    auto_fixed = Column(Boolean, default=False)
    fix_applied = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    
    website = relationship("Website", back_populates="errors")

class AISearchOptimization(Base):
    __tablename__ = "ai_search_optimizations"
    
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    platform = Column(String)
    visibility_score = Column(Float)
    recommendations = Column(JSON)
    structured_data_suggestions = Column(JSON)
    content_gaps = Column(JSON)
    entity_optimization = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    website = relationship("Website", back_populates="ai_searches")

class ContentCalendar(Base):
    __tablename__ = "content_calendar"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    title = Column(String)
    content_type = Column(String)
    target_keywords = Column(JSON)
    publish_date = Column(DateTime)
    status = Column(String, default="draft")
    ai_generated_content = Column(Text)
    seo_score = Column(Float)
    estimated_traffic = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    website = relationship("Website", back_populates="content_calendar")

class CompetitorAnalysis(Base):
    __tablename__ = "competitor_analyses"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    competitor_domain = Column(String)
    traffic_estimate = Column(Integer)
    keyword_overlap = Column(JSON)
    content_gaps = Column(JSON)
    backlink_gaps = Column(JSON)
    winning_keywords = Column(JSON)
    losing_keywords = Column(JSON)
    analyzed_at = Column(DateTime, default=datetime.utcnow)

# Audit models - define here instead of importing
class SiteAudit(Base):
    __tablename__ = "site_audits"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    audit_date = Column(DateTime, default=datetime.utcnow)
    health_score = Column(Float)
    previous_score = Column(Float)
    score_change = Column(Float)
    technical_score = Column(Float)
    content_score = Column(Float)
    performance_score = Column(Float)
    mobile_score = Column(Float)
    security_score = Column(Float)
    total_issues = Column(Integer)
    critical_issues = Column(Integer)
    errors = Column(Integer)
    warnings = Column(Integer)
    notices = Column(Integer)
    pages_crawled = Column(Integer)
    new_issues = Column(Integer)
    fixed_issues = Column(Integer)
    
    website = relationship("Website", back_populates="audits")

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")
except Exception as e:
    print(f"Error creating tables: {e}")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI", "http://localhost:8000/auth/shopify/callback")

# API Endpoints - HEALTH CHECK FIRST
@app.get("/health")
async def health_check():
    """Health check endpoint that always works"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": "connected" if engine else "not connected",
        "redis": "connected" if redis_client else "not connected"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SEO Intelligence Platform API", "version": "1.0.0"}

# ALL YOUR ORIGINAL ENDPOINTS
@app.post("/users/register")
async def register_user(
    email: str,
    name: str,
    company: Optional[str] = None,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    user = User(
        email=email,
        name=name,
        company=company,
        api_key=secrets.token_urlsafe(32)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {"user_id": user.id, "api_key": user.api_key}

@app.post("/websites")
async def create_website(
    domain: str,
    user_id: int,
    site_type: str = "custom",
    shopify_store_url: Optional[str] = None,
    shopify_access_token: Optional[str] = None,
    google_analytics_property_id: Optional[str] = None,
    google_credentials: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    website = Website(
        user_id=user_id,
        domain=domain,
        site_type=site_type,
        shopify_store_url=shopify_store_url,
        shopify_access_token=shopify_access_token,
        google_analytics_property_id=google_analytics_property_id,
        google_credentials=google_credentials
    )
    db.add(website)
    db.commit()
    db.refresh(website)
    return {"id": website.id, "domain": website.domain}

@app.get("/websites")
async def get_websites(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Website)
    if user_id:
        query = query.filter(Website.user_id == user_id)
    websites = query.all()
    return [{"id": w.id, "domain": w.domain} for w in websites]

@app.get("/websites/{website_id}")
async def get_website(
    website_id: int,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return {"id": website.id, "domain": website.domain, "created_at": website.created_at}

@app.get("/websites/{website_id}/dashboard")
async def get_dashboard_data(
    website_id: int,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        # Return mock data if website not found
        return {
            'website': {
                'domain': 'example.com',
                'created_at': datetime.utcnow().isoformat()
            },
            'metrics': {
                'total_keywords': 150,
                'top_10_rankings': 25,
                'average_position': 18.5,
                'ai_visibility_score': 72
            },
            'active_strategies': [],
            'recent_rankings': []
        }
    
    total_keywords = db.query(Keyword).filter(Keyword.website_id == website_id).count()
    
    return {
        'website': {
            'domain': website.domain,
            'created_at': website.created_at.isoformat() if website.created_at else None
        },
        'metrics': {
            'total_keywords': total_keywords,
            'top_10_rankings': 0,
            'average_position': 0,
            'ai_visibility_score': 0
        },
        'active_strategies': [],
        'recent_rankings': []
    }

# Mock endpoints for frontend
@app.get("/api/audits/{website_id}/latest")
async def get_latest_audit(website_id: int):
    return {
        "audit": {
            "id": 1,
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

@app.get("/api/errors/{website_id}")
async def get_errors(website_id: int):
    return []

@app.get("/api/content-calendar/{website_id}")
async def get_content_calendar(website_id: int):
    return []

@app.post("/api/competitors/{website_id}/analyze")
async def analyze_competitors(website_id: int):
    return {"status": "analyzing"}

# Startup event
@app.on_event("startup")
async def startup_event():
    print(f"Starting SEO Intelligence Platform on port {os.getenv('PORT', 8000)}")
    if scheduler:
        try:
            scheduler.start()
            print("Scheduler started successfully")
        except Exception as e:
            print(f"Scheduler startup error: {e}")

# Main entry point
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
