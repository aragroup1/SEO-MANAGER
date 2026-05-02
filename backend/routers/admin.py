import os
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database import (
    SessionLocal, Website, AuditReport, ContentItem,
    TrackedKeyword, DatabaseBackup,
)
from .state import active_sessions
from .websites import _DOMAIN_RE

router = APIRouter()

_BACKUP_DIR = os.path.abspath("backups")


@router.get("/health")
async def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "database": db_status, "version": "1.0.0"}


@router.get("/health/env")
async def env_check(request: Request):
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


@router.get("/")
async def root():
    return {"message": "SEO Intelligence Platform API", "version": "1.0.0"}


@router.get("/auth/google/init")
async def init_google_auth(user_id: int = 1, integration_type: str = "search_console"):
    return {"authorization_url": f"https://accounts.google.com/oauth/authorize?client_id=xxx&redirect_uri=xxx&scope={integration_type}"}


@router.post("/api/admin/db/backup")
async def create_backup():
    from export_engine import export_database_to_json
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


@router.get("/api/admin/db/backups")
async def list_backups():
    db = SessionLocal()
    try:
        backups = db.query(DatabaseBackup).order_by(DatabaseBackup.created_at.desc()).all()
        return [{"id": b.id, "type": b.backup_type, "file": b.file_path,
                 "size": b.size_bytes, "websites": b.websites_count,
                 "created_at": b.created_at.isoformat() if b.created_at else None}
                for b in backups]
    finally:
        db.close()


@router.post("/api/admin/db/restore")
async def restore_from_backup(request: Request):
    data = await request.json()
    filepath_raw = data.get("file", "")
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
