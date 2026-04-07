# backend/keyword_routes.py - API endpoints for keyword tracking
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import asyncio

from database import get_db, Website, TrackedKeyword

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


def _run_keyword_sync(website_id: int, days: int = 28):
    """Background task to sync keywords from Search Console."""
    try:
        from search_console import fetch_keyword_data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch_keyword_data(website_id, days=days))
        loop.close()

        # Auto-update tracked keywords with latest data
        if "keywords" in result:
            _update_tracked_keywords(website_id, result["keywords"])

        print("[KeywordSync] Completed for website " + str(website_id) + ": "
              + str(result.get("total_keywords", 0)) + " keywords")
    except Exception as e:
        print("[KeywordSync] Failed for website " + str(website_id) + ": " + str(e))
        import traceback
        traceback.print_exc()


def _update_tracked_keywords(website_id: int, keywords: list):
    """Update tracked keywords with latest ranking data from a sync."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
        if not tracked:
            return

        keyword_map = {kw["query"].lower(): kw for kw in keywords}

        for tk in tracked:
            data = keyword_map.get(tk.keyword.lower())
            if data:
                tk.current_position = data.get("position")
                tk.current_clicks = data.get("clicks", 0)
                tk.current_impressions = data.get("impressions", 0)
                tk.current_ctr = data.get("ctr", 0)
                tk.ranking_url = data.get("page", "")
                tk.updated_at = datetime.utcnow()

        db.commit()
    except Exception as e:
        print("[KeywordSync] Error updating tracked keywords: " + str(e))
    finally:
        db.close()


# ─── Sync & Fetch ───

@router.post("/{website_id}/sync")
async def sync_keywords(
    website_id: int,
    days: int = 28,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    background_tasks.add_task(_run_keyword_sync, website_id, days)
    return {"status": "syncing", "message": "Pulling keyword data from Search Console..."}


@router.get("/{website_id}")
async def get_keywords(website_id: int, db: Session = Depends(get_db)):
    from search_console import get_latest_snapshot
    result = await get_latest_snapshot(website_id)
    return result


@router.get("/{website_id}/history")
async def get_keyword_history_endpoint(website_id: int, limit: int = 10, db: Session = Depends(get_db)):
    from search_console import get_keyword_history
    result = await get_keyword_history(website_id, limit=limit)
    return result


@router.get("/{website_id}/properties")
async def list_properties(website_id: int, db: Session = Depends(get_db)):
    from search_console import list_gsc_properties
    result = await list_gsc_properties(website_id)
    return result


# ─── Tracked Keywords (Road to #1) ───

@router.get("/{website_id}/tracked")
async def get_tracked_keywords(website_id: int, db: Session = Depends(get_db)):
    tracked = db.query(TrackedKeyword).filter(
        TrackedKeyword.website_id == website_id
    ).order_by(TrackedKeyword.current_position.asc().nullsfirst()).all()

    return {
        "tracked": [
            {
                "id": tk.id,
                "keyword": tk.keyword,
                "current_position": tk.current_position,
                "current_clicks": tk.current_clicks,
                "current_impressions": tk.current_impressions,
                "current_ctr": tk.current_ctr,
                "ranking_url": tk.ranking_url,
                "target_position": tk.target_position,
                "notes": tk.notes,
                "status": tk.status,
                "created_at": tk.created_at.isoformat() if tk.created_at else None,
                "updated_at": tk.updated_at.isoformat() if tk.updated_at else None,
            }
            for tk in tracked
        ]
    }


@router.post("/{website_id}/track")
async def track_keyword(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Add a keyword to tracked list."""
    data = await request.json()
    keyword = data.get("keyword", "").strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")

    # Check if already tracked
    existing = db.query(TrackedKeyword).filter(
        TrackedKeyword.website_id == website_id,
        TrackedKeyword.keyword == keyword
    ).first()

    if existing:
        return {"already_tracked": True, "id": existing.id}

    tk = TrackedKeyword(
        website_id=website_id,
        keyword=keyword,
        current_position=data.get("position"),
        current_clicks=data.get("clicks", 0),
        current_impressions=data.get("impressions", 0),
        current_ctr=data.get("ctr", 0),
        ranking_url=data.get("page", ""),
        target_position=data.get("target_position", 1),
    )
    db.add(tk)
    db.commit()
    db.refresh(tk)

    return {"tracked": True, "id": tk.id, "keyword": tk.keyword}


@router.delete("/{website_id}/track/{keyword_id}")
async def untrack_keyword(website_id: int, keyword_id: int, db: Session = Depends(get_db)):
    tk = db.query(TrackedKeyword).filter(
        TrackedKeyword.id == keyword_id,
        TrackedKeyword.website_id == website_id
    ).first()
    if not tk:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")
    db.delete(tk)
    db.commit()
    return {"removed": True}
