# backend/report_routes.py - Reporting API endpoints with comprehensive PDF
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import io

from database import get_db, Website

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{website_id}")
async def get_report(website_id: int, month: Optional[str] = None, db: Session = Depends(get_db)):
    """Get comprehensive report data for a website."""
    from reporting import generate_report_data
    result = await generate_report_data(website_id, month=month)
    return result


@router.get("/{website_id}/pdf")
async def download_pdf_report(website_id: int, month: Optional[str] = None, db: Session = Depends(get_db)):
    """Generate and download a PDF SEO report."""
    from reporting import generate_report_data

    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")

    report_data = await generate_report_data(website_id, month=month)
    if "error" in report_data:
        raise HTTPException(status_code=500, detail=report_data["error"])

    pdf_bytes = _generate_pdf(report_data)

    month_label = month or report_data.get('generated_at', '')[:10]
    filename = f"seo-report-{website.domain}-{month_label}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _generate_pdf(data: dict) -> bytes:
    """Generate comprehensive PDF report."""
    try:
        from fpdf import FPDF
        return _generate_pdf_fpdf(data)
    except ImportError as e:
        print(f"[PDF] fpdf2 not installed: {e}")
        # Return a minimal PDF manually
        return _generate_minimal_pdf(data)


def _safe(text, max_len=200):
    """Sanitize text for PDF — replace chars that fpdf2 can't encode."""
    if not text:
        return ""
    s = str(text)[:max_len]
    # Replace common problematic characters
    replacements = {'\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
                    '\u2013': '-', '\u2014': '--', '\u2026': '...', '\u00a0': ' ',
                    '\u2022': '*', '\u25cf': '*', '\u25cb': 'o', '\u2714': '[x]',
                    '\u2716': '[!]', '\u25b2': '^', '\u25bc': 'v', '\u2191': '^', '\u2193': 'v'}
    for old, new in replacements.items():
        s = s.replace(old, new)
    # Remove any remaining non-latin1 characters
    return s.encode('latin-1', errors='replace').decode('latin-1')


