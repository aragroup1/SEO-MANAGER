# backend/cwv_monitor.py — Core Web Vitals Monitoring Engine
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, Website, CoreWebVitalsSnapshot

load_dotenv()

PAGESPEED_API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")
PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Google CWV thresholds
CWV_THRESHOLDS = {
    "lcp": {"good": 2.5, "poor": 4.0},      # seconds
    "inp": {"good": 0.2, "poor": 0.5},      # seconds (200ms, 500ms)
    "cls": {"good": 0.1, "poor": 0.25},     # unitless
    "fcp": {"good": 1.8, "poor": 3.0},      # seconds
    "ttfb": {"good": 0.8, "poor": 1.8},     # seconds
}


def _get_cwv_status(metric: str, value: Optional[float]) -> str:
    """Return 'good', 'needs_improvement', or 'poor' for a CWV metric."""
    if value is None:
        return "unknown"
    thresholds = CWV_THRESHOLDS.get(metric, {})
    good = thresholds.get("good", float("inf"))
    poor = thresholds.get("poor", float("inf"))
    if value <= good:
        return "good"
    if value <= poor:
        return "needs_improvement"
    return "poor"


def _extract_metric(lighthouse: dict, metric_id: str) -> Optional[float]:
    """Extract a metric value from Lighthouse result (in seconds)."""
    try:
        audits = lighthouse.get("audits", {})
        if metric_id in audits:
            val = audits[metric_id].get("numericValue")
            if val is not None:
                return round(val / 1000, 3)  # Convert ms to seconds
    except Exception:
        pass
    return None


def _extract_cls(lighthouse: dict) -> Optional[float]:
    """Extract CLS from Lighthouse (unitless, no conversion needed)."""
    try:
        audits = lighthouse.get("audits", {})
        cls_audit = audits.get("cumulative-layout-shift")
        if cls_audit:
            return round(cls_audit.get("numericValue", 0), 3)
    except Exception:
        pass
    return None


