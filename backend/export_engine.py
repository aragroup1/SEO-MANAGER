# backend/export_engine.py — CSV/JSON Export Engine
import csv
import io
import json
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from database import (
    SessionLocal, Website, AuditReport, KeywordSnapshot,
    TrackedKeyword, ProposedFix, ContentItem, CoreWebVitalsSnapshot,
    ImageAudit, MetaABTest
)


def _make_csv_response(rows: List[List[str]], filename: str):
    """Create a StreamingResponse-compatible CSV byte buffer."""
    output = io.StringIO()
    writer = csv.writer(output)
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return output.getvalue().encode("utf-8-sig")


def export_audit_to_csv(website_id: int) -> bytes:
    """Export all audit issues for a website as CSV."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return _make_csv_response([["Error", "Website not found"]], "error.csv")

        rows = [["Audit ID", "Date", "Health Score", "Technical", "Content", "Performance",
                 "Mobile", "Security", "Total Issues", "Critical", "Errors", "Warnings"]]

        audits = db.query(AuditReport).filter(AuditReport.website_id == website_id)\
            .order_by(AuditReport.audit_date.desc()).all()

        for a in audits:
            rows.append([
                a.id,
                a.audit_date.isoformat() if a.audit_date else "",
                a.health_score,
                a.technical_score,
                a.content_score,
                a.performance_score,
                a.mobile_score,
                a.security_score,
                a.total_issues,
                a.critical_issues,
                a.errors,
                a.warnings,
            ])

        # Add detailed issues as separate sheet-like section
        rows.append([])
        rows.append(["DETAILED ISSUES"])
        rows.append(["Audit Date", "Issue Type", "Severity", "Category", "Affected Pages", "How to Fix"])

        for a in audits:
            findings = a.detailed_findings or {}
            for issue in findings.get("issues", []):
                rows.append([
                    a.audit_date.isoformat() if a.audit_date else "",
                    issue.get("issue_type", ""),
                    issue.get("severity", ""),
                    issue.get("category", ""),
                    "; ".join(issue.get("affected_pages", [])[:5]),
                    issue.get("how_to_fix", ""),
                ])

        return _make_csv_response(rows, f"audit-export-{website.domain}.csv")
    finally:
        db.close()


def export_keywords_to_csv(website_id: int) -> bytes:
    """Export keyword ranking data as CSV."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return _make_csv_response([["Error", "Website not found"]], "error.csv")

        rows = [["Snapshot Date", "Keyword", "Clicks", "Impressions", "CTR (%)", "Position", "Page"]]

        snapshots = db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id)\
            .order_by(KeywordSnapshot.snapshot_date.desc()).all()

        for snap in snapshots:
            for kw in (snap.keyword_data or []):
                rows.append([
                    snap.snapshot_date.isoformat() if snap.snapshot_date else "",
                    kw.get("query", ""),
                    kw.get("clicks", 0),
                    kw.get("impressions", 0),
                    round(kw.get("ctr", 0) * 100, 2),
                    round(kw.get("position", 0), 1),
                    kw.get("page", ""),
                ])

        return _make_csv_response(rows, f"keywords-export-{website.domain}.csv")
    finally:
        db.close()


