# backend/geo_routes.py - GEO (Generative Engine Optimization) API endpoints
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Optional
import asyncio

from database import get_db, Website

router = APIRouter(prefix="/api/geo", tags=["geo"])


def _run_geo_audit(website_id: int):
    """Background task for GEO audit."""
    try:
        from geo_engine import run_geo_audit
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_geo_audit(website_id))
        loop.close()

        # Save result to website config or a cache
        from database import SessionLocal, Website
        db = SessionLocal()
        try:
            website = db.query(Website).filter(Website.id == website_id).first()
            if website:
                import json
                # Store in a simple way - could use a dedicated table later
                # For now, we'll return via the API and let frontend cache
                pass
        finally:
            db.close()

        print(f"[GEO] Audit completed for website {website_id}: score {result.get('scores', {}).get('overall', 0)}")
    except Exception as e:
        print(f"[GEO] Audit failed: {e}")
        import traceback
        traceback.print_exc()


@router.post("/{website_id}/audit")
async def run_geo_audit_endpoint(website_id: int, db: Session = Depends(get_db)):
    """Run a GEO audit synchronously (takes 10-30 seconds)."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from geo_engine import run_geo_audit
    result = await run_geo_audit(website_id)
    return result


@router.post("/{website_id}/test-citation")
async def test_citation(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Test if your domain gets cited by AI for a specific query."""
    data = await request.json()
    query = data.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from geo_engine import test_ai_citation
    result = await test_ai_citation(website.domain, query)
    return result
