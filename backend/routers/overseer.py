"""Overseer + cross-site overview + sync-all + portfolio + daily/weekly schedulers."""
import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from database import (
    get_db, SessionLocal, Website, AuditReport, KeywordSnapshot,
    ProposedFix, TrackedKeyword, StrategistResult,
)
from .state import sync_all_jobs

router = APIRouter()


@router.post("/api/overseer/{website_id}/run")
async def run_overseer(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    from ai_overseer import run_overseer_background
    background_tasks.add_task(run_overseer_background, website_id)
    return {"status": "running",
            "message": f"AI Overseer started for {website.domain}. Running: audit → keywords → GEO scan → fixes → strategy refresh. Check Issues & Fixes for results."}


@router.post("/api/overseer/run-all")
async def run_overseer_all(background_tasks: BackgroundTasks):
    from ai_overseer import run_overseer_background
    background_tasks.add_task(run_overseer_background, None)
    return {"status": "running", "message": "AI Overseer started for all websites."}


@router.get("/api/overseer/status")
async def overseer_status(website_id: Optional[int] = None):
    from ai_overseer import get_overseer_status
    return get_overseer_status(website_id)


@router.get("/api/overview")
async def get_overview_summary(db: Session = Depends(get_db)):
    """Per-site rollup: health, keywords, fixes, tracked keywords."""
    websites = db.query(Website).filter(Website.is_active == True).all()
    summaries = []

    for w in websites:
        summary = {"id": w.id, "domain": w.domain, "site_type": w.site_type}

        latest_audit = db.query(AuditReport).filter(AuditReport.website_id == w.id).order_by(AuditReport.audit_date.desc()).first()
        prev_audit = None
        if latest_audit:
            prev_audit = db.query(AuditReport).filter(AuditReport.website_id == w.id, AuditReport.id != latest_audit.id).order_by(AuditReport.audit_date.desc()).first()

        if latest_audit:
            prev_score = prev_audit.health_score if prev_audit else latest_audit.health_score
            summary["health_score"] = latest_audit.health_score
            summary["score_change"] = round(latest_audit.health_score - prev_score, 1)
            summary["total_issues"] = latest_audit.total_issues
            summary["critical_issues"] = latest_audit.critical_issues
            summary["issues_change"] = latest_audit.total_issues - (prev_audit.total_issues if prev_audit else latest_audit.total_issues)
            summary["last_audit"] = latest_audit.audit_date.isoformat()
        else:
            summary.update({"health_score": None, "score_change": 0, "total_issues": 0,
                            "critical_issues": 0, "issues_change": 0, "last_audit": None})

        latest_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == w.id).order_by(KeywordSnapshot.snapshot_date.desc()).first()
        prev_snap = None
        if latest_snap:
            prev_snap = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == w.id, KeywordSnapshot.id != latest_snap.id).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest_snap:
            summary["total_keywords"] = latest_snap.total_keywords
            summary["total_clicks"] = latest_snap.total_clicks
            summary["total_impressions"] = latest_snap.total_impressions
            summary["avg_position"] = latest_snap.avg_position
            summary["keywords_change"] = latest_snap.total_keywords - (prev_snap.total_keywords if prev_snap else 0)
            summary["clicks_change"] = latest_snap.total_clicks - (prev_snap.total_clicks if prev_snap else 0)
        else:
            summary.update({"total_keywords": 0, "total_clicks": 0, "total_impressions": 0,
                            "avg_position": 0, "keywords_change": 0, "clicks_change": 0})

        summary["pending_fixes"] = db.query(ProposedFix).filter(ProposedFix.website_id == w.id, ProposedFix.status == "pending").count()
        summary["applied_fixes"] = db.query(ProposedFix).filter(ProposedFix.website_id == w.id, ProposedFix.status == "applied").count()
        summary["autonomy_mode"] = w.autonomy_mode

        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == w.id).all()
        summary["tracked_count"] = len(tracked)
        summary["tracked_keywords"] = [{"keyword": tk.keyword, "position": tk.current_position,
                                          "clicks": tk.current_clicks} for tk in tracked[:5]]
        summaries.append(summary)

    return {"websites": summaries}


