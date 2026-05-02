import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session

from database import get_db, ContentItem

router = APIRouter()


@router.post("/api/content/{website_id}/generate")
async def generate_content_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    from content_writer import generate_content
    return await generate_content(
        website_id=website_id,
        content_type=data.get("content_type", "blog_post"),
        topic=data.get("topic", ""),
        target_keywords=data.get("target_keywords", []),
        word_count=data.get("word_count", 800),
        tone=data.get("tone", "professional"),
        additional_instructions=data.get("instructions", ""),
    )


@router.post("/api/content/{website_id}/ideas")
async def suggest_content_ideas_endpoint(website_id: int, db: Session = Depends(get_db)):
    from content_writer import suggest_content_ideas
    return await suggest_content_ideas(website_id)


@router.get("/api/content/{website_id}/list")
async def list_content(website_id: int, db: Session = Depends(get_db)):
    items = db.query(ContentItem).filter(ContentItem.website_id == website_id).order_by(ContentItem.id.desc()).all()
    return {
        "content": [{
            "id": item.id, "title": item.title, "content_type": item.content_type,
            "status": item.status, "keywords": item.keywords_target or [],
            "created_at": item.publish_date.isoformat() if item.publish_date else None,
            "has_content": bool(item.ai_generated_content),
        } for item in items]
    }


@router.get("/api/content/{website_id}/queue")
async def get_content_queue(website_id: int, db: Session = Depends(get_db)):
    from content_writer import get_publishing_queue
    result = await get_publishing_queue(website_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/api/content/{website_id}/{content_id}")
async def get_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.website_id == website_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    content_data = {}
    if item.ai_generated_content:
        try:
            content_data = json.loads(item.ai_generated_content)
        except Exception:
            content_data = {"content_html": item.ai_generated_content}
    return {"id": item.id, "title": item.title, "content_type": item.content_type,
            "status": item.status, "keywords": item.keywords_target, "content": content_data}


@router.post("/api/content/{website_id}/{content_id}/publish")
async def publish_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    from content_writer import publish_content
    return await publish_content(website_id, content_id)


@router.post("/api/content/{website_id}/{content_id}/schedule")
async def schedule_content_item(website_id: int, content_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    publish_date_str = data.get("publish_date")
    if not publish_date_str:
        raise HTTPException(status_code=400, detail="publish_date is required")
    try:
        publish_date = datetime.fromisoformat(publish_date_str.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid publish_date format. Use ISO 8601.")
    from content_writer import schedule_content
    result = await schedule_content(website_id, content_id, publish_date)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/content/{website_id}/{content_id}/cancel")
async def cancel_scheduled_content(website_id: int, content_id: int, db: Session = Depends(get_db)):
    from content_writer import cancel_scheduled
    result = await cancel_scheduled(website_id, content_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/api/content/{website_id}/{content_id}")
async def delete_content_item(website_id: int, content_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id, ContentItem.website_id == website_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    db.delete(item)
    db.commit()
    return {"deleted": True}
