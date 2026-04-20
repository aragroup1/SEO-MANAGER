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
    except ImportError as e:
        print(f"[PDF] fpdf2 not installed: {e}")
        return _generate_minimal_pdf(data)
    try:
        return _generate_pdf_fpdf(data)
    except Exception as e:
        import traceback
        print(f"[PDF] Full PDF generation failed, retrying without strategy sections: {e}")
        traceback.print_exc()
        # Retry without the optional strategy/hub/decay sections that may contain unexpected data
        safe_data = dict(data)
        safe_data["strategy"] = None
        safe_data["hub_and_spoke"] = None
        safe_data["content_decay"] = None
        try:
            return _generate_pdf_fpdf(safe_data)
        except Exception as e2:
            print(f"[PDF] Fallback also failed: {e2}")
            traceback.print_exc()
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


def _health_color(score):
    """Return RGB tuple based on health score."""
    if score >= 80: return (16, 185, 129)    # green
    if score >= 60: return (245, 158, 11)    # amber
    if score >= 40: return (239, 68, 68)     # red
    return (156, 163, 175)                    # grey (unknown)


def _health_label(score):
    if score >= 80: return "Excellent"
    if score >= 60: return "Good"
    if score >= 40: return "Needs Work"
    if score > 0:   return "Critical"
    return "Not Scored"


def _draw_section_header(pdf, title, subtitle=""):
    """Purple gradient-ish section bar."""
    pdf.set_fill_color(139, 92, 246)  # purple-500
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 11, f"  {_safe(title)}", ln=True, fill=True)
    if subtitle:
        pdf.set_fill_color(245, 243, 255)
        pdf.set_text_color(107, 33, 168)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 7, f"  {_safe(subtitle)}", ln=True, fill=True)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(4)


def _draw_metric_card(pdf, x, y, w, h, label, value, accent_rgb, sub=""):
    """Draw a rounded-ish metric card (rectangle with colored accent)."""
    # Card background
    pdf.set_fill_color(250, 250, 252)
    pdf.rect(x, y, w, h, style="F")
    # Left accent stripe
    pdf.set_fill_color(*accent_rgb)
    pdf.rect(x, y, 2.5, h, style="F")
    # Label
    pdf.set_xy(x + 5, y + 3)
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(w - 6, 5, _safe(label), ln=0)
    # Value
    pdf.set_xy(x + 5, y + 9)
    pdf.set_text_color(17, 24, 39)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(w - 6, 8, _safe(str(value)), ln=0)
    # Subtext
    if sub:
        pdf.set_xy(x + 5, y + h - 7)
        pdf.set_text_color(*accent_rgb)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(w - 6, 5, _safe(sub), ln=0)
    pdf.set_text_color(30, 30, 30)


