# backend/keyword_routes.py - API endpoints for keyword tracking
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import Optional
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
    except:
        return {"strategy": None, "notes": tk.notes}


# ─── Search Volume Lookup (DataForSEO) with Daily Cache ───

@router.post("/{website_id}/search-volumes")
async def get_search_volumes(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Fetch search volumes with MONTHLY caching to control DataForSEO costs.
    Only calls DataForSEO API once per month per website. Cached in database."""
    import base64
    from datetime import date

    data = await request.json()
    keywords = data.get("keywords", [])
    country = data.get("country", "GB")

    if not keywords:
        return {"volumes": {}, "source": "none"}

    # ─── Check cache first (monthly) ───
    website = db.query(Website).filter(Website.id == website_id).first()
    if website:
        from database import KeywordSnapshot
        latest = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest:
            cached = latest.keyword_data
            if isinstance(cached, list) and cached and cached[0].get("_volume_cache_date"):
                cache_date = cached[0].get("_volume_cache_date", "")
                # Monthly cache: check if same year-month
                today = date.today()
                cache_month = cache_date[:7] if len(cache_date) >= 7 else ""
                current_month = str(today)[:7]
                if cache_month == current_month:
                    # Return cached volumes
                    volumes = {}
                    for kw in cached:
                        if kw.get("_sv") is not None:
                            volumes[kw["query"].lower()] = {
                                "search_volume": kw.get("_sv", 0),
                                "competition": kw.get("_comp", 0),
                                "cpc": kw.get("_cpc", 0),
                            }
                    if volumes:
                        print(f"[DataForSEO] Returning monthly cached volumes ({len(volumes)} keywords, cached {cache_date})")
                        return {"volumes": volumes, "source": "dataforseo_cached", "total": len(volumes), "cached_date": cache_date}

    DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN", "")
    DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD", "")

    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return {"volumes": {}, "source": "not_configured", "message": "DataForSEO credentials not set. Add DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables."}

    location_map = {
        "GB": 2826, "US": 2840, "CA": 2124, "AU": 2036,
        "DE": 2276, "FR": 2250, "IN": 2356, "BR": 2076,
    }
    location_code = location_map.get(country, 2826)

    # Limit to 100 keywords per request to control costs
    kw_batch = [k.strip() for k in keywords[:100] if k.strip()]

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

                volumes = {}
                for r in results:
                    if r and r.get("keyword"):
                        try:
                            comp = float(r.get("competition") or 0)
                            cpc = float(r.get("cpc") or 0)
                        except (ValueError, TypeError):
                            comp = 0
                            cpc = 0
                        volumes[r["keyword"].lower()] = {
                            "search_volume": r.get("search_volume") or 0,
                            "competition": round(comp * 100),
                            "cpc": round(cpc, 2),
                        }

                print(f"[DataForSEO] Got volumes for {len(volumes)}/{len(kw_batch)} keywords")

                # ─── Save to monthly cache ───
                try:
                    from database import KeywordSnapshot
                    latest = db.query(KeywordSnapshot).filter(
                        KeywordSnapshot.website_id == website_id
                    ).order_by(KeywordSnapshot.snapshot_date.desc()).first()
                    if latest and latest.keyword_data:
                        updated_kw = []
                        for kw in latest.keyword_data:
                            q = kw.get("query", "").lower()
                            if q in volumes:
                                kw["_sv"] = volumes[q]["search_volume"]
                                kw["_comp"] = volumes[q]["competition"]
                                kw["_cpc"] = volumes[q]["cpc"]
                            kw["_volume_cache_date"] = str(date.today())
                            updated_kw.append(kw)
                        latest.keyword_data = updated_kw
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(latest, "keyword_data")
                        db.commit()
                        print(f"[DataForSEO] Cached volumes for this month")
                except Exception as cache_err:
                    print(f"[DataForSEO] Cache save error (non-fatal): {cache_err}")

                return {"volumes": volumes, "source": "dataforseo", "total": len(volumes)}
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
