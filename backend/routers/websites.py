import re
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from database import (
    get_db, Website, AuditReport, ContentItem, Integration,
    ProposedFix, KeywordSnapshot, TrackedKeyword, StrategistResult,
)
from .audit import _run_audit_task

router = APIRouter()

_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$')
_MAX_DOMAIN_LEN = 253


@router.post("/websites")
async def create_website(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        data = await request.json()
        domain_raw = data.get('domain', '').strip()
        if not domain_raw:
            raise HTTPException(status_code=400, detail="Domain is required")

        domain = domain_raw.replace('http://', '').replace('https://', '').split('/')[0].rstrip('/').lower()
        if len(domain) > _MAX_DOMAIN_LEN or not _DOMAIN_RE.match(domain):
            raise HTTPException(status_code=400, detail="Invalid domain format")

        existing = db.query(Website).filter(Website.domain == domain).first()
        if existing:
            raise HTTPException(status_code=400, detail="Domain already registered")

        website = Website(
            user_id=data.get('user_id', 1),
            domain=domain,
            site_type=data.get('site_type', 'custom'),
            shopify_store_url=data.get('shopify_store_url'),
            shopify_access_token=data.get('shopify_access_token'),
            monthly_traffic=data.get('monthly_traffic'),
        )
        db.add(website)
        db.commit()
        db.refresh(website)

        background_tasks.add_task(_run_audit_task, website.id)

        return {
            "id": website.id, "domain": website.domain, "site_type": website.site_type,
            "created_at": website.created_at.isoformat() if website.created_at else None
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.get("/websites")
async def get_websites(user_id: int | None = None, db: Session = Depends(get_db)):
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
        print(f"[Website] Error fetching websites: {e}")
        return []


@router.delete("/websites/{website_id}")
async def delete_website(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    try:
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


@router.put("/websites/{website_id}")
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


@router.get("/api/websites/{website_id}/automation-summary")
async def get_automation_summary(website_id: int, days: int = 7):
    from reporting import generate_automation_summary
    return await generate_automation_summary(website_id, days)


@router.get("/api/websites/{website_id}/full-summary")
async def get_full_website_summary(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id, Website.is_active == True).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    audit_history = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc())\
        .limit(30).all()
    audit_history_reversed = list(reversed(audit_history))

    latest_audit = audit_history[0] if audit_history else None
    prev_audit = audit_history[1] if len(audit_history) > 1 else None

    keyword_history = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc())\
        .limit(30).all()
    keyword_history_reversed = list(reversed(keyword_history))

    latest_snap = keyword_history[0] if keyword_history else None

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

    tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
    tracked_keywords = [{
        "id": tk.id, "keyword": tk.keyword,
        "current_position": tk.current_position, "target_position": tk.target_position,
        "status": tk.status, "current_clicks": tk.current_clicks,
        "current_impressions": tk.current_impressions,
    } for tk in tracked]

    strategist = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
    content_items = db.query(ContentItem).filter(ContentItem.website_id == website_id).order_by(ContentItem.id.desc()).limit(5).all()

    geo_audit = strategist.geo_audit if (strategist and strategist.geo_audit) else None

    return {
        "website": {
            "id": website.id, "domain": website.domain, "site_type": website.site_type,
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
                "desktop_score": latest_audit.desktop_score if latest_audit else None,
                "security_score": latest_audit.security_score if latest_audit else None,
                "total_issues": latest_audit.total_issues if latest_audit else 0,
                "critical_issues": latest_audit.critical_issues if latest_audit else 0,
                "errors": latest_audit.errors if latest_audit else 0,
                "warnings": latest_audit.warnings if latest_audit else 0,
                "audit_date": latest_audit.audit_date.isoformat() if latest_audit else None,
                "score_change": round(latest_audit.health_score - (prev_audit.health_score if prev_audit else latest_audit.health_score), 1) if latest_audit else 0,
            },
            "history": [
                {"date": a.audit_date.isoformat(), "health_score": a.health_score,
                 "technical_score": a.technical_score, "content_score": a.content_score,
                 "performance_score": a.performance_score, "total_issues": a.total_issues}
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
                {"date": s.snapshot_date.isoformat(), "total_keywords": s.total_keywords,
                 "total_clicks": s.total_clicks, "total_impressions": s.total_impressions,
                 "avg_position": s.avg_position}
                for s in keyword_history_reversed
            ],
            "tracked": tracked_keywords,
            "tracked_count": len(tracked_keywords),
        },
        "fixes": {
            "pending": pending_fixes, "approved": approved_fixes, "applied": applied_fixes,
            "auto_approved": auto_approved_count, "auto_applied": auto_applied_count,
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
            "recent": [{"id": c.id, "title": c.title, "content_type": c.content_type, "status": c.status} for c in content_items],
        },
    }
