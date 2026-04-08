# backend/road_to_one.py - Road to #1 Strategy Engine
# For each tracked keyword: crawls top competitors, analyzes gaps, generates action plan
import os
import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv

from database import SessionLocal, Website, TrackedKeyword, Integration, KeywordSnapshot

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


# ─────────────────────────────────────────────
#  Competitor page crawler
# ─────────────────────────────────────────────

async def _crawl_page(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    """Crawl a single page and extract SEO-relevant data."""
    try:
        start = time.time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), ssl=False, allow_redirects=True) as resp:
            elapsed = round((time.time() - start) * 1000)
            if resp.status != 200:
                return {"url": url, "error": "Status " + str(resp.status), "status": resp.status}

            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            # Title
            title_tag = soup.find('title')
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_description = (meta_desc.get('content') or '').strip() if meta_desc else ""

            # H1
            h1_tags = soup.find_all('h1')
            h1_text = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]

            # All headings structure
            headings = []
            for level in range(1, 7):
                for tag in soup.find_all(f'h{level}'):
                    text = tag.get_text(strip=True)
                    if text:
                        headings.append({"level": level, "text": text[:100]})

            # Content
            body = soup.find('body')
            content_text = ""
            if body:
                body_clone = BeautifulSoup(str(body), 'html.parser').find('body')
                for tag in body_clone.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                    tag.decompose()
                content_text = body_clone.get_text(separator=' ', strip=True)

            word_count = len(content_text.split())

            # Images
            images = soup.find_all('img')
            images_with_alt = sum(1 for img in images if img.get('alt', '').strip())

            # Internal/external links
            links = soup.find_all('a', href=True)
            parsed_url = urlparse(url)
            internal_links = 0
            external_links = 0
            for link in links:
                href = link['href']
                if href.startswith(('#', 'javascript:', 'mailto:')):
                    continue
                full = urljoin(url, href)
                if urlparse(full).netloc == parsed_url.netloc:
                    internal_links += 1
                else:
                    external_links += 1

            # Structured data
            json_ld = soup.find_all('script', type='application/ld+json')
            schema_types = []
            for script in json_ld:
                try:
                    data = json.loads(script.string or '{}')
                    t = data.get('@type', '')
                    if isinstance(t, list):
                        schema_types.extend(t)
                    elif t:
                        schema_types.append(t)
                except:
                    pass

            # Canonical
            canonical = soup.find('link', rel='canonical')
            canonical_url = canonical.get('href', '') if canonical else ""

            # OG tags
            og_tags = {tag.get('property', ''): tag.get('content', '') for tag in soup.find_all('meta', property=True) if tag.get('property', '').startswith('og:')}

            return {
                "url": url,
                "status": resp.status,
                "response_time_ms": elapsed,
                "title": title,
                "title_length": len(title),
                "meta_description": meta_description,
                "meta_description_length": len(meta_description),
                "h1": h1_text,
                "headings": headings[:30],
                "heading_count": len(headings),
                "word_count": word_count,
                "content_preview": content_text[:500],
                "total_images": len(images),
                "images_with_alt": images_with_alt,
                "internal_links": internal_links,
                "external_links": external_links,
                "schema_types": schema_types,
                "has_canonical": bool(canonical_url),
                "og_tags": og_tags,
                "html_size_kb": round(len(html.encode('utf-8')) / 1024, 1),
            }
    except Exception as e:
        return {"url": url, "error": str(e), "status": 0}


async def _search_google_for_competitors(keyword: str, country: str = "GB", num_results: int = 5) -> List[Dict]:
    """Get top Google results for a keyword using a scraping approach."""
    # Use Google's custom search JSON API or a simple scrape
    # For now, use Gemini to identify likely top-ranking pages
    if not GEMINI_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            prompt = f"""For the Google search query "{keyword}" in {country}, list the top 5 organic results that would typically rank.
For each result provide the exact URL and the page title.

Return ONLY a JSON array, no other text:
[
  {{"url": "https://example.com/page", "title": "Page Title", "position": 1}},
  ...
]"""
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                results = json.loads(text)
                if isinstance(results, list):
                    return results[:num_results]
    except Exception as e:
        print(f"[RoadTo1] Search error: {e}")

    return []


