# backend/ai_strategist.py - AI SEO Strategist
# The "general" that sees the entire battlefield. Generates master strategy,
# manages keyword portfolio, creates weekly action plans, and coordinates
# with Road to #1 individual keyword workers.
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, Integration, ProposedFix, StrategistResult
)

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


def _build_full_intelligence(website_id: int, db: Session) -> Dict[str, Any]:
    """
    Gather EVERY piece of intelligence about this website.
    This is the complete briefing document for the strategist.
    """
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        return {"error": "Website not found"}

    intel = {"domain": website.domain, "site_type": website.site_type}

    # ─── Audit Intelligence ───
    latest_audit = db.query(AuditReport).filter(
        AuditReport.website_id == website_id
    ).order_by(AuditReport.audit_date.desc()).first()

    prev_audit = None
    if latest_audit:
        prev_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id,
            AuditReport.id != latest_audit.id
        ).order_by(AuditReport.audit_date.desc()).first()

    if latest_audit:
        findings = latest_audit.detailed_findings or {}
        issues = findings.get("issues", [])
        cwv = findings.get("raw_data", {}).get("core_web_vitals", {})
        intel["audit"] = {
            "health_score": latest_audit.health_score,
            "prev_score": prev_audit.health_score if prev_audit else None,
            "technical": latest_audit.technical_score,
            "content": latest_audit.content_score,
            "performance": latest_audit.performance_score,
            "mobile": latest_audit.mobile_score,
            "security": latest_audit.security_score,
            "total_issues": latest_audit.total_issues,
            "critical_issues": latest_audit.critical_issues,
            "pages_crawled": findings.get("site_stats", {}).get("pages_crawled", 0),
            "avg_word_count": findings.get("site_stats", {}).get("avg_word_count", 0),
            "cwv": cwv,
            "top_issues": [
                {"type": i.get("issue_type",""), "severity": i.get("severity",""),
                 "count": i.get("affected_count",1), "detail": i.get("details","")[:100]}
                for i in issues[:15]
            ],
            "audit_date": latest_audit.audit_date.isoformat(),
        }
    else:
        intel["audit"] = None

    # ─── Keyword Intelligence ───
    latest_snap = db.query(KeywordSnapshot).filter(
        KeywordSnapshot.website_id == website_id
    ).order_by(KeywordSnapshot.snapshot_date.desc()).first()

    first_snap = db.query(KeywordSnapshot).filter(
        KeywordSnapshot.website_id == website_id
    ).order_by(KeywordSnapshot.snapshot_date.asc()).first()

    if latest_snap and latest_snap.keyword_data:
        kws = [{k: v for k, v in kw.items() if not k.startswith('_')} for kw in latest_snap.keyword_data]

        # Position distribution
        top3 = [k for k in kws if k.get("position", 100) <= 3]
        top10 = [k for k in kws if k.get("position", 100) <= 10]
        top20 = [k for k in kws if k.get("position", 100) <= 20]
        striking = [k for k in kws if 4 <= k.get("position", 100) <= 20]

        intel["keywords"] = {
            "total": latest_snap.total_keywords,
            "clicks": latest_snap.total_clicks,
            "impressions": latest_snap.total_impressions,
            "avg_position": latest_snap.avg_position,
            "top3_count": len(top3),
            "top10_count": len(top10),
            "top20_count": len(top20),
            "striking_distance": len(striking),
            "top_by_clicks": sorted(kws, key=lambda x: x.get("clicks",0), reverse=True)[:10],
            "top_by_impressions": sorted(kws, key=lambda x: x.get("impressions",0), reverse=True)[:10],
            "striking_keywords": sorted(striking, key=lambda x: x.get("impressions",0), reverse=True)[:15],
            "date_from": latest_snap.date_from.strftime("%Y-%m-%d"),
            "date_to": latest_snap.date_to.strftime("%Y-%m-%d"),
        }

        # Since inception
        if first_snap and first_snap.id != latest_snap.id:
            intel["keywords"]["since_inception"] = {
                "started": first_snap.snapshot_date.strftime("%Y-%m-%d"),
                "initial_keywords": first_snap.total_keywords,
                "initial_clicks": first_snap.total_clicks,
                "keywords_growth": latest_snap.total_keywords - first_snap.total_keywords,
                "clicks_growth": latest_snap.total_clicks - first_snap.total_clicks,
                "impressions_growth": latest_snap.total_impressions - first_snap.total_impressions,
                "position_change": round(first_snap.avg_position - latest_snap.avg_position, 1),
            }
    else:
        intel["keywords"] = None

    # ─── Tracked Keywords (Road to #1 portfolio) ───
    tracked = db.query(TrackedKeyword).filter(
        TrackedKeyword.website_id == website_id
    ).all()

    intel["tracked_keywords"] = []
    for tk in tracked:
        strategy = None
        if tk.notes:
            try:
                strategy = json.loads(tk.notes)
            except Exception:
                strategy = {"raw": tk.notes}

        intel["tracked_keywords"].append({
            "keyword": tk.keyword,
            "position": tk.current_position,
            "clicks": tk.current_clicks,
            "impressions": tk.current_impressions,
            "target_url": tk.target_url or tk.ranking_url,
            "ranking_url": tk.ranking_url,
            "has_strategy": bool(tk.notes),
            "strategy_summary": strategy.get("strategy", {}).get("summary", "")[:200] if isinstance(strategy, dict) and strategy.get("strategy") else None,
        })

    # ─── Cannibalization check ───
    cannibalization = []
    if latest_snap and latest_snap.keyword_data:
        from collections import defaultdict
        kw_pages = defaultdict(list)
        for kw in latest_snap.keyword_data:
            q = kw.get("query", "")
            page = kw.get("page", "")
            if q and page:
                kw_pages[q].append({"page": page, "position": kw.get("position",0)})
        for q, pages in kw_pages.items():
            unique = {p["page"]: p for p in pages}
            if len(unique) > 1:
                cannibalization.append({"keyword": q, "pages": list(unique.values())})

    intel["cannibalization"] = cannibalization[:20]

    # ─── Fix History ───
    fix_counts = {}
    for s in ["pending", "approved", "applied", "failed", "rejected"]:
        fix_counts[s] = db.query(ProposedFix).filter(
            ProposedFix.website_id == website_id, ProposedFix.status == s).count()

    fix_types = dict(db.query(ProposedFix.fix_type, func.count(ProposedFix.id)).filter(
        ProposedFix.website_id == website_id, ProposedFix.status == "applied"
    ).group_by(ProposedFix.fix_type).all())

    intel["fixes"] = {**fix_counts, "by_type": fix_types}

    # ─── Hub & Spoke / Content Decay (last saved analysis) ───
    sr = db.query(StrategistResult).filter(StrategistResult.website_id == website_id).first()
    if sr and sr.linking:
        L = sr.linking
        intel["linking"] = {
            "analyzed_at": sr.linking_generated_at.isoformat() if sr.linking_generated_at else None,
            "total_pages": L.get("total_pages", 0),
            "total_internal_links": L.get("total_internal_links", 0),
            "avg_links_per_page": L.get("avg_links_per_page", 0),
            "hubs": [{"url": h.get("url"), "inbound": h.get("inbound", 0)} for h in (L.get("hubs") or [])[:8]],
            "orphans": [{"url": o.get("url"), "inbound": o.get("inbound", 0)} for o in (L.get("orphans") or [])[:10]],
            "top_suggestions": [
                {"from": s.get("from_url"), "to": s.get("to_url"), "anchor": s.get("anchor_text"), "reason": s.get("reason")}
                for s in (L.get("suggestions") or [])[:8]
            ],
        }
    else:
        intel["linking"] = None

    if sr and sr.decay:
        D = sr.decay
        intel["decay"] = {
            "analyzed_at": sr.decay_generated_at.isoformat() if sr.decay_generated_at else None,
            "total_pages_analyzed": D.get("total_pages_analyzed", 0),
            "high_risk_count": len(D.get("high_risk") or []),
            "medium_risk_count": len(D.get("medium_risk") or []),
            "high_risk_samples": [
                {"url": i.get("url"), "days": i.get("days_since_update"), "rec": i.get("recommendation")}
                for i in (D.get("high_risk") or [])[:6]
            ],
        }
    else:
        intel["decay"] = None

    # ─── Integrations ───
    integrations = db.query(Integration).filter(
        Integration.website_id == website_id, Integration.status == "active"
    ).all()
    intel["connected_services"] = [i.integration_type for i in integrations]

    return intel