async def check_cwv_for_url(url: str, device: str = "mobile") -> Dict[str, Any]:
    """Run PageSpeed Insights for a URL and return CWV data."""
    if not PAGESPEED_API_KEY:
        return {"error": "GOOGLE_PAGESPEED_API_KEY not configured"}

    params = {
        "url": url if url.startswith("http") else f"https://{url}",
        "key": PAGESPEED_API_KEY,
        "strategy": device,
        "category": "PERFORMANCE",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(PAGESPEED_URL, params=params)
            if resp.status_code != 200:
                return {"error": f"PageSpeed API error: {resp.status_code}", "details": resp.text[:500]}

            data = resp.json()
            lighthouse = data.get("lighthouseResult", {})

            result = {
                "url": url,
                "device": device,
                "lcp": _extract_metric(lighthouse, "largest-contentful-paint"),
                "fcp": _extract_metric(lighthouse, "first-contentful-paint"),
                "ttfb": _extract_metric(lighthouse, "server-response-time"),
                "cls": _extract_cls(lighthouse),
                "inp": _extract_metric(lighthouse, "interaction-to-next-paint"),
                "performance_score": lighthouse.get("categories", {}).get("performance", {}).get("score"),
                "checked_at": datetime.utcnow().isoformat(),
            }

            # Add status labels
            for metric in ["lcp", "inp", "cls", "fcp", "ttfb"]:
                result[f"{metric}_status"] = _get_cwv_status(metric, result.get(metric))

            return result

    except Exception as e:
        return {"error": f"CWV check failed: {str(e)}"}


async def check_cwv_for_website(website_id: int) -> Dict[str, Any]:
    """Check CWV for a website (mobile + desktop)."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        url = f"https://{domain}" if not domain.startswith("http") else domain

        # Check both mobile and desktop
        mobile = await check_cwv_for_url(url, "mobile")
        desktop = await check_cwv_for_url(url, "desktop")

        # Store snapshots
        for device, data in [("mobile", mobile), ("desktop", desktop)]:
            if "error" not in data:
                snapshot = CoreWebVitalsSnapshot(
                    website_id=website_id,
                    url=url,
                    lcp=data.get("lcp"),
                    inp=data.get("inp"),
                    cls=data.get("cls"),
                    fcp=data.get("fcp"),
                    ttfb=data.get("ttfb"),
                    device_type=device,
                    source="pagespeed",
                )
                db.add(snapshot)

        db.commit()

        return {
            "website_id": website_id,
            "domain": domain,
            "mobile": mobile,
            "desktop": desktop,
        }
    finally:
        db.close()


def get_latest_cwv(website_id: int) -> Dict[str, Any]:
    """Get the most recent CWV snapshot for a website."""
    db = SessionLocal()
    try:
        latest_mobile = db.query(CoreWebVitalsSnapshot)\
            .filter(CoreWebVitalsSnapshot.website_id == website_id, CoreWebVitalsSnapshot.device_type == "mobile")\
            .order_by(CoreWebVitalsSnapshot.checked_at.desc()).first()

        latest_desktop = db.query(CoreWebVitalsSnapshot)\
            .filter(CoreWebVitalsSnapshot.website_id == website_id, CoreWebVitalsSnapshot.device_type == "desktop")\
            .order_by(CoreWebVitalsSnapshot.checked_at.desc()).first()

        def _format_snapshot(s):
            if not s:
                return None
            return {
                "lcp": s.lcp, "lcp_status": _get_cwv_status("lcp", s.lcp),
                "inp": s.inp, "inp_status": _get_cwv_status("inp", s.inp),
                "cls": s.cls, "cls_status": _get_cwv_status("cls", s.cls),
                "fcp": s.fcp, "fcp_status": _get_cwv_status("fcp", s.fcp),
                "ttfb": s.ttfb, "ttfb_status": _get_cwv_status("ttfb", s.ttfb),
                "checked_at": s.checked_at.isoformat() if s.checked_at else None,
            }

        return {
            "mobile": _format_snapshot(latest_mobile),
            "desktop": _format_snapshot(latest_desktop),
        }
    finally:
        db.close()


def get_cwv_history(website_id: int, days: int = 30, device: str = "mobile") -> List[Dict[str, Any]]:
    """Get CWV history for trend charts."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        snapshots = db.query(CoreWebVitalsSnapshot)\
            .filter(CoreWebVitalsSnapshot.website_id == website_id,
                    CoreWebVitalsSnapshot.device_type == device,
                    CoreWebVitalsSnapshot.checked_at >= since)\
            .order_by(CoreWebVitalsSnapshot.checked_at.asc()).all()

        return [
            {
                "date": s.checked_at.isoformat() if s.checked_at else None,
                "lcp": s.lcp, "inp": s.inp, "cls": s.cls,
                "fcp": s.fcp, "ttfb": s.ttfb,
            }
            for s in snapshots
        ]
    finally:
        db.close()


def get_cwv_trends(website_id: int) -> Dict[str, Any]:
    """Get 7-day and 30-day trend summaries."""
    db = SessionLocal()
    try:
        def _avg(values):
            clean = [v for v in values if v is not None]
            return round(sum(clean) / len(clean), 3) if clean else None

        def _trend_for_device(device: str):
            history_7d = get_cwv_history(website_id, 7, device)
            history_30d = get_cwv_history(website_id, 30, device)

            return {
                "7d": {
                    "lcp": _avg([h["lcp"] for h in history_7d]),
                    "inp": _avg([h["inp"] for h in history_7d]),
                    "cls": _avg([h["cls"] for h in history_7d]),
                    "fcp": _avg([h["fcp"] for h in history_7d]),
                    "ttfb": _avg([h["ttfb"] for h in history_7d]),
                    "data_points": len(history_7d),
                },
                "30d": {
                    "lcp": _avg([h["lcp"] for h in history_30d]),
                    "inp": _avg([h["inp"] for h in history_30d]),
                    "cls": _avg([h["cls"] for h in history_30d]),
                    "fcp": _avg([h["fcp"] for h in history_30d]),
                    "ttfb": _avg([h["ttfb"] for h in history_30d]),
                    "data_points": len(history_30d),
                },
            }

        return {
            "mobile": _trend_for_device("mobile"),
            "desktop": _trend_for_device("desktop"),
        }
    finally:
        db.close()
