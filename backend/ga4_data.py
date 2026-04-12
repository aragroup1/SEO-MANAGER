# backend/ga4_data.py - Google Analytics 4 Data Fetcher
# Pulls real traffic data from GA4 for use in reports and dashboards.
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
from dotenv import load_dotenv

from database import SessionLocal, Website, Integration

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")


async def _refresh_token(integration: Integration, db) -> Optional[str]:
    """Refresh the GA4 access token."""
    if not integration.refresh_token:
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
                    integration.token_expiry = datetime.utcnow() + timedelta(
                        seconds=tokens.get("expires_in", 3600))
                    db.commit()
                    return new_token
            else:
                print(f"[GA4] Token refresh failed: {resp.status_code}")
    except Exception as e:
        print(f"[GA4] Token refresh error: {e}")
    return None


async def _ga4_request(token: str, property_id: str, body: Dict,
                       integration: Integration = None, db=None) -> Optional[Dict]:
    """Make a GA4 Data API request."""
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=body
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401 and integration and db:
                new_token = await _refresh_token(integration, db)
                if new_token:
                    resp2 = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {new_token}"},
                        json=body
                    )
                    if resp2.status_code == 200:
                        return resp2.json()
                    print(f"[GA4] Retry failed: {resp2.status_code}")
                return {"error": "Token expired and refresh failed"}
            else:
                print(f"[GA4] API error: {resp.status_code} {resp.text[:200]}")
                return {"error": f"GA4 API error {resp.status_code}"}
    except Exception as e:
        print(f"[GA4] Request error: {e}")
        return {"error": str(e)}


