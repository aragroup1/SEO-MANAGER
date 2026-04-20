# backend/strategist_routes.py - AI SEO Strategist API Routes
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from collections import defaultdict

from database import get_db, Website, KeywordSnapshot, StrategistResult

router = APIRouter(prefix="/api/strategist", tags=["strategist"])


def _get_or_create_row(db: Session, website_id: int) -> StrategistResult:
    row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
    if not row:
        row = StrategistResult(website_id=website_id)
        db.add(row)
        db.flush()
    return row


@router.get("/{website_id}/saved")
async def get_saved(website_id: int, db: Session = Depends(get_db)):
    """Return the most recent saved strategy, weekly plan, and portfolio for this website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
    if not row:
        return {"strategy": None, "weekly_plan": None, "portfolio": None, "linking": None, "decay": None}

    return {
        "strategy": row.strategy,
        "strategy_generated_at": row.strategy_generated_at.isoformat() if row.strategy_generated_at else None,
        "weekly_plan": row.weekly_plan,
        "weekly_generated_at": row.weekly_generated_at.isoformat() if row.weekly_generated_at else None,
        "portfolio": row.portfolio,
        "portfolio_generated_at": row.portfolio_generated_at.isoformat() if row.portfolio_generated_at else None,
        "linking": row.linking,
        "linking_generated_at": row.linking_generated_at.isoformat() if row.linking_generated_at else None,
        "decay": row.decay,
        "decay_generated_at": row.decay_generated_at.isoformat() if row.decay_generated_at else None,
    }


@router.post("/{website_id}/generate-strategy")
async def generate_strategy(website_id: int, db: Session = Depends(get_db)):
    """Generate a comprehensive master SEO strategy for this website."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ai_strategist import generate_master_strategy
    result = await generate_master_strategy(website_id)

    if isinstance(result, dict) and not result.get("error"):
        try:
            row = _get_or_create_row(db, website_id)
            row.strategy = result
            row.strategy_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Strategist] Failed to persist strategy: {e}")
            db.rollback()
    return result


@router.post("/{website_id}/weekly-plan")
async def weekly_plan(website_id: int, db: Session = Depends(get_db)):
    """Generate a specific action plan for this week based on current data."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ai_strategist import generate_weekly_plan
    result = await generate_weekly_plan(website_id)

    if isinstance(result, dict) and not result.get("error"):
        try:
            row = _get_or_create_row(db, website_id)
            row.weekly_plan = result
            row.weekly_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Strategist] Failed to persist weekly plan: {e}")
            db.rollback()
    return result


@router.get("/{website_id}/portfolio")
async def portfolio_analysis(website_id: int, db: Session = Depends(get_db)):
    """Analyze the tracked keyword portfolio for conflicts and priorities.
    Returns the cached version if present; pass ?refresh=1 to regenerate."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from ai_strategist import analyze_keyword_portfolio
    result = await analyze_keyword_portfolio(website_id)

    if isinstance(result, dict) and not result.get("error"):
        try:
            row = _get_or_create_row(db, website_id)
            row.portfolio = result
            row.portfolio_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Strategist] Failed to persist portfolio: {e}")
            db.rollback()
    return result


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
    snapshot = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc()).first()

    if not snapshot or not snapshot.keyword_data:
        return {"cannibalization": [], "message": "No keyword data. Sync keywords first."}

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

    cannibalizing.sort(key=lambda x: (x["page_count"], sum(p.get("impressions", 0) for p in x["pages"])), reverse=True)

    return {"total_cannibalizing": len(cannibalizing), "cannibalization": cannibalizing[:50]}
