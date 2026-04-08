# backend/reporting.py - SEO Report Generation
import os
import json
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, ProposedFix
)


async def generate_report_data(website_id: int, month: str = None) -> Dict[str, Any]:
    """Generate comprehensive report data for a website.
    month: optional YYYY-MM string to filter data to that month."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        # Parse month filter
        month_start = None
        month_end = None
        if month:
            try:
                from calendar import monthrange
                parts = month.split('-')
                year, mo = int(parts[0]), int(parts[1])
                month_start = datetime(year, mo, 1)
                _, last_day = monthrange(year, mo)
                month_end = datetime(year, mo, last_day, 23, 59, 59)
            except:
                pass

        report = {
            "domain": website.domain,
            "site_type": website.site_type,
            "generated_at": datetime.utcnow().isoformat(),
            "report_month": month or "current",
        }

        # ─── Audit Summary ───
        audit_query = db.query(AuditReport)\
            .filter(AuditReport.website_id == website_id)
        if month_start and month_end:
            audit_query = audit_query.filter(
                AuditReport.audit_date >= month_start,
                AuditReport.audit_date <= month_end
            )
        latest_audit = audit_query.order_by(AuditReport.audit_date.desc()).first()

        previous_audit = None
        if latest_audit:
            prev_query = db.query(AuditReport)\
                .filter(AuditReport.website_id == website_id, AuditReport.id != latest_audit.id)
            if month_start:
                prev_query = prev_query.filter(AuditReport.audit_date < month_start)
            previous_audit = prev_query.order_by(AuditReport.audit_date.desc()).first()

        if latest_audit:
            findings = latest_audit.detailed_findings or {}
            raw = findings.get("raw_data", {})
            cwv = raw.get("core_web_vitals", {})
            report["audit"] = {
                "health_score": latest_audit.health_score,
                "previous_score": previous_audit.health_score if previous_audit else latest_audit.health_score,
                "technical_score": latest_audit.technical_score,
                "content_score": latest_audit.content_score,
                "performance_score": latest_audit.performance_score,
                "mobile_score": latest_audit.mobile_score,
                "security_score": latest_audit.security_score,
                "total_issues": latest_audit.total_issues,
                "critical_issues": latest_audit.critical_issues,
                "errors": latest_audit.errors,
                "warnings": latest_audit.warnings,
                "audit_date": latest_audit.audit_date.isoformat(),
                "pages_crawled": findings.get("site_stats", {}).get("pages_crawled", 0),
                "core_web_vitals": cwv,
                "top_issues": [
                    {"type": i.get("issue_type", ""), "severity": i.get("severity", ""), "count": i.get("affected_count", 1)}
                    for i in findings.get("issues", [])[:10]
                ],
            }
        else:
            report["audit"] = None

        # ─── Keywords Summary ───
        kw_query = db.query(KeywordSnapshot)\
            .filter(KeywordSnapshot.website_id == website_id)
        if month_start and month_end:
            kw_query = kw_query.filter(
                KeywordSnapshot.snapshot_date >= month_start,
                KeywordSnapshot.snapshot_date <= month_end
            )
        latest_snapshot = kw_query.order_by(KeywordSnapshot.snapshot_date.desc()).first()

        prev_snapshot = None
        if latest_snapshot:
            prev_kw_query = db.query(KeywordSnapshot)\
                .filter(KeywordSnapshot.website_id == website_id, KeywordSnapshot.id != latest_snapshot.id)
            if month_start:
                prev_kw_query = prev_kw_query.filter(KeywordSnapshot.snapshot_date < month_start)
            prev_snapshot = prev_kw_query.order_by(KeywordSnapshot.snapshot_date.desc()).first()

        if latest_snapshot:
            keywords = latest_snapshot.keyword_data or []
            top3 = len([k for k in keywords if k.get("position", 100) <= 3])
            top10 = len([k for k in keywords if k.get("position", 100) <= 10])
            top20 = len([k for k in keywords if k.get("position", 100) <= 20])

            report["keywords"] = {
                "total": latest_snapshot.total_keywords,
                "total_clicks": latest_snapshot.total_clicks,
                "total_impressions": latest_snapshot.total_impressions,
                "avg_position": latest_snapshot.avg_position,
                "avg_ctr": latest_snapshot.avg_ctr,
                "top3": top3,
                "top10": top10,
                "top20": top20,
                "prev_total": prev_snapshot.total_keywords if prev_snapshot else 0,
                "prev_clicks": prev_snapshot.total_clicks if prev_snapshot else 0,
                "date_from": latest_snapshot.date_from.strftime("%Y-%m-%d"),
                "date_to": latest_snapshot.date_to.strftime("%Y-%m-%d"),
                "top_keywords": [
                    {"query": k["query"], "position": k.get("position", 0), "clicks": k.get("clicks", 0), "country": k.get("country", "")}
                    for k in keywords[:15]
                ],
            }
        else:
            report["keywords"] = None

        # ─── Tracked Keywords ───
        tracked = db.query(TrackedKeyword)\
            .filter(TrackedKeyword.website_id == website_id).all()

        report["tracked_keywords"] = [
            {
                "keyword": tk.keyword,
                "position": tk.current_position,
                "clicks": tk.current_clicks,
                "target_url": tk.target_url or tk.ranking_url,
                "has_strategy": bool(tk.notes),
            }
            for tk in tracked
        ]

        # ─── Fix Summary ───
        fix_counts = {}
        for status in ["pending", "approved", "applied", "failed", "rejected"]:
            fix_counts[status] = db.query(ProposedFix)\
                .filter(ProposedFix.website_id == website_id, ProposedFix.status == status).count()

        report["fixes"] = fix_counts

        # ─── Audit History (last 5) ───
        history = db.query(AuditReport)\
            .filter(AuditReport.website_id == website_id)\
            .order_by(AuditReport.audit_date.desc()).limit(5).all()

        report["audit_history"] = [
            {"date": h.audit_date.strftime("%Y-%m-%d"), "score": h.health_score}
            for h in history
        ]

        return report

    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