async def fetch_ga4_traffic(website_id: int, days: int = 30) -> Dict[str, Any]:
    """
    Fetch traffic data from GA4 for a website.
    Returns: sessions, users, pageviews, bounce rate, traffic sources, top pages.
    """
    db = SessionLocal()
    try:
        integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "google_analytics",
            Integration.status == "active"
        ).first()

        if not integration:
            return {"error": "Google Analytics not connected"}

        token = integration.access_token
        if not token:
            return {"error": "No access token. Reconnect Google Analytics."}

        config = integration.config or {}
        property_id = config.get("ga4_property_id", "")
        if not property_id:
            return {"error": "No GA4 property selected. Go to Settings and select a GA4 property."}

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)
        prev_start = start_date - timedelta(days=days)
        prev_end = start_date - timedelta(days=1)

        print(f"[GA4] Fetching traffic for property {property_id}, {start_date} to {end_date}")

        # ─── Current period: overall metrics ───
        overview_body = {
            "dateRanges": [
                {"startDate": str(start_date), "endDate": str(end_date)},
                {"startDate": str(prev_start), "endDate": str(prev_end)},
            ],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
                {"name": "screenPageViews"},
                {"name": "bounceRate"},
                {"name": "averageSessionDuration"},
                {"name": "engagedSessions"},
            ],
        }

        overview = await _ga4_request(token, property_id, overview_body, integration, db)

        if not overview or "error" in overview:
            return {"error": overview.get("error", "Failed to fetch GA4 data") if overview else "GA4 request failed"}

        # Parse overview metrics
        current_metrics = {}
        previous_metrics = {}
        if overview.get("rows"):
            for row in overview["rows"]:
                date_range_idx = row.get("dimensionValues", [{}])[0].get("value", "date_range_0") if row.get("dimensionValues") else "date_range_0"
                metrics = {}
                metric_headers = overview.get("metricHeaders", [])
                for i, val in enumerate(row.get("metricValues", [])):
                    name = metric_headers[i]["name"] if i < len(metric_headers) else f"metric_{i}"
                    try:
                        metrics[name] = float(val.get("value", 0))
                    except:
                        metrics[name] = 0

                if not current_metrics:
                    current_metrics = metrics
                else:
                    previous_metrics = metrics

        # ─── Traffic sources ───
        sources_body = {
            "dateRanges": [{"startDate": str(start_date), "endDate": str(end_date)}],
            "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
                {"name": "screenPageViews"},
            ],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
            "limit": 10,
        }

        sources = await _ga4_request(token, property_id, sources_body, integration, db)
        traffic_sources = []
        if sources and "rows" in sources:
            for row in sources["rows"]:
                channel = row.get("dimensionValues", [{}])[0].get("value", "Unknown")
                vals = row.get("metricValues", [])
                traffic_sources.append({
                    "channel": channel,
                    "sessions": int(float(vals[0].get("value", 0))) if len(vals) > 0 else 0,
                    "users": int(float(vals[1].get("value", 0))) if len(vals) > 1 else 0,
                    "pageviews": int(float(vals[2].get("value", 0))) if len(vals) > 2 else 0,
                })

        # ─── Top pages ───
        pages_body = {
            "dateRanges": [{"startDate": str(start_date), "endDate": str(end_date)}],
            "dimensions": [{"name": "pagePath"}],
            "metrics": [
                {"name": "screenPageViews"},
                {"name": "totalUsers"},
                {"name": "averageSessionDuration"},
            ],
            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
            "limit": 20,
        }

        pages = await _ga4_request(token, property_id, pages_body, integration, db)
        top_pages = []
        if pages and "rows" in pages:
            for row in pages["rows"]:
                path = row.get("dimensionValues", [{}])[0].get("value", "/")
                vals = row.get("metricValues", [])
                top_pages.append({
                    "page": path,
                    "pageviews": int(float(vals[0].get("value", 0))) if len(vals) > 0 else 0,
                    "users": int(float(vals[1].get("value", 0))) if len(vals) > 1 else 0,
                    "avg_duration": round(float(vals[2].get("value", 0)), 1) if len(vals) > 2 else 0,
                })

        # ─── Daily sessions trend ───
        trend_body = {
            "dateRanges": [{"startDate": str(start_date), "endDate": str(end_date)}],
            "dimensions": [{"name": "date"}],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
            ],
            "orderBys": [{"dimension": {"dimensionName": "date"}, "desc": False}],
        }

        trend = await _ga4_request(token, property_id, trend_body, integration, db)
        daily_trend = []
        if trend and "rows" in trend:
            for row in trend["rows"]:
                date_str = row.get("dimensionValues", [{}])[0].get("value", "")
                vals = row.get("metricValues", [])
                # Format YYYYMMDD to YYYY-MM-DD
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                daily_trend.append({
                    "date": date_str,
                    "sessions": int(float(vals[0].get("value", 0))) if len(vals) > 0 else 0,
                    "users": int(float(vals[1].get("value", 0))) if len(vals) > 1 else 0,
                })

        # ─── Organic search specifically ───
        organic_sessions = 0
        for src in traffic_sources:
            if "organic" in src.get("channel", "").lower():
                organic_sessions += src.get("sessions", 0)

        # Build result
        def _safe_int(d, key):
            try: return int(d.get(key, 0))
            except: return 0

        def _safe_float(d, key):
            try: return round(float(d.get(key, 0)), 2)
            except: return 0

        result = {
            "property_id": property_id,
            "period": {"start": str(start_date), "end": str(end_date), "days": days},
            "current": {
                "sessions": _safe_int(current_metrics, "sessions"),
                "users": _safe_int(current_metrics, "totalUsers"),
                "pageviews": _safe_int(current_metrics, "screenPageViews"),
                "bounce_rate": _safe_float(current_metrics, "bounceRate"),
                "avg_duration": _safe_float(current_metrics, "averageSessionDuration"),
                "engaged_sessions": _safe_int(current_metrics, "engagedSessions"),
                "organic_sessions": organic_sessions,
            },
            "previous": {
                "sessions": _safe_int(previous_metrics, "sessions"),
                "users": _safe_int(previous_metrics, "totalUsers"),
                "pageviews": _safe_int(previous_metrics, "screenPageViews"),
            },
            "changes": {
                "sessions": _safe_int(current_metrics, "sessions") - _safe_int(previous_metrics, "sessions"),
                "users": _safe_int(current_metrics, "totalUsers") - _safe_int(previous_metrics, "totalUsers"),
                "pageviews": _safe_int(current_metrics, "screenPageViews") - _safe_int(previous_metrics, "screenPageViews"),
            },
            "traffic_sources": traffic_sources,
            "top_pages": top_pages,
            "daily_trend": daily_trend,
        }

        print(f"[GA4] Data fetched: {result['current']['sessions']} sessions, "
              f"{result['current']['organic_sessions']} organic, "
              f"{len(top_pages)} pages")

        return result

    except Exception as e:
        print(f"[GA4] Error: {e}")
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()
