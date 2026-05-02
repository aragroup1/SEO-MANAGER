# backend/database.py - Shared database setup (no circular imports)
import os
import secrets
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Boolean, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# Load .env from current dir or parent dir (project root)
load_dotenv()
if not os.getenv("DATABASE_URL"):
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://seo_user:seo_password@localhost/seo_tool")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def _create_engine_with_fallback():
    """Create engine with explicit connection test and SQLite fallback."""
    global engine, SessionLocal, Base
    try:
        if "postgresql" in DATABASE_URL:
            test_engine = create_engine(
                DATABASE_URL,
                pool_size=10, max_overflow=20,
                pool_pre_ping=True, pool_recycle=3600,
                connect_args={"connect_timeout": 5},
            )
        else:
            test_engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
        # Test the connection immediately
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine = test_engine
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()
        print(f"Database connection initialized: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    except Exception as e:
        print(f"Database connection error, using SQLite fallback: {e}")
        engine = create_engine("sqlite:///./seo_tool.db", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base = declarative_base()

_create_engine_with_fallback()

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
    autonomy_mode = Column(String, default="manual")  # manual | smart | ultra
    sitemap_xml = Column(Text, nullable=True)
    sitemap_generated_at = Column(DateTime, nullable=True)
    robots_txt = Column(Text, nullable=True)
    owner = relationship("User", back_populates="websites")
    audits = relationship("AuditReport", back_populates="website", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="website", cascade="all, delete-orphan")
    proposed_fixes = relationship("ProposedFix", back_populates="website", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="website", cascade="all, delete-orphan")
    keyword_snapshots = relationship("KeywordSnapshot", back_populates="website", cascade="all, delete-orphan")
    tracked_keywords = relationship("TrackedKeyword", back_populates="website", cascade="all, delete-orphan")

class AuditReport(Base):
    __tablename__ = "audit_reports"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), index=True)
    audit_date = Column(DateTime, default=datetime.utcnow, index=True)
    health_score = Column(Float, default=0)
    technical_score = Column(Float, default=0)
    content_score = Column(Float, default=0)
    performance_score = Column(Float, default=0)
    mobile_score = Column(Float, default=0)
    desktop_score = Column(Float, default=0)
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
    website_id = Column(Integer, ForeignKey("websites.id"), index=True)
    title = Column(String, nullable=False)
    content_type = Column(String, default="Blog Post")
    publish_date = Column(DateTime)
    scheduled_publish_date = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
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
    website = relationship("Website", back_populates="integrations")

class ProposedFix(Base):
    """
    Stores AI-generated fixes that need user approval before being applied.
    Each fix represents a single change to a single resource (product, page, etc.)
    """
    __tablename__ = "proposed_fixes"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
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
    status = Column(String, default="pending", index=True)
    # pending, approved, rejected, applied, failed

    # Metadata
    severity = Column(String, default="medium", index=True)  # critical, high, medium, low
    category = Column(String, default="content")  # content, technical, accessibility
    batch_id = Column(String, nullable=True)  # Group related fixes together
    error_message = Column(Text, nullable=True)  # If application failed, why
    applied_at = Column(DateTime, nullable=True)
    auto_approved_at = Column(DateTime, nullable=True)  # When auto-approval happened
    auto_applied = Column(Boolean, default=False)  # True if applied by automation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    website = relationship("Website", back_populates="proposed_fixes")


class KeywordSnapshot(Base):
    """
    Stores keyword ranking data pulled from Google Search Console.
    Each snapshot is a daily/weekly pull of all keyword data for a website.
    """
    __tablename__ = "keyword_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)

    # Date range this data covers
    date_from = Column(DateTime, nullable=False)
    date_to = Column(DateTime, nullable=False)
    snapshot_date = Column(DateTime, default=datetime.utcnow, index=True)

    # The actual keyword data — stored as JSON array of keyword objects
    # Each object: {query, clicks, impressions, ctr, position, page}
    keyword_data = Column(JSON, default=lambda: [])

    # Summary stats
    total_keywords = Column(Integer, default=0)
    total_clicks = Column(Integer, default=0)
    total_impressions = Column(Integer, default=0)
    avg_position = Column(Float, default=0)
    avg_ctr = Column(Float, default=0)

    # GSC property used
    gsc_property = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website", back_populates="keyword_snapshots")


