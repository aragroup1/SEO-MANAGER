# backend/ai_overseer.py - AI Overseer
# Weekly automated SEO orchestrator that:
# 1. Runs audits on all websites
# 2. Syncs keyword rankings from GSC
# 3. Runs GEO scans and generates fixes
# 4. Detects content decay on competitors
# 5. Updates tracked keyword strategies
# 6. Generates weekly summary
import os
import json
import asyncio
from typing import Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, Integration, ProposedFix
)

load_dotenv()


# ─── In-memory overseer status (per process) ───
# Maps website_id (or "all") -> {phase, message, started_at, finished_at, error}
_overseer_status: Dict[Any, Dict[str, Any]] = {}


def _set_phase(key: Any, phase: str, message: str):
    _overseer_status[key] = {
        "phase": phase,
        "message": message,
        "started_at": _overseer_status.get(key, {}).get("started_at") or datetime.utcnow().isoformat(),
        "finished_at": None,
        "error": None,
    }


def _finish(key: Any, error: str = None):
    cur = _overseer_status.get(key, {})
    cur["phase"] = "idle"
    cur["message"] = "Idle"
    cur["finished_at"] = datetime.utcnow().isoformat()
    cur["error"] = error
    _overseer_status[key] = cur


def get_overseer_status(website_id: int = None) -> Dict[str, Any]:
    """Return current overseer status for a website (or 'all'). Returns idle if nothing recorded."""
    key = website_id if website_id is not None else "all"
    return _overseer_status.get(key, {"phase": "idle", "message": "Idle", "started_at": None, "finished_at": None, "error": None})


