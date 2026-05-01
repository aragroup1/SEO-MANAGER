# backend/keyword_routes.py - API endpoints for keyword tracking
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import asyncio
import os

from database import get_db, Website, TrackedKeyword

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


def _run_keyword_sync(website_id: int, days: int = 3):
    """Background task to sync keywords from Search Console.
    days=3 gives latest rankings, days=28 gives monthly aggregate."""
    try:
        from search_console import fetch_keyword_data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(fetch_keyword_data(website_id, days=days))
        loop.close()

        # Auto-update tracked keywords with latest data
        if "keywords" in result:
            _update_tracked_keywords(website_id, result["keywords"])

        print("[KeywordSync] Completed for website " + str(website_id) + ": "
              + str(result.get("total_keywords", 0)) + " keywords")
    except Exception as e:
        print("[KeywordSync] Failed for website " + str(website_id) + ": " + str(e))
        import traceback
        traceback.print_exc()


def _update_tracked_keywords(website_id: int, keywords: list):
    """Update tracked keywords with latest ranking data from a sync."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
        if not tracked:
            return

        keyword_map = {kw["query"].lower(): kw for kw in keywords}

        for tk in tracked:
            data = keyword_map.get(tk.keyword.lower())
            if data:
                tk.current_position = data.get("position")
                tk.current_clicks = data.get("clicks", 0)
                tk.current_impressions = data.get("impressions", 0)
                tk.current_ctr = data.get("ctr", 0)
                tk.ranking_url = data.get("page", "")
                tk.updated_at = datetime.utcnow()

        db.commit()
    except Exception as e:
        print("[KeywordSync] Error updating tracked keywords: " + str(e))
    finally:
        db.close()


# ─── Sync & Fetch ───

@router.post("/{website_id}/sync")
async def sync_keywords(
    website_id: int,
    days: int = 3,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    background_tasks.add_task(_run_keyword_sync, website_id, days)
    return {"status": "syncing", "message": "Pulling keyword data from Search Console..."}


@router.get("/{website_id}")
async def get_keywords(website_id: int, db: Session = Depends(get_db)):
    from search_console import get_latest_snapshot
    result = await get_latest_snapshot(website_id)
    return result


@router.get("/{website_id}/history")
async def get_keyword_history_endpoint(website_id: int, limit: int = 10, db: Session = Depends(get_db)):
    from search_console import get_keyword_history
    result = await get_keyword_history(website_id, limit=limit)
    return result


@router.get("/{website_id}/keyword-history")
async def get_single_keyword_history(website_id: int, keyword: str, days: int = 90, db: Session = Depends(get_db)):
    """Get daily historical ranking data for a specific keyword."""
    from search_console import fetch_keyword_history_detail
    result = await fetch_keyword_history_detail(website_id, keyword, days=days)
    return result


@router.get("/{website_id}/properties")
async def list_properties(website_id: int, db: Session = Depends(get_db)):
    from search_console import list_gsc_properties
    result = await list_gsc_properties(website_id)
    return result


# ─── Tracked Keywords (Road to #1) ───

@router.get("/{website_id}/tracked")
async def get_tracked_keywords(website_id: int, db: Session = Depends(get_db)):
    tracked = db.query(TrackedKeyword).filter(
        TrackedKeyword.website_id == website_id
    ).order_by(TrackedKeyword.current_position.asc().nullsfirst()).all()

    return {
        "tracked": [
            {
                "id": tk.id,
                "keyword": tk.keyword,
                "current_position": tk.current_position,
                "current_clicks": tk.current_clicks,
                "current_impressions": tk.current_impressions,
                "current_ctr": tk.current_ctr,
                "ranking_url": tk.ranking_url,
                "target_url": tk.target_url,
                "target_position": tk.target_position,
                "notes": tk.notes,
                "status": tk.status,
                "has_strategy": bool(tk.notes and '"strategy"' in (tk.notes or '')),
                "created_at": tk.created_at.isoformat() if tk.created_at else None,
                "updated_at": tk.updated_at.isoformat() if tk.updated_at else None,
            }
            for tk in tracked
        ]
    }


@router.put("/{website_id}/track/{keyword_id}")
async def update_tracked_keyword(website_id: int, keyword_id: int, request: Request, db: Session = Depends(get_db)):
    """Update a tracked keyword (target URL, notes, status)."""
    data = await request.json()
    tk = db.query(TrackedKeyword).filter(
        TrackedKeyword.id == keyword_id,
        TrackedKeyword.website_id == website_id
    ).first()
    if not tk:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")

    if "target_url" in data:
        tk.target_url = data["target_url"]
    if "target_position" in data:
        tk.target_position = data["target_position"]
    if "status" in data:
        tk.status = data["status"]

    tk.updated_at = datetime.utcnow()
    db.commit()
    return {"updated": True}


@router.post("/{website_id}/track")
async def track_keyword(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Add a keyword to tracked list."""
    data = await request.json()
    keyword = data.get("keyword", "").strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")

    # Check if already tracked
    existing = db.query(TrackedKeyword).filter(
        TrackedKeyword.website_id == website_id,
        TrackedKeyword.keyword == keyword
    ).first()

    if existing:
        return {"already_tracked": True, "id": existing.id}

    tk = TrackedKeyword(
        website_id=website_id,
        keyword=keyword,
        current_position=data.get("position"),
        current_clicks=data.get("clicks", 0),
        current_impressions=data.get("impressions", 0),
        current_ctr=data.get("ctr", 0),
        ranking_url=data.get("page", ""),
        target_url=data.get("target_url", ""),
        target_position=data.get("target_position", 1),
    )
    db.add(tk)
    db.commit()
    db.refresh(tk)

    return {"tracked": True, "id": tk.id, "keyword": tk.keyword}