def _intel_to_text(intel: Dict) -> str:
    """Convert intelligence dict to readable text for the AI prompt."""
    parts = []
    parts.append(f"WEBSITE: {intel['domain']} ({intel['site_type']})")

    audit = intel.get("audit")
    if audit:
        parts.append(f"""
SITE HEALTH (audited {audit['audit_date'][:10]}):
  Score: {audit['health_score']}/100{' (was '+str(audit['prev_score'])+')' if audit.get('prev_score') else ''}
  Technical: {audit['technical']}/100 | Content: {audit['content']}/100 | Performance: {audit['performance']}/100
  Mobile: {audit['mobile']}/100 | Security: {audit['security']}/100
  Issues: {audit['total_issues']} total ({audit['critical_issues']} critical)
  Pages: {audit['pages_crawled']} crawled | Avg word count: {audit.get('avg_word_count', 'N/A')}
  CWV: LCP={audit['cwv'].get('lcp','N/A')}s, CLS={audit['cwv'].get('cls','N/A')}, TBT={audit['cwv'].get('tbt','N/A')}ms

  TOP ISSUES:""")
        for i in audit.get("top_issues", [])[:10]:
            parts.append(f"    [{i['severity']}] {i['type']} ({i['count']} pages)")

    kw = intel.get("keywords")
    if kw:
        parts.append(f"""
ORGANIC SEARCH PERFORMANCE ({kw['date_from']} to {kw['date_to']}):
  Keywords ranking: {kw['total']} | Clicks: {kw['clicks']} | Impressions: {kw['impressions']}
  Avg Position: {kw['avg_position']}
  Distribution: Top 3: {kw['top3_count']} | Top 10: {kw['top10_count']} | Top 20: {kw['top20_count']}
  Striking distance (4-20): {kw['striking_distance']} keywords — BIGGEST OPPORTUNITY

  TOP KEYWORDS BY CLICKS:""")
        for k in kw.get("top_by_clicks", [])[:8]:
            parts.append(f"    \"{k.get('query','')}\" — pos {k.get('position',0)}, {k.get('clicks',0)} clicks, {k.get('impressions',0)} impr")

        parts.append("\n  STRIKING DISTANCE (position 4-20, push to page 1):")
        for k in kw.get("striking_keywords", [])[:10]:
            parts.append(f"    \"{k.get('query','')}\" — pos {k.get('position',0)}, {k.get('impressions',0)} impressions")

        if kw.get("since_inception"):
            si = kw["since_inception"]
            parts.append(f"""
  SINCE TRACKING BEGAN ({si['started']}):
    Keywords: {si['initial_keywords']} → {kw['total']} ({si['keywords_growth']:+d})
    Clicks: {si['initial_clicks']} → {kw['clicks']} ({si['clicks_growth']:+d})
    Position change: {si['position_change']:+.1f} (positive = improved)""")

    tracked = intel.get("tracked_keywords", [])
    if tracked:
        parts.append(f"\nPRIORITY KEYWORDS (Road to #1 — {len(tracked)} tracked):")
        for tk in tracked:
            pos = f"#{tk['position']}" if tk['position'] else "Not ranking"
            parts.append(f"  \"{tk['keyword']}\" — {pos}, {tk.get('clicks',0)} clicks, target: {tk.get('target_url','unset')}")
            if tk.get("strategy_summary"):
                parts.append(f"    Strategy: {tk['strategy_summary']}")

    cann = intel.get("cannibalization", [])
    if cann:
        parts.append(f"\nCANNIBALIZATION WARNINGS ({len(cann)} keywords with multiple ranking pages):")
        for c in cann[:5]:
            pages = ", ".join([f"{p['page']} (pos {p['position']})" for p in c['pages'][:3]])
            parts.append(f"  \"{c['keyword']}\" ranks on: {pages}")

    fixes = intel.get("fixes", {})
    if fixes.get("applied", 0) > 0 or fixes.get("pending", 0) > 0:
        parts.append(f"""
TECHNICAL WORK:
  Applied: {fixes.get('applied',0)} | Pending: {fixes.get('pending',0)} | Failed: {fixes.get('failed',0)}
  By type: {', '.join([f'{t}: {c}' for t,c in fixes.get('by_type',{}).items()]) if fixes.get('by_type') else 'None'}""")

    linking = intel.get("linking")
    if linking:
        parts.append(f"""
HUB & SPOKE INTERNAL LINKING (analyzed {linking.get('analyzed_at','')[:10]}):
  Pages: {linking['total_pages']} | Internal links: {linking['total_internal_links']} | Avg links/page: {linking['avg_links_per_page']}
  Hubs: {len(linking.get('hubs', []))} | Orphans: {len(linking.get('orphans', []))}""")
        if linking.get("hubs"):
            parts.append("  TOP HUB PAGES (strong authority — link from these to priority pages):")
            for h in linking["hubs"][:5]:
                parts.append(f"    {h['url']} ({h['inbound']} inbound)")
        if linking.get("orphans"):
            parts.append("  ORPHAN PAGES (need internal links pointing to them):")
            for o in linking["orphans"][:5]:
                parts.append(f"    {o['url']} ({o['inbound']} inbound)")
        if linking.get("top_suggestions"):
            parts.append("  SUGGESTED LINKS (from AI linking engine):")
            for s in linking["top_suggestions"][:5]:
                parts.append(f"    {s['from']} → {s['to']} anchor=\"{s['anchor']}\" ({s['reason']})")
    else:
        parts.append("\nHUB & SPOKE: not yet analyzed — run the Hub & Spoke audit for linking intelligence.")

    decay = intel.get("decay")
    if decay:
        parts.append(f"""
CONTENT DECAY (analyzed {decay.get('analyzed_at','')[:10]}):
  Pages analyzed: {decay['total_pages_analyzed']} | High risk: {decay['high_risk_count']} | Medium: {decay['medium_risk_count']}""")
        if decay.get("high_risk_samples"):
            parts.append("  HIGH-RISK STALE PAGES:")
            for s in decay["high_risk_samples"][:5]:
                parts.append(f"    {s['url']} — {s['days']}d old → {s['rec']}")

    services = intel.get("connected_services", [])
    parts.append(f"\nCONNECTED: {', '.join(services) if services else 'None'}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# MASTER STRATEGY GENERATION
# ═══════════════════════════════════════════════════════════

async def generate_master_strategy(website_id: int) -> Dict[str, Any]:
    """
    Generate a comprehensive SEO master strategy.
    This is the "general's battle plan" — the overarching strategy
    that all individual keyword tactics must align with.
    """
    db = SessionLocal()
    try:
        intel = _build_full_intelligence(website_id, db)
        if "error" in intel:
            return intel

        intel_text = _intel_to_text(intel)

        if not GEMINI_API_KEY:
            return {"error": "AI API key not configured. Add GOOGLE_GEMINI_API_KEY."}

        prompt = f"""You are a world-class SEO strategist. You've been hired to dramatically increase organic traffic for this website. Based on the complete intelligence below, create a comprehensive SEO master strategy.

{intel_text}

Create a MASTER SEO STRATEGY as a JSON object with this exact structure:
{{
  "executive_summary": "2-3 sentence overview of the situation and primary goal",
  "current_state": {{
    "strengths": ["list 3-5 strengths"],
    "weaknesses": ["list 3-5 weaknesses"],
    "opportunities": ["list 3-5 biggest opportunities"],
    "threats": ["list 2-3 threats/risks"]
  }},
  "strategic_goals": [
    {{"goal": "description", "target": "measurable target", "timeframe": "1/3/6 months", "priority": 1}}
  ],
  "keyword_portfolio": {{
    "primary_keywords": ["top 5 keywords to focus most effort on, with reasoning"],
    "secondary_keywords": ["next 10 keywords"],
    "long_tail_opportunities": ["list emerging long-tail opportunities"],
    "keywords_to_deprioritize": ["keywords not worth effort right now, with reason"],
    "cannibalization_fixes": ["specific fixes for any cannibalization issues"]
  }},
  "content_strategy": {{
    "content_gaps": ["topics we should cover but don't"],
    "content_to_refresh": ["pages that need updating"],
    "content_to_create": ["new content pieces needed"],
    "hub_pages_needed": ["topic hub pages to build"]
  }},
  "technical_priorities": [
    {{"action": "specific technical fix", "impact": "high/medium/low", "effort": "easy/medium/hard"}}
  ],
  "link_strategy": {{
    "internal_linking": ["specific internal linking improvements"],
    "authority_building": ["ways to build domain authority"]
  }},
  "monthly_milestones": [
    {{"month": 1, "targets": ["specific measurable targets"], "actions": ["key actions"]}},
    {{"month": 2, "targets": ["..."], "actions": ["..."]}},
    {{"month": 3, "targets": ["..."], "actions": ["..."]}}
  ],
  "weekly_focus": {{
    "this_week": ["top 5 actions to take THIS week, in priority order"],
    "quick_wins": ["things that can be done in <1 hour with immediate impact"]
  }},
  "risks_and_mitigations": [
    {{"risk": "description", "mitigation": "how to handle it"}}
  ]
}}

Be extremely specific. Use actual keyword names, actual page URLs, actual numbers. No generic advice. Every recommendation must be actionable and tied to the data above."""

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 8000, "temperature": 0.4}
                }
            )
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                try:
                    strategy = json.loads(text)
                except Exception:
                    strategy = {"raw_strategy": text}

                # Save strategy to website
                website = db.query(Website).filter(Website.id == website_id).first()
                if website:
                    # Store in a JSON field — we'll use monthly_traffic as a temp store
                    # (or create a dedicated field later)
                    pass

                return {
                    "strategy": strategy,
                    "intelligence_snapshot": {
                        "health_score": intel.get("audit", {}).get("health_score"),
                        "total_keywords": intel.get("keywords", {}).get("total", 0),
                        "total_clicks": intel.get("keywords", {}).get("clicks", 0),
                        "tracked_keywords": len(intel.get("tracked_keywords", [])),
                        "pending_fixes": intel.get("fixes", {}).get("pending", 0),
                    },
                    "generated_at": datetime.utcnow().isoformat(),
                }
            elif resp.status_code == 429:
                return {"error": "AI rate limited. Enable billing on Gemini or try again later."}
            else:
                return {"error": f"AI API error: {resp.status_code}"}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════