def _generate_pdf_fpdf(data: dict) -> bytes:
    """Generate comprehensive PDF using fpdf2."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ─── Page 1: Cover + Health Score ───
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "SEO Intelligence Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, _safe(data.get("domain", "")), ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, "Generated: " + _safe(data.get("generated_at", "")[:10]), ln=True, align="C")
    pdf.cell(0, 7, "Report Period: " + _safe(data.get("report_month", "current")), ln=True, align="C")
    pdf.ln(10)

    audit = data.get("audit")
    kw = data.get("keywords")
    fixes = data.get("fixes", {})
    tracked = data.get("tracked_keywords", [])
    inception = data.get("since_inception")

    # ─── Health Score Section ───
    if audit:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_fill_color(240, 240, 250)
        pdf.cell(0, 10, "  Site Health Overview", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(3)

        score = audit.get("health_score", 0)
        prev = audit.get("previous_score", score)
        change = round(score - prev, 1)

        pdf.cell(95, 8, f"Health Score: {score}/100 ({'+' if change > 0 else ''}{change})", ln=False)
        pdf.cell(95, 8, f"Pages Crawled: {audit.get('pages_crawled', 'N/A')}", ln=True)
        pdf.cell(95, 8, f"Total Issues: {audit.get('total_issues', 0)} ({audit.get('issues_change', 0):+d} vs previous)", ln=False)
        pdf.cell(95, 8, f"Critical Issues: {audit.get('critical_issues', 0)}", ln=True)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Category Scores:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for label, key in [("Technical", "technical_score"), ("Content", "content_score"),
                           ("Performance", "performance_score"), ("Mobile", "mobile_score"), ("Security", "security_score")]:
            pdf.cell(38, 7, f"{label}: {audit.get(key, 0)}/100", ln=False)
        pdf.ln(10)

        # CWV
        cwv = audit.get("core_web_vitals", {})
        if cwv and cwv.get("lcp"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Core Web Vitals:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(48, 7, f"LCP: {cwv.get('lcp', 'N/A')}s", ln=False)
            pdf.cell(48, 7, f"CLS: {cwv.get('cls', 'N/A')}", ln=False)
            pdf.cell(48, 7, f"TBT: {cwv.get('tbt', 'N/A')}ms", ln=False)
            pdf.cell(48, 7, f"Perf: {cwv.get('performance_score', 'N/A')}/100", ln=True)
            pdf.ln(3)

        # Top Issues
        issues = audit.get("top_issues", [])
        if issues:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"Top Issues ({len(issues)} found):", ln=True)
            pdf.set_font("Helvetica", "", 9)
            for issue in issues[:10]:
                pdf.cell(0, 6, f"  [{_safe(issue.get('severity',''))}] {_safe(issue.get('type',''))} - affects {issue.get('count',1)} page(s)", ln=True)

    # ─── Page 2: Organic Search Performance ───
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(240, 240, 250)
    pdf.cell(0, 10, "  Organic Search Performance", ln=True, fill=True)
    pdf.ln(3)

    if kw:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Current Period", ln=True)
        pdf.set_font("Helvetica", "", 11)

        pdf.cell(95, 8, f"Total Keywords Ranking: {kw.get('total', 0)}", ln=False)
        pdf.cell(95, 8, f"Change: {kw.get('keywords_change', 0):+d}", ln=True)
        pdf.cell(95, 8, f"Total Clicks: {kw.get('total_clicks', 0)}", ln=False)
        pdf.cell(95, 8, f"Change: {kw.get('clicks_change', 0):+d}", ln=True)
        pdf.cell(95, 8, f"Total Impressions: {kw.get('total_impressions', 0)}", ln=False)
        pdf.cell(95, 8, f"Change: {kw.get('impressions_change', 0):+d}", ln=True)
        pdf.cell(95, 8, f"Avg Position: {kw.get('avg_position', 0)}", ln=False)
        pdf.cell(95, 8, f"Avg CTR: {kw.get('avg_ctr', 0)}%", ln=True)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Ranking Distribution:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, f"  Top 3: {kw.get('top3', 0)}  |  Top 10: {kw.get('top10', 0)}  |  Top 20: {kw.get('top20', 0)}", ln=True)
        pdf.ln(3)

        # Ranking changes
        rc = kw.get("ranking_changes", {})
        improved = rc.get("improved", [])
        declined = rc.get("declined", [])

        if improved:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"Rankings Improved ({rc.get('total_improved', len(improved))}):", ln=True)
            pdf.set_font("Helvetica", "", 9)
            for c in improved[:8]:
                pdf.cell(0, 6, f"  {_safe(c.get('query',''))}:  #{c.get('previous','')} -> #{c.get('current','')}  (+{c.get('change','')} positions)", ln=True)
            pdf.ln(2)

        if declined:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, f"Rankings Declined ({rc.get('total_declined', len(declined))}):", ln=True)
            pdf.set_font("Helvetica", "", 9)
            for c in declined[:8]:
                pdf.cell(0, 6, f"  {_safe(c.get('query',''))}:  #{c.get('previous','')} -> #{c.get('current','')}  ({c.get('change','')} positions)", ln=True)
            pdf.ln(2)

        # Top keywords table
        top_kws = kw.get("top_keywords", [])
        if top_kws:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Top 15 Keywords:", ln=True)
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(80, 6, "Keyword", ln=False)
            pdf.cell(20, 6, "Position", ln=False, align="R")
            pdf.cell(25, 6, "Clicks", ln=False, align="R")
            pdf.cell(30, 6, "Impressions", ln=False, align="R")
            pdf.cell(20, 6, "Country", ln=True, align="R")
            pdf.set_font("Helvetica", "", 8)
            for k in top_kws[:15]:
                pdf.cell(80, 5, _safe(k.get("query", ""), 50), ln=False)
                pdf.cell(20, 5, str(k.get("position", "")), ln=False, align="R")
                pdf.cell(25, 5, str(k.get("clicks", 0)), ln=False, align="R")
                pdf.cell(30, 5, str(k.get("impressions", 0)), ln=False, align="R")
                pdf.cell(20, 5, _safe(k.get("country", "")), ln=True, align="R")

    # ─── Since Inception ───
    if inception:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Since Tracking Began ({_safe(inception.get('tracking_started',''))})", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f"Keywords: {inception.get('initial_keywords',0)} -> {kw.get('total',0) if kw else 0} ({inception.get('keywords_growth',0):+d})", ln=False)
        pdf.cell(95, 7, f"Clicks: {inception.get('initial_clicks',0)} -> {kw.get('total_clicks',0) if kw else 0} ({inception.get('clicks_growth',0):+d})", ln=True)
        pdf.cell(95, 7, f"Impressions: {inception.get('initial_impressions',0)} -> {kw.get('total_impressions',0) if kw else 0} ({inception.get('impressions_growth',0):+d})", ln=False)
        pdf.cell(95, 7, f"Avg Position Change: {inception.get('position_change',0):+.1f}", ln=True)
        pdf.cell(95, 7, f"Total Audits Run: {inception.get('total_audits',0)}", ln=False)
        pdf.cell(95, 7, f"Total Fixes Applied: {inception.get('total_fixes_applied',0)}", ln=True)

    # ─── Page 3: Tracked Keywords + Work Done ───
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(240, 240, 250)
    pdf.cell(0, 10, "  Primary Keyword Tracking (Road to #1)", ln=True, fill=True)
    pdf.ln(3)

    if tracked:
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(70, 6, "Keyword", ln=False)
        pdf.cell(20, 6, "Position", ln=False, align="R")
        pdf.cell(20, 6, "Clicks", ln=False, align="R")
        pdf.cell(25, 6, "Impressions", ln=False, align="R")
        pdf.cell(20, 6, "Strategy", ln=False, align="R")
        pdf.cell(35, 6, "Target URL", ln=True, align="R")
        pdf.set_font("Helvetica", "", 8)
        for tk in tracked:
            pos = tk.get("position") or "N/R"
            pdf.cell(70, 5, _safe(tk.get("keyword",""), 45), ln=False)
            pdf.cell(20, 5, str(pos), ln=False, align="R")
            pdf.cell(20, 5, str(tk.get("clicks", 0)), ln=False, align="R")
            pdf.cell(25, 5, str(tk.get("impressions", 0)), ln=False, align="R")
            pdf.cell(20, 5, "Yes" if tk.get("has_strategy") else "No", ln=False, align="R")
            pdf.cell(35, 5, _safe(tk.get("target_url",""), 25), ln=True, align="R")
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, "No primary keywords tracked yet.", ln=True)

    # ─── Technical Work Completed ───
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(240, 240, 250)
    pdf.cell(0, 10, "  Technical SEO Work Completed", ln=True, fill=True)
    pdf.ln(3)

    if fixes.get("applied", 0) > 0 or fixes.get("pending", 0) > 0:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Fix Summary:", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(95, 7, f"Applied: {fixes.get('applied', 0)}", ln=False)
        pdf.cell(95, 7, f"Pending Review: {fixes.get('pending', 0)}", ln=True)
        pdf.cell(95, 7, f"Failed: {fixes.get('failed', 0)}", ln=False)
        pdf.cell(95, 7, f"Rejected: {fixes.get('rejected', 0)}", ln=True)
        pdf.cell(95, 7, f"Applied This Period: {fixes.get('applied_this_month', 0)}", ln=False)
        pdf.cell(95, 7, f"Generated This Period: {fixes.get('generated_this_month', 0)}", ln=True)
        pdf.ln(3)

        # By type
        by_type = fixes.get("by_type", {})
        if by_type:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Work Breakdown by Type (All Time Applied):", ln=True)
            pdf.set_font("Helvetica", "", 10)
            type_labels = {"alt_text": "Alt Text Added to Images", "meta_title": "Meta Titles Optimized",
                          "meta_description": "Meta Descriptions Written", "thin_content": "Content Expanded",
                          "structured_data": "Structured Data Added", "broken_link": "Broken Links Fixed"}
            for fix_type, count in by_type.items():
                label = type_labels.get(fix_type, fix_type.replace("_", " ").title())
                pdf.cell(0, 6, f"  * {label}: {count} fixes applied", ln=True)
            pdf.ln(2)

        # By resource
        by_resource = fixes.get("by_resource", {})
        if by_resource:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Resources Fixed:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for res_type, count in by_resource.items():
                pdf.cell(0, 6, f"  * {count} {res_type}(s) optimized", ln=True)
            pdf.ln(2)

        # Recent work
        recent = fixes.get("recent_work", [])
        if recent:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Recent Fixes Applied:", ln=True)
            pdf.set_font("Helvetica", "", 8)
            for w in recent[:15]:
                pdf.cell(0, 5, f"  [{_safe(w.get('type',''))}] {_safe(w.get('resource',''), 60)} - {_safe(w.get('applied_at','')[:10])}", ln=True)
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, "No fixes have been applied yet. Run a scan to generate fix proposals.", ln=True)

    # ─── AI Summary ───
    ai_summary = data.get("ai_summary", "")
    if ai_summary:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_fill_color(240, 240, 250)
        pdf.cell(0, 10, "  AI Analysis & Strategic Assessment", ln=True, fill=True)
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 10)
        # Split into paragraphs and write
        for para in ai_summary.split("\n\n"):
            if para.strip():
                pdf.multi_cell(0, 5, _safe(para.strip(), 2000))
                pdf.ln(3)

    return pdf.output()


def _generate_minimal_pdf(data: dict) -> bytes:
    """Generate a minimal PDF without fpdf2 — basic PDF structure."""
    lines = [
        "SEO INTELLIGENCE REPORT",
        "=" * 50,
        f"Domain: {data.get('domain', '')}",
        f"Generated: {data.get('generated_at', '')[:10]}",
        "",
    ]

    audit = data.get("audit")
    if audit:
        lines.extend([
            f"HEALTH SCORE: {audit.get('health_score', 0)}/100",
            f"Issues: {audit.get('total_issues', 0)} (Critical: {audit.get('critical_issues', 0)})",
            "",
        ])

    kw = data.get("keywords")
    if kw:
        lines.extend([
            f"KEYWORDS: {kw.get('total', 0)} ranking",
            f"Clicks: {kw.get('total_clicks', 0)} | Impressions: {kw.get('total_impressions', 0)}",
            "",
        ])

    fixes = data.get("fixes", {})
    if fixes.get("applied", 0):
        lines.append(f"FIXES APPLIED: {fixes.get('applied', 0)}")

    ai = data.get("ai_summary", "")
    if ai:
        lines.extend(["", "AI ANALYSIS:", ai[:1000]])

    content = "\n".join(lines)

    # Build minimal PDF
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>
endobj
4 0 obj
<< /Length {len(content) + 50} >>
stream
BT
/F1 9 Tf
36 756 Td
12 TL
"""
    for line in content.split('\n')[:80]:  # Limit to prevent overflow
        safe_line = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')[:90]
        pdf_content += f"({safe_line}) Tj T*\n"

    pdf_content += """ET
endstream
endobj
xref
0 6
trailer
<< /Size 6 /Root 1 0 R >>
startxref
0
%%EOF"""

    return pdf_content.encode('latin-1', errors='replace')
