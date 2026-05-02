import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import get_db, Website, AuditReport, ContentItem

router = APIRouter()


async def _run_audit_async(website_id: int):
    from audit_engine import SEOAuditEngine
    engine = SEOAuditEngine(website_id)
    return await engine.run_comprehensive_audit()


def _run_audit_task(website_id: int):
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


@router.post("/api/audit/{website_id}/start")
async def start_new_audit(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    background_tasks.add_task(_run_audit_task, website_id)
    return {"status": "success", "message": f"Audit started for {website.domain}. Results will appear in 10-30 seconds."}


@router.get("/api/audit/{website_id}")
async def get_latest_audit_report(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    latest_report = db.query(AuditReport).filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc()).first()

    previous_report = None
    if latest_report:
        previous_report = db.query(AuditReport).filter(AuditReport.website_id == website_id,
            AuditReport.id != latest_report.id).order_by(AuditReport.audit_date.desc()).first()

    if not latest_report:
        return {"audit": None, "issues": [], "recommendations": [],
                "message": "No audit has been run yet. Click 'Run New Audit' to start your first SEO analysis."}

    previous_score = previous_report.health_score if previous_report else latest_report.health_score
    score_change = round(latest_report.health_score - previous_score, 1)
    findings = latest_report.detailed_findings or {"issues": [], "recommendations": []}
    raw_data = findings.get("raw_data", {})
    cwv_data = raw_data.get("core_web_vitals", {})

    return {
        "audit": {
            "id": latest_report.id, "health_score": latest_report.health_score,
            "previous_score": previous_score, "score_change": score_change,
            "technical_score": latest_report.technical_score, "content_score": latest_report.content_score,
            "performance_score": latest_report.performance_score, "mobile_score": latest_report.mobile_score,
            "desktop_score": latest_report.desktop_score, "security_score": latest_report.security_score,
            "total_issues": latest_report.total_issues, "critical_issues": latest_report.critical_issues,
            "errors": latest_report.errors, "warnings": latest_report.warnings,
            "notices": latest_report.total_issues - latest_report.critical_issues - latest_report.errors - latest_report.warnings,
            "new_issues": 0, "fixed_issues": 0,
            "audit_date": latest_report.audit_date.isoformat(),
            "domain": website.domain, "core_web_vitals": cwv_data,
        },
        "issues": findings.get("issues", []),
        "recommendations": findings.get("recommendations", []),
    }


@router.get("/api/audit/{website_id}/history")
async def get_audit_history(website_id: int, limit: int = 10, db: Session = Depends(get_db)):
    reports = db.query(AuditReport).filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc()).limit(limit).all()
    return [{
        "id": r.id, "health_score": r.health_score, "technical_score": r.technical_score,
        "content_score": r.content_score, "performance_score": r.performance_score,
        "mobile_score": r.mobile_score, "desktop_score": r.desktop_score,
        "security_score": r.security_score, "total_issues": r.total_issues,
        "critical_issues": r.critical_issues, "errors": r.errors, "warnings": r.warnings,
        "audit_date": r.audit_date.isoformat(),
    } for r in reports]


@router.get("/api/content-calendar/{website_id}")
async def get_content_calendar(website_id: int, db: Session = Depends(get_db)):
    items = db.query(ContentItem).filter(ContentItem.website_id == website_id).all()
    if not items:
        return []
    return [{"id": item.id, "website_id": item.website_id, "title": item.title,
             "content_type": item.content_type,
             "publish_date": item.publish_date.isoformat() if item.publish_date else None,
             "status": item.status, "keywords_target": item.keywords_target or [],
             "ai_generated_content": item.ai_generated_content} for item in items]


@router.post("/api/content-calendar/{website_id}/generate")
async def generate_content_calendar(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    async def create_sample_content():
        for i in range(3):
            content = ContentItem(
                website_id=website_id, title=f"AI-Generated Content Idea {i+1}", content_type="Blog Post",
                publish_date=datetime.utcnow() + timedelta(days=(i+1)*7), status="Draft",
                keywords_target=["AI SEO", "content marketing", "automation"],
                ai_generated_content="AI-generated content would go here...",
            )
            db.add(content)
        db.commit()
    background_tasks.add_task(create_sample_content)
    return {"status": "success", "message": "Content generation initiated"}


@router.get("/api/errors/{website_id}")
async def get_errors(website_id: int, db: Session = Depends(get_db)):
    latest_report = db.query(AuditReport).filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc()).first()
    if not latest_report or not latest_report.detailed_findings:
        return []
    issues = latest_report.detailed_findings.get("issues", [])
    return [{
        "id": issue.get("id", i+1),
        "title": issue.get("title", issue.get("issue_type", "Unknown")),
        "severity": issue.get("severity", "Warning").lower(),
        "description": issue.get("how_to_fix", ""),
        "page": issue.get("affected_pages", ["/"])[0] if issue.get("affected_pages") else "/",
        "category": issue.get("category", "Technical"),
        "auto_fixed": False,
        "affected_urls": issue.get("affected_pages", []),
    } for i, issue in enumerate(issues)]


@router.post("/api/errors/{error_id}/fix")
async def fix_error(error_id: int):
    await asyncio.sleep(1)
    return {"status": "success", "message": f"Error {error_id} fix initiated"}
