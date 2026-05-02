# backend/report_routes.py — Reporting API endpoints
# PDF generation lives in pdf_report.py (clean, focused, client-friendly layout)
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
    return await generate_report_data(website_id, month=month)


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

    pdf_bytes = _build_pdf(report_data)

    month_label = month or report_data.get("generated_at", "")[:10]
    filename = f"seo-report-{website.domain}-{month_label}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _build_pdf(data: dict) -> bytes:
    """Try the new clean generator; fall back to a minimal text PDF on failure."""
    try:
        from pdf_report import generate_pdf
        return generate_pdf(data)
    except Exception as e:
        import traceback
        print(f"[PDF] generation failed: {e}")
        traceback.print_exc()
        return _minimal_pdf(data)


def _minimal_pdf(data: dict) -> bytes:
    """Fallback plain-text PDF when fpdf2 is unavailable or generation fails."""
    audit = data.get("audit") or {}
    kw = data.get("keywords") or {}
    fixes = data.get("fixes", {}) or {}

    lines = [
        "SEO REPORT",
        "=" * 50,
        f"Domain: {data.get('domain', '')}",
        f"Generated: {data.get('generated_at', '')[:10]}",
        "",
        f"HEALTH SCORE: {audit.get('health_score', 0)}/100",
        f"Issues: {audit.get('total_issues', 0)} (Critical: {audit.get('critical_issues', 0)})",
        "",
        f"KEYWORDS: {kw.get('total', 0)} ranking",
        f"Clicks: {kw.get('total_clicks', 0)}    Impressions: {kw.get('total_impressions', 0)}",
        "",
        f"FIXES APPLIED: {fixes.get('applied', 0)}",
        "",
        (data.get("ai_summary") or "")[:1500],
    ]
    body = "\n".join(lines)

    pdf = (
        "%PDF-1.4\n"
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n"
        f"4 0 obj\n<< /Length {len(body) + 50} >>\nstream\nBT\n/F1 9 Tf\n36 756 Td\n12 TL\n"
    )
    for line in body.split("\n")[:80]:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:90]
        pdf += f"({safe}) Tj T*\n"
    pdf += "ET\nendstream\nendobj\nxref\n0 6\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n0\n%%EOF"
    return pdf.encode("latin-1", errors="replace")