# WEEKLY ACTION PLAN
# ═══════════════════════════════════════════════════════════

async def generate_weekly_plan(website_id: int) -> Dict[str, Any]:
    """Generate a specific action plan for this week based on current data."""
    db = SessionLocal()
    try:
        intel = _build_full_intelligence(website_id, db)
        if "error" in intel:
            return intel

        intel_text = _intel_to_text(intel)

        if not GEMINI_API_KEY:
            return {"error": "AI API key not configured."}

        prompt = f"""You are a hands-on SEO manager. Based on the data below, create a SPECIFIC action plan for THIS WEEK. No generic advice — every task must reference actual keywords, pages, or issues from the data.

{intel_text}

Create a weekly plan as JSON:
{{
  "week_of": "{datetime.utcnow().strftime('%Y-%m-%d')}",
  "priority_score": "overall urgency 1-10",
  "summary": "1 sentence: what we're focusing on this week and why",
  "critical_actions": [
    {{"task": "specific actionable task", "why": "reason tied to data", "estimated_time": "Xh", "expected_impact": "description"}}
  ],
  "keyword_work": [
    {{"keyword": "actual keyword", "current_position": N, "action": "what to do", "target_page": "URL"}}
  ],
  "technical_fixes": [
    {{"fix": "specific fix", "pages_affected": N, "priority": "critical/high/medium"}}
  ],
  "content_tasks": [
    {{"task": "create/update/expand", "topic": "what", "target_keyword": "which keyword this serves"}}
  ],
  "monitoring": ["what to keep an eye on this week"]
}}

Maximum 5 items per category. Only the most impactful work."""

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 3000, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                try:
                    plan = json.loads(text)
                except Exception:
                    plan = {"raw_plan": text}
                return {"plan": plan, "generated_at": datetime.utcnow().isoformat()}
            else:
                return {"error": f"AI API error: {resp.status_code}"}

    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════
