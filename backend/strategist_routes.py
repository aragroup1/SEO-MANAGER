# backend/strategist_routes.py - AI SEO Strategist Chat API
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from database import get_db, Website

router = APIRouter(prefix="/api/strategist", tags=["strategist"])


@router.post("/{website_id}/chat")
async def chat(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Chat with the AI SEO strategist about this website."""
    data = await request.json()
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ai_strategist import chat_with_strategist
    result = await chat_with_strategist(website_id, message, conversation_history=history)
    return result


@router.get("/{website_id}/cannibalization")
async def detect_cannibalization(website_id: int, db: Session = Depends(get_db)):
    """Detect keyword cannibalization across the site."""
    from database import KeywordSnapshot
    from collections import defaultdict

    snapshot = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc()).first()

    if not snapshot or not snapshot.keyword_data:
        return {"cannibalization": [], "message": "No keyword data. Sync keywords first."}

    # Group by query — find keywords with multiple ranking pages
    keyword_pages = defaultdict(list)
    for kw in snapshot.keyword_data:
        query = kw.get("query", "")
        page = kw.get("page", "")
        if query and page:
            keyword_pages[query].append({
                "page": page,
                "position": kw.get("position", 0),
                "clicks": kw.get("clicks", 0),
                "impressions": kw.get("impressions", 0),
            })

    # Filter to keywords with 2+ distinct pages
    cannibalizing = []
    for query, pages in keyword_pages.items():
        unique_pages = {}
        for p in pages:
            url = p["page"]
            if url not in unique_pages or p["clicks"] > unique_pages[url].get("clicks", 0):
                unique_pages[url] = p

        if len(unique_pages) > 1:
            cannibalizing.append({
                "keyword": query,
                "pages": list(unique_pages.values()),
                "page_count": len(unique_pages),
            })

    # Sort by page count desc, then by total impressions
    cannibalizing.sort(key=lambda x: (x["page_count"], sum(p.get("impressions", 0) for p in x["pages"])), reverse=True)

    return {
        "total_cannibalizing": len(cannibalizing),
        "cannibalization": cannibalizing[:50],
    }