# ─────────────────────────────────────────────
#  Strategy generation
# ─────────────────────────────────────────────

async def _generate_strategy(
    keyword: str,
    your_page: Dict,
    competitor_pages: List[Dict],
    current_position: float,
    website_domain: str,
) -> Dict[str, Any]:
    """Use AI to generate a comprehensive Road to #1 strategy."""
    if not GEMINI_API_KEY:
        return {"error": "No AI API key configured"}

    # Build competitor comparison data
    comp_summaries = []
    for i, comp in enumerate(competitor_pages):
        if comp.get("error"):
            continue
        comp_summaries.append(f"""
Competitor #{i+1} (Position ~{i+1}): {comp.get('url', '')}
- Title ({comp.get('title_length', 0)} chars): {comp.get('title', '')}
- Meta Description ({comp.get('meta_description_length', 0)} chars): {comp.get('meta_description', '')[:150]}
- Word Count: {comp.get('word_count', 0)}
- H1: {', '.join(comp.get('h1', [])[:2])}
- Headings: {comp.get('heading_count', 0)} total
- Images: {comp.get('total_images', 0)} ({comp.get('images_with_alt', 0)} with alt)
- Internal Links: {comp.get('internal_links', 0)}
- External Links: {comp.get('external_links', 0)}
- Schema Types: {', '.join(comp.get('schema_types', [])) or 'None'}
- Content Preview: {comp.get('content_preview', '')[:200]}
""")

    your_summary = "NOT RANKING / NO PAGE FOUND"
    if your_page and not your_page.get("error"):
        your_summary = f"""
Your Page: {your_page.get('url', '')}
- Title ({your_page.get('title_length', 0)} chars): {your_page.get('title', '')}
- Meta Description ({your_page.get('meta_description_length', 0)} chars): {your_page.get('meta_description', '')[:150]}
- Word Count: {your_page.get('word_count', 0)}
- H1: {', '.join(your_page.get('h1', [])[:2])}
- Headings: {your_page.get('heading_count', 0)} total
- Images: {your_page.get('total_images', 0)} ({your_page.get('images_with_alt', 0)} with alt)
- Internal Links: {your_page.get('internal_links', 0)}
- External Links: {your_page.get('external_links', 0)}
- Schema Types: {', '.join(your_page.get('schema_types', [])) or 'None'}
- Content Preview: {your_page.get('content_preview', '')[:200]}
"""

    prompt = f"""You are a world-class SEO strategist. Analyze the following data and create a comprehensive strategy to rank #{1} for the keyword "{keyword}".

Current Position: {current_position or 'Not ranking'}
Website: {website_domain}

=== YOUR PAGE ===
{your_summary}

=== COMPETITOR PAGES ===
{''.join(comp_summaries) if comp_summaries else 'No competitor data available'}

Create a detailed strategy as a JSON object with this EXACT structure:
{{
  "summary": "2-3 sentence executive summary of what needs to happen",
  "current_gaps": [
    {{"gap": "description of gap", "severity": "critical/high/medium/low", "category": "content/technical/authority/ux"}}
  ],
  "action_plan": [
    {{
      "priority": 1,
      "action": "specific action to take",
      "category": "content/technical/authority/ux",
      "effort": "quick_win/medium/major",
      "impact": "high/medium/low",
      "details": "detailed implementation instructions",
      "auto_fixable": true/false
    }}
  ],
  "content_recommendations": {{
    "target_word_count": 1500,
    "suggested_title": "optimized title for the keyword",
    "suggested_meta_description": "optimized meta description",
    "suggested_h1": "optimized H1 heading",
    "content_outline": ["Section 1: ...", "Section 2: ...", "..."],
    "missing_topics": ["topic competitors cover that you don't"],
    "internal_linking_suggestions": ["suggested internal links to add"]
  }},
  "technical_fixes": [
    {{"fix": "description", "auto_fixable": true/false, "how_to": "implementation steps"}}
  ],
  "estimated_timeline": "estimated time to reach #1 with these changes",
  "confidence_score": 75
}}

Return ONLY the JSON object, no other text."""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                strategy = json.loads(text)
                return strategy
            else:
                print(f"[RoadTo1] AI error: {resp.status_code} {resp.text[:200]}")
                return {"error": "AI generation failed: " + str(resp.status_code)}
    except json.JSONDecodeError as e:
        print(f"[RoadTo1] JSON parse error: {e}")
        return {"error": "Failed to parse AI response"}
    except Exception as e:
        print(f"[RoadTo1] Strategy error: {e}")
        return {"error": str(e)}


