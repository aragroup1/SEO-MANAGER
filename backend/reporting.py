# backend/reporting.py - Enhanced SEO Report Generation
import os
import json
from typing import Dict, Any, List
from datetime import datetime, timedelta
from calendar import monthrange
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, ProposedFix
)

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


async def generate_report_data(website_id: int, month: str = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        month_start, month_end, prev_month_start, prev_month_end = None, None, None, None
        if month:
            try:
                parts = month.split('-')
                year, mo = int(parts[0]), int(parts[1])
                month_start = datetime(year, mo, 1)
                _, last_day = monthrange(year, mo)
                month_end = datetime(year, mo, last_day, 23, 59, 59)
                if mo == 1:
                    prev_month_start = datetime(year - 1, 12, 1)
                    prev_month_end = datetime(year - 1, 12, 31, 23, 59, 59)
                else:
                    _, prev_last = monthrange(year, mo - 1)
                    prev_month_start = datetime(year, mo - 1, 1)
                    prev_month_end = datetime(year, mo - 1, prev_last, 23, 59, 59)
            except:
                pass

        report = {"domain": website.domain, "site_type": website.site_type,
                  "generated_at": datetime.utcnow().isoformat(), "report_month": month or "current"}

        # ─── Audit ───
        aq = db.query(AuditReport).filter(AuditReport.website_id == website_id)
        if month_start: aq = aq.filter(AuditReport.audit_date >= month_start, AuditReport.audit_date <= month_end)
        latest_audit = aq.order_by(AuditReport.audit_date.desc()).first()

        prev_audit = None
        if latest_audit:
            pq = db.query(AuditReport).filter(AuditReport.website_id == website_id, AuditReport.id != latest_audit.id)
            if prev_month_start: pq = pq.filter(AuditReport.audit_date >= prev_month_start, AuditReport.audit_date <= prev_month_end)
            prev_audit = pq.order_by(AuditReport.audit_date.desc()).first()

        if latest_audit:
            findings = latest_audit.detailed_findings or {}
            raw = findings.get("raw_data", {})
            ps = prev_audit.health_score if prev_audit else latest_audit.health_score
            report["audit"] = {
                "health_score": latest_audit.health_score, "previous_score": ps,
                "score_change": round(latest_audit.health_score - ps, 1),
                "technical_score": latest_audit.technical_score, "content_score": latest_audit.content_score,
                "performance_score": latest_audit.performance_score, "mobile_score": latest_audit.mobile_score,
                "security_score": latest_audit.security_score,
                "total_issues": latest_audit.total_issues, "critical_issues": latest_audit.critical_issues,
                "errors": latest_audit.errors, "warnings": latest_audit.warnings,
                "audit_date": latest_audit.audit_date.isoformat(),
                "pages_crawled": findings.get("site_stats", {}).get("pages_crawled", 0),
                "core_web_vitals": raw.get("core_web_vitals", {}),
                "previous_issues": prev_audit.total_issues if prev_audit else latest_audit.total_issues,
                "issues_change": latest_audit.total_issues - (prev_audit.total_issues if prev_audit else latest_audit.total_issues),
                "top_issues": [{"type": i.get("issue_type",""), "severity": i.get("severity",""), "count": i.get("affected_count",1)} for i in findings.get("issues",[])[:10]],
            }
        else:
            report["audit"] = None

        # ─── Keywords with Ranking Changes ───
        kq = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id)
        if month_start: kq = kq.filter(KeywordSnapshot.snapshot_date >= month_start, KeywordSnapshot.snapshot_date <= month_end)
        latest_snap = kq.order_by(KeywordSnapshot.snapshot_date.desc()).first()

        prev_snap = None
        if latest_snap:
            pkq = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id, KeywordSnapshot.id != latest_snap.id)
            if prev_month_start: pkq = pkq.filter(KeywordSnapshot.snapshot_date >= prev_month_start, KeywordSnapshot.snapshot_date <= prev_month_end)
            prev_snap = pkq.order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest_snap:
            kws = latest_snap.keyword_data or []
            clean = [{k: v for k, v in kw.items() if not k.startswith('_')} for kw in kws]
            top3 = len([k for k in clean if k.get("position", 100) <= 3])
            top10 = len([k for k in clean if k.get("position", 100) <= 10])
            top20 = len([k for k in clean if k.get("position", 100) <= 20])

            ranking_changes = []
            if prev_snap and prev_snap.keyword_data:
                prev_map = {kw.get("query","").lower(): kw.get("position",0) for kw in prev_snap.keyword_data}
                for kw in clean[:50]:
                    q = kw.get("query","").lower()
                    pp = prev_map.get(q)
                    cp = kw.get("position", 0)
                    if pp and cp:
                        ch = round(pp - cp, 1)
                        if abs(ch) >= 1:
                            ranking_changes.append({"query": kw.get("query",""), "current": cp, "previous": pp, "change": ch, "clicks": kw.get("clicks",0)})
                ranking_changes.sort(key=lambda x: x["change"], reverse=True)

            report["keywords"] = {
                "total": latest_snap.total_keywords, "total_clicks": latest_snap.total_clicks,
                "total_impressions": latest_snap.total_impressions,
                "avg_position": latest_snap.avg_position, "avg_ctr": latest_snap.avg_ctr,
                "top3": top3, "top10": top10, "top20": top20,
                "prev_total": prev_snap.total_keywords if prev_snap else 0,
                "prev_clicks": prev_snap.total_clicks if prev_snap else 0,
                "prev_impressions": prev_snap.total_impressions if prev_snap else 0,
                "clicks_change": latest_snap.total_clicks - (prev_snap.total_clicks if prev_snap else 0),
                "impressions_change": latest_snap.total_impressions - (prev_snap.total_impressions if prev_snap else 0),
                "keywords_change": latest_snap.total_keywords - (prev_snap.total_keywords if prev_snap else 0),
                "date_from": latest_snap.date_from.strftime("%Y-%m-%d"), "date_to": latest_snap.date_to.strftime("%Y-%m-%d"),
                "top_keywords": [{"query": k["query"], "position": k.get("position",0), "clicks": k.get("clicks",0), "impressions": k.get("impressions",0), "country": k.get("country","")} for k in clean[:15]],
                "ranking_changes": {
                    "improved": [c for c in ranking_changes if c["change"] > 0][:10],
                    "declined": [c for c in ranking_changes if c["change"] < 0][:10],
                    "total_improved": len([c for c in ranking_changes if c["change"] > 0]),
                    "total_declined": len([c for c in ranking_changes if c["change"] < 0]),
                },
            }
        else:
            report["keywords"] = None

        # ─── Tracked Keywords ───
        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
        report["tracked_keywords"] = [{"keyword": tk.keyword, "position": tk.current_position, "clicks": tk.current_clicks, "impressions": tk.current_impressions, "target_url": tk.target_url or tk.ranking_url, "has_strategy": bool(tk.notes)} for tk in tracked]

        # ─── Fixes Done ───
        fq = db.query(ProposedFix).filter(ProposedFix.website_id == website_id)
        applied_period = fq.filter(ProposedFix.status == "applied")
        generated_period = fq
        if month_start:
            applied_period = applied_period.filter(ProposedFix.applied_at >= month_start, ProposedFix.applied_at <= month_end)
            generated_period = generated_period.filter(ProposedFix.created_at >= month_start, ProposedFix.created_at <= month_end)

        fix_counts = {}
        for s in ["pending", "approved", "applied", "failed", "rejected"]:
            fix_counts[s] = db.query(ProposedFix).filter(ProposedFix.website_id == website_id, ProposedFix.status == s).count()

        fix_types = dict(db.query(ProposedFix.fix_type, func.count(ProposedFix.id)).filter(
            ProposedFix.website_id == website_id, ProposedFix.status == "applied").group_by(ProposedFix.fix_type).all())

        report["fixes"] = {**fix_counts, "applied_this_month": applied_period.count(), "generated_this_month": generated_period.count(), "by_type": fix_types}

        # ─── History Charts ───
        report["audit_history"] = [{"date": h.audit_date.strftime("%Y-%m-%d"), "score": h.health_score, "issues": h.total_issues} for h in db.query(AuditReport).filter(AuditReport.website_id == website_id).order_by(AuditReport.audit_date.asc()).limit(20).all()]

        report["keyword_history"] = [{"date": s.snapshot_date.strftime("%Y-%m-%d"), "total": s.total_keywords, "clicks": s.total_clicks, "impressions": s.total_impressions, "avg_position": s.avg_position} for s in db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).order_by(KeywordSnapshot.snapshot_date.asc()).limit(30).all()]

        # ─── AI Summary ───
        report["ai_summary"] = await _generate_ai_summary(report)

        return report
    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def _generate_ai_summary(report: Dict) -> str:
    if not GEMINI_API_KEY:
        return _fallback_summary(report)
    audit = report.get("audit")
    kw = report.get("keywords")
    fixes = report.get("fixes", {})
    tracked = report.get("tracked_keywords", [])
    if not audit and not kw:
        return "Run an audit and sync keywords to generate a report summary."

    prompt = f"""Write a monthly SEO progress report for {report.get('domain','')}.

Health Score: {audit['health_score'] if audit else 'N/A'}/100 (change: {audit.get('score_change',0):+.1f}) | Issues: {audit['total_issues'] if audit else 0} ({audit.get('issues_change',0):+d} vs previous)
Keywords: {kw['total'] if kw else 0} ({kw.get('keywords_change',0):+d}) | Clicks: {kw['total_clicks'] if kw else 0} ({kw.get('clicks_change',0):+d}) | Impressions: {kw['total_impressions'] if kw else 0} ({kw.get('impressions_change',0):+d})
Top 3: {kw.get('top3',0)} | Top 10: {kw.get('top10',0)} | Top 20: {kw.get('top20',0)}
Fixes applied: {fixes.get('applied_this_month',0)} | Pending: {fixes.get('pending',0)}
Tracked keywords: {len(tracked)}
{f"Improved: {', '.join([c['query']+' (+'+str(c['change'])+')' for c in kw.get('ranking_changes',{}).get('improved',[])[:5]])}" if kw and kw.get('ranking_changes',{}).get('improved') else ''}
{f"Declined: {', '.join([c['query']+' ('+str(c['change'])+')' for c in kw.get('ranking_changes',{}).get('declined',[])[:5]])}" if kw and kw.get('ranking_changes',{}).get('declined') else ''}

Write 4 paragraphs: 1) Overall trajectory 2) Keyword performance 3) Work accomplished 4) Next steps. Be specific with numbers. Professional tone."""

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 800, "temperature": 0.3}})
            if resp.status_code == 200:
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[Report] AI summary error: {e}")
    return _fallback_summary(report)


def _fallback_summary(report: Dict) -> str:
    audit = report.get("audit")
    kw = report.get("keywords")
    fixes = report.get("fixes", {})
    parts = []
    if audit:
        d = "improving" if audit.get("score_change",0) > 0 else "declining" if audit.get("score_change",0) < 0 else "stable"
        parts.append(f"Site health is {d} at {audit['health_score']}/100 ({audit.get('score_change',0):+.1f}). {audit['total_issues']} issues, {audit['critical_issues']} critical.")
    if kw:
        parts.append(f"Ranking for {kw['total']} keywords ({kw.get('keywords_change',0):+d}). {kw['total_clicks']} clicks ({kw.get('clicks_change',0):+d}), {kw['total_impressions']} impressions ({kw.get('impressions_change',0):+d}). {kw.get('top10',0)} in top 10.")
    if fixes.get("applied_this_month",0) > 0:
        parts.append(f"{fixes['applied_this_month']} fixes applied. {fixes.get('pending',0)} pending.")
    return " ".join(parts) if parts else "Run an audit and sync keywords to generate a report."
