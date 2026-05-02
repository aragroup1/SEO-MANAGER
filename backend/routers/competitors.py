import os
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from database import get_db, Website, TrackedKeyword, KeywordSnapshot

router = APIRouter()


@router.post("/api/competitors/{website_id}/research")
async def research_competitor(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    competitor_domain = data.get("competitor_domain", "").strip()
    if not competitor_domain:
        return {"error": "Competitor domain is required"}

    competitor_domain = competitor_domain.replace("https://", "").replace("http://", "").rstrip("/")

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        return {"error": "Website not found"}

    tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
    tracked_kws = [{"keyword": tk.keyword, "position": tk.current_position, "url": tk.target_url} for tk in tracked]

    latest_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc()).first()
    top_keywords = []
    if latest_snap and latest_snap.keyword_data:
        top_keywords = [{"query": kw.get("query", ""), "position": kw.get("position", 0),
                         "clicks": kw.get("clicks", 0)} for kw in latest_snap.keyword_data[:20]]

    competitor_content = ""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(f"https://{competitor_domain}")
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                title = soup.title.string if soup.title else ""
                meta_tag = soup.find("meta", attrs={"name": "description"})
                meta_desc = meta_tag.get("content", "") if meta_tag else ""
                headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])[:20]]
                links = [a.get('href', '') for a in soup.find_all('a', href=True) if competitor_domain in a.get('href', '')][:30]
                competitor_content = f"Title: {title}\nMeta: {meta_desc}\nHeadings: {', '.join(headings)}\nInternal pages: {len(links)}"
    except Exception as e:
        competitor_content = f"Could not crawl: {e}"

    GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
    if not GEMINI_API_KEY:
        return {"error": "AI API key not configured"}

    prompt = f"""You are an SEO competitive analyst. Analyze this competitor and provide actionable intelligence.

YOUR WEBSITE: {website.domain}
Your top keywords: {json.dumps(top_keywords[:10])}
Your tracked keywords (Road to #1): {json.dumps(tracked_kws)}

COMPETITOR: {competitor_domain}
Competitor page data: {competitor_content[:2000]}

Provide:
1. COMPETITOR OVERVIEW: What they do, their apparent SEO strategy, strengths
2. CONTENT GAPS: Topics/keywords they cover that {website.domain} doesn't
3. THEIR WEAKNESSES: Where {website.domain} already beats them or could easily beat them
4. KEYWORD OPPORTUNITIES: Keywords they rank for that {website.domain} should target
5. ACTION PLAN: 5 specific things to do this week to gain ground against them

Be specific, actionable, and reference actual data. Format with clear sections."""

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.4}}
            )
            if resp.status_code == 200:
                analysis = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {"competitor_analysis": analysis, "competitor_domain": competitor_domain, "your_domain": website.domain}
            elif resp.status_code == 429:
                return {"error": "AI rate limited. Try again in a minute or enable Gemini billing."}
            else:
                return {"error": f"AI error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}
