# backend/fix_routes.py - API endpoints for the auto-fix engine
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional, List
import asyncio

from database import SessionLocal, get_db, ProposedFix, Website

router = APIRouter(prefix="/api/fixes", tags=["fixes"])


# ─────────────────────────────────────────
#  Background task wrapper
# ─────────────────────────────────────────

def _run_fix_scan_task(website_id: int):
    """Background task to run the fix scanner."""
    try:
        from fix_engine import generate_fixes_for_website
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_fixes_for_website(website_id))
        loop.close()
        print(f"[FixScan] Completed for website {website_id}: {result}")
    except Exception as e:
        print(f"[FixScan] Failed for website {website_id}: {e}")
        import traceback
        traceback.print_exc()


def _run_apply_fix_task(fix_id: int):
    """Background task to apply a single fix."""
    try:
        from fix_engine import apply_approved_fix
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(apply_approved_fix(fix_id))
        loop.close()
        print(f"[FixApply] Fix {fix_id}: {result}")
    except Exception as e:
        print(f"[FixApply] Failed for fix {fix_id}: {e}")


def _run_apply_batch_task(fix_ids: List[int]):
    """Background task to apply multiple fixes."""
    try:
        from fix_engine import apply_approved_fix
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for fix_id in fix_ids:
            result = loop.run_until_complete(apply_approved_fix(fix_id))
            print(f"[FixApply] Fix {fix_id}: {result}")
        loop.close()
    except Exception as e:
        print(f"[FixApply] Batch apply failed: {e}")


# ─────────────────────────────────────────
#  Scan & Generate
# ─────────────────────────────────────────

@router.post("/{website_id}/scan")
async def scan_for_fixes(
    website_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Scan a website and generate proposed fixes. Runs in background."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    if website.site_type not in ["shopify", "wordpress"]:
        raise HTTPException(
            status_code=400,
            detail="Auto-fix scanning is available for Shopify and WordPress sites. Custom sites can use audit recommendations for manual fixes."
        )

    background_tasks.add_task(_run_fix_scan_task, website_id)

    return {
        "status": "scanning",
        "message": f"Scanning {website.domain} for fixable issues. This may take 1-2 minutes depending on the number of products/pages."
    }


# ─────────────────────────────────────────
#  List & Filter fixes
# ─────────────────────────────────────────

@router.get("/{website_id}")
async def get_fixes(
    website_id: int,
    status: Optional[str] = None,
    fix_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get proposed fixes for a website with optional filters."""
    query = db.query(ProposedFix).filter(ProposedFix.website_id == website_id)

    if status:
        query = query.filter(ProposedFix.status == status)
    if fix_type:
        query = query.filter(ProposedFix.fix_type == fix_type)
    if severity:
        query = query.filter(ProposedFix.severity == severity)

    total = query.count()
    fixes = query.order_by(ProposedFix.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "fixes": [
            {
                "id": f.id,
                "fix_type": f.fix_type,
                "platform": f.platform,
                "resource_type": f.resource_type,
                "resource_id": f.resource_id,
                "resource_url": f.resource_url,
                "resource_title": f.resource_title,
                "field_name": f.field_name,
                "current_value": f.current_value,
                "proposed_value": f.proposed_value,
                "ai_reasoning": f.ai_reasoning,
                "status": f.status,
                "severity": f.severity,
                "category": f.category,
                "batch_id": f.batch_id,
                "error_message": f.error_message,
                "applied_at": f.applied_at.isoformat() if f.applied_at else None,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in fixes
        ]
    }


@router.get("/{website_id}/summary")
async def get_fix_summary(website_id: int, db: Session = Depends(get_db)):
    """Get a summary of fixes by status and type."""
    # Count by status
    status_counts = dict(
        db.query(ProposedFix.status, func.count(ProposedFix.id))
        .filter(ProposedFix.website_id == website_id)
        .group_by(ProposedFix.status)
        .all()
    )

    # Count by fix type
    type_counts = dict(
        db.query(ProposedFix.fix_type, func.count(ProposedFix.id))
        .filter(ProposedFix.website_id == website_id)
        .group_by(ProposedFix.fix_type)
        .all()
    )

    # Count by severity
    severity_counts = dict(
        db.query(ProposedFix.severity, func.count(ProposedFix.id))
        .filter(ProposedFix.website_id == website_id)
        .group_by(ProposedFix.severity)
        .all()
    )

    return {
        "total": sum(status_counts.values()),
        "by_status": {
            "pending": status_counts.get("pending", 0),
            "approved": status_counts.get("approved", 0),
            "rejected": status_counts.get("rejected", 0),
            "applied": status_counts.get("applied", 0),
            "failed": status_counts.get("failed", 0),
        },
        "by_type": type_counts,
        "by_severity": severity_counts,
    }


# ─────────────────────────────────────────
#  Approve / Reject / Apply
# ─────────────────────────────────────────

@router.post("/{fix_id}/approve")
async def approve_fix(fix_id: int, db: Session = Depends(get_db)):
    """Approve a proposed fix."""
    fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found")
    if fix.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot approve a fix with status '{fix.status}'")

    fix.status = "approved"
    fix.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "approved", "message": "Fix approved. Click 'Apply' to push the change to your site."}


@router.post("/{fix_id}/reject")
async def reject_fix(fix_id: int, db: Session = Depends(get_db)):
    """Reject a proposed fix."""
    fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found")

    fix.status = "rejected"
    fix.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "rejected", "message": "Fix rejected and will not be applied."}


@router.post("/{fix_id}/apply")
async def apply_fix(
    fix_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Apply an approved fix to the live site."""
    fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found")
    if fix.status != "approved":
        raise HTTPException(status_code=400, detail=f"Fix must be approved first (current status: {fix.status})")

    background_tasks.add_task(_run_apply_fix_task, fix_id)

    return {"status": "applying", "message": "Fix is being applied to your site..."}


@router.post("/{fix_id}/edit")
async def edit_fix(fix_id: int, request: Request, db: Session = Depends(get_db)):
    """Edit the proposed value before approving."""
    data = await request.json()
    fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found")
    if fix.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail=f"Cannot edit a fix with status '{fix.status}'")

    if "proposed_value" in data:
        fix.proposed_value = data["proposed_value"]
    fix.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "updated", "proposed_value": fix.proposed_value}


