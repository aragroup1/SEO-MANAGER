# backend/link_checker.py — Broken Link Checker for SEO Intelligence Platform
# Crawls a website, finds all outbound links, checks them with HEAD requests,
# categorizes errors, and stores results.

import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from urllib.parse import urlparse, urljoin, urlunparse
from collections import defaultdict

import httpx
from bs4 import BeautifulSoup

from database import SessionLocal, Website, BrokenLink


# ─── Configuration ───
CRAWL_DELAY = 0.5          # seconds between requests
REQUEST_TIMEOUT = 15       # seconds per request
MAX_REDIRECTS = 5          # flag as redirect chain if exceeded
USER_AGENT = "SEOIntelligenceBot/2.0 (+https://seointelligence.app/bot)"

# Links to skip
SKIP_SCHEMES = {"mailto:", "tel:", "javascript:", "data:", "ftp:", "file:"}
SKIP_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".pdf", ".zip", ".mp4", ".mp3", ".woff",
    ".woff2", ".ttf", ".eot", ".map", ".xml", ".json",
}

# Error type categorization
ERROR_TYPES = {
    "404": "not_found",
    "410": "not_found",
    "500": "server_error",
    "502": "server_error",
    "503": "server_error",
    "504": "server_error",
    "timeout": "timeout",
    "ssl_error": "ssl_error",
    "redirect_chain": "redirect_chain",
    "dns_error": "dns_error",
    "connection_error": "connection_error",
    "unknown": "unknown",
}


def _normalize_url(url: str) -> Optional[str]:
    """Normalize URL for deduplication."""
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme:
            parsed = parsed._replace(scheme="https")
        # Remove fragment, keep query for external links
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path,
            "",
            parsed.query,
            "",  # no fragment
        ))
        return normalized
    except Exception:
        return None


def _should_skip_link(href: str) -> bool:
    """Check if a link should be skipped."""
    href = href.strip()
    if not href or href == "#" or href.startswith("#"):
        return True
    lower = href.lower()
    for scheme in SKIP_SCHEMES:
        if lower.startswith(scheme):
            return True
    # Skip common non-HTML file extensions
    for ext in SKIP_EXTENSIONS:
        if lower.endswith(ext):
            return True
    return False


def _is_internal_link(url: str, domain: str) -> bool:
    """Check if URL belongs to the same domain."""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    return not netloc or netloc == domain.lower() or netloc.endswith("." + domain.lower())


def _categorize_error(status_code: int, error_msg: str = "") -> Tuple[str, str]:
    """Categorize an error into a type and human-readable label."""
    if status_code == 404 or status_code == 410:
        return ERROR_TYPES.get("404", "not_found"), "Not Found (404)"
    if 500 <= status_code < 600:
        return ERROR_TYPES.get("500", "server_error"), f"Server Error ({status_code})"
    if status_code == 0:
        msg = error_msg.lower()
        if "ssl" in msg or "certificate" in msg:
            return ERROR_TYPES["ssl_error"], "SSL Certificate Error"
        if "timeout" in msg or "timed out" in msg:
            return ERROR_TYPES["timeout"], "Request Timeout"
        if "dns" in msg or "name resolution" in msg or "getaddrinfo" in msg:
            return ERROR_TYPES["dns_error"], "DNS Error"
        if "connection" in msg or "refused" in msg:
            return ERROR_TYPES["connection_error"], "Connection Error"
        return ERROR_TYPES["unknown"], f"Unknown Error: {error_msg}"
    if 300 <= status_code < 400:
        return ERROR_TYPES["redirect_chain"], f"Redirect ({status_code})"
    return "other", f"HTTP {status_code}"


