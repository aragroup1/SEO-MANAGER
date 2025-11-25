# backend/main.py - Complete FastAPI Backend
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime, timedelta
import asyncio
import httpx
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import os
from dotenv import load_dotenv
import json
import pandas as pd
import numpy as np
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.analytics.data_v1beta import BetaAnalyticsDataClient
import shopify
import openai
from anthropic import Anthropic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis import Redis
import hashlib
import secrets
from enum import Enum as PyEnum
import resend
from bs4 import BeautifulSoup
import aiohttp
from urllib.parse import urlparse

load_dotenv()

# Initialize services
app = FastAPI(title="SEO Intelligence Platform")
redis_client = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
scheduler = AsyncIOScheduler()
anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai.api_key = os.getenv("OPENAI_API_KEY")
resend.api_key = os.getenv("RESEND_API_KEY", ""))

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    websites = relationship("Website", back_populates="user")
    integrations = relationship("Integration", back_populates="user")

class Website(Base):
    __tablename__ = "websites"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    domain = Column(String, unique=True, index=True)
    site_type = Column(String, default="custom")  # shopify, wordpress, custom
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
    integrations = relationship("WebsiteIntegration", back_populates="website")
    optimizations = relationship("Optimization", back_populates="website")
    errors = relationship("ErrorLog", back_populates="website")
    keywords = relationship("Keyword", back_populates="website")
    rankings = relationship("Ranking", back_populates="website")
    strategies = relationship("Strategy", back_populates="website")
    audits = relationship("SiteAudit", back_populates="website")
    ai_searches = relationship("AISearchOptimization", back_populates="website")
    content_calendar = relationship("ContentCalendar", back_populates="website")

class Integration(Base):
    __tablename__ = "integrations"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)  # google_analytics, shopify, etc.
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
    intent = Column(String)  # navigational, informational, commercial, transactional
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
    type = Column(String)  # content, technical, backlink, ai_optimization
    title = Column(String)
    description = Column(Text)
    priority = Column(Integer)
    status = Column(String, default="pending")  # pending, in_progress, completed
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
    type = Column(String)  # title, description, meta, schema, content
    entity_type = Column(String)  # product, collection, page, blog
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
    error_type = Column(String)  # crawl, indexing, schema, speed, mobile, security
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
    platform = Column(String)  # google_sge, bing_chat, perplexity, claude
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
    content_type = Column(String)  # blog, product_update, landing_page
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

# Import audit models
from audit_engine import (
    SiteAudit, AuditIssue, IssueHistory, 
    AuditRecommendation, PageAudit, ImplementationTracker
)

# Create all tables
Base.metadata.create_all(bind=engine)

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

# Google Integration Class
class GoogleIntegration:
    def __init__(self, credentials_json):
        from google.oauth2 import service_account
        self.credentials = service_account.Credentials.from_service_account_info(
            credentials_json,
            scopes=[
                'https://www.googleapis.com/auth/analytics.readonly',
                'https://www.googleapis.com/auth/webmasters.readonly',
                'https://www.googleapis.com/auth/content',
                'https://www.googleapis.com/auth/business.manage'
            ]
        )
    
    async def get_search_console_data(self, site_url, start_date, end_date):
        service = build('searchconsole', 'v1', credentials=self.credentials)
        request = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['query', 'page'],
            'rowLimit': 25000,
            'dataState': 'all'
        }
        response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
        return response.get('rows', [])
    
    async def get_analytics_data(self, property_id):
        client = BetaAnalyticsDataClient(credentials=self.credentials)
        from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
        
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[
                Dimension(name="pagePath"),
                Dimension(name="sessionSource"),
                Dimension(name="sessionMedium")
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration")
            ],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")]
        )
        response = client.run_report(request)
        return response