# ─── Sync-All ───
@router.post("/api/sync-all/{website_id}")
async def sync_all(website_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    job_id = f"syncall_{website_id}_{int(time.time())}"
    sync_all_jobs[job_id] = {
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "steps": [], "current_step": None, "error": None,
    }
    background_tasks.add_task(_run_sync_all, website_id, job_id)
    return {"job_id": job_id, "status": "started", "message": "Full sync started. This will take 5-15 minutes."}


async def _run_sync_all(website_id: int, job_id: str):
    from geo_engine import run_geo_audit
    from geo_fix_engine import scan_geo_fixes
    from fix_engine import AIFixGenerator
    from linking_engine import analyze_internal_links
    from content_decay import analyze_content_decay
    from cwv_monitor import check_cwv
    from image_optimizer import ImageOptimizer
    from local_seo import check_gbp_presence

    def _step(name: str):
        sync_all_jobs[job_id]["current_step"] = name
        sync_all_jobs[job_id]["steps"].append({"step": name, "at": datetime.utcnow().isoformat(), "status": "running"})
        print(f"[SyncAll] {job_id}: {name}")

    def _step_done(name: str, result: str = "ok"):
        for s in sync_all_jobs[job_id]["steps"]:
            if s["step"] == name and s.get("status") == "running":
                s["status"] = result
        print(f"[SyncAll] {job_id}: {name} → {result}")

    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            sync_all_jobs[job_id]["status"] = "failed"
            sync_all_jobs[job_id]["error"] = "Website not found"
            return

        base_url = f"https://{website.domain}"

        steps = [
            ("Site Audit", lambda: _do_audit(website_id)),
            ("Keyword Sync", lambda: _do_keyword_sync(website_id)),
            ("GEO Audit", lambda: _do_geo_audit(website_id, db)),
            ("GEO Fix Scan", lambda: scan_geo_fixes(website_id)),
            ("Fix Scan", lambda: AIFixGenerator(website_id).scan_and_generate_fixes()),
            ("Linking Analysis", lambda: analyze_internal_links(website_id)),
            ("Content Decay", lambda: analyze_content_decay(website_id)),
            ("Core Web Vitals", lambda: _do_cwv(website_id, base_url)),
            ("Image Audit", lambda: ImageOptimizer(website_id).analyze_images()),
            ("Local SEO", lambda: check_gbp_presence(website_id)),
            ("Sitemap Generation", lambda: _do_sitemap(website_id)),
            ("Broken Link Scan", lambda: _do_link_scan(website_id)),
            ("Index Status Sync", lambda: _do_index_sync(website_id)),
        ]
        for name, fn in steps:
            _step(name)
            try:
                await fn()
                _step_done(name, "done")
            except Exception as e:
                _step_done(name, f"error: {e}")

        sync_all_jobs[job_id]["status"] = "completed"
        sync_all_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        print(f"[SyncAll] {job_id}: ALL DONE")

    except Exception as e:
        sync_all_jobs[job_id]["status"] = "failed"
        sync_all_jobs[job_id]["error"] = str(e)
        print(f"[SyncAll] {job_id}: FAILED — {e}")
    finally:
        db.close()


async def _do_audit(website_id: int):
    from audit_engine import SEOAuditEngine
    await SEOAuditEngine(website_id).run_comprehensive_audit()


async def _do_keyword_sync(website_id: int):
    from search_console import sync_gsc_keywords
    await sync_gsc_keywords(website_id)


async def _do_geo_audit(website_id: int, db):
    from geo_engine import run_geo_audit
    geo_result = await run_geo_audit(website_id)
    sr = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
    if not sr:
        sr = StrategistResult(website_id=website_id)
        db.add(sr)
    sr.geo_audit = geo_result
    sr.geo_audit_at = datetime.utcnow()
    db.commit()


async def _do_cwv(website_id: int, base_url: str):
    from cwv_monitor import check_cwv
    await check_cwv(website_id, base_url, "mobile")
    await check_cwv(website_id, base_url, "desktop")


async def _do_sitemap(website_id: int):
    from sitemap_generator import generate_sitemap
    await generate_sitemap(website_id)


async def _do_link_scan(website_id: int):
    from link_checker import scan_broken_links
    await scan_broken_links(website_id)


async def _do_index_sync(website_id: int):
    from index_tracker import sync_index_status
    await sync_index_status(website_id)


@router.get("/api/sync-all/{website_id}/status")
async def sync_all_status(website_id: int, job_id: str):
    job = sync_all_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


# ─── Daily Audit Scheduler ───
_daily_audit_running = False


async def _run_daily_audits():
    global _daily_audit_running
    if _daily_audit_running:
        print("[DailyAudit] Already running, skipping")
        return
    _daily_audit_running = True
    try:
        db = SessionLocal()
        websites = db.query(Website).filter(Website.is_active == True).all()
        db.close()

        print(f"[DailyAudit] Starting daily audits for {len(websites)} websites")
        for w in websites:
            try:
                from audit_engine import SEOAuditEngine
                engine = SEOAuditEngine(w.id)
                result = await engine.run_comprehensive_audit()
                print(f"[DailyAudit] {w.domain}: score {result.get('health_score', 'N/A')}")

                if w.autonomy_mode in ["smart", "ultra"] and w.site_type in ["shopify", "wordpress"]:
                    try:
                        print(f"[DailyAudit] {w.domain}: auto-fix scan (mode: {w.autonomy_mode})")
                        from fix_engine import generate_fixes_for_website
                        fix_result = await generate_fixes_for_website(w.id)
                        print(f"[DailyAudit] {w.domain}: {fix_result.get('total_fixes', 0)} fixes generated, {fix_result.get('auto_applied', 0)} auto-applied")
                    except Exception as e:
                        print(f"[DailyAudit] {w.domain}: auto-fix scan failed: {e}")

                await asyncio.sleep(5)
            except Exception as e:
                print(f"[DailyAudit] {w.domain} failed: {e}")
        print("[DailyAudit] All daily audits complete")
    except Exception as e:
        print(f"[DailyAudit] Error: {e}")
    finally:
        _daily_audit_running = False


def schedule_daily_audits():
    """Start daily audit + weekly overseer scheduler threads. Called from main.py startup."""
    def _daily_loop():
        while True:
            now = datetime.utcnow()
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Next daily audit in {wait_seconds/3600:.1f} hours (3 AM UTC)")
            time.sleep(wait_seconds)
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_daily_audits())
                loop.close()
            except Exception as e:
                print(f"[Scheduler] Daily audit error: {e}")

    def _weekly_loop():
        while True:
            now = datetime.utcnow()
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 4:
                days_until_monday = 7
            target = (now + timedelta(days=days_until_monday)).replace(hour=4, minute=0, second=0, microsecond=0)
            wait_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Next weekly overseer in {wait_seconds/3600:.1f} hours (Monday 4 AM UTC)")
            time.sleep(wait_seconds)
            try:
                from ai_overseer import run_overseer_background
                run_overseer_background(None)
                print("[Scheduler] Weekly overseer cycle complete")
            except Exception as e:
                print(f"[Scheduler] Weekly overseer error: {e}")

    def _client_reports_loop():
        """Daily client ranking emails at 8 AM UTC."""
        while True:
            now = datetime.utcnow()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"[Scheduler] Next client reports run in {wait_seconds/3600:.1f} hours (8 AM UTC)")
            time.sleep(wait_seconds)
            try:
                from client_reports import send_daily_reports_all
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(send_daily_reports_all())
                loop.close()
            except Exception as e:
                print(f"[Scheduler] Client reports error: {e}")

    threading.Thread(target=_daily_loop, daemon=True).start()
    print("[Scheduler] Daily audit scheduler started (runs at 3 AM UTC)")
    threading.Thread(target=_weekly_loop, daemon=True).start()
    print("[Scheduler] Weekly overseer scheduler started (runs Monday 4 AM UTC)")
    threading.Thread(target=_client_reports_loop, daemon=True).start()
    print("[Scheduler] Client ranking reports scheduler started (runs at 8 AM UTC)")
