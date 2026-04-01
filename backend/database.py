# backend/database.py - Shared database setup (no circular imports)
import os
import secrets
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    if "postgresql" in DATABASE_URL:
        engine = create_engine(DATABASE_URL)
    else:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    print(f"Database connection initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
except Exception as e:
    print(f"Database connection error, using SQLite fallback: {e}")
    engine = create_engine("sqlite:///./seo_tool.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()

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
    site_type = Column(String, default="custom")
    shopify_store_url = Column(String, nullable=True)
    shopify_access_token = Column(String, nullable=True)
    monthly_traffic = Column(Integer, nullable=True)
    api_key = Column(String, unique=True, index=True, default=lambda: secrets.token_urlsafe(16))
    last_audit = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    owner = relationship("User", back_populates="websites")
    audits = relationship("AuditReport", back_populates="website", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="website", cascade="all, delete-orphan")
    proposed_fixes = relationship("ProposedFix", back_populates="website", cascade="all, delete-orphan")

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
    total_issues = Column(Integer, default=0)
    critical_issues = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
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

class Integration(Base):
    __tablename__ = "integrations"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    integration_type = Column(String, nullable=False)
    status = Column(String, default="pending")
    connected_at = Column(DateTime, nullable=True)
    last_synced = Column(DateTime, nullable=True)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    account_name = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    scopes = Column(JSON, default=lambda: [])
    config = Column(JSON, default=lambda: {})
    created_at = Column(DateTime, default=datetime.utcnow)

class ProposedFix(Base):
    """
    Stores AI-generated fixes that need user approval before being applied.
    Each fix represents a single change to a single resource (product, page, etc.)
    """
    __tablename__ = "proposed_fixes"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    audit_report_id = Column(Integer, nullable=True)  # Which audit triggered this fix

    # What type of fix
    fix_type = Column(String, nullable=False)
    # Types: alt_text, meta_title, meta_description, broken_link, structured_data, canonical, viewport

    # What platform resource this applies to
    platform = Column(String, nullable=False)  # shopify, wordpress, custom
    resource_type = Column(String, nullable=False)  # product, page, blog_post, collection, image
    resource_id = Column(String, nullable=True)  # Platform-specific ID (e.g. Shopify product ID)
    resource_url = Column(String, nullable=True)  # URL of the affected page
    resource_title = Column(String, nullable=True)  # Human-readable name

    # The actual fix content
    field_name = Column(String, nullable=False)  # Which field to change (e.g. "alt", "meta_title")
    current_value = Column(Text, nullable=True)  # What it is now (can be null/empty)
    proposed_value = Column(Text, nullable=False)  # What AI suggests
    ai_reasoning = Column(Text, nullable=True)  # Why the AI chose this

    # Status workflow: pending -> approved/rejected -> applied/failed
    status = Column(String, default="pending")
    # pending, approved, rejected, applied, failed

    # Metadata
    severity = Column(String, default="medium")  # critical, high, medium, low
    category = Column(String, default="content")  # content, technical, accessibility
    batch_id = Column(String, nullable=True)  # Group related fixes together
    error_message = Column(Text, nullable=True)  # If application failed, why
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    website = relationship("Website", back_populates="proposed_fixes")


# Create all tables
Base.metadata.create_all(bind=engine)

# Initialize default user
def init_db():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            default_user = User(id=1, email="user@example.com", name="Default User")
            db.add(default_user)
            db.commit()
            print("Default user created")
    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

init_db()