async def run_overseer_cycle(website_id: int = None) -> Dict[str, Any]:
    """
    Run a full AI Overseer cycle for one or all websites.
    This is the "brain" that drives the SEO strategy automatically.
    
    Cycle:
    1. Audit — crawl and score the site
    2. Keywords — sync latest rankings from GSC
    3. GEO — scan for AI search optimization gaps
    4. Fixes — generate proposed fixes (approval queue)
    5. Strategy — refresh Road to #1 strategies for tracked keywords
    6. Summary — log what was done
    """
    db = SessionLocal()
    results = {"websites_processed": 0, "actions": []}

    try:
        if website_id:
            websites = [db.query(Website).filter(Website.id == website_id).first()]
            websites = [w for w in websites if w]
        else:
            websites = db.query(Website).filter(Website.is_active == True).all()

        if not websites:
            return {"error": "No websites found"}

        status_key = website_id if website_id is not None else "all"

        for website in websites:
            site_result = {"domain": website.domain, "id": website.id, "actions": []}
            print(f"\n[Overseer] ═══ Starting cycle for {website.domain} ═══")
            _set_phase(status_key, "audit", f"Running audit for {website.domain}")
            _set_phase(website.id, "audit", f"Running audit for {website.domain}")

            # ─── Step 1: Run Audit ───
            try:
                from audit_engine import SEOAuditEngine
                print(f"[Overseer] Step 1: Running audit...")
                engine = SEOAuditEngine(website.id)
                audit_result = await engine.run_comprehensive_audit()
                score = audit_result.get("health_score", 0)
                issues = len(audit_result.get("issues", []))
                site_result["actions"].append({
                    "step": "audit",
                    "status": "completed",
                    "health_score": score,
                    "issues_found": issues,
                })
                print(f"[Overseer]   Audit done: score {score}, {issues} issues")
            except Exception as e:
                print(f"[Overseer]   Audit failed: {e}")
                site_result["actions"].append({"step": "audit", "status": "failed", "error": str(e)})

            # ─── Step 2: Sync Keywords from GSC ───
            try:
                integration = db.query(Integration).filter(
                    Integration.website_id == website.id,
                    Integration.integration_type == "google_search_console",
                    Integration.status == "active"
                ).first()

                if integration:
                    print(f"[Overseer] Step 2: Syncing keywords from GSC...")
                    _set_phase(status_key, "keywords", f"Syncing keywords for {website.domain}")
                    _set_phase(website.id, "keywords", f"Syncing keywords for {website.domain}")
                    from search_console import fetch_keyword_data
                    kw_result = await fetch_keyword_data(website.id, days=7)
                    total_kw = kw_result.get("total_keywords", 0)
                    site_result["actions"].append({
                        "step": "keyword_sync",
                        "status": "completed",
                        "total_keywords": total_kw,
                    })
                    print(f"[Overseer]   Keywords synced: {total_kw} keywords")

                    # Update tracked keywords with latest data
                    from keyword_routes import _update_tracked_keywords
                    if "keywords" in kw_result:
                        _update_tracked_keywords(website.id, kw_result["keywords"])
                else:
                    site_result["actions"].append({"step": "keyword_sync", "status": "skipped", "reason": "GSC not connected"})
                    print(f"[Overseer]   Keywords skipped: GSC not connected")
            except Exception as e:
                print(f"[Overseer]   Keyword sync failed: {e}")
                site_result["actions"].append({"step": "keyword_sync", "status": "failed", "error": str(e)})

            # ─── Step 3: GEO Fix Scan ───
            try:
                print(f"[Overseer] Step 3: Scanning for GEO fixes...")
                _set_phase(status_key, "geo", f"Scanning GEO opportunities for {website.domain}")
                _set_phase(website.id, "geo", f"Scanning GEO opportunities for {website.domain}")
                from geo_fix_engine import scan_and_generate_geo_fixes
                geo_result = await scan_and_generate_geo_fixes(website.id)
                geo_fixes = geo_result.get("total_fixes", 0)
                site_result["actions"].append({
                    "step": "geo_scan",
                    "status": "completed",
                    "fixes_generated": geo_fixes,
                })
                print(f"[Overseer]   GEO scan done: {geo_fixes} fix proposals")
            except Exception as e:
                print(f"[Overseer]   GEO scan failed: {e}")
                site_result["actions"].append({"step": "geo_scan", "status": "failed", "error": str(e)})

            # ─── Step 4: Platform Fix Scan (Shopify/WordPress) ───
            if website.site_type in ["shopify", "wordpress"]:
                try:
                    print(f"[Overseer] Step 4: Scanning for {website.site_type} fixes...")
                    _set_phase(status_key, "fixes", f"Generating {website.site_type} fixes for {website.domain}")
                    _set_phase(website.id, "fixes", f"Generating {website.site_type} fixes for {website.domain}")
                    from fix_engine import generate_fixes_for_website
                    fix_result = await generate_fixes_for_website(website.id)
                    platform_fixes = fix_result.get("total_fixes", 0)
                    auto_approved = fix_result.get("auto_approved", 0)
                    auto_applied = fix_result.get("auto_applied", 0)
                    site_result["actions"].append({
                        "step": "platform_fix_scan",
                        "status": "completed",
                        "platform": website.site_type,
                        "fixes_generated": platform_fixes,
                        "auto_approved": auto_approved,
                        "auto_applied": auto_applied,
                        "autonomy_mode": website.autonomy_mode,
                    })
                    print(f"[Overseer]   Platform scan done: {platform_fixes} fixes (auto-approved: {auto_approved}, auto-applied: {auto_applied})")
                except Exception as e:
                    print(f"[Overseer]   Platform scan failed: {e}")
                    site_result["actions"].append({"step": "platform_fix_scan", "status": "failed", "error": str(e)})

            # ─── Step 5: Refresh Strategies for Striking Distance Keywords ───
            try:
                tracked = db.query(TrackedKeyword).filter(
                    TrackedKeyword.website_id == website.id,
                    TrackedKeyword.status == "tracking"
                ).all()

                # Focus on striking distance keywords (position 4-20)
                striking = [tk for tk in tracked if tk.current_position and 4 <= tk.current_position <= 20]

                if striking:
                    print(f"[Overseer] Step 5: Refreshing strategies for {len(striking)} striking distance keywords...")
                    _set_phase(status_key, "strategy", f"Refreshing strategies for {website.domain}")
                    _set_phase(website.id, "strategy", f"Refreshing strategies for {website.domain}")
                    from road_to_one import generate_road_to_one_strategy
                    refreshed = 0
                    for tk in striking[:3]:  # Max 3 per cycle to control API costs
                        try:
                            await generate_road_to_one_strategy(website.id, tk.id)
                            refreshed += 1
                            await asyncio.sleep(2)  # Rate limit
                        except:
                            pass
                    site_result["actions"].append({
                        "step": "strategy_refresh",
                        "status": "completed",
                        "keywords_refreshed": refreshed,
                        "striking_distance_count": len(striking),
                    })
                    print(f"[Overseer]   Strategies refreshed: {refreshed}")
                else:
                    site_result["actions"].append({"step": "strategy_refresh", "status": "skipped", "reason": "No striking distance keywords"})
            except Exception as e:
                print(f"[Overseer]   Strategy refresh failed: {e}")
                site_result["actions"].append({"step": "strategy_refresh", "status": "failed", "error": str(e)})

            # ─── Summary ───
            total_pending = db.query(ProposedFix).filter(
                ProposedFix.website_id == website.id,
                ProposedFix.status == "pending"
            ).count()

            site_result["total_pending_fixes"] = total_pending
            site_result["completed_at"] = datetime.utcnow().isoformat()
            results["websites_processed"] += 1
            results["actions"].append(site_result)

            print(f"[Overseer] ═══ Cycle complete for {website.domain} — {total_pending} pending fixes ═══\n")

        return results

    except Exception as e:
        print(f"[Overseer] Critical error: {e}")
        import traceback
        traceback.print_exc()
        try:
            _finish(website_id if website_id is not None else "all", error=str(e))
            if website_id is not None:
                _finish(website_id, error=str(e))
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        try:
            key = website_id if website_id is not None else "all"
            if _overseer_status.get(key, {}).get("phase") not in ("idle", None):
                _finish(key)
            if website_id is not None and _overseer_status.get(website_id, {}).get("phase") not in ("idle", None):
                _finish(website_id)
        except Exception:
            pass
        db.close()


def run_overseer_background(website_id: int = None):
    """Background task wrapper for the overseer."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_overseer_cycle(website_id))
        loop.close()
        print(f"[Overseer] Background cycle complete: {json.dumps(result, indent=2, default=str)[:500]}")
    except Exception as e:
        print(f"[Overseer] Background cycle failed: {e}")
        import traceback
        traceback.print_exc()