class TrackedKeyword(Base):
    """
    Keywords the user has selected as primary targets for Road to #1.
    These get special tracking, competitor analysis, and optimization recommendations.
    """
    __tablename__ = "tracked_keywords"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    keyword = Column(String, nullable=False)

    # Latest ranking data (updated on each sync)
    current_position = Column(Float, nullable=True)
    current_clicks = Column(Integer, default=0)
    current_impressions = Column(Integer, default=0)
    current_ctr = Column(Float, default=0)
    ranking_url = Column(String, nullable=True)

    # Target
    target_position = Column(Integer, default=1)
    target_url = Column(String, nullable=True)  # User-selected URL to rank for this keyword
    notes = Column(Text, nullable=True)

    # Status
    status = Column(String, default="tracking")  # tracking, achieved, paused

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    website = relationship("Website", back_populates="tracked_keywords")


class SerpRankingHistory(Base):
    """
    Append-only history of live SERP positions from Serper.dev.
    Every refresh-live call writes a row per keyword. NEVER deleted on
    untrack — keyword is stored as a string so history survives.
    """
    __tablename__ = "serp_ranking_history"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)
    position = Column(Float, nullable=True)  # null = not in top 100
    ranking_url = Column(String, nullable=True)
    country = Column(String, default="gb")
    source = Column(String, default="serper")
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


class StrategistResult(Base):
    """
    Persistent cache of AI Strategist outputs per website.
    One row per website — strategy, weekly plan, and portfolio each kept as
    the most recent generation so dashboard re-renders don't lose findings.
    """
    __tablename__ = "strategist_results"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, unique=True, index=True)
    strategy = Column(JSON, nullable=True)
    strategy_generated_at = Column(DateTime, nullable=True)
    weekly_plan = Column(JSON, nullable=True)
    weekly_generated_at = Column(DateTime, nullable=True)
    portfolio = Column(JSON, nullable=True)
    portfolio_generated_at = Column(DateTime, nullable=True)
    linking = Column(JSON, nullable=True)
    linking_generated_at = Column(DateTime, nullable=True)
    decay = Column(JSON, nullable=True)
    decay_generated_at = Column(DateTime, nullable=True)
    geo_audit = Column(JSON, nullable=True)
    geo_audit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KeywordVolume(Base):
    """
    Persistent monthly search volume per (website, keyword, country, month).
    Survives GSC syncs and tracked-keyword deletions. One row per month.
    """
    __tablename__ = "keyword_volumes"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    keyword = Column(String, nullable=False, index=True)
    country = Column(String, default="GB")
    year_month = Column(String, nullable=False, index=True)  # "2026-04"
    search_volume = Column(Integer, default=0)
    competition = Column(Integer, default=0)  # 0-100
    cpc = Column(Float, default=0)
    source = Column(String, default="dataforseo")
    fetched_at = Column(DateTime, default=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW MODELS FOR "WHAT'S MISSING" FEATURES
# ═══════════════════════════════════════════════════════════════════════════════

class CoreWebVitalsSnapshot(Base):
    """Stores Core Web Vitals measurements over time for trend analysis."""
    __tablename__ = "core_web_vitals"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    url = Column(String, default="/")
    lcp = Column(Float, nullable=True)  # Largest Contentful Paint (seconds)
    inp = Column(Float, nullable=True)  # Interaction to Next Paint (seconds)
    cls = Column(Float, nullable=True)  # Cumulative Layout Shift
    fcp = Column(Float, nullable=True)  # First Contentful Paint
    ttfb = Column(Float, nullable=True)  # Time to First Byte
    device_type = Column(String, default="mobile")  # mobile | desktop
    source = Column(String, default="pagespeed")
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


class NotificationChannel(Base):
    """Configured notification channels per website (Slack, email, webhook, Discord)."""
    __tablename__ = "notification_channels"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    channel_type = Column(String, nullable=False)  # slack, email, webhook, discord
    name = Column(String, nullable=False)
    config = Column(JSON, default=lambda: {})  # {url, token, email, smtp_host, etc.}
    events = Column(JSON, default=lambda: [])  # ["audit_complete", "fix_applied", "ranking_drop", "cwv_poor"]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationLog(Base):
    """History of sent notifications."""
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=False)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    status = Column(String, default="pending")  # sent, failed, pending
    message = Column(Text)
    response = Column(Text, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)