# ─────────────────────────────────────────
#  Batch operations
# ─────────────────────────────────────────

@router.post("/{website_id}/batch/approve")
async def batch_approve(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Approve multiple fixes at once."""
    data = await request.json()
    fix_ids = data.get("fix_ids", [])
    fix_type = data.get("fix_type")  # Optional: approve all of a type

    query = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id,
        ProposedFix.status == "pending"
    )

    if fix_ids:
        query = query.filter(ProposedFix.id.in_(fix_ids))
    elif fix_type:
        query = query.filter(ProposedFix.fix_type == fix_type)
    else:
        raise HTTPException(status_code=400, detail="Provide fix_ids or fix_type")

    count = query.update({"status": "approved", "updated_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    return {"approved": count, "message": f"Approved {count} fixes"}


@router.post("/{website_id}/batch/apply")
async def batch_apply(
    website_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Apply all approved fixes for a website."""
    data = await request.json()
    fix_ids = data.get("fix_ids", [])

    if not fix_ids:
        # Apply all approved fixes
        approved = db.query(ProposedFix).filter(
            ProposedFix.website_id == website_id,
            ProposedFix.status == "approved"
        ).all()
        fix_ids = [f.id for f in approved]

    if not fix_ids:
        return {"message": "No approved fixes to apply"}

    background_tasks.add_task(_run_apply_batch_task, fix_ids)

    return {"applying": len(fix_ids), "message": f"Applying {len(fix_ids)} fixes in the background..."}


@router.post("/{website_id}/batch/reject")
async def batch_reject(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Reject multiple fixes."""
    data = await request.json()
    fix_ids = data.get("fix_ids", [])
    fix_type = data.get("fix_type")

    query = db.query(ProposedFix).filter(
        ProposedFix.website_id == website_id,
        ProposedFix.status == "pending"
    )

    if fix_ids:
        query = query.filter(ProposedFix.id.in_(fix_ids))
    elif fix_type:
        query = query.filter(ProposedFix.fix_type == fix_type)

    count = query.update({"status": "rejected", "updated_at": datetime.utcnow()}, synchronize_session=False)
    db.commit()

    return {"rejected": count}


@router.delete("/{website_id}/clear")
async def clear_fixes(
    website_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Clear fixes (rejected/applied) to clean up the queue."""
    query = db.query(ProposedFix).filter(ProposedFix.website_id == website_id)

    if status:
        query = query.filter(ProposedFix.status == status)
    else:
        # Default: only clear rejected and applied
        query = query.filter(ProposedFix.status.in_(["rejected", "applied"]))

    count = query.delete(synchronize_session=False)
    db.commit()

    return {"cleared": count}
