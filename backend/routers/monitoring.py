"""Monitoring/utility endpoints: cwv, notifications, schema, images, links,
index, sitemap, robots, local-seo, ab-test, ga4, linking, decay."""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from database import (
    get_db, SessionLocal, Website, NotificationChannel, StrategistResult,
)
from sitemap_generator import generate_sitemap, get_sitemap, submit_to_gsc, validate_sitemap
from robots_generator import (
    generate_robots_txt, validate_robots_txt, check_existing_robots,
    get_robots_txt, update_robots_txt,
)

router = APIRouter()


# ─── Linking ───
@router.post("/api/linking/{website_id}/analyze")
async def analyze_linking(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from linking_engine import analyze_internal_linking
    raw = await analyze_internal_linking(website_id)
    if isinstance(raw, dict) and not raw.get("error"):
        domain = raw.get("domain", "")
        def _abs(path: str) -> str:
            if not path: return ""
            if path.startswith("http"): return path
            return f"https://{domain}{path}" if domain else path
        hubs = [{"url": _abs(h.get("path", "")), "title": h.get("path", ""),
                 "inbound": h.get("inbound_links", 0), "outbound": 0,
                 "is_hub": True, "is_orphan": False} for h in raw.get("hub_pages", [])]
        orphans = [{"url": _abs(o.get("path", "")), "title": o.get("title", ""),
                    "inbound": o.get("inbound", 0), "outbound": 0,
                    "is_hub": False, "is_orphan": True} for o in raw.get("orphan_pages", [])]
        suggestions = [{"from_url": _abs(s.get("source_page", "")),
                        "to_url": _abs(s.get("target_page", "")),
                        "anchor_text": s.get("anchor_text", ""),
                        "reason": s.get("reason", "")} for s in raw.get("link_suggestions", [])]
        result = {
            "total_pages": raw.get("pages_analyzed", 0),
            "total_internal_links": raw.get("total_internal_links", 0),
            "avg_links_per_page": raw.get("avg_internal_links", 0),
            "hubs": hubs, "orphans": orphans, "suggestions": suggestions,
            "analyzed_at": raw.get("analyzed_at"),
        }
        try:
            row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
            if not row:
                row = StrategistResult(website_id=website_id)
                db.add(row); db.flush()
            row.linking = result
            row.linking_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Linking] persist failed: {e}")
            db.rollback()
        return result
    return raw


