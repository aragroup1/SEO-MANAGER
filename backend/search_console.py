# backend/search_console.py - Google Search Console data fetching
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, Website, Integration, KeywordSnapshot

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")


async def _refresh_google_token(integration: Integration, db: Session) -> Optional[str]:
    """Refresh an expired Google OAuth token. Returns new access token or None."""
    if not integration.refresh_token:
        print("[GSC] No refresh token available")
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "refresh_token": integration.refresh_token,
                    "grant_type": "refresh_token",
                }
            )
            if resp.status_code == 200:
                tokens = resp.json()
                new_token = tokens.get("access_token")
                if new_token:
                    integration.access_token = new_token
                    integration.token_expiry = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
                    db.commit()
                    print("[GSC] Token refreshed successfully")
                    return new_token
            else:
                print("[GSC] Token refresh failed: " + str(resp.status_code) + " " + resp.text[:200])
    except Exception as e:
        print("[GSC] Token refresh error: " + str(e))

    return None


async def _get_valid_token(integration: Integration, db: Session) -> Optional[str]:
    """Get a valid access token, refreshing if needed."""
    token = integration.access_token
    if not token:
        return None

    # Try the existing token first — if it fails, refresh
    return token


async def _gsc_api_request(token: str, url: str, method: str = "GET",
                           json_data: Dict = None) -> Optional[Any]:
    """Make an authenticated request to Google Search Console API."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {"Authorization": "Bearer " + token}
            if method == "POST":
                resp = await client.post(url, headers=headers, json=json_data)
            else:
                resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                return {"error": "unauthorized", "status": 401}
            elif resp.status_code == 403:
                return {"error": "forbidden", "status": 403,
                        "detail": resp.text[:300]}
            else:
                print("[GSC] API error: " + str(resp.status_code) + " " + resp.text[:200])
                return {"error": resp.text[:200], "status": resp.status_code}
    except Exception as e:
        print("[GSC] API request error: " + str(e))
        return None


async def list_gsc_properties(website_id: int) -> Dict[str, Any]:
    """List all Search Console properties available to the connected Google account."""
    db = SessionLocal()
    try:
        integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "google_search_console",
            Integration.status == "active"
        ).first()

        if not integration:
            return {"error": "Google Search Console not connected. Connect it via the integration checklist."}

        token = await _get_valid_token(integration, db)
        if not token:
            return {"error": "No valid access token. Please reconnect Google Search Console."}

        # List sites
        result = await _gsc_api_request(token, "https://www.googleapis.com/webmasters/v3/sites")

        if result and "error" in result:
            if result.get("status") == 401:
                # Try refresh
                new_token = await _refresh_google_token(integration, db)
                if new_token:
                    result = await _gsc_api_request(new_token, "https://www.googleapis.com/webmasters/v3/sites")
                else:
                    return {"error": "Token expired and refresh failed. Please reconnect Google Search Console."}

        if not result or "error" in result:
            return {"error": "Could not list properties: " + str(result)}

        properties = []
        for entry in result.get("siteEntry", []):
            properties.append({
                "site_url": entry.get("siteUrl", ""),
                "permission_level": entry.get("permissionLevel", ""),
            })

        return {"properties": properties}

    except Exception as e:
        print("[GSC] Error listing properties: " + str(e))
        return {"error": str(e)}
    finally:
        db.close()


async def fetch_keyword_data(
    website_id: int,
    days: int = 28,
    gsc_property: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch keyword data from Google Search Console for the last N days.
    Stores a snapshot in the database.
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "google_search_console",
            Integration.status == "active"
        ).first()

        if not integration:
            return {"error": "Google Search Console not connected. Connect it via the integration checklist."}

        token = await _get_valid_token(integration, db)
        if not token:
            return {"error": "No valid access token. Please reconnect Google Search Console."}

        # Determine the GSC property URL to query
        if not gsc_property:
            # Try to auto-detect from the website domain
            config = integration.config or {}
            gsc_property = config.get("gsc_property", "")

            if not gsc_property:
                # Try common formats
                domain = website.domain
                candidates = [
                    "sc-domain:" + domain,
                    "https://" + domain + "/",
                    "http://" + domain + "/",
                    "https://www." + domain + "/",
                ]

                # List properties to find the matching one
                props_result = await list_gsc_properties(website_id)
                if "properties" in props_result:
                    available = [p["site_url"] for p in props_result["properties"]]
                    for candidate in candidates:
                        if candidate in available:
                            gsc_property = candidate
                            break

                    if not gsc_property and available:
                        # Use first available property
                        gsc_property = available[0]

                if not gsc_property:
                    return {
                        "error": "Could not find a Search Console property for " + domain + ". "
                                 "Please verify your site is added in Google Search Console.",
                        "available_properties": props_result.get("properties", [])
                    }

                # Save for future use
                config["gsc_property"] = gsc_property
                integration.config = config
                db.commit()

        # Date range
        date_to = datetime.utcnow().date() - timedelta(days=3)  # GSC data has ~3 day lag
        date_from = date_to - timedelta(days=days)

        print("[GSC] Fetching data for " + gsc_property + " from " + str(date_from) + " to " + str(date_to))

        # Fetch keyword data (queries + pages)
        query_data = await _fetch_search_analytics(
            token, integration, db, gsc_property,
            str(date_from), str(date_to),
            dimensions=["query"]
        )

        if query_data is None or "error" in (query_data or {}):
            return {"error": "Failed to fetch keyword data: " + str(query_data)}

        # Also fetch per-page data
        page_data = await _fetch_search_analytics(
            token, integration, db, gsc_property,
            str(date_from), str(date_to),
            dimensions=["query", "page"]
        )

        # Process keyword data
        keywords = []
        for row in query_data.get("rows", []):
            keywords.append({
                "query": row["keys"][0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            })

        # Add page URLs to keywords from the per-page data
        query_page_map = {}
        if page_data and "rows" in page_data:
            for row in page_data.get("rows", []):
                query = row["keys"][0]
                page_url = row["keys"][1]
                clicks = row.get("clicks", 0)
                if query not in query_page_map or clicks > query_page_map[query].get("clicks", 0):
                    query_page_map[query] = {"page": page_url, "clicks": clicks}

        for kw in keywords:
            page_info = query_page_map.get(kw["query"])
            if page_info:
                kw["page"] = page_info["page"]

        # Sort by clicks descending
        keywords.sort(key=lambda x: x["clicks"], reverse=True)

        # Calculate totals
        total_clicks = sum(k["clicks"] for k in keywords)
        total_impressions = sum(k["impressions"] for k in keywords)
        avg_position = round(sum(k["position"] for k in keywords) / len(keywords), 1) if keywords else 0
        avg_ctr = round(sum(k["ctr"] for k in keywords) / len(keywords), 2) if keywords else 0

        # Save snapshot
        snapshot = KeywordSnapshot(
            website_id=website_id,
            date_from=datetime.combine(date_from, datetime.min.time()),
            date_to=datetime.combine(date_to, datetime.min.time()),
            keyword_data=keywords[:5000],  # Cap at 5000 keywords
            total_keywords=len(keywords),
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            avg_position=avg_position,
            avg_ctr=avg_ctr,
            gsc_property=gsc_property,
        )
        db.add(snapshot)

        # Update integration last_synced
        integration.last_synced = datetime.utcnow()
        db.commit()
        db.refresh(snapshot)

        print("[GSC] Saved snapshot #" + str(snapshot.id) + " with " + str(len(keywords)) + " keywords")

        return {
            "snapshot_id": snapshot.id,
            "gsc_property": gsc_property,
            "date_from": str(date_from),
            "date_to": str(date_to),
            "total_keywords": len(keywords),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "avg_position": avg_position,
            "avg_ctr": avg_ctr,
            "keywords": keywords[:500],  # Return top 500 in response
        }

    except Exception as e:
        print("[GSC] Error: " + str(e))
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def _fetch_search_analytics(
    token: str, integration: Integration, db: Session,
    site_url: str, date_from: str, date_to: str,
    dimensions: List[str], row_limit: int = 25000
) -> Optional[Dict]:
    """Fetch search analytics from GSC API with token refresh retry."""
    url = "https://www.googleapis.com/webmasters/v3/sites/" + _encode_site_url(site_url) + "/searchAnalytics/query"

    body = {
        "startDate": date_from,
        "endDate": date_to,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "startRow": 0,
    }

    result = await _gsc_api_request(token, url, method="POST", json_data=body)

    # Handle token expiry
    if result and isinstance(result, dict) and result.get("status") == 401:
        new_token = await _refresh_google_token(integration, db)
        if new_token:
            result = await _gsc_api_request(new_token, url, method="POST", json_data=body)
        else:
            return {"error": "Token expired and refresh failed"}

    return result


def _encode_site_url(site_url: str) -> str:
    """URL-encode the site URL for the API path."""
    import urllib.parse
    return urllib.parse.quote(site_url, safe='')


async def get_latest_snapshot(website_id: int) -> Dict[str, Any]:
    """Get the most recent keyword snapshot for a website."""
    db = SessionLocal()
    try:
        snapshot = db.query(KeywordSnapshot)\
            .filter(KeywordSnapshot.website_id == website_id)\
            .order_by(KeywordSnapshot.snapshot_date.desc())\
            .first()

        if not snapshot:
            return {"snapshot": None, "message": "No keyword data yet. Click 'Sync Keywords' to pull data from Search Console."}

        return {
            "snapshot": {
                "id": snapshot.id,
                "date_from": snapshot.date_from.strftime("%Y-%m-%d"),
                "date_to": snapshot.date_to.strftime("%Y-%m-%d"),
                "snapshot_date": snapshot.snapshot_date.isoformat(),
                "total_keywords": snapshot.total_keywords,
                "total_clicks": snapshot.total_clicks,
                "total_impressions": snapshot.total_impressions,
                "avg_position": snapshot.avg_position,
                "avg_ctr": snapshot.avg_ctr,
                "gsc_property": snapshot.gsc_property,
                "keywords": snapshot.keyword_data[:500] if snapshot.keyword_data else [],
            }
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


async def get_keyword_history(website_id: int, limit: int = 10) -> Dict[str, Any]:
    """Get historical keyword snapshots (summary only, no keyword lists)."""
    db = SessionLocal()
    try:
        snapshots = db.query(KeywordSnapshot)\
            .filter(KeywordSnapshot.website_id == website_id)\
            .order_by(KeywordSnapshot.snapshot_date.desc())\
            .limit(limit)\
            .all()

        return {
            "snapshots": [
                {
                    "id": s.id,
                    "date_from": s.date_from.strftime("%Y-%m-%d"),
                    "date_to": s.date_to.strftime("%Y-%m-%d"),
                    "snapshot_date": s.snapshot_date.isoformat(),
                    "total_keywords": s.total_keywords,
                    "total_clicks": s.total_clicks,
                    "total_impressions": s.total_impressions,
                    "avg_position": s.avg_position,
                    "avg_ctr": s.avg_ctr,
                }
                for s in snapshots
            ]
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
