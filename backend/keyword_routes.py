# backend/keyword_routes.py - API endpoints for keyword tracking
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from database import get_db, Website

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


def _run_keyword_sync(website_id: int, days: int = 28):
    """Background task to sync keywords from Search Console."""
    try:
        from search_console import fetch_keyword_data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch_keyword_data(website_id, days=days))
        loop.close()
        print("[KeywordSync] Completed for website " + str(website_id) + ": " + str(result.get("total_keywords", 0)) + " keywords")
    except Exception as e:
        print("[KeywordSync] Failed for website " + str(website_id) + ": " + str(e))
        import traceback
        traceback.print_exc()


@router.post("/{website_id}/sync")
async def sync_keywords(
    website_id: int,
    days: int = 28,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Pull keyword data from Google Search Console. Runs in background."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    background_tasks.add_task(_run_keyword_sync, website_id, days)

    return {
        "status": "syncing",
        "message": "Pulling keyword data from Search Console. This may take 10-30 seconds."
    }


@router.get("/{website_id}")
async def get_keywords(website_id: int, db: Session = Depends(get_db)):
    """Get the latest keyword snapshot for a website."""
    from search_console import get_latest_snapshot
    result = await get_latest_snapshot(website_id)
    return result


@router.get("/{website_id}/history")
async def get_keyword_history_endpoint(website_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """Get historical keyword snapshots."""
    from search_console import get_keyword_history
    result = await get_keyword_history(website_id, limit=limit)
    return result


@router.get("/{website_id}/properties")
async def list_properties(website_id: int, db: Session = Depends(get_db)):
    """List available Search Console properties for this website."""
    from search_console import list_gsc_properties
    result = await list_gsc_properties(website_id)
    return result