async def _check_link(
    client: httpx.AsyncClient,
    link_url: str,
    max_redirects: int = MAX_REDIRECTS,
) -> Dict[str, Any]:
    """
    Check a single link with a HEAD request (fallback to GET).
    Returns dict with status_code, error_type, error_label, is_broken, redirect_count.
    """
    result = {
        "status_code": 0,
        "error_type": "",
        "error_label": "",
        "is_broken": False,
        "redirect_count": 0,
        "response_time_ms": 0,
    }

    start = time.time()
    try:
        # Try HEAD first
        resp = await client.head(
            link_url,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = (time.time() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)

        # Count redirects manually if possible
        if hasattr(resp, "history"):
            result["redirect_count"] = len(resp.history)

        # Some servers don't support HEAD; fallback to GET on 405 or similar
        if resp.status_code in (405, 501, 503) or resp.status_code == 0:
            start = time.time()
            resp = await client.get(
                link_url,
                follow_redirects=True,
                timeout=REQUEST_TIMEOUT,
                headers={"Range": "bytes=0-0"},  # minimal body
            )
            elapsed = (time.time() - start) * 1000
            result["response_time_ms"] = round(elapsed, 1)
            if hasattr(resp, "history"):
                result["redirect_count"] = len(resp.history)

        result["status_code"] = resp.status_code

        # Determine if broken
        if resp.status_code >= 400:
            result["is_broken"] = True
        elif result["redirect_count"] > max_redirects:
            result["is_broken"] = True
            result["error_type"] = "redirect_chain"
            result["error_label"] = f"Redirect Chain ({result['redirect_count']} hops)"
            return result

        if result["is_broken"]:
            err_type, err_label = _categorize_error(resp.status_code)
            result["error_type"] = err_type
            result["error_label"] = err_label

    except httpx.TimeoutException:
        elapsed = (time.time() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)
        result["is_broken"] = True
        result["error_type"] = "timeout"
        result["error_label"] = "Request Timeout"
    except httpx.ConnectError as e:
        elapsed = (time.time() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)
        result["is_broken"] = True
        err_str = str(e).lower()
        if "ssl" in err_str or "certificate" in err_str:
            result["error_type"] = "ssl_error"
            result["error_label"] = "SSL Certificate Error"
        elif "dns" in err_str or "name resolution" in err_str or "getaddrinfo" in err_str:
            result["error_type"] = "dns_error"
            result["error_label"] = "DNS Error"
        else:
            result["error_type"] = "connection_error"
            result["error_label"] = "Connection Error"
    except httpx.HTTPStatusError as e:
        elapsed = (time.time() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)
        result["status_code"] = e.response.status_code
        result["is_broken"] = True
        err_type, err_label = _categorize_error(e.response.status_code)
        result["error_type"] = err_type
        result["error_label"] = err_label
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        result["response_time_ms"] = round(elapsed, 1)
        result["is_broken"] = True
        err_str = str(e).lower()
        if "ssl" in err_str or "certificate" in err_str:
            result["error_type"] = "ssl_error"
            result["error_label"] = "SSL Certificate Error"
        elif "timeout" in err_str:
            result["error_type"] = "timeout"
            result["error_label"] = "Request Timeout"
        else:
            result["error_type"] = "unknown"
            result["error_label"] = f"Unknown: {str(e)[:80]}"

    return result


async def _fetch_page_html(
    client: httpx.AsyncClient,
    url: str,
) -> Optional[str]:
    """Fetch HTML of a page."""
    try:
        resp = await client.get(
            url,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def _extract_links_from_html(html: str, page_url: str) -> List[Tuple[str, str]]:
    """
    Extract all anchor links from HTML.
    Returns list of (absolute_url, anchor_text) tuples.
    """
    links: List[Tuple[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if _should_skip_link(href):
                continue
            absolute = urljoin(page_url, href)
            anchor_text = a.get_text(strip=True)[:200]
            links.append((absolute, anchor_text))
    except Exception:
        pass
    return links


# ─── Public API ───

async def scan_broken_links(website_id: int, max_pages: int = 500) -> Dict[str, Any]:
    """
    Crawl a website and check all outbound links for broken ones.
    Stores results in the BrokenLink table.
    """
    print(f"[LinkChecker] Starting broken link scan for website {website_id}, max_pages={max_pages}")

    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        if not domain.startswith(("http://", "https://")):
            base_url = "https://" + domain
        else:
            base_url = domain
            domain = urlparse(base_url).netloc

        # Clear old broken links for this website (only non-fixed ones get overwritten)
        db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
            BrokenLink.is_fixed == False,
        ).delete(synchronize_session=False)
        db.commit()

        # Crawl state
        crawled_urls: Set[str] = set()
        urls_to_crawl: List[str] = [base_url]
        all_checked_links: Dict[str, Dict[str, Any]] = {}  # link_url -> check result
        broken_links_found: List[Dict[str, Any]] = []
        page_count = 0
        total_links_checked = 0

        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        async with httpx.AsyncClient(
            limits=limits,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:

            while urls_to_crawl and page_count < max_pages:
                page_url = urls_to_crawl.pop(0)
                norm_page = _normalize_url(page_url)
                if not norm_page or norm_page in crawled_urls:
                    continue
                if not _is_internal_link(norm_page, domain):
                    continue

                crawled_urls.add(norm_page)
                page_count += 1

                # Fetch page
                html = await _fetch_page_html(client, norm_page)
                if html is None:
                    print(f"[LinkChecker] Could not fetch {norm_page}")
                    await asyncio.sleep(CRAWL_DELAY)
                    continue

                # Extract links
                page_links = _extract_links_from_html(html, norm_page)

                # Filter to external (outbound) links only
                outbound = [
                    (url, text) for url, text in page_links
                    if not _is_internal_link(url, domain)
                ]

                # Deduplicate outbound links for this page
                seen_on_page: Set[str] = set()
                unique_outbound: List[Tuple[str, str]] = []
                for url, text in outbound:
                    norm = _normalize_url(url)
                    if norm and norm not in seen_on_page:
                        seen_on_page.add(norm)
                        unique_outbound.append((norm, text))

                # Check each outbound link
                for link_url, anchor_text in unique_outbound:
                    # Skip if already checked globally
                    if link_url in all_checked_links:
                        result = all_checked_links[link_url]
                        total_links_checked += 1
                        if result["is_broken"]:
                            broken_links_found.append({
                                "page_url": norm_page,
                                "link_url": link_url,
                                "anchor_text": anchor_text,
                                "status_code": result["status_code"],
                                "error_type": result["error_type"],
                                "error_label": result["error_label"],
                            })
                        continue

                    result = await _check_link(client, link_url)
                    all_checked_links[link_url] = result
                    total_links_checked += 1

                    if result["is_broken"]:
                        broken_links_found.append({
                            "page_url": norm_page,
                            "link_url": link_url,
                            "anchor_text": anchor_text,
                            "status_code": result["status_code"],
                            "error_type": result["error_type"],
                            "error_label": result["error_label"],
                        })

                    await asyncio.sleep(CRAWL_DELAY)

                # Add internal links to crawl queue
                for url, _ in page_links:
                    if _is_internal_link(url, domain):
                        norm = _normalize_url(url)
                        if norm and norm not in crawled_urls and norm not in urls_to_crawl:
                            urls_to_crawl.append(norm)

                if page_count % 25 == 0:
                    print(f"[LinkChecker] Crawled {page_count} pages, {len(broken_links_found)} broken links found so far")

                await asyncio.sleep(CRAWL_DELAY)

        # Store broken links in DB
        checked_at = datetime.utcnow()
        for bl in broken_links_found:
            record = BrokenLink(
                website_id=website_id,
                page_url=bl["page_url"][:1000],
                link_url=bl["link_url"][:1000],
                anchor_text=bl["anchor_text"][:500],
                status_code=bl["status_code"],
                error_type=bl["error_type"],
                checked_at=checked_at,
                is_fixed=False,
            )
            db.add(record)

        db.commit()

        # Build summary
        error_counts: Dict[str, int] = defaultdict(int)
        for bl in broken_links_found:
            error_counts[bl["error_type"]] += 1

        summary = {
            "pages_crawled": page_count,
            "total_links_checked": total_links_checked,
            "broken_count": len(broken_links_found),
            "error_breakdown": dict(error_counts),
            "checked_at": checked_at.isoformat(),
        }

        print(f"[LinkChecker] Scan complete for {domain}. Pages: {page_count}, Links checked: {total_links_checked}, Broken: {len(broken_links_found)}")
        return {"success": True, "summary": summary}

    except Exception as e:
        db.rollback()
        print(f"[LinkChecker] Error scanning website {website_id}: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


def get_broken_links(website_id: int, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve stored broken links for a website, optionally filtered by error_type."""
    db = SessionLocal()
    try:
        query = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
            BrokenLink.is_fixed == False,
        )
        if status_filter:
            query = query.filter(BrokenLink.error_type == status_filter)

        results = query.order_by(BrokenLink.checked_at.desc()).all()
        return [
            {
                "id": r.id,
                "website_id": r.website_id,
                "page_url": r.page_url,
                "link_url": r.link_url,
                "anchor_text": r.anchor_text,
                "status_code": r.status_code,
                "error_type": r.error_type,
                "checked_at": r.checked_at.isoformat() if r.checked_at else None,
                "is_fixed": r.is_fixed,
            }
            for r in results
        ]
    finally:
        db.close()


def get_link_health_summary(website_id: int) -> Dict[str, Any]:
    """Get aggregate stats for link health of a website."""
    db = SessionLocal()
    try:
        total = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
        ).count()

        broken = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
            BrokenLink.is_fixed == False,
        ).count()

        fixed = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
            BrokenLink.is_fixed == True,
        ).count()

        # Breakdown by error type
        rows = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
            BrokenLink.is_fixed == False,
        ).all()

        error_breakdown: Dict[str, int] = defaultdict(int)
        for r in rows:
            error_breakdown[r.error_type] += 1

        # Recent scan time
        latest = db.query(BrokenLink).filter(
            BrokenLink.website_id == website_id,
        ).order_by(BrokenLink.checked_at.desc()).first()

        return {
            "website_id": website_id,
            "total_links_recorded": total,
            "broken_count": broken,
            "fixed_count": fixed,
            "error_breakdown": dict(error_breakdown),
            "last_checked": latest.checked_at.isoformat() if latest and latest.checked_at else None,
        }
    finally:
        db.close()


def mark_link_fixed(link_id: int) -> Dict[str, Any]:
    """Mark a broken link as fixed."""
    db = SessionLocal()
    try:
        link = db.query(BrokenLink).filter(BrokenLink.id == link_id).first()
        if not link:
            return {"error": "Link not found"}
        link.is_fixed = True
        db.commit()
        return {"success": True, "id": link_id, "is_fixed": True}
    finally:
        db.close()
