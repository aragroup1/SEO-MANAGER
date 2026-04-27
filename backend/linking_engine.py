# backend/linking_engine.py - Hub & Spoke Internal Linking Engine
# Scans website pages, identifies topic clusters, and suggests internal links
# to strengthen topical authority and improve ranking for target keywords.
import os
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from collections import defaultdict
import socket
import ipaddress
from dotenv import load_dotenv

from database import SessionLocal, Website, AuditReport, TrackedKeyword, KeywordSnapshot

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


async def _crawl_page_for_links(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    """Crawl a page and extract content + existing internal links."""
    if not _is_safe_url(url):
        return {"url": url, "error": "unsafe_url"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15),
                               allow_redirects=True) as resp:
            if resp.status != 200:
                return {"url": url, "error": f"Status {resp.status}"}

            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""

            # H1
            h1_tags = soup.find_all('h1')
            h1 = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]

            # All headings
            headings = []
            for level in range(1, 4):
                for h in soup.find_all(f'h{level}'):
                    t = h.get_text(strip=True)
                    if t:
                        headings.append({"level": level, "text": t[:100]})

            # Content text
            body = soup.find('body')
            content = ""
            if body:
                bc = BeautifulSoup(str(body), 'html.parser').find('body')
                for tag in bc.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                    tag.decompose()
                content = bc.get_text(separator=' ', strip=True)

            # Extract existing internal links
            parsed = urlparse(url)
            domain = parsed.netloc
            internal_links = []
            external_links = []
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    continue
                full = urljoin(url, href)
                link_parsed = urlparse(full)
                anchor = a.get_text(strip=True)[:80]
                if link_parsed.netloc == domain:
                    path = link_parsed.path.rstrip('/') or '/'
                    internal_links.append({"url": full, "path": path, "anchor": anchor})
                else:
                    external_links.append({"url": full, "anchor": anchor})

            return {
                "url": url,
                "path": parsed.path.rstrip('/') or '/',
                "title": title_text,
                "h1": h1,
                "headings": headings[:15],
                "word_count": len(content.split()),
                "content_preview": content[:600],
                "internal_links": internal_links,
                "internal_link_count": len(internal_links),
                "external_link_count": len(external_links),
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def analyze_internal_linking(website_id: int) -> Dict[str, Any]:
    """
    Full Hub & Spoke analysis:
    1. Crawl key pages
    2. Map existing internal link structure
    3. Identify hub pages (most linked) and orphans (least linked)
    4. Cross-reference with tracked keywords to find link opportunities
    5. Use AI to generate specific link suggestions
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = f"https://{domain}" if not domain.startswith("http") else domain

        print(f"[Linking] Starting internal link analysis for {domain}")

        # Get tracked keywords for context
        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
        tracked_map = {tk.keyword.lower(): {"url": tk.target_url or tk.ranking_url, "position": tk.current_position} for tk in tracked}

        # Get latest keyword data
        latest_snap = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        striking_keywords = []
        if latest_snap and latest_snap.keyword_data:
            for kw in latest_snap.keyword_data:
                pos = kw.get("position", 100)
                if 4 <= pos <= 20:  # Striking distance
                    striking_keywords.append({
                        "query": kw.get("query", ""),
                        "position": pos,
                        "page": kw.get("page", ""),
                        "clicks": kw.get("clicks", 0),
                    })

        # Get pages from latest audit
        latest_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id
        ).order_by(AuditReport.audit_date.desc()).first()

        pages_to_scan = [base_url]
        if latest_audit and latest_audit.detailed_findings:
            summaries = latest_audit.detailed_findings.get("page_summaries", [])
            for ps in summaries[:50]:
                url = ps.get("url", "")
                if url and url not in pages_to_scan:
                    pages_to_scan.append(url)

        # Crawl pages
        connector = aiohttp.TCPConnector(limit=5)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "SEOIntelligenceBot/2.0"}
        ) as session:
            page_data = []
            for url in pages_to_scan[:40]:  # Cap at 40 pages
                if not _is_safe_url(url):
                    continue
                data = await _crawl_page_for_links(session, url)
                if not data.get("error"):
                    page_data.append(data)
                await asyncio.sleep(0.3)

        if not page_data:
            return {"error": "Could not crawl any pages"}

        print(f"[Linking] Crawled {len(page_data)} pages, analyzing structure...")

        # ─── Build link graph ───
        # Count inbound links per page
        inbound_count = defaultdict(int)
        inbound_from = defaultdict(list)
        outbound_count = {}

        for page in page_data:
            page_path = page["path"]
            outbound_count[page_path] = page["internal_link_count"]
            for link in page.get("internal_links", []):
                target_path = link["path"]
                inbound_count[target_path] += 1
                inbound_from[target_path].append({"from": page_path, "anchor": link["anchor"]})

        # Identify hub pages (most inbound links)
        hub_pages = sorted(
            [(path, count) for path, count in inbound_count.items()],
            key=lambda x: x[1], reverse=True
        )[:10]

        # Identify orphan pages (0-1 inbound links)
        all_paths = {p["path"] for p in page_data}
        orphan_pages = [
            {"path": p["path"], "title": p["title"], "inbound": inbound_count.get(p["path"], 0)}
            for p in page_data
            if inbound_count.get(p["path"], 0) <= 1 and p["path"] != "/"
        ]

        # Identify pages with no outbound internal links
        isolated_pages = [
            {"path": p["path"], "title": p["title"], "outbound": p["internal_link_count"]}
            for p in page_data
            if p["internal_link_count"] <= 2 and p["path"] != "/"
        ]

        # ─── Generate AI link suggestions ───
        suggestions = await _generate_link_suggestions(
            page_data, striking_keywords, tracked_map,
            orphan_pages, hub_pages, domain
        )

        result = {
            "domain": domain,
            "pages_analyzed": len(page_data),
            "total_internal_links": sum(p["internal_link_count"] for p in page_data),
            "avg_internal_links": round(sum(p["internal_link_count"] for p in page_data) / len(page_data), 1),
            "hub_pages": [{"path": path, "inbound_links": count} for path, count in hub_pages],
            "orphan_pages": orphan_pages[:15],
            "isolated_pages": isolated_pages[:15],
            "striking_distance_keywords": len(striking_keywords),
            "link_suggestions": suggestions,
            "link_graph_summary": {
                "pages_with_0_inbound": len([p for p in page_data if inbound_count.get(p["path"], 0) == 0 and p["path"] != "/"]),
                "pages_with_1_inbound": len([p for p in page_data if inbound_count.get(p["path"], 0) == 1]),
                "pages_with_5plus_inbound": len([p for p in page_data if inbound_count.get(p["path"], 0) >= 5]),
                "max_inbound": hub_pages[0][1] if hub_pages else 0,
            },
            "analyzed_at": datetime.utcnow().isoformat(),
        }

        print(f"[Linking] Analysis complete: {len(suggestions)} link suggestions, "
              f"{len(orphan_pages)} orphans, {len(hub_pages)} hubs")

        return result

    except Exception as e:
        print(f"[Linking] Error: {e}")
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def _generate_link_suggestions(
    pages: List[Dict], striking_keywords: List[Dict],
    tracked_map: Dict, orphan_pages: List[Dict],
    hub_pages: List, domain: str
) -> List[Dict]:
    """Use AI to generate specific internal linking suggestions."""
    if not GEMINI_API_KEY:
        return _fallback_suggestions(pages, striking_keywords, orphan_pages)

    # Build context
    page_summaries = []
    for p in pages[:30]:
        page_summaries.append(
            f"- {p['path']}: \"{p['title']}\" ({p['word_count']} words, "
            f"{p['internal_link_count']} internal links out, "
            f"headings: {', '.join([h['text'][:40] for h in p.get('headings', [])[:3]])})"
        )

    striking_text = ""
    if striking_keywords:
        striking_text = "\n\nSTRIKING DISTANCE KEYWORDS (position 4-20, need link juice):\n"
        for sk in striking_keywords[:15]:
            striking_text += f"- \"{sk['query']}\" at position {sk['position']}, ranking on: {sk.get('page', 'unknown')}\n"

    orphan_text = ""
    if orphan_pages:
        orphan_text = "\n\nORPHAN PAGES (0-1 inbound links, need more links pointing to them):\n"
        for op in orphan_pages[:10]:
            orphan_text += f"- {op['path']}: \"{op['title']}\" ({op['inbound']} inbound links)\n"

    prompt = f"""You are an internal linking expert. Analyze this website's page structure and suggest specific internal links to add.

WEBSITE: {domain}

PAGES:
{chr(10).join(page_summaries)}
{striking_text}
{orphan_text}

HUB PAGES (most linked to): {', '.join([f"{h[0]} ({h[1]} inbound)" for h in hub_pages[:5]])}

Generate 10-15 specific internal link suggestions. For each suggestion:
1. Which page should the link be ON (source page)
2. Which page should it link TO (target page)
3. What anchor text to use
4. Why this link helps SEO (brief reason)

Focus on:
- Linking from high-authority hub pages to striking distance keyword pages
- Connecting orphan pages to the main site structure
- Creating topical clusters (group related content pages together)
- Using keyword-rich anchor text for target keywords

Return ONLY a JSON array:
[
  {{
    "source_page": "/page-url",
    "target_page": "/other-page-url",
    "anchor_text": "suggested anchor text",
    "reason": "brief SEO reason",
    "priority": "high|medium|low",
    "category": "hub_spoke|orphan_rescue|keyword_boost|topic_cluster"
  }}
]"""

    try:
        async with httpx.AsyncClient(timeout=45) as client:
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
                suggestions = json.loads(text)
                if isinstance(suggestions, list):
                    return suggestions
    except Exception as e:
        print(f"[Linking] AI suggestion error: {e}")

    return _fallback_suggestions(pages, striking_keywords, orphan_pages)


def _fallback_suggestions(pages, striking_keywords, orphan_pages):
    """Basic suggestions when AI is unavailable."""
    suggestions = []

    # Link hub pages to orphans
    for orphan in orphan_pages[:5]:
        suggestions.append({
            "source_page": "/",
            "target_page": orphan["path"],
            "anchor_text": orphan.get("title", orphan["path"]),
            "reason": "This page has very few inbound links and needs more link juice",
            "priority": "high",
            "category": "orphan_rescue",
        })

    # Link to striking distance pages
    for sk in striking_keywords[:5]:
        page = sk.get("page", "")
        if page:
            path = urlparse(page).path
            suggestions.append({
                "source_page": "/",
                "target_page": path,
                "anchor_text": sk["query"],
                "reason": f"Currently at position {sk['position']} — more internal links can push to page 1",
                "priority": "high",
                "category": "keyword_boost",
            })

    return suggestions


def get_link_graph(website_id: int) -> Dict[str, Any]:
    """
    Return the internal link graph as nodes and edges for visualization.
    Uses the same crawling logic as analyze_internal_linking but returns
    a graph-friendly structure.
    """
    import asyncio
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = f"https://{domain}" if not domain.startswith("http") else domain

        # Get pages from latest audit
        latest_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id
        ).order_by(AuditReport.audit_date.desc()).first()

        pages_to_scan = [base_url]
        if latest_audit and latest_audit.detailed_findings:
            summaries = latest_audit.detailed_findings.get("page_summaries", [])
            for ps in summaries[:50]:
                url = ps.get("url", "")
                if url and url not in pages_to_scan:
                    pages_to_scan.append(url)

        # Crawl pages
        async def _crawl():
            connector = aiohttp.TCPConnector(limit=5)
            async with aiohttp.ClientSession(
                connector=connector,
                headers={"User-Agent": "SEOIntelligenceBot/2.0"}
            ) as session:
                page_data = []
                for url in pages_to_scan[:40]:
                    if not _is_safe_url(url):
                        continue
                    data = await _crawl_page_for_links(session, url)
                    if not data.get("error"):
                        page_data.append(data)
                    await asyncio.sleep(0.3)
                return page_data

        page_data = asyncio.run(_crawl())

        if not page_data:
            return {"error": "Could not crawl any pages"}

        # Build link graph
        inbound_count = defaultdict(int)
        inbound_from = defaultdict(list)
        outbound_count = {}
        edges = []
        path_to_url = {}
        path_to_title = {}

        for page in page_data:
            page_path = page["path"]
            path_to_url[page_path] = page["url"]
            path_to_title[page_path] = page["title"] or page_path
            outbound_count[page_path] = page["internal_link_count"]
            for link in page.get("internal_links", []):
                target_path = link["path"]
                inbound_count[target_path] += 1
                inbound_from[target_path].append({"from": page_path, "anchor": link["anchor"]})
                edges.append({
                    "source": page_path,
                    "target": target_path,
                    "anchor": link["anchor"],
                })

        # Identify hubs and orphans
        hub_threshold = 5
        all_paths = {p["path"] for p in page_data}
        hub_paths = {path for path, count in inbound_count.items() if count >= hub_threshold}
        orphan_paths = {path for path in all_paths if inbound_count.get(path, 0) <= 1 and path != "/"}

        nodes = []
        for page in page_data:
            path = page["path"]
            inc = inbound_count.get(path, 0)
            out = outbound_count.get(path, 0)
            is_hub = path in hub_paths
            is_orphan = path in orphan_paths
            nodes.append({
                "id": path,
                "url": page["url"],
                "title": page["title"] or path,
                "inbound": inc,
                "outbound": out,
                "is_hub": is_hub,
                "is_orphan": is_orphan,
            })

        # Deduplicate edges for cleaner visualization
        seen_edges = set()
        unique_edges = []
        for e in edges:
            key = (e["source"], e["target"])
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        return {
            "domain": domain,
            "nodes": nodes,
            "edges": unique_edges,
            "total_pages": len(nodes),
            "total_edges": len(unique_edges),
        }

    except Exception as e:
        print(f"[LinkGraph] Error: {e}")
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()