# CHAT WITH STRATEGIST (in context of strategy)
# ═══════════════════════════════════════════════════════════

async def chat_with_strategist(
    website_id: int, message: str,
    conversation_history: List[Dict] = None
) -> Dict[str, Any]:
    """Chat with the AI strategist — it knows everything about your site."""
    db = SessionLocal()
    try:
        intel = _build_full_intelligence(website_id, db)
        intel_text = _intel_to_text(intel)

        if not GEMINI_API_KEY:
            return {"error": "AI API key not configured."}

        system_context = f"""You are a world-class SEO strategist managing the SEO for {intel.get('domain', 'this website')}. You have access to ALL the data about this website and its SEO performance. You are the "general" — you see the entire battlefield.

Your role:
1. You manage the overall SEO strategy (the big picture)
2. You coordinate Road to #1 keyword campaigns (the individual battles)
3. You prioritize work based on business impact
4. You identify opportunities and threats before they become problems
5. You give specific, actionable advice tied to real data

CURRENT INTELLIGENCE:
{intel_text}

Rules:
- Always reference actual data, keywords, and pages
- Be specific — no generic SEO advice
- Think about keyword conflicts and cannibalization
- Consider the priority order of keyword targets
- Factor in effort vs impact for every recommendation
- Think like a business owner — traffic must convert to revenue"""

        # Build conversation
        messages = [{"role": "user", "parts": [{"text": system_context + "\n\nRespond to my first question naturally."}]}]
        messages.append({"role": "model", "parts": [{"text": f"I've reviewed all the data for {intel.get('domain', 'your website')}. I can see the full picture — health score, keyword rankings, tracked keywords, technical issues, and fix history. What would you like to discuss?"}]})

        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = "user" if msg.get("role") == "user" else "model"
                messages.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        messages.append({"role": "user", "parts": [{"text": message}]})

        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": messages,
                    "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.5}
                }
            )
            if resp.status_code == 200:
                reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {"response": reply}
            elif resp.status_code == 429:
                return {"response": "I'm temporarily rate-limited. Enable Gemini billing or try again in a minute."}
            else:
                return {"response": f"I encountered an error (status {resp.status_code}). Please try again."}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════
