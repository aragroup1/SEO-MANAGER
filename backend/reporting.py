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

        # ─── Fixes Done (detailed work breakdown) ───
        fq = db.query(ProposedFix).filter(ProposedFix.website_id == website_id)
        applied_period = fq.filter(ProposedFix.status == "applied")
        generated_period = fq
        if month_start:
            applied_period = applied_period.filter(ProposedFix.applied_at >= month_start, ProposedFix.applied_at <= month_end)
            generated_period = generated_period.filter(ProposedFix.created_at >= month_start, ProposedFix.created_at <= month_end)

        fix_counts = {}
        for s in ["pending", "approved", "applied", "failed", "rejected"]:
            fix_counts[s] = db.query(ProposedFix).filter(ProposedFix.website_id == website_id, ProposedFix.status == s).count()

        # Detailed breakdown by type (all time applied)
        fix_types_all = dict(db.query(ProposedFix.fix_type, func.count(ProposedFix.id)).filter(
            ProposedFix.website_id == website_id, ProposedFix.status == "applied").group_by(ProposedFix.fix_type).all())

        # Detailed breakdown by type (this month applied)
        fix_types_month = {}
        if month_start:
            fix_types_month = dict(db.query(ProposedFix.fix_type, func.count(ProposedFix.id)).filter(
                ProposedFix.website_id == website_id, ProposedFix.status == "applied",
                ProposedFix.applied_at >= month_start, ProposedFix.applied_at <= month_end
            ).group_by(ProposedFix.fix_type).all())
        else:
            fix_types_month = fix_types_all

        # Breakdown by resource type (products, pages, collections, etc)
        fix_by_resource = dict(db.query(ProposedFix.resource_type, func.count(ProposedFix.id)).filter(
            ProposedFix.website_id == website_id, ProposedFix.status == "applied").group_by(ProposedFix.resource_type).all())

        # Recent applied fixes (last 20) for detail section
        recent_fixes = db.query(ProposedFix).filter(
            ProposedFix.website_id == website_id, ProposedFix.status == "applied"
        ).order_by(ProposedFix.applied_at.desc()).limit(20).all()

        work_details = []
        for f in recent_fixes:
            work_details.append({
                "type": f.fix_type, "resource": f.resource_title or f.resource_url or "",
                "field": f.field_name, "applied_at": f.applied_at.isoformat() if f.applied_at else "",
                "category": f.category,
            })

        report["fixes"] = {
            **fix_counts,
            "applied_this_month": applied_period.count(),
            "generated_this_month": generated_period.count(),
            "by_type": fix_types_all,
            "by_type_this_month": fix_types_month,
            "by_resource": fix_by_resource,
            "recent_work": work_details,
        }

        # ─── Since Inception (first snapshot vs latest) ───
        first_snap = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.asc()).first()

        if first_snap and latest_snap and first_snap.id != latest_snap.id:
            report["since_inception"] = {
                "tracking_started": first_snap.snapshot_date.strftime("%Y-%m-%d"),
                "initial_keywords": first_snap.total_keywords,
                "initial_clicks": first_snap.total_clicks,
                "initial_impressions": first_snap.total_impressions,
                "initial_avg_position": first_snap.avg_position,
                "keywords_growth": latest_snap.total_keywords - first_snap.total_keywords,
                "clicks_growth": latest_snap.total_clicks - first_snap.total_clicks,
                "impressions_growth": latest_snap.total_impressions - first_snap.total_impressions,
                "position_change": round(first_snap.avg_position - latest_snap.avg_position, 1),
                "total_fixes_applied": fix_counts.get("applied", 0),
                "total_audits": db.query(AuditReport).filter(AuditReport.website_id == website_id).count(),
            }
        else:
            report["since_inception"] = None

        # ─── GA4 Traffic Data ───
        try:
            from ga4_data import fetch_ga4_traffic
            ga4 = await fetch_ga4_traffic(website_id, days=30)
            if ga4 and "error" not in ga4:
                report["ga4_traffic"] = ga4
            else:
                report["ga4_traffic"] = None
        except Exception as ga4_err:
            print(f"[Report] GA4 data error (non-fatal): {ga4_err}")
            report["ga4_traffic"] = None

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

WORK DONE THIS PERIOD:
{chr(10).join([f"- {t}: {c} fixes applied" for t, c in fixes.get('by_type_this_month',{}).items()]) if fixes.get('by_type_this_month') else '- No fixes applied this period'}
Resources fixed: {', '.join([f"{c} {t}s" for t, c in fixes.get('by_resource',{}).items()]) if fixes.get('by_resource') else 'None'}

{f"SINCE TRACKING BEGAN ({report.get('since_inception',{}).get('tracking_started','')}):" if report.get('since_inception') else ''}
{f"- Keywords growth: {report['since_inception']['initial_keywords']} → {kw['total'] if kw else 0} ({report['since_inception']['keywords_growth']:+d})" if report.get('since_inception') and kw else ''}
{f"- Clicks growth: {report['since_inception']['initial_clicks']} → {kw['total_clicks'] if kw else 0} ({report['since_inception']['clicks_growth']:+d})" if report.get('since_inception') and kw else ''}
{f"- Position change: {report['since_inception']['position_change']:+.1f} (positive = improved)" if report.get('since_inception') else ''}
{f"- Total fixes applied: {report['since_inception']['total_fixes_applied']}, Audits run: {report['since_inception']['total_audits']}" if report.get('since_inception') else ''}

{f"Improved: {', '.join([c['query']+' (+'+str(c['change'])+')' for c in kw.get('ranking_changes',{}).get('improved',[])[:5]])}" if kw and kw.get('ranking_changes',{}).get('improved') else ''}
{f"Declined: {', '.join([c['query']+' ('+str(c['change'])+')' for c in kw.get('ranking_changes',{}).get('declined',[])[:5]])}" if kw and kw.get('ranking_changes',{}).get('declined') else ''}

Write 5 paragraphs:
1) Overall SEO trajectory and health score trend
2) Organic search performance - clicks, impressions, keyword growth vs last month AND since tracking began
3) Primary keyword ranking changes and tracked keyword progress
4) Technical work completed - specific numbers of alt texts added, meta titles fixed, content expanded, etc.
5) Recommended next steps based on current gaps
Be specific with numbers. Professional tone."""

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