# Shopify Integration
class ShopifyIntegration:
    def __init__(self, store_url, access_token):
        shopify.ShopifyResource.set_site(f"https://{store_url}")
        shopify.ShopifyResource.set_headers({'X-Shopify-Access-Token': access_token})
    
    async def get_products(self):
        products = shopify.Product.find()
        return [self._serialize_product(p) for p in products]
    
    async def get_collections(self):
        collections = shopify.Collection.find()
        return [self._serialize_collection(c) for c in collections]
    
    async def update_product_seo(self, product_id, title, meta_description):
        product = shopify.Product.find(product_id)
        if title:
            product.title = title
        if meta_description:
            product.meta_description = meta_description
        product.save()
        return product
    
    def _serialize_product(self, product):
        return {
            'id': product.id,
            'title': product.title,
            'handle': product.handle,
            'description': product.body_html,
            'vendor': product.vendor,
            'product_type': product.product_type,
            'tags': product.tags,
            'images': [img.src for img in product.images] if product.images else []
        }
    
    def _serialize_collection(self, collection):
        return {
            'id': collection.id,
            'title': collection.title,
            'handle': collection.handle,
            'description': collection.body_html
        }

# SEO Agent
class SEOAgent:
    def __init__(self):
        self.anthropic = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.serp_api_key = os.getenv("SERP_API_KEY")
    
    async def analyze_keyword_opportunity(self, keyword, current_ranking, competitor_data):
        prompt = f"""
        Analyze this keyword opportunity:
        Keyword: {keyword}
        Current Ranking: {current_ranking}
        Competitor Data: {json.dumps(competitor_data)}
        
        Provide:
        1. Difficulty assessment
        2. Traffic potential
        3. Content gap analysis
        4. Specific optimization recommendations
        5. Expected timeline to improve ranking
        6. AI search optimization tactics
        """
        
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        return response.content[0].text
    
    async def generate_content_strategy(self, website_data, keyword_data, analytics_data):
        prompt = f"""
        As an expert SEO strategist, create a comprehensive content strategy:
        
        Website: {website_data['domain']}
        Top Keywords: {json.dumps(keyword_data[:20])}
        Analytics Insights: {json.dumps(analytics_data)}
        
        Generate:
        1. Content calendar for next 30 days
        2. Topic clusters and pillar pages
        3. Internal linking strategy
        4. Schema markup recommendations
        5. AI search optimization tactics (SGE, Bing Chat, Perplexity)
        6. Featured snippet optimization
        7. E-E-A-T signals enhancement
        """
        
        response = self.anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000
        )
        return response.content[0].text
    
    async def get_serp_data(self, keyword, location="United States"):
        async with httpx.AsyncClient() as client:
            params = {
                'api_key': self.serp_api_key,
                'q': keyword,
                'location': location,
                'hl': 'en',
                'gl': 'us',
                'google_domain': 'google.com',
                'num': 100
            }
            response = await client.get('https://serpapi.com/search', params=params)
            return response.json()

# API Endpoints

@app.get("/")
async def root():
    return {"message": "SEO Intelligence Platform API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0"
    }

