# backend/report_routes.py - Reporting API endpoints
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io

from database import get_db, Website

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{website_id}")
async def get_report(website_id: int, db: Session = Depends(get_db)):
    """Get comprehensive report data for a website."""
    from reporting import generate_report_data
    result = await generate_report_data(website_id)
    return result


@router.get("/{website_id}/pdf")
async def download_pdf_report(website_id: int, db: Session = Depends(get_db)):
    """Generate and download a PDF SEO report."""
    from reporting import generate_report_data

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    report_data = await generate_report_data(website_id)
    if "error" in report_data:
        raise HTTPException(status_code=500, detail=report_data["error"])

    pdf_bytes = _generate_pdf(report_data)

    filename = f"seo-report-{website.domain}-{report_data.get('generated_at', '')[:10]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_pdf(data: dict) -> bytes:
    """Generate a PDF report using reportlab-style approach with basic HTML->PDF."""
    # Use a simple HTML-to-text approach since we may not have reportlab
    # Build a simple text-based PDF using fpdf2 or fall back to plain text

    try:
        from fpdf import FPDF
        return _generate_pdf_fpdf(data)
    except ImportError:
        pass

    # Fallback: generate a clean text report as PDF-like content
    return _generate_text_report(data).encode('utf-8')


def _generate_pdf_fpdf(data: dict) -> bytes:
    """Generate PDF using fpdf2 library."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "SEO Intelligence Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, data.get("domain", ""), ln=True, align="C")
    pdf.cell(0, 6, "Generated: " + (data.get("generated_at", "")[:10]), ln=True, align="C")
    pdf.ln(10)

    # Health Score
    audit = data.get("audit")
    if audit:
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Site Health", ln=True)
        pdf.set_font("Helvetica", "", 11)

        score = audit.get("health_score", 0)
        prev = audit.get("previous_score", score)
        change = round(score - prev, 1)
        change_str = ("+" + str(change)) if change > 0 else str(change)

        pdf.cell(95, 8, f"Health Score: {score}/100 ({change_str})", ln=False)
        pdf.cell(95, 8, f"Pages Crawled: {audit.get('pages_crawled', 'N/A')}", ln=True)

        pdf.cell(95, 8, f"Technical: {audit.get('technical_score', 0)}/100", ln=False)
        pdf.cell(95, 8, f"Content: {audit.get('content_score', 0)}/100", ln=True)
        pdf.cell(95, 8, f"Performance: {audit.get('performance_score', 0)}/100", ln=False)
        pdf.cell(95, 8, f"Security: {audit.get('security_score', 0)}/100", ln=True)

        pdf.ln(3)
        pdf.cell(0, 8, f"Issues: {audit.get('total_issues', 0)} total ({audit.get('critical_issues', 0)} critical, {audit.get('errors', 0)} errors, {audit.get('warnings', 0)} warnings)", ln=True)

        # CWV
        cwv = audit.get("core_web_vitals", {})
        if cwv:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Core Web Vitals", ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(95, 7, f"LCP: {cwv.get('lcp', 'N/A')}s", ln=False)
            pdf.cell(95, 7, f"CLS: {cwv.get('cls', 'N/A')}", ln=True)
            pdf.cell(95, 7, f"TBT: {cwv.get('tbt', 'N/A')}ms", ln=False)
            pdf.cell(95, 7, f"Performance: {cwv.get('performance_score', 'N/A')}/100", ln=True)

        # Top Issues
        issues = audit.get("top_issues", [])
        if issues:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Top Issues", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for issue in issues[:8]:
                pdf.cell(0, 7, f"  [{issue.get('severity', '')}] {issue.get('type', '')} ({issue.get('count', 1)} pages)", ln=True)

    # Keywords
    kw = data.get("keywords")
    if kw:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Keyword Rankings", ln=True)
        pdf.set_font("Helvetica", "", 11)

        pdf.cell(95, 8, f"Total Keywords: {kw.get('total', 0)}", ln=False)
        pdf.cell(95, 8, f"Total Clicks: {kw.get('total_clicks', 0)}", ln=True)
        pdf.cell(95, 8, f"Impressions: {kw.get('total_impressions', 0)}", ln=False)
        pdf.cell(95, 8, f"Avg Position: {kw.get('avg_position', 0)}", ln=True)
        pdf.cell(95, 8, f"Top 3: {kw.get('top3', 0)}", ln=False)
        pdf.cell(95, 8, f"Top 10: {kw.get('top10', 0)}", ln=True)

        top_kws = kw.get("top_keywords", [])
        if top_kws:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Top Keywords", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for k in top_kws[:10]:
                pdf.cell(0, 7, f"  \"{k.get('query', '')}\" - Pos: {k.get('position', '')}, Clicks: {k.get('clicks', 0)}", ln=True)

    # Tracked Keywords
    tracked = data.get("tracked_keywords", [])
    if tracked:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Road to #1 - Tracked Keywords", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for tk in tracked:
            pos = tk.get("position") or "N/R"
            pdf.cell(0, 7, f"  \"{tk.get('keyword', '')}\" - Position: {pos}, Clicks: {tk.get('clicks', 0)}", ln=True)

    # Fixes
    fixes = data.get("fixes", {})
    if any(fixes.values()):
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Auto-Fix Status", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Applied: {fixes.get('applied', 0)} | Pending: {fixes.get('pending', 0)} | Failed: {fixes.get('failed', 0)}", ln=True)

    return pdf.output()


def _generate_text_report(data: dict) -> str:
    """Fallback text report."""
    lines = ["SEO INTELLIGENCE REPORT", "=" * 40, f"Domain: {data.get('domain', '')}", f"Generated: {data.get('generated_at', '')[:10]}", ""]

    audit = data.get("audit")
    if audit:
        lines.extend([
            "SITE HEALTH", "-" * 20,
            f"Score: {audit.get('health_score', 0)}/100",
            f"Issues: {audit.get('total_issues', 0)}",
            ""
        ])

    kw = data.get("keywords")
    if kw:
        lines.extend([
            "KEYWORDS", "-" * 20,
            f"Total: {kw.get('total', 0)}",
            f"Clicks: {kw.get('total_clicks', 0)}",
            ""
        ])

    return "\n".join(lines)
