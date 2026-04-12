# backend/content_decay.py - Content Decay Detection
# Monitors competitor pages and your own content for freshness signals.
# Detects when competitors update content, when your content is getting stale,
# and flags opportunities to refresh content for ranking gains.
import os
import json
import asyncio
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import httpx
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

from database import (
    SessionLocal, Website, TrackedKeyword, KeywordSnapshot, AuditReport
)

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


async def _check_page_freshness(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    """Check freshness signals on a single page."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15),
                               ssl=False, allow_redirects=True) as resp:
            if resp.status != 200:
                return {"url": url, "error": f"Status {resp.status}"}

            html = await resp.text()
            headers = dict(resp.headers)
            soup = BeautifulSoup(html, 'html.parser')

            # Extract freshness signals
            signals = {}

            # 1. Last-Modified header
            last_modified = headers.get("Last-Modified", "")
            if last_modified:
                try:
                    from email.utils import parsedate_to_datetime
                    signals["last_modified"] = parsedate_to_datetime(last_modified).isoformat()
                except:
                    signals["last_modified_raw"] = last_modified

            # 2. Published date from meta tags
            pub_meta = soup.find('meta', attrs={'property': 'article:published_time'})
            if pub_meta and pub_meta.get('content'):
                signals["published_date"] = pub_meta['content'][:10]

            # 3. Modified date from meta tags
            mod_meta = soup.find('meta', attrs={'property': 'article:modified_time'})
            if mod_meta and mod_meta.get('content'):
                signals["modified_date"] = mod_meta['content'][:10]

            # 4. Visible dates on page
            time_tags = soup.find_all('time')
            visible_dates = []
            for t in time_tags:
                dt = t.get('datetime', '') or t.get_text(strip=True)
                if dt:
                    visible_dates.append(dt[:20])
            if visible_dates:
                signals["visible_dates"] = visible_dates[:3]

            # 5. Date patterns in content
            body = soup.find('body')
            content = ""
            if body:
                bc = BeautifulSoup(str(body), 'html.parser').find('body')
                for tag in bc.find_all(['script', 'style', 'nav', 'footer']):
                    tag.decompose()
                content = bc.get_text(separator=' ', strip=True)

            # Check for year references (freshness indicator)
            current_year = datetime.utcnow().year
            year_refs = re.findall(r'\b(20\d{2})\b', content)
            if year_refs:
                latest_year = max(int(y) for y in year_refs)
                signals["latest_year_mentioned"] = latest_year
                signals["mentions_current_year"] = current_year in [int(y) for y in year_refs]

            # 6. JSON-LD dateModified
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    ld = json.loads(script.string or '{}')
                    if ld.get('dateModified'):
                        signals["schema_date_modified"] = str(ld['dateModified'])[:10]
                    if ld.get('datePublished'):
                        signals["schema_date_published"] = str(ld['datePublished'])[:10]
                except:
                    pass

            # Title and word count
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""

            return {
                "url": url,
                "title": title_text[:100],
                "word_count": len(content.split()),
                "freshness_signals": signals,
                "content_preview": content[:300],
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


def _calculate_freshness_score(signals: Dict) -> int:
    """Score 0-100 how fresh a page appears."""
    score = 50  # Base score

    now = datetime.utcnow()
    current_year = now.year

    # Check modified date
    mod_date = signals.get("modified_date") or signals.get("schema_date_modified")
    if mod_date:
        try:
            mod = datetime.fromisoformat(mod_date.replace("Z", "+00:00").split("+")[0])
            days_ago = (now - mod).days
            if days_ago < 30:
                score += 30
            elif days_ago < 90:
                score += 20
            elif days_ago < 180:
                score += 10
            elif days_ago > 365:
                score -= 20
        except:
            pass

    # Check if mentions current year
    if signals.get("mentions_current_year"):
        score += 15
    elif signals.get("latest_year_mentioned"):
        diff = current_year - signals["latest_year_mentioned"]
        if diff == 1:
            score -= 5
        elif diff >= 2:
            score -= 15

    # Has visible dates
    if signals.get("visible_dates"):
        score += 5

    return max(0, min(100, score))


async def detect_content_decay(website_id: int) -> Dict[str, Any]:
    """
    Full content decay analysis:
    1. Check your own pages for staleness
    2. For tracked keywords, check competitor pages for freshness
    3. Flag pages that need updating
    4. Generate refresh recommendations
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = f"https://{domain}" if not domain.startswith("http") else domain

        print(f"[Decay] Starting content decay analysis for {domain}")

        # Get tracked keywords with ranking URLs
        tracked = db.query(TrackedKeyword).filter(
            TrackedKeyword.website_id == website_id,
            TrackedKeyword.current_position.isnot(None)
        ).all()

        # Get pages from latest audit
        latest_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id
        ).order_by(AuditReport.audit_date.desc()).first()

        own_pages = []
        if latest_audit and latest_audit.detailed_findings:
            for ps in latest_audit.detailed_findings.get("page_summaries", [])[:30]:
                if ps.get("url"):
                    own_pages.append(ps["url"])

        connector = aiohttp.TCPConnector(limit=5, ssl=False)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "SEOIntelligenceBot/2.0"}
        ) as session:

            # ─── Check own pages freshness ───
            own_freshness = []
            for url in own_pages[:20]:
                data = await _check_page_freshness(session, url)
                if not data.get("error"):
                    score = _calculate_freshness_score(data.get("freshness_signals", {}))
                    own_freshness.append({**data, "freshness_score": score})
                await asyncio.sleep(0.2)

            # Sort by freshness score (stalest first)
            own_freshness.sort(key=lambda x: x.get("freshness_score", 50))

            # ─── Check competitor pages for tracked keywords ───
            competitor_freshness = []
            for tk in tracked[:10]:
                if not tk.ranking_url:
                    continue

                # Check our own page
                our_data = await _check_page_freshness(session, tk.ranking_url)
                our_score = _calculate_freshness_score(our_data.get("freshness_signals", {})) if not our_data.get("error") else 0

                # Use AI to find top competitor URL for this keyword
                comp_urls = await _find_competitor_urls(tk.keyword)

                comp_results = []
                for comp_url in comp_urls[:3]:
                    comp_data = await _check_page_freshness(session, comp_url)
                    if not comp_data.get("error"):
                        comp_score = _calculate_freshness_score(comp_data.get("freshness_signals", {}))
                        comp_results.append({
                            "url": comp_url,
                            "title": comp_data.get("title", ""),
                            "freshness_score": comp_score,
                            "word_count": comp_data.get("word_count", 0),
                            "signals": comp_data.get("freshness_signals", {}),
                        })
                    await asyncio.sleep(0.3)

                # Flag if competitors are fresher
                max_comp_score = max([c["freshness_score"] for c in comp_results], default=0)
                freshness_gap = max_comp_score - our_score

                competitor_freshness.append({
                    "keyword": tk.keyword,
                    "position": tk.current_position,
                    "our_page": tk.ranking_url,
                    "our_freshness": our_score,
                    "competitors": comp_results,
                    "freshness_gap": freshness_gap,
                    "needs_update": freshness_gap > 20 or our_score < 40,
                })

            # Sort by freshness gap (biggest gap first)
            competitor_freshness.sort(key=lambda x: x.get("freshness_gap", 0), reverse=True)

            # ─── Stale pages (own content needing refresh) ───
            stale_pages = [p for p in own_freshness if p.get("freshness_score", 50) < 40]

            # ─── Generate recommendations ───
            recommendations = await _generate_decay_recommendations(
                stale_pages, competitor_freshness, domain
            )

        result = {
            "domain": domain,
            "pages_checked": len(own_freshness),
            "keywords_compared": len(competitor_freshness),
            "stale_pages": len(stale_pages),
            "own_pages": [
                {"url": p["url"], "title": p.get("title",""), "freshness_score": p["freshness_score"],
                 "word_count": p.get("word_count",0), "signals": p.get("freshness_signals",{})}
                for p in own_freshness[:20]
            ],
            "competitor_comparison": competitor_freshness,
            "recommendations": recommendations,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        print(f"[Decay] Analysis complete: {len(stale_pages)} stale pages, "
              f"{len([c for c in competitor_freshness if c['needs_update']])} keywords need refresh")

        return result

    except Exception as e:
        print(f"[Decay] Error: {e}")
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def _find_competitor_urls(keyword: str) -> List[str]:
    """Use AI to identify likely top-ranking competitor URLs for a keyword."""
    if not GEMINI_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text":
                        f'For the search query "{keyword}", list the 3 most likely top-ranking URLs. '
                        f'Return ONLY a JSON array of URL strings, nothing else. Example: ["https://example.com/page"]'
                    }]}],
                    "generationConfig": {"maxOutputTokens": 300, "temperature": 0.2}
                }
            )
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                urls = json.loads(text)
                return [u for u in urls if u.startswith("http")][:3]
    except:
        pass
    return []