@app.post("/users/register")
async def register_user(
    email: str,
    name: str,
    company: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create new user
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
    return website

@app.get("/websites")
async def get_websites(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Website)
    if user_id:
        query = query.filter(Website.user_id == user_id)
    websites = query.all()
    return websites

@app.get("/websites/{website_id}")
async def get_website(
    website_id: int,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return website

@app.post("/websites/{website_id}/keywords/bulk")
async def add_keywords_bulk(
    website_id: int,
    keywords: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    background_tasks.add_task(research_keywords, website_id, keywords, db)
    
    return {"message": f"Queued {len(keywords)} keywords for research", "website_id": website_id}

async def research_keywords(website_id: int, keywords: List[str], db: Session):
    agent = SEOAgent()
    
    for keyword in keywords:
        try:
            serp_data = await agent.get_serp_data(keyword)
            
            organic_results = serp_data.get('organic_results', [])
            search_volume = serp_data.get('search_information', {}).get('total_results', 0)
            
            difficulty = calculate_keyword_difficulty(organic_results)
            
            keyword_obj = Keyword(
                website_id=website_id,
                keyword=keyword,
                search_volume=search_volume,
                difficulty=difficulty,
                competitor_analysis=organic_results[:10],
                ai_search_visibility=extract_ai_features(serp_data)
            )
            db.add(keyword_obj)
        except Exception as e:
            print(f"Error researching keyword {keyword}: {e}")
    
    db.commit()

def calculate_keyword_difficulty(organic_results):
    top_10_domains = [r.get('domain', '') for r in organic_results[:10]]
    authority_domains = ['wikipedia.org', 'amazon.com', 'youtube.com', 'facebook.com']
    authority_count = sum(1 for d in top_10_domains if any(auth in d for auth in authority_domains))
    return min(authority_count * 10 + 20, 100)

def extract_ai_features(serp_data):
    return {
        'has_featured_snippet': 'answer_box' in serp_data,
        'has_people_also_ask': 'people_also_ask' in serp_data,
        'has_knowledge_graph': 'knowledge_graph' in serp_data,
        'ai_overview': serp_data.get('ai_overview', {})
    }

@app.get("/websites/{website_id}/rankings")
async def get_rankings(
    website_id: int,
    db: Session = Depends(get_db)
):
    rankings = db.query(Ranking).filter(
        Ranking.website_id == website_id
    ).order_by(Ranking.date.desc()).limit(100).all()
    return rankings

@app.post("/websites/{website_id}/strategies/generate")
async def generate_strategies(
    website_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    background_tasks.add_task(create_ai_strategies, website_id, db)
    return {"message": "AI strategy generation started", "website_id": website_id}

async def create_ai_strategies(website_id: int, db: Session):
    agent = SEOAgent()
    
    website = db.query(Website).filter(Website.id == website_id).first()
    keywords = db.query(Keyword).filter(Keyword.website_id == website_id).all()
    
    analytics_data = {}
    if website.google_analytics_property_id and website.google_credentials:
        google_integration = GoogleIntegration(website.google_credentials)
        analytics_data = await google_integration.get_analytics_data(website.google_analytics_property_id)
    
    keyword_data = [
        {
            'keyword': k.keyword,
            'volume': k.search_volume,
            'difficulty': k.difficulty
        } for k in keywords
    ]
    
    strategy_content = await agent.generate_content_strategy(
        {'domain': website.domain},
        keyword_data,
        analytics_data
    )
    
    strategies = parse_strategy_content(strategy_content)
    
    for strategy in strategies:
        strategy_obj = Strategy(
            website_id=website_id,
            type=strategy['type'],
            title=strategy['title'],
            description=strategy['description'],
            priority=strategy['priority'],
            impact_score=strategy['impact_score'],
            ai_recommendations=strategy['recommendations'],
            execution_plan=strategy['execution_plan']
        )
        db.add(strategy_obj)
    
    db.commit()

def parse_strategy_content(content):
    strategies = []
    lines = content.split('\n')
    current_strategy = {}
    
    for line in lines:
        if line.startswith('Strategy:'):
            if current_strategy:
                strategies.append(current_strategy)
            current_strategy = {
                'title': line.replace('Strategy:', '').strip(),
                'type': 'content',
                'priority': 1,
                'impact_score': 0.8,
                'description': '',
                'recommendations': [],
                'execution_plan': []
            }
        elif line.strip():
            current_strategy['description'] += line + '\n'
    
    if current_strategy:
        strategies.append(current_strategy)
    
    return strategies

@app.get("/websites/{website_id}/dashboard")
async def get_dashboard_data(
    website_id: int,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    total_keywords = db.query(Keyword).filter(Keyword.website_id == website_id).count()
    
    recent_rankings = db.query(Ranking).filter(
        Ranking.website_id == website_id
    ).order_by(Ranking.date.desc()).limit(100).all()
    
    top_10_count = sum(1 for r in recent_rankings if r.position <= 10)
    avg_position = np.mean([r.position for r in recent_rankings]) if recent_rankings else 0
    
    active_strategies = db.query(Strategy).filter(
        Strategy.website_id == website_id,
        Strategy.status.in_(['pending', 'in_progress'])
    ).all()
    
    latest_ai_optimization = db.query(AISearchOptimization).filter(
        AISearchOptimization.website_id == website_id
    ).order_by(AISearchOptimization.created_at.desc()).first()
    
    return {
        'website': {
            'domain': website.domain,
            'created_at': website.created_at
        },
        'metrics': {
            'total_keywords': total_keywords,
            'top_10_rankings': top_10_count,
            'average_position': round(avg_position, 1),
            'ai_visibility_score': latest_ai_optimization.visibility_score if latest_ai_optimization else 0
        },
        'active_strategies': [
            {
                'id': s.id,
                'title': s.title,
                'type': s.type,
                'status': s.status,
                'impact_score': s.impact_score
            } for s in active_strategies
        ],
        'recent_rankings': [
            {
                'keyword': r.keyword.keyword if r.keyword else '',
                'position': r.position,
                'change': 0,
                'date': r.date
            } for r in recent_rankings[:20]
        ]
    }

# OAuth Endpoints
@app.get("/auth/google/init")
async def google_auth_init(user_id: int, integration_type: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=[
            'https://www.googleapis.com/auth/analytics.readonly',
            'https://www.googleapis.com/auth/webmasters',
            'openid',
            'email',
            'profile'
        ]
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    redis_client.setex(
        f"oauth_state:{state}", 
        600, 
        json.dumps({"user_id": user_id, "integration_type": integration_type})
    )
    
    return {"authorization_url": authorization_url}

@app.get("/auth/google/callback")
async def google_auth_callback(code: str, state: str, db: Session = Depends(get_db)):
    state_data = redis_client.get(f"oauth_state:{state}")
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid state")
    
    state_info = json.loads(state_data)
    user_id = state_info["user_id"]
    integration_type = state_info["integration_type"]
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=[
            'https://www.googleapis.com/auth/analytics.readonly',
            'https://www.googleapis.com/auth/webmasters',
            'openid',
            'email',
            'profile'
        ]
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"}
        )
        user_info = response.json()
    
    integration = Integration(
        user_id=user_id,
        type=integration_type,
        name=user_info.get("email", "Google Account"),
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        expires_at=credentials.expiry,
        scope=",".join(flow.scopes)
    )
    db.add(integration)
    db.commit()
    
    return RedirectResponse(url=f"http://localhost:3000/integrations?success=true&type={integration_type}")

# Notification helper
async def send_audit_notification(website_id: int, results: Dict):
    """Send email notification after audit completion"""
    # Implementation depends on your email service
    print(f"Audit completed for website {website_id}: {results}")

# Scheduled Jobs
@app.on_event("startup")
async def startup_event():
    scheduler.add_job(
        daily_ranking_check,
        'cron',
        hour=2,
        minute=0,
        id='daily_ranking_check'
    )
    scheduler.add_job(
        ai_search_monitoring,
        'cron',
        hour=6,
        minute=0,
        id='ai_search_monitoring'
    )
    scheduler.start()

async def daily_ranking_check():
    db = SessionLocal()
    websites = db.query(Website).all()
    
    for website in websites:
        keywords = db.query(Keyword).filter(Keyword.website_id == website.id).all()
        agent = SEOAgent()
        
        for keyword in keywords:
            try:
                serp_data = await agent.get_serp_data(keyword.keyword)
                
                position = None
                for i, result in enumerate(serp_data.get('organic_results', []), 1):
                    if website.domain in result.get('link', ''):
                        position = i
                        break
                
                if position:
                    ranking = Ranking(
                        website_id=website.id,
                        keyword_id=keyword.id,
                        position=position,
                        url=result.get('link'),
                        featured_snippet='answer_box' in serp_data,
                        ai_overview_present='ai_overview' in serp_data
                    )
                    db.add(ranking)
            except Exception as e:
                print(f"Error checking ranking for {keyword.keyword}: {e}")
        
        db.commit()
    
    db.close()

async def ai_search_monitoring():
    db = SessionLocal()
    websites = db.query(Website).all()
    agent = SEOAgent()
    
    for website in websites:
        keywords = db.query(Keyword).filter(
            Keyword.website_id == website.id
        ).order_by(Keyword.priority.desc()).limit(50).all()
        
        visibility_scores = {}
        
        for keyword in keywords:
            try:
                serp_data = await agent.get_serp_data(keyword.keyword)
                
                ai_features = {
                    'google_sge': 'ai_overview' in serp_data,
                    'featured_snippet': 'answer_box' in serp_data,
                    'people_also_ask': 'people_also_ask' in serp_data,
                    'knowledge_panel': 'knowledge_graph' in serp_data
                }
                
                score = sum(1 for v in ai_features.values() if v) * 25
                visibility_scores[keyword.keyword] = score
            except Exception as e:
                print(f"Error monitoring AI search for {keyword.keyword}: {e}")
        
        avg_score = np.mean(list(visibility_scores.values())) if visibility_scores else 0
        
        ai_optimization = AISearchOptimization(
            website_id=website.id,
            platform='google_sge',
            visibility_score=avg_score,
            recommendations={}
        )
        db.add(ai_optimization)
    
    db.commit()
    db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
