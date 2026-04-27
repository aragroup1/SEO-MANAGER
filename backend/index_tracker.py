# backend/index_tracker.py - Page Index Status Tracker
import os
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import quote
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal, Website, Integration, IndexStatus, AuditReport

# ─── Rate limiting for fallback Google search ───
_search_last_call = 0.0
_SEARCH_MIN_INTERVAL = 3.0  # seconds between search fallback calls


def _get_db() -> Session:
    return SessionLocal()


# ─────────────────────────────────────────────
#  GSC URL Inspection API
# ─────────────────────────────────────────────
async def _gsc_inspect_url(
    token: str,
    gsc_property: str,
    url: str
) -> Optional[Dict[str, Any]]:
    """Call GSC URL Inspection API for a single URL."""
    try:
        import urllib.parse
        encoded_site = urllib.parse.quote(gsc_property, safe='')
        api_url = f"https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
        body = {
            "inspectionUrl": url,
            "siteUrl": gsc_property,
            "languageCode": "en-US"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            resp = await client.post(api_url, headers=headers, json=body)
            if resp.status_code == 200:
                data = resp.json()
                inspection = data.get("inspectionResult", {})
                index_status = inspection.get("indexStatusResult", {})
                verdict = index_status.get("verdict", "")
                # verdict can be: "PASS", "FAIL", "NEUTRAL"
                is_indexed = verdict == "PASS" or index_status.get("coverageState", "") == "Submitted and indexed"
                return {
                    "is_indexed": is_indexed,
                    "coverage_state": index_status.get("coverageState", "Unknown"),
                    "last_crawl": index_status.get("lastCrawlTime", ""),
                    "check_method": "gsc_url_inspection"
                }
            elif resp.status_code == 429:
                print(f"[IndexTracker] GSC API rate limited")
                return None
            else:
                print(f"[IndexTracker] GSC inspect error {resp.status_code}: {resp.text[:200]}")
                return None
    except Exception as e:
        print(f"[IndexTracker] GSC inspect exception: {e}")
        return None


# ─────────────────────────────────────────────
#  Fallback: site: search (rate limited)
# ─────────────────────────────────────────────
async def _search_google_site(url: str) -> Optional[Dict[str, Any]]:
    """Fallback: search Google with site:domain.com/url pattern."""
    global _search_last_call
    now = time.time()
    elapsed = now - _search_last_call
    if elapsed < _SEARCH_MIN_INTERVAL:
        await asyncio.sleep(_SEARCH_MIN_INTERVAL - elapsed)
    _search_last_call = time.time()

    try:
        query = f"site:{url}"
        search_url = f"https://www.google.com/search?q={quote(query)}&num=1"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = await client.get(search_url, headers=headers)
            if resp.status_code == 200:
                html = resp.text.lower()
                # If no results, Google shows "did not match any documents"
                no_results = (
                    "did not match any documents" in html
                    or "no results found" in html
                    or 'class="card-section"' in html and "try different keywords" in html
                )
                is_indexed = not no_results
                return {
                    "is_indexed": is_indexed,
                    "coverage_state": "Indexed" if is_indexed else "Not indexed",
                    "last_crawl": "",
                    "check_method": "google_search_fallback"
                }
            elif resp.status_code == 429:
                print(f"[IndexTracker] Google search rate limited")
                return None
            else:
                print(f"[IndexTracker] Google search error {resp.status_code}")
                return None
    except Exception as e:
        print(f"[IndexTracker] Search fallback exception: {e}")
        return None


# ─────────────────────────────────────────────
#  Check index status for a list of URLs
# ─────────────────────────────────────────────
async def check_index_status(
    website_id: int,
    urls: List[str]
) -> Dict[str, Any]:
    """
    Check if URLs are indexed in Google.
    Uses GSC URL Inspection API if available, otherwise falls back to site: search.
    Stores results in IndexStatus table.
    """
    db = _get_db()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        # Check for GSC integration
        integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "google_search_console",
            Integration.status == "active"
        ).first()

        token = None
        gsc_property = None
        if integration:
            token = integration.access_token
            config = integration.config or {}
            gsc_property = config.get("gsc_property", "")
            # Auto-detect property if missing
            if not gsc_property:
                from search_console import list_gsc_properties
                props_result = await list_gsc_properties(website_id)
                if "properties" in props_result:
                    domain = website.domain.replace("www.", "")
                    candidates = [
                        f"sc-domain:{domain}",
                        f"https://{domain}/",
                        f"http://{domain}/",
                        f"https://www.{domain}/",
                        f"http://www.{domain}/",
                    ]
                    available = [p["site_url"] for p in props_result["properties"]]
                    for candidate in candidates:
                        if candidate in available:
                            gsc_property = candidate
                            break
                    if not gsc_property:
                        for prop_url in available:
                            if domain in prop_url:
                                gsc_property = prop_url
                                break
                    if gsc_property:
                        config["gsc_property"] = gsc_property
                        integration.config = config
                        db.commit()

        use_gsc = token and gsc_property
        print(f"[IndexTracker] Checking {len(urls)} URLs for {website.domain} (GSC={'yes' if use_gsc else 'no'})")

        results = []
        for url in urls:
            url = url.strip()
            if not url:
                continue

            # Normalize URL
            if not url.startswith("http"):
                url = f"https://{website.domain.rstrip('/')}/{url.lstrip('/')}"

            result = None
            if use_gsc:
                result = await _gsc_inspect_url(token, gsc_property, url)

            if not result:
                result = await _search_google_site(url)

            if not result:
                result = {
                    "is_indexed": False,
                    "coverage_state": "Check failed",
                    "last_crawl": "",
                    "check_method": "unknown"
                }

            # Upsert into database
            existing = db.query(IndexStatus).filter(
                IndexStatus.website_id == website_id,
                IndexStatus.url == url
            ).first()

            if existing:
                existing.is_indexed = result["is_indexed"]
                existing.last_checked = datetime.utcnow()
                existing.check_method = result["check_method"]
                existing.coverage_state = result["coverage_state"]
            else:
                new_status = IndexStatus(
                    website_id=website_id,
                    url=url,
                    is_indexed=result["is_indexed"],
                    last_checked=datetime.utcnow(),
                    check_method=result["check_method"],
                    first_seen=datetime.utcnow(),
                    coverage_state=result["coverage_state"]
                )
                db.add(new_status)

            results.append({
                "url": url,
                "is_indexed": result["is_indexed"],
                "coverage_state": result["coverage_state"],
                "check_method": result["check_method"]
            })

            # Small delay to be respectful to APIs
            await asyncio.sleep(0.5)

        db.commit()
        print(f"[IndexTracker] Checked {len(results)} URLs for {website.domain}")
        return {
            "checked": len(results),
            "indexed": sum(1 for r in results if r["is_indexed"]),
            "not_indexed": sum(1 for r in results if not r["is_indexed"]),
            "method": "gsc" if use_gsc else "search_fallback",
            "results": results
        }

    except Exception as e:
        db.rollback()
        print(f"[IndexTracker] Error checking index status: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


# ─────────────────────────────────────────────
#  Sync all known URLs for a website
# ─────────────────────────────────────────────
async def sync_index_status(website_id: int) -> Dict[str, Any]:
    """
    Pull all known URLs from sitemap/audit/keyword snapshots and check index status.
    """
    db = _get_db()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        urls = set()

        # 1. From sitemap XML
        if website.sitemap_xml:
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(website.sitemap_xml)
                # Handle both sitemapindex and urlset
                for elem in root.iter():
                    if elem.tag.endswith("loc"):
                        urls.add(elem.text.strip())
            except Exception as e:
                print(f"[IndexTracker] Sitemap parse error: {e}")

        # 2. From latest audit findings (affected pages)
        latest_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id
        ).order_by(AuditReport.audit_date.desc()).first()

        if latest_audit and latest_audit.detailed_findings:
            findings = latest_audit.detailed_findings
            for issue in findings.get("issues", []):
                affected = issue.get("affected_pages", [])
                for page in affected:
                    if page and page != "/":
                        urls.add(page if page.startswith("http") else f"https://{website.domain.rstrip('/')}/{page.lstrip('/')}")

        # 3. From keyword snapshots (pages that get impressions)
        from database import KeywordSnapshot
        latest_snap = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest_snap and latest_snap.keyword_data:
            for kw in latest_snap.keyword_data:
                page = kw.get("page", "")
                if page:
                    urls.add(page if page.startswith("http") else f"https://{website.domain.rstrip('/')}/{page.lstrip('/')}")

        # 4. Add domain homepage if no URLs found
        if not urls:
            urls.add(f"https://{website.domain}")

        # Limit to reasonable batch size
        url_list = sorted(list(urls))[:200]
        print(f"[IndexTracker] Syncing {len(url_list)} URLs for {website.domain}")

        return await check_index_status(website_id, url_list)

    except Exception as e:
        print(f"[IndexTracker] Sync error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


# ─────────────────────────────────────────────
#  Get index trends over time
# ─────────────────────────────────────────────
def get_index_trends(website_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Show indexed vs not-indexed over time.
    Returns daily counts of indexed and not-indexed URLs based on last_checked.
    """
    db = _get_db()
    try:
        since = datetime.utcnow() - timedelta(days=days)

        # Group by date (truncated) and count indexed/not indexed
        # For SQLite we use strftime; for PostgreSQL we use date()
        from sqlalchemy import text
        from database import engine

        is_postgres = "postgresql" in str(engine.url)

        if is_postgres:
            date_trunc = "DATE(last_checked)"
        else:
            date_trunc = "DATE(last_checked)"

        # Query all records in range
        records = db.query(IndexStatus).filter(
            IndexStatus.website_id == website_id,
            IndexStatus.last_checked >= since
        ).all()

        # Build daily buckets
        daily: Dict[str, Dict[str, int]] = {}
        for r in records:
            date_key = r.last_checked.strftime("%Y-%m-%d") if r.last_checked else None
            if not date_key:
                continue
            if date_key not in daily:
                daily[date_key] = {"indexed": 0, "not_indexed": 0}
            if r.is_indexed:
                daily[date_key]["indexed"] += 1
            else:
                daily[date_key]["not_indexed"] += 1

        # Fill in missing days with zeros
        trends = []
        for i in range(days):
            day = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            entry = daily.get(day, {"indexed": 0, "not_indexed": 0})
            trends.append({
                "date": day,
                "indexed": entry["indexed"],
                "not_indexed": entry["not_indexed"],
                "total": entry["indexed"] + entry["not_indexed"]
            })

        return {"days": days, "trends": trends}

    except Exception as e:
        print(f"[IndexTracker] Trends error: {e}")
        return {"error": str(e), "days": days, "trends": []}
    finally:
        db.close()


# ─────────────────────────────────────────────
#  Get index summary
# ─────────────────────────────────────────────
def get_index_summary(website_id: int) -> Dict[str, Any]:
    """
    Get summary stats: total URLs, indexed count, not indexed count, index rate %.
    """
    db = _get_db()
    try:
        total = db.query(IndexStatus).filter(IndexStatus.website_id == website_id).count()
        indexed = db.query(IndexStatus).filter(
            IndexStatus.website_id == website_id,
            IndexStatus.is_indexed == True
        ).count()
        not_indexed = db.query(IndexStatus).filter(
            IndexStatus.website_id == website_id,
            IndexStatus.is_indexed == False
        ).count()

        index_rate = round((indexed / total) * 100, 1) if total > 0 else 0.0

        # Recent activity
        last_24h = db.query(IndexStatus).filter(
            IndexStatus.website_id == website_id,
            IndexStatus.last_checked >= datetime.utcnow() - timedelta(hours=24)
        ).count()

        # Method breakdown
        gsc_count = db.query(IndexStatus).filter(
            IndexStatus.website_id == website_id,
            IndexStatus.check_method == "gsc_url_inspection"
        ).count()

        return {
            "total_urls": total,
            "indexed": indexed,
            "not_indexed": not_indexed,
            "index_rate": index_rate,
            "checked_last_24h": last_24h,
            "gsc_inspected": gsc_count,
            "search_fallback": total - gsc_count,
        }

    except Exception as e:
        print(f"[IndexTracker] Summary error: {e}")
        return {"error": str(e)}
    finally:
        db.close()


# ─────────────────────────────────────────────
#  Get all index statuses with optional filter
# ─────────────────────────────────────────────
def get_index_statuses(
    website_id: int,
    indexed: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0
) -> Dict[str, Any]:
    """Get all index statuses for a website with optional filter."""
    db = _get_db()
    try:
        query = db.query(IndexStatus).filter(IndexStatus.website_id == website_id)

        if indexed is not None:
            query = query.filter(IndexStatus.is_indexed == indexed)

        total = query.count()
        records = query.order_by(IndexStatus.last_checked.desc()).limit(limit).offset(offset).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": r.id,
                    "url": r.url,
                    "is_indexed": r.is_indexed,
                    "coverage_state": r.coverage_state or ("Indexed" if r.is_indexed else "Not indexed"),
                    "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                    "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                    "check_method": r.check_method,
                }
                for r in records
            ]
        }

    except Exception as e:
        print(f"[IndexTracker] List error: {e}")
        return {"error": str(e), "total": 0, "items": []}
    finally:
        db.close()