def _generate_pdf_fpdf(data: dict) -> bytes:
    """Client-friendly SEO report PDF — plain English, visual, simplified."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)

    audit = data.get("audit") or {}
    kw = data.get("keywords") or {}
    fixes = data.get("fixes", {}) or {}
    tracked = data.get("tracked_keywords", []) or []
    inception = data.get("since_inception") or {}
    domain = data.get("domain", "")

    score = audit.get("health_score", 0) or 0
    score_color = _health_color(score)
    score_label = _health_label(score)

    # ══════════════ PAGE 1: COVER ══════════════
    pdf.add_page()
    # Purple banner top
    pdf.set_fill_color(139, 92, 246)
    pdf.rect(0, 0, 210, 70, style="F")
    # Pink accent bar
    pdf.set_fill_color(236, 72, 153)
    pdf.rect(0, 70, 210, 3, style="F")

    pdf.set_xy(15, 22)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 30)
    pdf.cell(0, 12, "SEO Report", ln=True)
    pdf.set_xy(15, 36)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 8, _safe(domain), ln=True)
    pdf.set_xy(15, 47)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Reporting period: {_safe(data.get('report_month', 'Current'))}", ln=True)
    pdf.set_xy(15, 53)
    pdf.cell(0, 6, f"Generated {_safe(data.get('generated_at', '')[:10])}", ln=True)

    pdf.set_text_color(30, 30, 30)
    pdf.set_y(90)

    # Health gauge block
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 7, "Overall Site Health", ln=True, align="C")
    pdf.ln(2)
    # Big score
    pdf.set_font("Helvetica", "B", 60)
    pdf.set_text_color(*score_color)
    pdf.cell(0, 22, f"{int(score)}", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, _safe(score_label), ln=True, align="C")
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("Helvetica", "", 9)
    change = audit.get("score_change", 0) or 0
    if change:
        arrow = "+" if change > 0 else ""
        pdf.cell(0, 6, f"{arrow}{change} vs previous period", ln=True, align="C")
    pdf.ln(6)

    # Quick numbers strip
    y0 = pdf.get_y()
    cards_w = 58
    gap = 3
    start_x = (210 - (cards_w * 3 + gap * 2)) / 2
    _draw_metric_card(pdf, start_x, y0, cards_w, 22, "Keywords Ranking", kw.get("total", 0) or 0, (139, 92, 246),
                      f"{kw.get('keywords_change', 0):+d}" if kw.get('keywords_change') else "")
    _draw_metric_card(pdf, start_x + cards_w + gap, y0, cards_w, 22, "Monthly Visitors", kw.get("total_clicks", 0) or 0, (236, 72, 153),
                      f"{kw.get('clicks_change', 0):+d}" if kw.get('clicks_change') else "")
    _draw_metric_card(pdf, start_x + (cards_w + gap) * 2, y0, cards_w, 22, "Fixes Applied", fixes.get("applied", 0) or 0, (16, 185, 129),
                      f"+{fixes.get('applied_this_month', 0)} this period" if fixes.get('applied_this_month') else "")
    pdf.set_y(y0 + 30)

    # Plain-english what-this-means
    pdf.set_fill_color(245, 243, 255)
    pdf.set_text_color(76, 29, 149)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "  What this report covers", ln=True, fill=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(55, 65, 81)
    pdf.set_fill_color(250, 245, 255)
    bullets = [
        "Your site's overall SEO health and how it's trending.",
        "Which keywords are bringing in the most visitors from Google.",
        "Which rankings went up, which went down, and why it matters.",
        "Technical improvements we completed this period.",
        "What's next and where the biggest opportunities are.",
    ]
    for b in bullets:
        pdf.cell(5, 6, "", ln=0)
        pdf.cell(0, 6, f"- {_safe(b)}", ln=True)
    pdf.set_text_color(30, 30, 30)

    # ══════════════ PAGE 2: EXECUTIVE SUMMARY ══════════════
    pdf.add_page()
    _draw_section_header(pdf, "The Headline", "A quick read on how your site is performing.")

    # Health breakdown cards
    y0 = pdf.get_y()
    cat_w = 37
    cat_gap = 1.5
    cats = [
        ("Technical", audit.get("technical_score", 0) or 0),
        ("Content", audit.get("content_score", 0) or 0),
        ("Speed", audit.get("performance_score", 0) or 0),
        ("Mobile", audit.get("mobile_score", 0) or 0),
        ("Security", audit.get("security_score", 0) or 0),
    ]
    cx = (210 - (cat_w * 5 + cat_gap * 4)) / 2
    for label, val in cats:
        _draw_metric_card(pdf, cx, y0, cat_w, 24, label, f"{int(val)}", _health_color(val), _health_label(val))
        cx += cat_w + cat_gap
    pdf.set_y(y0 + 30)

    # Issues summary
    total_issues = audit.get("total_issues", 0) or 0
    critical = audit.get("critical_issues", 0) or 0
    issues_change = audit.get("issues_change", 0) or 0
    pages_crawled = audit.get("pages_crawled", 0) or 0

    pdf.set_fill_color(249, 250, 251)
    pdf.rect(15, pdf.get_y(), 180, 28, style="F")
    pdf.set_xy(20, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(170, 5, "SITE SCAN RESULTS", ln=True)
    pdf.set_xy(20, pdf.get_y() + 1)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    scan_line = f"We scanned {pages_crawled} pages and found {total_issues} things to fix"
    if critical:
        scan_line += f" — {critical} need attention now."
    else:
        scan_line += "."
    pdf.cell(170, 6, _safe(scan_line), ln=True)
    if issues_change:
        pdf.set_x(20)
        trend_color = (16, 185, 129) if issues_change < 0 else (239, 68, 68)
        pdf.set_text_color(*trend_color)
        pdf.set_font("Helvetica", "B", 10)
        direction = "fewer" if issues_change < 0 else "more"
        pdf.cell(170, 6, f"{abs(issues_change)} {direction} issues than last period.", ln=True)
        pdf.set_text_color(30, 30, 30)
    pdf.ln(6)

    # Core Web Vitals (plain english)
    cwv = audit.get("core_web_vitals", {}) or {}
    if cwv and cwv.get("lcp"):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "Page Speed (what Google measures)", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 10)
        lcp = cwv.get("lcp", 0) or 0
        try: lcp_f = float(lcp)
        except: lcp_f = 0
        lcp_verdict = "Fast" if lcp_f <= 2.5 else ("OK" if lcp_f <= 4 else "Slow")
        perf = cwv.get("performance_score", 0) or 0
        pdf.multi_cell(0, 5, _safe(f"Main content loads in {lcp}s ({lcp_verdict}). Overall speed score: {perf}/100."))
        pdf.ln(4)

    # AI narrative (condensed)
    ai_summary = data.get("ai_summary", "") or ""
    if ai_summary:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "What this means for your business", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9.5)
        paragraphs = [p.strip() for p in ai_summary.split("\n\n") if p.strip()][:3]
        for para in paragraphs:
            pdf.multi_cell(0, 5, _safe(para, 800))
            pdf.ln(2)

    # ══════════════ PAGE 3: RANKING WINS ══════════════
    pdf.add_page()
    _draw_section_header(pdf, "Where You Show Up on Google", "Your keywords, visitors, and where rankings moved.")

    # Top metrics row
    y0 = pdf.get_y()
    _draw_metric_card(pdf, 15, y0, 56, 22, "On Page 1 of Google", kw.get("top10", 0) or 0, (16, 185, 129), f"of {kw.get('total', 0)} total")
    _draw_metric_card(pdf, 77, y0, 56, 22, "Monthly Clicks", kw.get("total_clicks", 0) or 0, (139, 92, 246),
                      f"{kw.get('clicks_change', 0):+d}" if kw.get("clicks_change") else "")
    _draw_metric_card(pdf, 139, y0, 56, 22, "Times Shown", kw.get("total_impressions", 0) or 0, (236, 72, 153),
                      f"{kw.get('impressions_change', 0):+d}" if kw.get("impressions_change") else "")
    pdf.set_y(y0 + 28)

    # Ranking distribution
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(76, 29, 149)
    pdf.cell(0, 7, "Ranking Positions", ln=True)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _safe(f"Top 3 spots: {kw.get('top3', 0)}   |   Top 10 (page 1): {kw.get('top10', 0)}   |   Top 20: {kw.get('top20', 0)}"), ln=True)
    pdf.ln(4)

    # Wins
    rc = kw.get("ranking_changes", {}) or {}
    improved = rc.get("improved", [])
    declined = rc.get("declined", [])

    if improved:
        pdf.set_fill_color(236, 253, 245)
        pdf.set_text_color(5, 150, 105)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"  Wins: {len(improved)} keywords moved UP", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9)
        for c in improved[:8]:
            pdf.cell(100, 5, _safe(f"  {c.get('query','')}", 50), ln=0)
            pdf.cell(0, 5, _safe(f"#{c.get('previous','')} -> #{c.get('current','')}  (+{c.get('change','')})"), ln=True)
        pdf.ln(3)

    if declined:
        pdf.set_fill_color(254, 242, 242)
        pdf.set_text_color(185, 28, 28)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"  Watching: {len(declined)} keywords slipped", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9)
        for c in declined[:6]:
            pdf.cell(100, 5, _safe(f"  {c.get('query','')}", 50), ln=0)
            pdf.cell(0, 5, _safe(f"#{c.get('previous','')} -> #{c.get('current','')}  ({c.get('change','')})"), ln=True)
        pdf.ln(3)

    # Top keywords (simplified)
    top_kws = kw.get("top_keywords", []) or []
    if top_kws:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "Top 10 Keywords Driving Traffic", ln=True)
        pdf.set_text_color(30, 30, 30)
        # Header row
        pdf.set_fill_color(243, 244, 246)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(110, 7, "  Keyword", ln=0, fill=True)
        pdf.cell(30, 7, "Position", ln=0, fill=True, align="C")
        pdf.cell(40, 7, "Clicks/month", ln=True, fill=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        for i, k in enumerate(top_kws[:10]):
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 252)
                pdf.cell(180, 6, "", ln=0, fill=True)
                pdf.set_x(15)
            pdf.cell(110, 6, _safe(f"  {k.get('query','')}", 55), ln=0)
            pdf.cell(30, 6, f"#{k.get('position','')}", ln=0, align="C")
            pdf.cell(40, 6, str(k.get("clicks", 0)), ln=True, align="C")

    # Tracked (Road to #1)
    if tracked:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "Priority Keywords (Road to #1)", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_fill_color(243, 244, 246)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(130, 7, "  Keyword", ln=0, fill=True)
        pdf.cell(25, 7, "Current", ln=0, fill=True, align="C")
        pdf.cell(25, 7, "Clicks", ln=True, fill=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        for i, tk in enumerate(tracked[:12]):
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 252)
                pdf.cell(180, 6, "", ln=0, fill=True)
                pdf.set_x(15)
            pos = tk.get("position")
            pos_str = f"#{int(pos)}" if pos else "N/R"
            pdf.cell(130, 6, _safe(f"  {tk.get('keyword','')}", 65), ln=0)
            pdf.cell(25, 6, pos_str, ln=0, align="C")
            pdf.cell(25, 6, str(tk.get("clicks", 0)), ln=True, align="C")

    # ══════════════ PAGE 4: WORK COMPLETED ══════════════
    pdf.add_page()
    _draw_section_header(pdf, "What We Did This Period", "The work completed on your site behind the scenes.")

    y0 = pdf.get_y()
    _draw_metric_card(pdf, 15, y0, 56, 22, "Fixes Applied This Period", fixes.get("applied_this_month", 0) or 0, (16, 185, 129))
    _draw_metric_card(pdf, 77, y0, 56, 22, "Fixes Applied All-Time", fixes.get("applied", 0) or 0, (139, 92, 246))
    _draw_metric_card(pdf, 139, y0, 56, 22, "Pending Review", fixes.get("pending", 0) or 0, (245, 158, 11))
    pdf.set_y(y0 + 28)

    by_type = fixes.get("by_type", {}) or {}
    if by_type:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "Types of Improvements Made", ln=True)
        pdf.set_text_color(30, 30, 30)
        type_labels = {
            "alt_text": "Images given descriptive text (helps SEO + accessibility)",
            "meta_title": "Page titles rewritten for Google",
            "meta_description": "Search result previews improved",
            "thin_content": "Pages with too little content expanded",
            "structured_data": "Rich snippets added (star ratings, prices)",
            "broken_link": "Broken links fixed",
        }
        for fix_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            label = type_labels.get(fix_type, fix_type.replace("_", " ").title())
            pdf.set_fill_color(250, 250, 252)
            pdf.rect(15, pdf.get_y(), 180, 8, style="F")
            pdf.set_fill_color(139, 92, 246)
            pdf.rect(15, pdf.get_y(), 2, 8, style="F")
            pdf.set_xy(20, pdf.get_y() + 1)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(15, 6, str(count), ln=0)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, _safe(label), ln=True)
            pdf.ln(0.5)
        pdf.ln(3)

    recent = fixes.get("recent_work", []) or []
    if recent:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(76, 29, 149)
        pdf.cell(0, 7, "Recent Fixes", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 8.5)
        for w in recent[:10]:
            pdf.cell(35, 5, _safe(w.get('applied_at', '')[:10]), ln=0)
            pdf.cell(40, 5, _safe(w.get('type', '').replace('_', ' ').title(), 25), ln=0)
            pdf.cell(0, 5, _safe(w.get('resource', ''), 80), ln=True)

    # Inception / cumulative
    if inception:
        pdf.ln(4)
        pdf.set_fill_color(245, 243, 255)
        pdf.set_text_color(76, 29, 149)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"  Since we started working together ({_safe(inception.get('tracking_started',''))})", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 9)
        lines = [
            f"Keywords grown: {inception.get('initial_keywords',0)} -> {kw.get('total',0) or 0} ({inception.get('keywords_growth',0):+d})",
            f"Traffic grown: {inception.get('initial_clicks',0)} -> {kw.get('total_clicks',0) or 0} ({inception.get('clicks_growth',0):+d})",
            f"Total audits run: {inception.get('total_audits',0)}    |    Total fixes applied: {inception.get('total_fixes_applied',0)}",
        ]
        for L in lines:
            pdf.cell(5, 6, "", ln=0)
            pdf.cell(0, 6, _safe(L), ln=True)

    # ══════════════ AI STRATEGY ══════════════
    strategy = data.get("strategy") or {}
    if strategy:
        pdf.add_page()
        _draw_section_header(pdf, "AI Master Strategy", "What the SEO engine recommends, based on all site intelligence.")

        exec_s = strategy.get("executive_summary")
        if exec_s:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Executive Summary", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.multi_cell(0, 5, _safe(exec_s, 900))
            pdf.ln(3)

        cs = strategy.get("current_state") or {}
        if not isinstance(cs, dict):
            cs = {}
        def _listify(v):
            if isinstance(v, list): return v
            if v: return [v]
            return []
        swot = [
            ("Strengths", _listify(cs.get("strengths")), (16, 185, 129)),
            ("Weaknesses", _listify(cs.get("weaknesses")), (239, 68, 68)),
            ("Opportunities", _listify(cs.get("opportunities")), (14, 165, 233)),
            ("Threats", _listify(cs.get("threats")), (245, 158, 11)),
        ]
        if any(items for _, items, _ in swot):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Current State (SWOT)", ln=True)
            pdf.set_text_color(30, 30, 30)
            for label, items, color in swot:
                if not items:
                    continue
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(*color)
                pdf.cell(0, 5, _safe(label), ln=True)
                pdf.set_text_color(30, 30, 30)
                pdf.set_font("Helvetica", "", 9)
                for it in items[:5]:
                    pdf.cell(5, 5, "", ln=0)
                    pdf.multi_cell(0, 5, _safe(f"- {it}", 240))
                pdf.ln(1)
            pdf.ln(2)

        wf = strategy.get("weekly_focus") or {}
        if wf.get("this_week"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "This Week's Focus", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for i, a in enumerate(wf["this_week"][:7], 1):
                pdf.cell(5, 5, "", ln=0)
                pdf.multi_cell(0, 5, _safe(f"{i}. {a}", 240))
            pdf.ln(2)

        if wf.get("quick_wins"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(5, 150, 105)
            pdf.cell(0, 6, "Quick Wins (<1 hour)", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for a in wf["quick_wins"][:6]:
                pdf.cell(5, 5, "", ln=0)
                pdf.multi_cell(0, 5, _safe(f"- {a}", 240))
            pdf.ln(2)

        goals = [g for g in (strategy.get("strategic_goals") or []) if isinstance(g, dict)]
        if goals:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Strategic Goals", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for g in goals[:6]:
                line = f"- [{_safe(g.get('timeframe',''),20)}] {_safe(g.get('goal',''),140)}"
                pdf.multi_cell(0, 5, line)
                if g.get("target"):
                    pdf.set_text_color(107, 114, 128)
                    pdf.cell(8, 4, "", ln=0)
                    pdf.multi_cell(0, 4, _safe(f"target: {g['target']}", 200))
                    pdf.set_text_color(30, 30, 30)
            pdf.ln(2)

        tech = [t for t in (strategy.get("technical_priorities") or []) if isinstance(t, dict)]
        if tech:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Technical Priorities", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for t in tech[:8]:
                impact = _safe(t.get("impact", ""), 10)
                effort = _safe(t.get("effort", ""), 10)
                pdf.multi_cell(0, 5, _safe(f"- [{impact}/{effort}] {t.get('action','')}", 240))

    # ══════════════ HUB & SPOKE ══════════════
    hub = data.get("hub_and_spoke") or {}
    if hub:
        pdf.add_page()
        _draw_section_header(pdf, "Hub & Spoke Internal Linking", "How the site's pages connect and where authority flows.")

        y0 = pdf.get_y()
        _draw_metric_card(pdf, 15, y0, 43, 22, "Pages", hub.get("total_pages", 0), (139, 92, 246))
        _draw_metric_card(pdf, 60, y0, 43, 22, "Internal Links", hub.get("total_internal_links", 0), (236, 72, 153))
        _draw_metric_card(pdf, 105, y0, 43, 22, "Avg Links/Page", hub.get("avg_links_per_page", 0), (14, 165, 233))
        _draw_metric_card(pdf, 150, y0, 43, 22, "Orphans", len(hub.get("orphans") or []), (245, 158, 11))
        pdf.set_y(y0 + 28)

        hubs = [h for h in (hub.get("hubs") or []) if isinstance(h, dict)]
        if hubs:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Top Hub Pages (authority sources)", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_fill_color(243, 244, 246)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(150, 6, "  URL", ln=0, fill=True)
            pdf.cell(30, 6, "Inbound", ln=True, fill=True, align="C")
            pdf.set_font("Helvetica", "", 9)
            for i, h in enumerate(hubs[:8]):
                if i % 2 == 0:
                    pdf.set_fill_color(250, 250, 252)
                    pdf.cell(180, 5, "", ln=0, fill=True)
                    pdf.set_x(15)
                pdf.cell(150, 5, _safe(f"  {h.get('url','')}", 85), ln=0)
                pdf.cell(30, 5, str(h.get("inbound", 0)), ln=True, align="C")
            pdf.ln(3)

        orphans = [o for o in (hub.get("orphans") or []) if isinstance(o, dict)]
        if orphans:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(185, 28, 28)
            pdf.cell(0, 6, "Orphan Pages (need inbound links)", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for o in orphans[:8]:
                pdf.multi_cell(0, 5, _safe(f"- {o.get('url','')}", 200))
            pdf.ln(2)

        suggestions = [s for s in (hub.get("suggestions") or []) if isinstance(s, dict)]
        if suggestions:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(76, 29, 149)
            pdf.cell(0, 6, "Recommended Internal Links", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 8.5)
            for s in suggestions[:10]:
                line = f"- {s.get('from','')}  ->  {s.get('to','')}"
                pdf.multi_cell(0, 4.5, _safe(line, 220))
                if s.get("anchor") or s.get("reason"):
                    pdf.set_text_color(107, 114, 128)
                    extra = []
                    if s.get("anchor"): extra.append(f'anchor: "{s["anchor"]}"')
                    if s.get("reason"): extra.append(s["reason"])
                    pdf.cell(5, 4, "", ln=0)
                    pdf.multi_cell(0, 4, _safe(" - ".join(extra), 240))
                    pdf.set_text_color(30, 30, 30)

    # ══════════════ CONTENT DECAY ══════════════
    decay = data.get("content_decay") or {}
    if decay and (decay.get("high_risk_count") or decay.get("medium_risk_count")):
        pdf.add_page()
        _draw_section_header(pdf, "Content Decay", "Pages that may be losing rankings because they haven't been updated.")

        y0 = pdf.get_y()
        _draw_metric_card(pdf, 15, y0, 58, 22, "Pages Analyzed", decay.get("total_pages_analyzed", 0), (139, 92, 246))
        _draw_metric_card(pdf, 77, y0, 58, 22, "High Risk", decay.get("high_risk_count", 0), (239, 68, 68))
        _draw_metric_card(pdf, 139, y0, 58, 22, "Medium Risk", decay.get("medium_risk_count", 0), (245, 158, 11))
        pdf.set_y(y0 + 28)

        hr = [p for p in (decay.get("high_risk") or []) if isinstance(p, dict)]
        if hr:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(185, 28, 28)
            pdf.cell(0, 6, "High-Risk Stale Pages", ln=True)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("Helvetica", "", 9)
            for p in hr[:8]:
                pdf.multi_cell(0, 5, _safe(f"- {p.get('url','')} ({p.get('days','?')}d old)", 220))
                if p.get("rec"):
                    pdf.set_text_color(107, 114, 128)
                    pdf.cell(5, 4, "", ln=0)
                    pdf.multi_cell(0, 4, _safe(f"-> {p['rec']}", 240))
                    pdf.set_text_color(30, 30, 30)

    # ══════════════ PAGE 5: WHAT'S NEXT ══════════════
    if ai_summary:
        pdf.add_page()
        _draw_section_header(pdf, "What's Next", "Where we're focusing effort next.")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)
        # Show full AI summary here (the condensed version was on page 2)
        for para in ai_summary.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            pdf.multi_cell(0, 5.5, _safe(para, 2000))
            pdf.ln(2)

    # Footer accent on last page
    pdf.set_y(-20)
    pdf.set_fill_color(139, 92, 246)
    pdf.rect(0, pdf.get_y() + 12, 210, 2, style="F")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(156, 163, 175)
    pdf.cell(0, 6, _safe(f"{domain}  -  SEO Report  -  {data.get('generated_at', '')[:10]}"), align="C")

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