# ─────────────────────────────────────────────
#  Main orchestrator
# ─────────────────────────────────────────────

async def generate_road_to_one_strategy(
    website_id: int,
    keyword_id: int,
) -> Dict[str, Any]:
    """
    Full Road to #1 workflow for a tracked keyword:
    1. Find your current ranking page
    2. Search for top competitors
    3. Crawl competitor pages
    4. Generate AI strategy
    5. Save to tracked keyword
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        tracked = db.query(TrackedKeyword).filter(
            TrackedKeyword.id == keyword_id,
            TrackedKeyword.website_id == website_id
        ).first()
        if not tracked:
            return {"error": "Tracked keyword not found"}

        keyword = tracked.keyword
        current_position = tracked.current_position
        ranking_url = tracked.ranking_url

        print(f"[RoadTo1] Generating strategy for '{keyword}' on {website.domain}")
        print(f"[RoadTo1] Current position: {current_position}, ranking URL: {ranking_url}")

        connector = aiohttp.TCPConnector(limit=5, ssl=False)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "SEOIntelligenceBot/2.0"}
        ) as session:

            # Step 1: Crawl your current ranking page (if you have one)
            your_page = {}
            if ranking_url:
                print(f"[RoadTo1] Crawling your page: {ranking_url}")
                your_page = await _crawl_page(session, ranking_url)
            else:
                # Try homepage or a likely page
                test_url = f"https://{website.domain}/"
                your_page = await _crawl_page(session, test_url)
                your_page["note"] = "No specific ranking page found — analyzed homepage"

            # Step 2: Find top competitors
            print(f"[RoadTo1] Finding competitors for '{keyword}'...")
            search_results = await _search_google_for_competitors(keyword, "GB", 5)

            # Filter out own domain from competitors
            competitors = [r for r in search_results if website.domain not in r.get("url", "")][:3]

            # Step 3: Crawl competitor pages
            competitor_pages = []
            for comp in competitors:
                url = comp.get("url", "")
                if url:
                    print(f"[RoadTo1] Crawling competitor: {url}")
                    page_data = await _crawl_page(session, url)
                    page_data["search_position"] = comp.get("position", 0)
                    page_data["search_title"] = comp.get("title", "")
                    competitor_pages.append(page_data)
                    await asyncio.sleep(0.5)  # Polite delay

            # Step 4: Generate AI strategy
            print(f"[RoadTo1] Generating AI strategy...")
            strategy = await _generate_strategy(
                keyword=keyword,
                your_page=your_page,
                competitor_pages=competitor_pages,
                current_position=current_position,
                website_domain=website.domain,
            )

            if "error" in strategy:
                return strategy

            # Step 5: Save strategy to tracked keyword
            tracked.notes = json.dumps({
                "strategy": strategy,
                "competitors": [
                    {
                        "url": cp.get("url", ""),
                        "title": cp.get("title", ""),
                        "word_count": cp.get("word_count", 0),
                        "position": cp.get("search_position", 0),
                    }
                    for cp in competitor_pages if not cp.get("error")
                ],
                "your_page": {
                    "url": your_page.get("url", ""),
                    "title": your_page.get("title", ""),
                    "word_count": your_page.get("word_count", 0),
                },
                "generated_at": datetime.utcnow().isoformat(),
            })
            tracked.updated_at = datetime.utcnow()
            db.commit()

            print(f"[RoadTo1] Strategy saved for '{keyword}'")

            return {
                "keyword": keyword,
                "current_position": current_position,
                "your_page": your_page,
                "competitors": competitor_pages,
                "strategy": strategy,
            }

    except Exception as e:
        print(f"[RoadTo1] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()
