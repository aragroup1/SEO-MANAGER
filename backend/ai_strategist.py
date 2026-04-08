# backend/ai_strategist.py - AI SEO Strategist Chat
# Context-aware chat that knows everything about the user's website
import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, Integration, ProposedFix
)

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


def _build_website_context(website_id: int, db: Session) -> str:
    """Build a comprehensive context string about the website for the AI."""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        return "Website not found."

    context_parts = []

    # ─── Website basics ───
    context_parts.append(f"""
WEBSITE: {website.domain}
Type: {website.site_type}
Created: {website.created_at}
""")

    # ─── Latest Audit ───
    latest_audit = db.query(AuditReport)\
        .filter(AuditReport.website_id == website_id)\
        .order_by(AuditReport.audit_date.desc()).first()

    if latest_audit:
        findings = latest_audit.detailed_findings or {}
        issues = findings.get("issues", [])
        site_stats = findings.get("site_stats", {})

        context_parts.append(f"""
LATEST SEO AUDIT (Date: {latest_audit.audit_date}):
- Health Score: {latest_audit.health_score}/100
- Technical: {latest_audit.technical_score}/100
- Content: {latest_audit.content_score}/100
- Performance: {latest_audit.performance_score}/100
- Mobile: {latest_audit.mobile_score}/100
- Security: {latest_audit.security_score}/100
- Total Issues: {latest_audit.total_issues} (Critical: {latest_audit.critical_issues}, Errors: {latest_audit.errors}, Warnings: {latest_audit.warnings})
- Pages Crawled: {site_stats.get('pages_crawled', 'N/A')}
- Avg Word Count: {site_stats.get('avg_word_count', 'N/A')}
- Avg Response Time: {site_stats.get('avg_response_time_ms', 'N/A')}ms

Top Issues:""")
        for issue in issues[:10]:
            context_parts.append(f"  - [{issue.get('severity', '')}] {issue.get('issue_type', '')}: {issue.get('title', '')} (affects {issue.get('affected_count', 1)} pages)")

    # ─── Keyword Rankings ───
    latest_snapshot = db.query(KeywordSnapshot)\
        .filter(KeywordSnapshot.website_id == website_id)\
        .order_by(KeywordSnapshot.snapshot_date.desc()).first()

    if latest_snapshot:
        keywords = latest_snapshot.keyword_data or []
        context_parts.append(f"""
KEYWORD RANKINGS (Period: {latest_snapshot.date_from} to {latest_snapshot.date_to}):
- Total Keywords: {latest_snapshot.total_keywords}
- Total Clicks: {latest_snapshot.total_clicks}
- Total Impressions: {latest_snapshot.total_impressions}
- Avg Position: {latest_snapshot.avg_position}
- Avg CTR: {latest_snapshot.avg_ctr}%
- GSC Property: {latest_snapshot.gsc_property}

Top 20 Keywords by Clicks:""")
        for kw in keywords[:20]:
            context_parts.append(f"  - \"{kw.get('query', '')}\" — Pos: {kw.get('position', '')}, Clicks: {kw.get('clicks', 0)}, Impressions: {kw.get('impressions', 0)}, CTR: {kw.get('ctr', 0)}%, Country: {kw.get('country', 'N/A')}")

    # ─── Tracked Keywords (Road to #1) ───
    tracked = db.query(TrackedKeyword)\
        .filter(TrackedKeyword.website_id == website_id).all()

    if tracked:
        context_parts.append("\nTRACKED KEYWORDS (Road to #1):")
        for tk in tracked:
            strategy_info = ""
            if tk.notes:
                try:
                    notes = json.loads(tk.notes)
                    if "strategy" in notes:
                        s = notes["strategy"]
                        strategy_info = f" | Strategy: {s.get('summary', '')[:100]}"
                except:
                    pass
            context_parts.append(f"  - \"{tk.keyword}\" — Current Pos: {tk.current_position or 'Not ranking'}, Target: #{tk.target_position}, Target URL: {tk.target_url or tk.ranking_url or 'Not set'}{strategy_info}")

    # ─── Integrations ───
    integrations = db.query(Integration)\
        .filter(Integration.website_id == website_id).all()

    if integrations:
        context_parts.append("\nCONNECTED INTEGRATIONS:")
        for integ in integrations:
            context_parts.append(f"  - {integ.integration_type}: {integ.status} ({integ.account_name or 'N/A'})")

    # ─── Pending Fixes ───
    pending_fixes = db.query(ProposedFix)\
        .filter(ProposedFix.website_id == website_id, ProposedFix.status == "pending")\
        .count()
    applied_fixes = db.query(ProposedFix)\
        .filter(ProposedFix.website_id == website_id, ProposedFix.status == "applied")\
        .count()
    failed_fixes = db.query(ProposedFix)\
        .filter(ProposedFix.website_id == website_id, ProposedFix.status == "failed")\
        .count()

    context_parts.append(f"""
AUTO-FIX STATUS:
- Pending fixes: {pending_fixes}
- Applied fixes: {applied_fixes}
- Failed fixes: {failed_fixes}
""")

    # ─── Cannibalization Detection ───
    if latest_snapshot and latest_snapshot.keyword_data:
        # Check for keywords ranking on multiple pages
        from collections import defaultdict
        page_keyword_map = defaultdict(list)
        keyword_page_map = defaultdict(list)

        # We need query+page data — check if stored
        for kw in latest_snapshot.keyword_data:
            query = kw.get("query", "")
            page = kw.get("page", "")
            if query and page:
                keyword_page_map[query].append(page)

        cannibalizing = {q: pages for q, pages in keyword_page_map.items() if len(set(pages)) > 1}
        if cannibalizing:
            context_parts.append("\nCANNIBALIZATION WARNINGS (multiple pages ranking for same keyword):")
            for q, pages in list(cannibalizing.items())[:5]:
                context_parts.append(f"  - \"{q}\" ranks on: {', '.join(set(pages))}")

    return "\n".join(context_parts)


