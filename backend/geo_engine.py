# backend/geo_engine.py - Generative Engine Optimization (GEO) Analysis
# Analyzes how well a website is optimized for AI search engines
# (ChatGPT, Perplexity, Google AI Overviews, Gemini)
import os
import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
import ipaddress
from dotenv import load_dotenv

from database import SessionLocal, Website

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


def _is_safe_url(url: str) -> bool:
    """Prevent SSRF by blocking internal/private URLs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        if hostname == "169.254.169.254":
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for _, _, _, _, sockaddr in resolved:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_private or ip.is_loopback or ip.is_reserved:
                        return False
            except socket.gaierror:
                pass
        return True
    except Exception:
        return False


async def _crawl_page_for_geo(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    """Crawl a page and extract GEO-relevant signals."""
    if not _is_safe_url(url):
        return {"url": url, "error": "unsafe_url"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
            if resp.status != 200:
                return {"url": url, "error": "Status " + str(resp.status)}

            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            # ─── Content Analysis ───
            body = soup.find('body')
            body_clone = BeautifulSoup(str(body), 'html.parser').find('body') if body else None
            if body_clone:
                for tag in body_clone.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                    tag.decompose()
                content_text = body_clone.get_text(separator=' ', strip=True)
            else:
                content_text = ""

            word_count = len(content_text.split())

            # ─── GEO Signals ───

            # 1. Structured Data (JSON-LD)
            json_ld = soup.find_all('script', type='application/ld+json')
            schema_types = []
            has_faq_schema = False
            has_howto_schema = False
            has_article_schema = False
            has_organization_schema = False
            has_author_schema = False

            for script in json_ld:
                try:
                    data = json.loads(script.string or '{}')
                    t = data.get('@type', '')
                    types = t if isinstance(t, list) else [t]
                    for st in types:
                        schema_types.append(st)
                        if st == 'FAQPage': has_faq_schema = True
                        if st == 'HowTo': has_howto_schema = True
                        if st in ['Article', 'BlogPosting', 'NewsArticle']: has_article_schema = True
                        if st == 'Organization': has_organization_schema = True
                        if st in ['Person', 'ProfilePage']: has_author_schema = True
                except Exception:
                    pass

            # 2. FAQ content (even without schema)
            faq_patterns = soup.find_all(['details', 'summary'])
            question_headings = [h for h in soup.find_all(['h2', 'h3', 'h4'])
                                if any(w in h.get_text(strip=True).lower() for w in ['?', 'what ', 'how ', 'why ', 'when ', 'where ', 'which ', 'can ', 'does ', 'is '])]
            has_faq_content = len(question_headings) > 0 or len(faq_patterns) > 0

            # 3. Statistics and data citations
            import re
            stat_patterns = re.findall(r'\d+%|\$[\d,.]+|\d+\s*(million|billion|thousand|percent)', content_text.lower())
            citation_patterns = re.findall(r'according to|source:|study|research shows|data from|report by', content_text.lower())
            has_statistics = len(stat_patterns) > 2
            has_citations = len(citation_patterns) > 0

            # 4. Author/Expertise signals (E-E-A-T)
            has_author_byline = bool(soup.find(class_=re.compile(r'author|byline|writer', re.I)) or
                                    soup.find('meta', attrs={'name': 'author'}) or
                                    soup.find(attrs={'rel': 'author'}))

            has_published_date = bool(soup.find('time') or
                                     soup.find('meta', attrs={'property': 'article:published_time'}) or
                                     soup.find(class_=re.compile(r'date|published|posted', re.I)))

            has_updated_date = bool(soup.find('meta', attrs={'property': 'article:modified_time'}) or
                                   soup.find(class_=re.compile(r'updated|modified', re.I)))

            # 5. Direct answer patterns (AI-friendly content)
            paragraphs = soup.find_all('p')
            short_answer_paragraphs = [p for p in paragraphs
                                      if 10 < len(p.get_text(strip=True).split()) < 40
                                      and any(w in p.get_text(strip=True).lower()[:50]
                                             for w in ['is a', 'is the', 'are ', 'refers to', 'means '])]
            has_direct_answers = len(short_answer_paragraphs) > 0

            # 6. Lists and tables (structured content AI loves)
            lists = soup.find_all(['ul', 'ol'])
            tables = soup.find_all('table')
            has_structured_content = len(lists) > 1 or len(tables) > 0

            # 7. Meta and title
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_text = (meta_desc.get('content', '') or '').strip() if meta_desc else ""

            # 8. About page / trust signals
            about_link = soup.find('a', href=re.compile(r'/about|/about-us', re.I))
            contact_link = soup.find('a', href=re.compile(r'/contact', re.I))
            privacy_link = soup.find('a', href=re.compile(r'/privacy', re.I))

            # 9. Headings structure
            headings = []
            for level in range(1, 4):
                for h in soup.find_all(f'h{level}'):
                    text = h.get_text(strip=True)
                    if text:
                        headings.append({"level": level, "text": text[:80]})

            return {
                "url": url,
                "title": title_text,
                "meta_description": meta_text,
                "word_count": word_count,
                "headings": headings[:20],
                "geo_signals": {
                    "schema_types": schema_types,
                    "has_faq_schema": has_faq_schema,
                    "has_howto_schema": has_howto_schema,
                    "has_article_schema": has_article_schema,
                    "has_organization_schema": has_organization_schema,
                    "has_author_schema": has_author_schema,
                    "has_faq_content": has_faq_content,
                    "question_headings_count": len(question_headings),
                    "has_statistics": has_statistics,
                    "statistics_count": len(stat_patterns),
                    "has_citations": has_citations,
                    "citation_count": len(citation_patterns),
                    "has_author_byline": has_author_byline,
                    "has_published_date": has_published_date,
                    "has_updated_date": has_updated_date,
                    "has_direct_answers": has_direct_answers,
                    "has_structured_content": has_structured_content,
                    "lists_count": len(lists),
                    "tables_count": len(tables),
                    "has_about_page": bool(about_link),
                    "has_contact_page": bool(contact_link),
                    "has_privacy_policy": bool(privacy_link),
                },
                "content_preview": content_text[:500],
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def run_geo_audit(website_id: int) -> Dict[str, Any]:
    """Run a full GEO audit on a website."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = "https://" + domain if not domain.startswith("http") else domain

        print(f"[GEO] Starting GEO audit for {domain}")

        connector = aiohttp.TCPConnector(limit=5)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "SEOIntelligenceBot/2.0"}
        ) as session:

            # Crawl key pages
            pages_to_check = [
                base_url,
                base_url + "/about",
                base_url + "/about-us",
                base_url + "/contact",
            ]

            # Also crawl a few content pages from the sitemap or internal links
            if not _is_safe_url(base_url):
                return {"error": "unsafe_url"}
            homepage_data = await _crawl_page_for_geo(session, base_url)
            page_results = [homepage_data]

            # Extract some internal links from homepage to sample content pages
            if not homepage_data.get("error"):
                try:
                    async with session.get(base_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            internal_links = []
                            for link in soup.find_all('a', href=True):
                                href = link['href']
                                if href.startswith('/') and not href.startswith('//'):
                                    full = base_url.rstrip('/') + href
                                    if any(seg in href.lower() for seg in ['/blog', '/post', '/article', '/guide', '/faq', '/how-to', '/product']):
                                        internal_links.append(full)
                            # Sample up to 5 content pages
                            for link_url in list(set(internal_links))[:5]:
                                result = await _crawl_page_for_geo(session, link_url)
                                page_results.append(result)
                                await asyncio.sleep(0.3)
                except Exception:
                    pass

            # Crawl about/contact pages
            for extra_url in pages_to_check[1:]:
                result = await _crawl_page_for_geo(session, extra_url)
                if not result.get("error"):
                    page_results.append(result)
                await asyncio.sleep(0.3)

        # ─── Calculate GEO scores ───
        valid_pages = [p for p in page_results if not p.get("error")]

        if not valid_pages:
            return {"error": "Could not crawl any pages"}

        scores = _calculate_geo_scores(valid_pages, domain)

        # ─── Generate AI recommendations ───
        recommendations = await _generate_geo_recommendations(valid_pages, domain, scores)

        print(f"[GEO] Audit complete for {domain}. Score: {scores['overall']}")

        return {
            "domain": domain,
            "pages_analyzed": len(valid_pages),
            "scores": scores,
            "page_details": [
                {
                    "url": p.get("url", ""),
                    "title": p.get("title", ""),
                    "word_count": p.get("word_count", 0),
                    "signals": p.get("geo_signals", {}),
                }
                for p in valid_pages
            ],
            "recommendations": recommendations,
            "audit_date": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"[GEO] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


def _calculate_geo_scores(pages: List[Dict], domain: str) -> Dict[str, Any]:
    """Calculate GEO readiness scores from crawled page data."""

    # Aggregate signals across all pages
    total_pages = len(pages)
    signals = {
        "faq_schema": sum(1 for p in pages if p.get("geo_signals", {}).get("has_faq_schema")),
        "howto_schema": sum(1 for p in pages if p.get("geo_signals", {}).get("has_howto_schema")),
        "article_schema": sum(1 for p in pages if p.get("geo_signals", {}).get("has_article_schema")),
        "org_schema": sum(1 for p in pages if p.get("geo_signals", {}).get("has_organization_schema")),
        "faq_content": sum(1 for p in pages if p.get("geo_signals", {}).get("has_faq_content")),
        "statistics": sum(1 for p in pages if p.get("geo_signals", {}).get("has_statistics")),
        "citations": sum(1 for p in pages if p.get("geo_signals", {}).get("has_citations")),
        "author_byline": sum(1 for p in pages if p.get("geo_signals", {}).get("has_author_byline")),
        "published_date": sum(1 for p in pages if p.get("geo_signals", {}).get("has_published_date")),
        "updated_date": sum(1 for p in pages if p.get("geo_signals", {}).get("has_updated_date")),
        "direct_answers": sum(1 for p in pages if p.get("geo_signals", {}).get("has_direct_answers")),
        "structured_content": sum(1 for p in pages if p.get("geo_signals", {}).get("has_structured_content")),
        "about_page": any(p.get("geo_signals", {}).get("has_about_page") for p in pages),
        "contact_page": any(p.get("geo_signals", {}).get("has_contact_page") for p in pages),
        "privacy_policy": any(p.get("geo_signals", {}).get("has_privacy_policy") for p in pages),
    }

    pct = lambda count: round(count / total_pages * 100) if total_pages > 0 else 0

    # Category scores (0-100)
    # 1. Content Structure (how AI-friendly is the content format)
    content_structure = min(100, (
        (pct(signals["faq_content"]) * 0.3) +
        (pct(signals["direct_answers"]) * 0.3) +
        (pct(signals["structured_content"]) * 0.2) +
        (min(pct(signals["statistics"]), 100) * 0.2)
    ))

    # 2. Schema & Structured Data (machine-readable signals)
    schema_score = min(100, (
        (30 if signals["faq_schema"] > 0 else 0) +
        (20 if signals["howto_schema"] > 0 else 0) +
        (20 if signals["article_schema"] > 0 else 0) +
        (15 if signals["org_schema"] > 0 else 0) +
        (15 if any(p.get("geo_signals", {}).get("has_author_schema") for p in pages) else 0)
    ))

    # 3. Authority & Trust (E-E-A-T signals)
    authority = min(100, (
        (pct(signals["author_byline"]) * 0.25) +
        (pct(signals["citations"]) * 0.25) +
        (25 if signals["about_page"] else 0) +
        (15 if signals["contact_page"] else 0) +
        (10 if signals["privacy_policy"] else 0)
    ))

    # 4. Freshness (recency signals)
    freshness = min(100, (
        (pct(signals["published_date"]) * 0.5) +
        (pct(signals["updated_date"]) * 0.5)
    ))

    # 5. Citability (how likely AI is to cite this content)
    avg_word_count = sum(p.get("word_count", 0) for p in pages) / total_pages if total_pages > 0 else 0
    depth_score = min(40, avg_word_count / 25)  # 1000 words = 40 points
    citability = min(100, (
        depth_score +
        (pct(signals["statistics"]) * 0.2) +
        (pct(signals["citations"]) * 0.2) +
        (pct(signals["direct_answers"]) * 0.2)
    ))

    # Overall
    overall = round(
        content_structure * 0.25 +
        schema_score * 0.20 +
        authority * 0.25 +
        freshness * 0.10 +
        citability * 0.20
    )

    return {
        "overall": overall,
        "content_structure": round(content_structure),
        "schema_data": round(schema_score),
        "authority_trust": round(authority),
        "freshness": round(freshness),
        "citability": round(citability),
        "signals": signals,
        "avg_word_count": round(avg_word_count),
    }


async def _generate_geo_recommendations(pages: List[Dict], domain: str, scores: Dict) -> List[Dict]:
    """Use AI to generate specific GEO improvement recommendations."""
    if not GEMINI_API_KEY:
        return _fallback_geo_recommendations(scores)

    signals = scores.get("signals", {})
    page_summaries = []
    for p in pages[:5]:
        geo = p.get("geo_signals", {})
        page_summaries.append(f"URL: {p.get('url', '')}\n  Words: {p.get('word_count', 0)}, FAQ schema: {geo.get('has_faq_schema')}, "
                             f"Stats: {geo.get('statistics_count', 0)}, Citations: {geo.get('citation_count', 0)}, "
                             f"Author: {geo.get('has_author_byline')}, Direct answers: {geo.get('has_direct_answers')}")

    prompt = f"""You are a GEO (Generative Engine Optimization) expert. Analyze this website's readiness for AI search engines (ChatGPT, Perplexity, Google AI Overviews).

Domain: {domain}
GEO Score: {scores['overall']}/100
Content Structure: {scores['content_structure']}/100
Schema Data: {scores['schema_data']}/100
Authority: {scores['authority_trust']}/100
Freshness: {scores['freshness']}/100
Citability: {scores['citability']}/100

Pages analyzed:
{chr(10).join(page_summaries)}

Generate 8-12 specific, actionable recommendations to improve this site's visibility in AI-generated answers.
Focus on: getting cited by ChatGPT/Perplexity, appearing in Google AI Overviews, and being the source AI models reference.

Return ONLY a JSON array:
[
  {{
    "priority": 1,
    "title": "short action title",
    "description": "detailed implementation instructions",
    "category": "content_structure|schema|authority|freshness|citability",
    "impact": "high|medium|low",
    "effort": "quick_win|medium|major"
  }}
]"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 3000, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                recs = json.loads(text)
                if isinstance(recs, list):
                    return recs
    except Exception as e:
        print(f"[GEO] AI recommendation error: {e}")

    return _fallback_geo_recommendations(scores)


def _fallback_geo_recommendations(scores: Dict) -> List[Dict]:
    """Basic recommendations when AI is unavailable."""
    recs = []
    s = scores.get("signals", {})

    if scores.get("schema_data", 0) < 50:
        recs.append({"priority": 1, "title": "Add FAQ Schema markup", "description": "Add FAQPage JSON-LD to your key content pages with common questions and answers about your topics.", "category": "schema", "impact": "high", "effort": "medium"})

    if scores.get("content_structure", 0) < 50:
        recs.append({"priority": 2, "title": "Add Q&A formatted content", "description": "Structure content with question-based headings (H2/H3) followed by concise 1-2 sentence answers before expanding.", "category": "content_structure", "impact": "high", "effort": "medium"})

    if scores.get("authority_trust", 0) < 50:
        recs.append({"priority": 3, "title": "Add author bylines and credentials", "description": "Add visible author names with credentials on content pages. Link to author bio pages.", "category": "authority", "impact": "high", "effort": "quick_win"})

    if scores.get("citability", 0) < 50:
        recs.append({"priority": 4, "title": "Include statistics and data", "description": "Add specific numbers, percentages, and data points to your content. Cite sources for statistics.", "category": "citability", "impact": "high", "effort": "medium"})

    return recs


async def test_ai_citation(domain: str, query: str) -> Dict[str, Any]:
    """Test if a domain gets cited by AI for a specific query."""
    if not GEMINI_API_KEY:
        return {"error": "No AI key configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Ask Gemini the query and see if it mentions the domain
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": f"Please answer this question thoroughly and cite your sources with URLs: {query}"}]}],
                    "generationConfig": {"maxOutputTokens": 1000, "temperature": 0.3},
                    "tools": [{"google_search": {}}]  # Enable grounding with search
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                is_cited = domain.lower() in text.lower()
                return {
                    "query": query,
                    "domain": domain,
                    "is_cited": is_cited,
                    "ai_response_preview": text[:500],
                    "tested_at": datetime.utcnow().isoformat(),
                }
            else:
                return {"error": "AI request failed: " + str(resp.status_code)}
    except Exception as e:
        return {"error": str(e)}