@router.delete("/{website_id}/track/{keyword_id}")
async def untrack_keyword(website_id: int, keyword_id: int, db: Session = Depends(get_db)):
    tk = db.query(TrackedKeyword).filter(
        TrackedKeyword.id == keyword_id,
        TrackedKeyword.website_id == website_id
    ).first()
    if not tk:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")
    db.delete(tk)
    db.commit()
    return {"removed": True}


@router.post("/{website_id}/reset")
async def reset_keyword_data(website_id: int, db: Session = Depends(get_db)):
    """Clear all keyword snapshots and reset GSC property config for this website.
    Use when the wrong GSC property was auto-detected."""
    from database import KeywordSnapshot, Integration

    # Clear snapshots
    count = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).delete()

    # Clear saved GSC property from integration config
    integration = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == "google_search_console"
    ).first()
    if integration:
        config = integration.config or {}
        config.pop("gsc_property", None)
        integration.config = config

    db.commit()
    return {"cleared": count, "message": "Keyword data cleared. Sync again to pull fresh data."}


# ─── Keyword Research ───

@router.post("/{website_id}/research")
async def research_keywords(website_id: int, request: Request, db: Session = Depends(get_db)):
    """AI-powered keyword research from a seed keyword."""
    data = await request.json()
    seed = data.get("seed_keyword", "").strip()
    if not seed:
        raise HTTPException(status_code=400, detail="seed_keyword is required")

    country = data.get("country", "GB")
    niche = data.get("niche", "")

    website = db.query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else ""

    # Get current ranking keywords to avoid suggesting duplicates
    from database import KeywordSnapshot
    latest = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc())\
        .first()

    current_keywords = []
    if latest and latest.keyword_data:
        current_keywords = [kw["query"] for kw in latest.keyword_data[:100]]

    from keyword_research import run_keyword_research
    result = await run_keyword_research(
        seed_keyword=seed,
        domain=domain,
        country=country,
        niche=niche,
        current_keywords=current_keywords,
    )

    return result


# ─── Road to #1 Strategy ───