async def chat_with_strategist(
    website_id: int,
    message: str,
    conversation_history: List[Dict] = None,
) -> Dict[str, Any]:
    """Chat with the AI SEO strategist."""
    if not GEMINI_API_KEY:
        return {"error": "No AI API key configured"}

    db = SessionLocal()
    try:
        # Build context
        context = _build_website_context(website_id, db)

        system_prompt = f"""You are an elite SEO strategist with 15 years of experience. You have deep expertise in:
- Technical SEO (Core Web Vitals, crawl budget, indexation, structured data)
- Content strategy (keyword targeting, cannibalization, topic clusters, E-E-A-T)
- Link building and authority
- Local SEO
- Generative Engine Optimization (GEO) — optimizing for AI search (ChatGPT, Perplexity, Google AI Overviews)
- E-commerce SEO (Shopify, WooCommerce)
- International SEO

You have full access to this website's data:

{context}

RULES:
- Give specific, actionable advice based on the actual data above
- Reference specific keywords, pages, and metrics from the data
- Prioritize recommendations by impact
- Be direct and practical — no fluff
- If asked about something not in the data, say what additional data would help
- When discussing cannibalization, check if multiple pages rank for the same keyword
- When recommending content, check existing keywords to avoid overlap
- For technical issues, reference the specific audit findings
- Consider the site type ({db.query(Website).filter(Website.id == website_id).first().site_type if db.query(Website).filter(Website.id == website_id).first() else 'unknown'}) when giving platform-specific advice
"""

        # Build messages
        messages = [{"role": "user", "parts": [{"text": system_prompt + "\n\nUser question: " + message}]}]

        if conversation_history:
            # Rebuild conversation for Gemini format
            gemini_messages = []
            for msg in conversation_history[-10:]:  # Last 10 messages
                role = "user" if msg.get("role") == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
            gemini_messages.append({"role": "user", "parts": [{"text": message}]})
            # Prepend system context to first message
            gemini_messages[0]["parts"][0]["text"] = system_prompt + "\n\n" + gemini_messages[0]["parts"][0]["text"]
            messages = gemini_messages

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": messages,
                    "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.4}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                response_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return {
                    "response": response_text,
                    "context_summary": {
                        "health_score": db.query(AuditReport).filter(AuditReport.website_id == website_id).order_by(AuditReport.audit_date.desc()).first().health_score if db.query(AuditReport).filter(AuditReport.website_id == website_id).first() else None,
                        "total_keywords": db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).order_by(KeywordSnapshot.snapshot_date.desc()).first().total_keywords if db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).first() else 0,
                        "tracked_keywords": db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).count(),
                    }
                }
            else:
                return {"error": "AI request failed: " + str(resp.status_code)}

    except Exception as e:
        print(f"[Strategist] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()