@router.get("/api/linking/{website_id}/graph")
async def get_linking_graph(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from linking_engine import get_link_graph
    result = get_link_graph(website_id)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Content Decay ───
@router.post("/api/decay/{website_id}/analyze")
async def analyze_decay(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    from content_decay import detect_content_decay
    raw = await detect_content_decay(website_id)
    if isinstance(raw, dict) and not raw.get("error"):
        def _bucket(score):
            if score < 40: return "high"
            if score < 65: return "medium"
            return "low"

        def _days_since(signals):
            for k in ("modified_date", "schema_date_modified", "last_modified", "published_date", "schema_date_published"):
                v = signals.get(k) if signals else None
                if not v: continue
                try:
                    dt = datetime.fromisoformat(str(v).replace("Z", "+00:00").split("+")[0])
                    return max(0, (datetime.utcnow() - dt).days)
                except Exception: pass
            return 0

        items = []
        for p in raw.get("own_pages", []):
            score = p.get("freshness_score", 50)
            signals = p.get("signals", {}) or {}
            last_mod = (signals.get("modified_date") or signals.get("schema_date_modified")
                        or signals.get("last_modified") or signals.get("published_date") or "")
            days = _days_since(signals)
            items.append({
                "url": p.get("url", ""), "title": p.get("title", ""),
                "last_modified": last_mod, "days_since_update": days,
                "decay_risk": _bucket(score),
                "recommendation": (
                    "Refresh content — very stale" if score < 40 else
                    "Consider updating soon" if score < 65 else
                    "Fresh enough — monitor"
                ),
            })
        comp_map = {c.get("our_page", ""): c for c in raw.get("competitor_comparison", [])}
        for it in items:
            c = comp_map.get(it["url"])
            if c:
                it["current_position"] = c.get("position")
                it["competitor_freshness"] = f"Gap {c.get('freshness_gap', 0):+d} vs top competitor"
        result = {
            "total_pages_analyzed": raw.get("pages_checked", len(items)),
            "high_risk": [i for i in items if i["decay_risk"] == "high"],
            "medium_risk": [i for i in items if i["decay_risk"] == "medium"],
            "low_risk": [i for i in items if i["decay_risk"] == "low"],
            "refresh_recommendations": [
                (r if isinstance(r, str) else
                 f"[{r.get('priority','med').upper()}] {r.get('action','')} — {r.get('reason','')}".strip(" —"))
                for r in (raw.get("recommendations") or [])
            ],
            "analyzed_at": raw.get("analyzed_at"),
        }
        try:
            row = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
            if not row:
                row = StrategistResult(website_id=website_id)
                db.add(row); db.flush()
            row.decay = result
            row.decay_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:
            print(f"[Decay] persist failed: {e}")
            db.rollback()
        return result
    return raw


# ─── GA4 ───
@router.get("/api/ga4/{website_id}/traffic")
async def get_ga4_traffic(website_id: int, days: int = 30, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from ga4_data import fetch_ga4_traffic
    return await fetch_ga4_traffic(website_id, days=days)


# ─── Core Web Vitals ───
@router.post("/api/cwv/{website_id}/check")
async def check_cwv(website_id: int):
    from cwv_monitor import check_cwv_for_website
    return await check_cwv_for_website(website_id)


@router.get("/api/cwv/{website_id}/latest")
async def get_latest_cwv_endpoint(website_id: int):
    from cwv_monitor import get_latest_cwv
    return get_latest_cwv(website_id)


@router.get("/api/cwv/{website_id}/history")
async def get_cwv_history_endpoint(website_id: int, days: int = 30, device: str = "mobile"):
    from cwv_monitor import get_cwv_history
    return {"history": get_cwv_history(website_id, days, device)}


@router.get("/api/cwv/{website_id}/trends")
async def get_cwv_trends_endpoint(website_id: int):
    from cwv_monitor import get_cwv_trends
    return get_cwv_trends(website_id)


# ─── Notifications ───
@router.post("/api/notifications/{website_id}/channels")
async def add_notification_channel(website_id: int, request: Request):
    data = await request.json()
    db = SessionLocal()
    try:
        channel = NotificationChannel(
            website_id=website_id,
            channel_type=data.get("channel_type"),
            name=data.get("name"),
            config=data.get("config", {}),
            events=data.get("events", []),
            is_active=data.get("is_active", True),
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
        return {"id": channel.id, "name": channel.name,
                "channel_type": channel.channel_type, "events": channel.events}
    finally:
        db.close()


@router.get("/api/notifications/{website_id}/channels")
async def list_notification_channels(website_id: int):
    from notifications import get_notification_channels
    return {"channels": get_notification_channels(website_id)}


@router.delete("/api/notifications/channels/{channel_id}")
async def delete_notification_channel(channel_id: int):
    db = SessionLocal()
    try:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        db.delete(channel)
        db.commit()
        return {"success": True}
    finally:
        db.close()


@router.post("/api/notifications/channels/{channel_id}/test")
async def test_notification_channel(channel_id: int):
    from notifications import notify_event
    db = SessionLocal()
    try:
        channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        results = await notify_event(
            channel.website_id, "test", "Test Notification",
            f"This is a test notification from your {channel.name} channel. If you see this, your setup is working! 🎉",
            {"test": True}
        )
        return {"success": True, "results": results}
    finally:
        db.close()


@router.get("/api/notifications/{website_id}/logs")
async def get_notification_logs(website_id: int, limit: int = 50):
    from notifications import get_notification_logs
    return {"logs": get_notification_logs(website_id, limit)}


# ─── Schema ───
@router.post("/api/schema/{website_id}/generate")
async def generate_schema_endpoint(website_id: int, request: Request):
    from schema_generator import generate_schema
    data = await request.json()
    schema_type = data.get("schema_type", "Organization")
    return await generate_schema(schema_type, data.get("data", {}))


@router.post("/api/schema/{website_id}/validate")
async def validate_schema_endpoint(request: Request):
    from schema_generator import validate_schema
    data = await request.json()
    return validate_schema(data.get("schema", {}))


# ─── Images ───
@router.post("/api/images/{website_id}/audit")
async def run_image_audit(website_id: int):
    from image_optimizer import ImageOptimizer
    return await ImageOptimizer(website_id).analyze_images()


@router.get("/api/images/{website_id}/stats")
async def get_image_stats_endpoint(website_id: int):
    from image_optimizer import get_image_stats
    return get_image_stats(website_id)


@router.get("/api/images/{website_id}/issues")
async def get_image_issues_endpoint(website_id: int, severity: str = None, limit: int = 100):
    from image_optimizer import get_image_issues
    return {"issues": get_image_issues(website_id, severity, limit)}


# ─── A/B Tests ───
@router.post("/api/ab-test/{website_id}/create")
async def create_ab_test(website_id: int, request: Request):
    from ab_testing import create_test
    data = await request.json()
    return await create_test(
        website_id=website_id,
        page_url=data.get("page_url", ""),
        element_type=data.get("element_type", "title"),
        variant_a=data.get("variant_a", ""),
        keywords=data.get("keywords", []),
    )


@router.get("/api/ab-test/{website_id}/list")
async def list_ab_tests(website_id: int):
    from ab_testing import list_tests
    return {"tests": list_tests(website_id)}


@router.post("/api/ab-test/{test_id}/start")
async def start_ab_test(test_id: int):
    from ab_testing import start_test
    return start_test(test_id)


@router.post("/api/ab-test/{test_id}/end")
async def end_ab_test(test_id: int, request: Request):
    from ab_testing import end_test
    data = await request.json()
    return end_test(test_id, data.get("winner", "tie"), data.get("notes"))


@router.get("/api/ab-test/{test_id}/results")
async def get_ab_test_results(test_id: int):
    from ab_testing import get_test_results
    return get_test_results(test_id)


# ─── Local SEO ───
@router.post("/api/local-seo/{website_id}/setup")
async def setup_local_seo(website_id: int, request: Request):
    from local_seo import update_local_seo
    data = await request.json()
    return update_local_seo(website_id, data)


@router.get("/api/local-seo/{website_id}/status")
async def get_local_seo_endpoint(website_id: int):
    from local_seo import get_local_seo_status
    return get_local_seo_status(website_id)


@router.post("/api/local-seo/{website_id}/check-citations")
async def check_local_citations(website_id: int):
    from local_seo import check_citations
    return await check_citations(website_id)


@router.get("/api/local-seo/{website_id}/schema")
async def get_local_schema_endpoint(website_id: int):
    from local_seo import generate_local_schema
    return generate_local_schema(website_id)


# ─── Sitemap ───
@router.post("/api/sitemap/{website_id}/generate")
async def generate_sitemap_endpoint(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    result = await generate_sitemap(website_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/sitemap/{website_id}")
async def get_sitemap_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return await get_sitemap(website_id)


@router.post("/api/sitemap/{website_id}/submit")
async def submit_sitemap_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    data = await request.json()
    sitemap_url = data.get("sitemap_url", "") or f"https://{website.domain}/sitemap.xml"
    return await submit_to_gsc(website_id, sitemap_url)


@router.get("/api/sitemap/{website_id}/validate")
async def validate_sitemap_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    if not website.sitemap_xml:
        return {"valid": False, "error": "No sitemap generated yet"}
    validation = validate_sitemap(website.sitemap_xml)
    return {"valid": validation["valid"], "url_count": validation["url_count"],
            "errors": validation["errors"], "warnings": validation["warnings"]}


# ─── Robots ───
@router.post("/api/robots/{website_id}/generate")
async def generate_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    result = generate_robots_txt(website_id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/api/robots/{website_id}")
async def get_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return get_robots_txt(website_id)


@router.post("/api/robots/{website_id}/validate")
async def validate_robots_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    data = await request.json()
    content = data.get("content", website.robots_txt or "")
    if not content:
        return {"valid": False, "error": "No robots.txt content to validate"}
    return validate_robots_txt(content, website_id)


@router.get("/api/robots/{website_id}/check")
async def check_existing_robots_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    return await check_existing_robots(website_id)


@router.put("/api/robots/{website_id}")
async def update_robots_endpoint(website_id: int, request: Request, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    data = await request.json()
    content = data.get("content", "")
    result = update_robots_txt(website_id, content)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Broken Links ───
@router.post("/api/links/{website_id}/scan")
async def start_link_scan(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    async def _run_scan():
        from link_checker import scan_broken_links
        await scan_broken_links(website_id)

    background_tasks.add_task(_run_scan)
    return {"status": "success",
            "message": f"Broken link scan started for {website.domain}. Results will appear shortly."}


@router.get("/api/links/{website_id}/broken")
async def get_broken_links_endpoint(website_id: int, status: Optional[str] = None, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from link_checker import get_broken_links
    results = get_broken_links(website_id, status_filter=status)
    return {"broken_links": results, "count": len(results)}


@router.get("/api/links/{website_id}/summary")
async def get_link_summary_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from link_checker import get_link_health_summary
    return get_link_health_summary(website_id)


@router.post("/api/links/{link_id}/mark-fixed")
async def mark_link_fixed_endpoint(link_id: int, db: Session = Depends(get_db)):
    from link_checker import mark_link_fixed
    result = mark_link_fixed(link_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─── Index Tracker ───
@router.post("/api/index/{website_id}/sync")
async def sync_index_status_endpoint(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    async def _run_sync():
        from index_tracker import sync_index_status
        result = await sync_index_status(website_id)
        print(f"[IndexTracker] Sync complete for {website.domain}: {result.get('checked', 0)} URLs checked")

    background_tasks.add_task(_run_sync)
    return {"status": "syncing",
            "message": f"Index status sync started for {website.domain}. Results will appear shortly."}


@router.get("/api/index/{website_id}")
async def get_index_statuses_endpoint(website_id: int, indexed: Optional[bool] = None,
                                        limit: int = 500, offset: int = 0,
                                        db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from index_tracker import get_index_statuses
    return get_index_statuses(website_id, indexed=indexed, limit=limit, offset=offset)


@router.get("/api/index/{website_id}/summary")
async def get_index_summary_endpoint(website_id: int, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from index_tracker import get_index_summary
    return get_index_summary(website_id)


@router.get("/api/index/{website_id}/trends")
async def get_index_trends_endpoint(website_id: int, days: int = 30, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from index_tracker import get_index_trends
    return get_index_trends(website_id, days=days)