# PORTFOLIO ANALYSIS
# ═══════════════════════════════════════════════════════════

async def analyze_keyword_portfolio(website_id: int) -> Dict[str, Any]:
    """Analyze the keyword portfolio for conflicts, priorities, and gaps."""
    db = SessionLocal()
    try:
        intel = _build_full_intelligence(website_id, db)
        if "error" in intel:
            return intel

        tracked = intel.get("tracked_keywords", [])
        kw_data = intel.get("keywords", {})
        cannibalization = intel.get("cannibalization", [])

        if not tracked:
            return {"error": "No tracked keywords. Add keywords to Road to #1 first."}

        # Check for conflicts between tracked keywords
        conflicts = []
        for i, tk1 in enumerate(tracked):
            for tk2 in tracked[i+1:]:
                # Same target URL = potential conflict
                if tk1.get("target_url") and tk1["target_url"] == tk2.get("target_url"):
                    conflicts.append({
                        "type": "same_target_url",
                        "keywords": [tk1["keyword"], tk2["keyword"]],
                        "url": tk1["target_url"],
                        "recommendation": "These keywords target the same page. Consider whether they should have separate pages or if one should be primary."
                    })

        # Priority scoring
        priority_scored = []
        for tk in tracked:
            score = 0
            # Position factor: closer to #1 = higher priority
            if tk.get("position"):
                if tk["position"] <= 5:
                    score += 30  # Almost there
                elif tk["position"] <= 10:
                    score += 50  # Striking distance, biggest opportunity
                elif tk["position"] <= 20:
                    score += 40  # Page 2, worth pushing
                else:
                    score += 10  # Far away

            # Traffic factor
            score += min(tk.get("impressions", 0) / 100, 30)
            score += min(tk.get("clicks", 0) * 2, 20)

            priority_scored.append({**tk, "priority_score": round(score, 1)})

        priority_scored.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "portfolio_size": len(tracked),
            "priorities": priority_scored,
            "conflicts": conflicts,
            "cannibalization": cannibalization[:10],
            "recommendations": {
                "focus_keywords": [p["keyword"] for p in priority_scored[:3]],
                "deprioritize": [p["keyword"] for p in priority_scored if p["priority_score"] < 20],
            },
            "analyzed_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