class ImageAudit(Base):
    """Image optimization audit results per image per page."""
    __tablename__ = "image_audits"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    page_url = Column(String, nullable=False)
    image_url = Column(String, nullable=False)
    alt_text = Column(String, nullable=True)
    has_dimensions = Column(Boolean, default=False)
    file_size_kb = Column(Integer, nullable=True)
    format = Column(String, nullable=True)
    is_lazy_loaded = Column(Boolean, default=False)
    is_above_fold = Column(Boolean, default=False)
    issues = Column(JSON, default=lambda: [])
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


class MetaABTest(Base):
    """A/B tests for meta titles and descriptions."""
    __tablename__ = "meta_ab_tests"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    page_url = Column(String, nullable=False)
    element_type = Column(String, nullable=False)  # title, description
    variant_a = Column(Text, nullable=False)  # Original
    variant_b = Column(Text, nullable=False)  # AI-generated
    status = Column(String, default="draft")  # draft, running, completed
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    winner = Column(String, nullable=True)  # a, b, tie
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LocalSEOPresence(Base):
    """Local SEO / Google Business Profile data per website."""
    __tablename__ = "local_seo_presence"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, unique=True)
    business_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    postcode = Column(String, nullable=True)
    country = Column(String, default="GB")
    phone = Column(String, nullable=True)
    category = Column(String, nullable=True)
    gbp_url = Column(String, nullable=True)
    gbp_status = Column(String, default="not_claimed")  # not_claimed, claimed, optimized
    review_count = Column(Integer, default=0)
    avg_rating = Column(Float, nullable=True)
    last_checked = Column(DateTime, nullable=True)


class UserRole(Base):
    """Multi-user role assignments per website."""
    __tablename__ = "user_roles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False)
    role = Column(String, default="admin")  # admin, editor, viewer
    created_at = Column(DateTime, default=datetime.utcnow)


class DatabaseBackup(Base):
    """Track database backups for recovery."""
    __tablename__ = "database_backups"
    id = Column(Integer, primary_key=True, index=True)
    backup_type = Column(String, default="manual")  # manual, scheduled, pre_migration
    format = Column(String, default="json")  # json, sql
    file_path = Column(String, nullable=False)
    size_bytes = Column(Integer, default=0)
    websites_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class BrokenLink(Base):
    """Broken outbound link checker results."""
    __tablename__ = "broken_links"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    page_url = Column(String, nullable=False)
    link_url = Column(String, nullable=False)
    anchor_text = Column(String, nullable=True)
    status_code = Column(Integer, nullable=True)
    error_type = Column(String, nullable=False, default="unknown")
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)
    is_fixed = Column(Boolean, default=False, index=True)


class IndexStatus(Base):
    """Page index status tracker — tracks whether URLs are indexed in Google."""
    __tablename__ = "index_statuses"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    url = Column(String, nullable=False, index=True)
    is_indexed = Column(Boolean, default=False, index=True)
    coverage_state = Column(String, nullable=True)  # e.g. "Submitted and indexed"
    last_checked = Column(DateTime, default=datetime.utcnow, index=True)
    check_method = Column(String, default="unknown")  # gsc_url_inspection | google_search_fallback
    first_seen = Column(DateTime, default=datetime.utcnow)

    website = relationship("Website")


class ClientRecipient(Base):
    """Email recipient for daily ranking updates per website."""
    __tablename__ = "client_recipients"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    send_hour_utc = Column(Integer, default=8)  # hour-of-day to send
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClientReportLog(Base):
    """Log of daily client emails sent."""
    __tablename__ = "client_report_logs"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, nullable=False, index=True)
    recipient_id = Column(Integer, nullable=True, index=True)
    email = Column(String, nullable=False)
    status = Column(String, default="sent")  # sent | failed | skipped
    error = Column(Text, nullable=True)
    keywords_count = Column(Integer, default=0)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)


# Create all tables (with fallback if primary engine fails)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Primary engine table creation failed: {e}")
    # Fallback engine should already be set if primary failed during init
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e2:
        print(f"Fallback engine table creation also failed: {e2}")

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
