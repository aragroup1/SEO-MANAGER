from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/api/client-reports/{website_id}/recipients")
async def list_recipients_endpoint(website_id: int):
    from client_reports import list_recipients
    return {"recipients": list_recipients(website_id)}


@router.post("/api/client-reports/{website_id}/recipients")
async def add_recipient_endpoint(website_id: int, request: Request):
    from client_reports import add_recipient
    data = await request.json()
    email = (data.get("email") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    result = add_recipient(
        website_id, email,
        name=data.get("name"),
        send_hour_utc=int(data.get("send_hour_utc", 8)),
    )
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.put("/api/client-reports/recipients/{recipient_id}")
async def update_recipient_endpoint(recipient_id: int, request: Request):
    from client_reports import update_recipient
    data = await request.json()
    result = update_recipient(recipient_id, **data)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/api/client-reports/recipients/{recipient_id}")
async def delete_recipient_endpoint(recipient_id: int):
    from client_reports import delete_recipient
    result = delete_recipient(recipient_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/api/client-reports/recipients/{recipient_id}/send-now")
async def send_now_endpoint(recipient_id: int):
    """Send today's report immediately, ignoring the once-per-day guard."""
    from client_reports import send_daily_report_for_recipient
    result = await send_daily_report_for_recipient(recipient_id, force=True)
    return result


@router.post("/api/client-reports/run-all")
async def run_all_endpoint():
    """Trigger daily run for all recipients (manual button)."""
    from client_reports import send_daily_reports_all
    return await send_daily_reports_all()


@router.get("/api/client-reports/{website_id}/logs")
async def list_logs_endpoint(website_id: int, limit: int = 30):
    from client_reports import list_logs
    return {"logs": list_logs(website_id, limit=limit)}