async def _generate_decay_recommendations(
    stale_pages: List[Dict], competitor_data: List[Dict], domain: str
) -> List[Dict]:
    """Generate content refresh recommendations."""
    if not GEMINI_API_KEY:
        recs = []
        for p in stale_pages[:5]:
            recs.append({
                "priority": "high",
                "page": p.get("url", ""),
                "action": f"Refresh content on \"{p.get('title', 'this page')}\"",
                "reason": f"Freshness score: {p.get('freshness_score', 0)}/100 — content appears outdated",
            })
        for c in competitor_data[:5]:
            if c.get("needs_update"):
                recs.append({
                    "priority": "high" if c["freshness_gap"] > 30 else "medium",
                    "page": c.get("our_page", ""),
                    "action": f"Update content for keyword \"{c['keyword']}\"",
                    "reason": f"Competitors are {c['freshness_gap']} points fresher. Your position: #{c['position']}",
                })
        return recs

    prompt = f"""Analyze these content decay findings for {domain} and generate actionable recommendations.

STALE OWN PAGES (low freshness scores):
{json.dumps([{"url": p["url"], "title": p.get("title",""), "score": p["freshness_score"]} for p in stale_pages[:8]], indent=2) if stale_pages else "None found"}

COMPETITOR FRESHNESS COMPARISON:
{json.dumps([{"keyword": c["keyword"], "position": c["position"], "our_freshness": c["our_freshness"], "competitor_freshness": max([cc["freshness_score"] for cc in c["competitors"]], default=0), "gap": c["freshness_gap"]} for c in competitor_data[:8] if c.get("needs_update")], indent=2) if any(c.get("needs_update") for c in competitor_data) else "All content appears fresh"}

Generate 5-10 specific recommendations as a JSON array:
[{{"priority": "high|medium|low", "page": "url", "action": "what to do", "reason": "why", "estimated_impact": "description of expected ranking impact"}}]"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                recs = json.loads(text)
                if isinstance(recs, list):
                    return recs
    except Exception as e:
        print(f"[Decay] AI recommendation error: {e}")

    return []