def _run_strategy_task(website_id: int, keyword_id: int):
    """Background task to generate Road to #1 strategy."""
    try:
        from road_to_one import generate_road_to_one_strategy
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_road_to_one_strategy(website_id, keyword_id))
        loop.close()
        print("[RoadTo1] Strategy completed for keyword_id " + str(keyword_id))
    except Exception as e:
        print("[RoadTo1] Strategy failed: " + str(e))
        import traceback
        traceback.print_exc()


@router.post("/{website_id}/track/{keyword_id}/strategy")
async def generate_strategy(
    website_id: int,
    keyword_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate a Road to #1 strategy for a tracked keyword."""
    tk = db.query(TrackedKeyword).filter(
        TrackedKeyword.id == keyword_id,
        TrackedKeyword.website_id == website_id
    ).first()
    if not tk:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")

    background_tasks.add_task(_run_strategy_task, website_id, keyword_id)

    return {
        "status": "generating",
        "message": "Generating Road to #1 strategy for '" + tk.keyword + "'. Analyzing competitors — takes 30-60 seconds."
    }


@router.get("/{website_id}/track/{keyword_id}/strategy")
async def get_strategy(website_id: int, keyword_id: int, db: Session = Depends(get_db)):
    """Get the saved strategy for a tracked keyword."""
    import json as json_mod
    tk = db.query(TrackedKeyword).filter(
        TrackedKeyword.id == keyword_id,
        TrackedKeyword.website_id == website_id
    ).first()
    if not tk:
        raise HTTPException(status_code=404, detail="Tracked keyword not found")

    if not tk.notes:
        return {"strategy": None, "message": "No strategy generated yet."}

    try:
        data = json_mod.loads(tk.notes)
        return {
            "keyword": tk.keyword,
            "current_position": tk.current_position,
            "strategy": data.get("strategy"),
            "competitors": data.get("competitors", []),
            "your_page": data.get("your_page"),
            "generated_at": data.get("generated_at"),
        }
    except Exception:
        return {"strategy": None, "notes": tk.notes}


# ─── Live Rankings via Serper.dev (on-demand, 6h cache) ───

@router.post("/{website_id}/refresh-live")
async def refresh_live_rankings(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch real-time SERP positions for tracked keywords via Serper.dev.
    Cached 6h per keyword. Pass {"force": true} to bypass cache."""
    import httpx
    from datetime import datetime, timedelta

    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    if not SERPER_API_KEY:
        return {"error": "SERPER_API_KEY not configured", "message": "Add SERPER_API_KEY to Railway env vars (get one at serper.dev)."}

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    force = bool(body.get("force"))
    keyword_ids = body.get("keyword_ids")  # optional list to refresh specific ones
    country = (body.get("country") or "gb").lower()

    q = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id)
    if keyword_ids:
        q = q.filter(TrackedKeyword.id.in_(keyword_ids))
    tracked = q.all()
    if not tracked:
        return {"updated": 0, "skipped": 0, "message": "No tracked keywords."}

    domain = (website.domain or "").lower().replace("https://", "").replace("http://", "").rstrip("/")
    if not domain:
        return {"error": "Website has no domain"}

    cache_cutoff = datetime.utcnow() - timedelta(hours=6)
    updated_count = 0
    skipped_count = 0
    results = []

    async with httpx.AsyncClient(timeout=20) as client:
        for tk in tracked:
            if not force and tk.updated_at and tk.updated_at > cache_cutoff:
                skipped_count += 1
                results.append({"id": tk.id, "keyword": tk.keyword, "status": "cached", "position": tk.current_position, "url": tk.ranking_url})
                continue
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": tk.keyword, "gl": country, "num": 100}
                )
                if resp.status_code != 200:
                    print(f"[Serper] {tk.keyword}: HTTP {resp.status_code} {resp.text[:200]}")
                    results.append({"id": tk.id, "keyword": tk.keyword, "status": "error", "message": f"HTTP {resp.status_code}"})
                    continue
                data = resp.json()
                organic = data.get("organic", [])
                found_pos = None
                found_url = None
                for item in organic:
                    link = (item.get("link") or "").lower()
                    if domain in link:
                        found_pos = item.get("position")
                        found_url = item.get("link")
                        break
                if found_pos:
                    tk.current_position = float(found_pos)
                    tk.ranking_url = found_url
                else:
                    tk.current_position = None
                    tk.ranking_url = None
                tk.updated_at = datetime.utcnow()
                updated_count += 1

                # Append to persistent history (never deleted on untrack)
                from database import SerpRankingHistory
                db.add(SerpRankingHistory(
                    website_id=website_id,
                    keyword=tk.keyword,
                    position=float(found_pos) if found_pos else None,
                    ranking_url=found_url,
                    country=country,
                    source="serper",
                ))

                results.append({"id": tk.id, "keyword": tk.keyword, "status": "updated", "position": found_pos, "url": found_url})
                print(f"[Serper] {tk.keyword}: #{found_pos or 'N/R'} -> {found_url or '-'}")
            except Exception as e:
                print(f"[Serper] {tk.keyword} error: {e}")
                results.append({"id": tk.id, "keyword": tk.keyword, "status": "error", "message": str(e)})

    db.commit()
    return {
        "updated": updated_count,
        "skipped": skipped_count,
        "total": len(tracked),
        "source": "serper",
        "results": results,
    }


# ─── SERP History (persistent Serper.dev rankings over time) ───

@router.get("/{website_id}/serp-history")
async def get_serp_history(website_id: int, keyword: str, days: int = 90, db: Session = Depends(get_db)):
    """Persistent SERP history for a keyword (from Serper.dev polls)."""
    from datetime import timedelta
    from database import SerpRankingHistory
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.query(SerpRankingHistory).filter(
        SerpRankingHistory.website_id == website_id,
        SerpRankingHistory.keyword == keyword.strip().lower(),
        SerpRankingHistory.checked_at >= cutoff,
    ).order_by(SerpRankingHistory.checked_at.asc()).all()
    return {
        "keyword": keyword,
        "history": [
            {
                "date": r.checked_at.isoformat(),
                "position": r.position,
                "url": r.ranking_url,
                "country": r.country,
                "source": r.source,
            } for r in rows
        ]
    }


@router.post("/{website_id}/check-serp")
async def check_serp_for_keywords(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Check Serper.dev SERP positions for any list of keyword strings (not just tracked).
    Always writes to SerpRankingHistory — data is permanent."""
    import httpx
    from database import SerpRankingHistory

    SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
    if not SERPER_API_KEY:
        return {"error": "SERPER_API_KEY not configured"}

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    body = await request.json()
    keywords = [k.strip() for k in body.get("keywords", []) if k and k.strip()]
    country = (body.get("country") or "gb").lower()
    if not keywords:
        return {"checked": 0, "results": []}

    domain = (website.domain or "").lower().replace("https://", "").replace("http://", "").rstrip("/")
    results = []

    async with httpx.AsyncClient(timeout=20) as client:
        for kw in keywords[:50]:  # cap to control cost
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
                    json={"q": kw, "gl": country, "num": 100}
                )
                if resp.status_code != 200:
                    results.append({"keyword": kw, "status": "error", "message": f"HTTP {resp.status_code}"})
                    continue
                organic = resp.json().get("organic", [])
                found_pos = None
                found_url = None
                for item in organic:
                    link = (item.get("link") or "").lower()
                    if domain and domain in link:
                        found_pos = item.get("position")
                        found_url = item.get("link")
                        break
                db.add(SerpRankingHistory(
                    website_id=website_id,
                    keyword=kw.lower(),
                    position=float(found_pos) if found_pos else None,
                    ranking_url=found_url,
                    country=country,
                    source="serper",
                ))
                results.append({"keyword": kw, "position": found_pos, "url": found_url, "status": "checked"})
                print(f"[Serper] {kw}: #{found_pos or 'N/R'}")
            except Exception as e:
                results.append({"keyword": kw, "status": "error", "message": str(e)})

    db.commit()
    return {"checked": len(results), "source": "serper", "results": results}


# ─── Stored Volumes (read all persisted volumes for a site) ───

@router.get("/{website_id}/stored-volumes")
async def get_stored_volumes(website_id: int, country: str = "GB", db: Session = Depends(get_db)):
    """Return every persisted volume row for this site — historical data, never deleted."""
    from database import KeywordVolume
    rows = db.query(KeywordVolume).filter(
        KeywordVolume.website_id == website_id,
        KeywordVolume.country == country,
    ).order_by(KeywordVolume.year_month.desc(), KeywordVolume.keyword.asc()).all()
    return {
        "country": country,
        "total": len(rows),
        "volumes": [
            {
                "keyword": r.keyword,
                "year_month": r.year_month,
                "search_volume": r.search_volume,
                "competition": r.competition,
                "cpc": r.cpc,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            } for r in rows
        ]
    }


# ─── Search Volume Lookup (DataForSEO) with Daily Cache ───

@router.post("/{website_id}/search-volumes")
async def get_search_volumes(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch search volumes with persistent monthly storage (KeywordVolume table).
    Only calls DataForSEO once per month per (keyword, country). All historical
    volumes are kept forever — never overwritten or deleted."""
    import base64
    from datetime import date
    from database import KeywordVolume

    data = await request.json()
    keywords = data.get("keywords", [])
    country = data.get("country", "GB")

    if not keywords:
        return {"volumes": {}, "source": "none"}

    current_month = str(date.today())[:7]
    kw_lower = [k.strip().lower() for k in keywords if k and k.strip()]

    # ─── Read persistent store first ───
    existing = db.query(KeywordVolume).filter(
        KeywordVolume.website_id == website_id,
        KeywordVolume.country == country,
        KeywordVolume.year_month == current_month,
        KeywordVolume.keyword.in_(kw_lower),
    ).all()
    volumes = {
        v.keyword: {"search_volume": v.search_volume, "competition": v.competition, "cpc": v.cpc}
        for v in existing
    }
    missing = [k for k in kw_lower if k not in volumes]

    # If everything's already stored for this month, return early.
    if not missing:
        print(f"[Volumes] All {len(volumes)} keywords already stored for {current_month}")
        return {"volumes": volumes, "source": "stored", "total": len(volumes), "cached_month": current_month}

    DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN", "")
    DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD", "")

    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return {"volumes": {}, "source": "not_configured", "message": "DataForSEO credentials not set. Add DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables."}

    location_map = {
        "GB": 2826, "US": 2840, "CA": 2124, "AU": 2036,
        "DE": 2276, "FR": 2250, "IN": 2356, "BR": 2076,
    }
    location_code = location_map.get(country, 2826)

    # Only fetch what we don't already have stored for this month (cap at 100)
    kw_batch = missing[:100]

    try:
        auth = base64.b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json"
                },
                json=[{
                    "keywords": kw_batch,
                    "location_code": location_code,
                    "language_code": "en",
                }]
            )

            if resp.status_code == 200:
                api_data = resp.json()
                # Check for task-level errors (402 = no balance, 40200 = payment required)
                tasks = api_data.get("tasks", [])
                if tasks and tasks[0].get("status_code") != 20000:
                    task_code = tasks[0].get("status_code", 0)
                    error_msg = tasks[0].get("status_message", "Unknown task error")
                    if task_code == 40200 or task_code == 40201:
                        print(f"[DataForSEO] No balance (status {task_code}). Add funds at dataforseo.com/account")
                        return {"volumes": {}, "source": "error", "message": "DataForSEO account has no balance. Add funds at dataforseo.com → Dashboard → Balance."}
                    print(f"[DataForSEO] Task error: {task_code} {error_msg}")
                    return {"volumes": {}, "source": "error", "message": f"DataForSEO error {task_code}: {error_msg}"}

                results = tasks[0].get("result", []) if tasks else []

                fresh = {}
                for r in results:
                    if r and r.get("keyword"):
                        try:
                            comp = float(r.get("competition") or 0)
                            cpc = float(r.get("cpc") or 0)
                        except (ValueError, TypeError):
                            comp = 0
                            cpc = 0
                        fresh[r["keyword"].lower()] = {
                            "search_volume": r.get("search_volume") or 0,
                            "competition": round(comp * 100),
                            "cpc": round(cpc, 2),
                        }

                print(f"[DataForSEO] Got volumes for {len(fresh)}/{len(kw_batch)} keywords")

                # ─── Persist to KeywordVolume table (one row per kw per month) ───
                try:
                    for kw_lc, v in fresh.items():
                        db.add(KeywordVolume(
                            website_id=website_id,
                            keyword=kw_lc,
                            country=country,
                            year_month=current_month,
                            search_volume=v["search_volume"],
                            competition=v["competition"],
                            cpc=v["cpc"],
                            source="dataforseo",
                        ))
                    db.commit()
                    print(f"[DataForSEO] Persisted {len(fresh)} volumes for {current_month}")
                except Exception as save_err:
                    db.rollback()
                    print(f"[DataForSEO] Persist error (non-fatal): {save_err}")

                volumes.update(fresh)
                return {"volumes": volumes, "source": "dataforseo", "total": len(volumes), "fetched": len(fresh), "from_store": len(volumes) - len(fresh)}
            elif resp.status_code == 401:
                print(f"[DataForSEO] Auth failed (401). Check login email and API password (not account password).")
                return {"volumes": {}, "source": "error", "message": "DataForSEO authentication failed. Use your API password from dataforseo.com/account, not your login password."}
            elif resp.status_code == 402:
                print(f"[DataForSEO] Payment required (402). Add funds at dataforseo.com")
                return {"volumes": {}, "source": "error", "message": "DataForSEO account has no balance. Add funds at dataforseo.com → Dashboard → Balance."}
            else:
                error_text = resp.text[:300]
                print(f"[DataForSEO] Error: {resp.status_code} {error_text}")
                return {"volumes": {}, "source": "error", "message": f"DataForSEO API error {resp.status_code}: {error_text}"}
    except Exception as e:
        print(f"[DataForSEO] Error: {e}")
        return {"volumes": {}, "source": "error", "message": str(e)}


@router.get("/test-dataforseo")
async def test_dataforseo():
    """Quick test to check if DataForSEO credentials work."""
    import base64
    import httpx

    login = os.getenv("DATAFORSEO_LOGIN", "")
    password = os.getenv("DATAFORSEO_PASSWORD", "")

    if not login or not password:
        return {"status": "not_configured", "login_set": bool(login), "password_set": bool(password)}

    try:
        auth = base64.b64encode(f"{login}:{password}".encode()).decode()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"keywords": ["test"], "location_code": 2826, "language_code": "en"}]
            )
            return {
                "status_code": resp.status_code,
                "response": resp.json() if resp.status_code == 200 else resp.text[:500],
                "login_used": login[:3] + "***",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── Keyword Clustering & Intent (Gemini-powered) ───

class _ClusterReq(BaseModel):
    keywords: List[str]
    target_clusters: Optional[int] = None


class _IntentReq(BaseModel):
    queries: List[str]


@router.post("/cluster")
async def cluster_keywords_endpoint(req: _ClusterReq):
    """Group keywords into topical clusters with a representative head term per cluster."""
    if not req.keywords:
        raise HTTPException(status_code=400, detail="keywords list is empty")
    try:
        from keyword_clustering import cluster_keywords
        return await cluster_keywords(req.keywords, req.target_clusters)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clustering failed: {e}")


@router.post("/intent")
async def classify_intent_endpoint(req: _IntentReq):
    """Classify search intent (informational/navigational/transactional/commercial) for each query."""
    if not req.queries:
        raise HTTPException(status_code=400, detail="queries list is empty")
    try:
        from keyword_clustering import classify_intent
        return await classify_intent(req.queries)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent classification failed: {e}")

