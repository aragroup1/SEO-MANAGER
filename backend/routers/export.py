import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from database import SessionLocal, Website

router = APIRouter()


@router.get("/api/export/{website_id}/audit.csv")
async def export_audit_csv(website_id: int):
    from export_engine import export_audit_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_audit_to_csv(website_id)
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit-{domain}.csv"})


@router.get("/api/export/{website_id}/keywords.csv")
async def export_keywords_csv(website_id: int):
    from export_engine import export_keywords_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_keywords_to_csv(website_id)
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=keywords-{domain}.csv"})


@router.get("/api/export/{website_id}/fixes.csv")
async def export_fixes_csv(website_id: int):
    from export_engine import export_fixes_to_csv
    website = SessionLocal().query(Website).filter(Website.id == website_id).first()
    domain = website.domain if website else "unknown"
    csv_bytes = export_fixes_to_csv(website_id)
    return StreamingResponse(io.BytesIO(csv_bytes), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fixes-{domain}.csv"})


@router.get("/api/export/{website_id}/full-report.json")
async def export_full_report_json(website_id: int):
    from export_engine import export_full_report_to_json
    json_str = export_full_report_to_json(website_id)
    return StreamingResponse(io.BytesIO(json_str.encode("utf-8")), media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=report-{website_id}.json"})