def export_fixes_to_csv(website_id: int) -> bytes:
    """Export proposed fixes as CSV."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return _make_csv_response([["Error", "Website not found"]], "error.csv")

        rows = [["ID", "Type", "Severity", "Status", "Platform", "Resource", "Field",
                 "Current Value", "Proposed Value", "AI Reasoning", "Created At"]]

        fixes = db.query(ProposedFix).filter(ProposedFix.website_id == website_id)\
            .order_by(ProposedFix.created_at.desc()).all()

        for f in fixes:
            rows.append([
                f.id, f.fix_type, f.severity, f.status, f.platform,
                f.resource_title or f.resource_url or "",
                f.field_name,
                (f.current_value or "")[:100],
                (f.proposed_value or "")[:100],
                (f.ai_reasoning or "")[:200],
                f.created_at.isoformat() if f.created_at else "",
            ])

        return _make_csv_response(rows, f"fixes-export-{website.domain}.csv")
    finally:
        db.close()


def export_full_report_to_json(website_id: int) -> str:
    """Export complete website data as JSON string."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return json.dumps({"error": "Website not found"})

        report = {
            "exported_at": datetime.utcnow().isoformat(),
            "website": {
                "id": website.id,
                "domain": website.domain,
                "site_type": website.site_type,
                "monthly_traffic": website.monthly_traffic,
                "autonomy_mode": website.autonomy_mode,
                "created_at": website.created_at.isoformat() if website.created_at else None,
            },
            "audits": [],
            "keywords": [],
            "fixes": [],
            "content": [],
            "core_web_vitals": [],
            "image_audits": [],
            "ab_tests": [],
        }

        # Audits
        for a in db.query(AuditReport).filter(AuditReport.website_id == website_id).all():
            report["audits"].append({
                "id": a.id, "audit_date": a.audit_date.isoformat() if a.audit_date else None,
                "health_score": a.health_score, "technical_score": a.technical_score,
                "content_score": a.content_score, "performance_score": a.performance_score,
                "mobile_score": a.mobile_score, "security_score": a.security_score,
                "total_issues": a.total_issues, "critical_issues": a.critical_issues,
                "errors": a.errors, "warnings": a.warnings,
                "findings": a.detailed_findings,
            })

        # Keywords
        for s in db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website_id).all():
            report["keywords"].append({
                "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                "total_keywords": s.total_keywords, "total_clicks": s.total_clicks,
                "total_impressions": s.total_impressions, "avg_position": s.avg_position,
                "keyword_data": s.keyword_data,
            })

        # Fixes
        for f in db.query(ProposedFix).filter(ProposedFix.website_id == website_id).all():
            report["fixes"].append({
                "id": f.id, "fix_type": f.fix_type, "severity": f.severity,
                "status": f.status, "platform": f.platform,
                "resource_url": f.resource_url, "field_name": f.field_name,
                "current_value": f.current_value, "proposed_value": f.proposed_value,
                "ai_reasoning": f.ai_reasoning, "created_at": f.created_at.isoformat() if f.created_at else None,
            })

        # Content
        for c in db.query(ContentItem).filter(ContentItem.website_id == website_id).all():
            report["content"].append({
                "id": c.id, "title": c.title, "content_type": c.content_type,
                "status": c.status, "keywords_target": c.keywords_target,
                "publish_date": c.publish_date.isoformat() if c.publish_date else None,
            })

        # Core Web Vitals
        for cwv in db.query(CoreWebVitalsSnapshot).filter(CoreWebVitalsSnapshot.website_id == website_id).all():
            report["core_web_vitals"].append({
                "url": cwv.url, "lcp": cwv.lcp, "inp": cwv.inp, "cls": cwv.cls,
                "fcp": cwv.fcp, "ttfb": cwv.ttfb, "device_type": cwv.device_type,
                "checked_at": cwv.checked_at.isoformat() if cwv.checked_at else None,
            })

        # Image audits
        for img in db.query(ImageAudit).filter(ImageAudit.website_id == website_id).all():
            report["image_audits"].append({
                "page_url": img.page_url, "image_url": img.image_url,
                "alt_text": img.alt_text, "has_dimensions": img.has_dimensions,
                "file_size_kb": img.file_size_kb, "format": img.format,
                "is_lazy_loaded": img.is_lazy_loaded, "issues": img.issues,
                "checked_at": img.checked_at.isoformat() if img.checked_at else None,
            })

        # A/B tests
        for ab in db.query(MetaABTest).filter(MetaABTest.website_id == website_id).all():
            report["ab_tests"].append({
                "page_url": ab.page_url, "element_type": ab.element_type,
                "variant_a": ab.variant_a, "variant_b": ab.variant_b,
                "status": ab.status, "winner": ab.winner,
                "created_at": ab.created_at.isoformat() if ab.created_at else None,
            })

        return json.dumps(report, indent=2, default=str)
    finally:
        db.close()


def export_database_to_json() -> str:
    """Export entire database (all websites) as JSON for backup."""
    db = SessionLocal()
    try:
        backup = {
            "exported_at": datetime.utcnow().isoformat(),
            "version": "1.1.0",
            "websites": [],
        }

        for website in db.query(Website).all():
            w_data = {
                "id": website.id,
                "domain": website.domain,
                "site_type": website.site_type,
                "monthly_traffic": website.monthly_traffic,
                "autonomy_mode": website.autonomy_mode,
                "created_at": website.created_at.isoformat() if website.created_at else None,
                "audits": [],
                "keywords": [],
                "fixes": [],
                "content": [],
                "tracked_keywords": [],
                "integrations": [],
            }

            for a in db.query(AuditReport).filter(AuditReport.website_id == website.id).all():
                w_data["audits"].append({
                    "audit_date": a.audit_date.isoformat() if a.audit_date else None,
                    "health_score": a.health_score, "technical_score": a.technical_score,
                    "content_score": a.content_score, "performance_score": a.performance_score,
                    "mobile_score": a.mobile_score, "security_score": a.security_score,
                    "total_issues": a.total_issues, "critical_issues": a.critical_issues,
                    "errors": a.errors, "warnings": a.warnings,
                    "findings": a.detailed_findings,
                })

            for s in db.query(KeywordSnapshot).filter(KeywordSnapshot.website_id == website.id).all():
                w_data["keywords"].append({
                    "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                    "keyword_data": s.keyword_data,
                })

            for f in db.query(ProposedFix).filter(ProposedFix.website_id == website.id).all():
                w_data["fixes"].append({
                    "fix_type": f.fix_type, "severity": f.severity, "status": f.status,
                    "platform": f.platform, "resource_url": f.resource_url,
                    "field_name": f.field_name, "current_value": f.current_value,
                    "proposed_value": f.proposed_value, "ai_reasoning": f.ai_reasoning,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                })

            for c in db.query(ContentItem).filter(ContentItem.website_id == website.id).all():
                w_data["content"].append({
                    "title": c.title, "content_type": c.content_type,
                    "status": c.status, "keywords_target": c.keywords_target,
                    "publish_date": c.publish_date.isoformat() if c.publish_date else None,
                })

            for tk in db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website.id).all():
                w_data["tracked_keywords"].append({
                    "keyword": tk.keyword, "current_position": tk.current_position,
                    "target_position": tk.target_position, "status": tk.status,
                })

            backup["websites"].append(w_data)

        return json.dumps(backup, indent=2, default=str)
    finally:
        db.close()
