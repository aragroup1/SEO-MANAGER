"""Daily ranking-update emails for client recipients.

Pulls SerpRankingHistory for each tracked keyword, computes the day-over-day
delta, renders an HTML email, and sends via Resend (or falls back to SMTP if
RESEND_API_KEY is not set).
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import (
    SessionLocal, Website, TrackedKeyword, SerpRankingHistory,
    ClientRecipient, ClientReportLog,
)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "SEO Reports <reports@yourdomain.com>")
PUBLIC_DASHBOARD_URL = os.getenv("PUBLIC_DASHBOARD_URL", "")


# ─── Ranking diff ───
def _compute_ranking_diff(db: Session, website_id: int) -> Dict[str, Any]:
    """For each tracked keyword, compare today's last position vs the most
    recent prior position (typically yesterday). Return movers + a snapshot."""
    tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
    if not tracked:
        return {"keywords": [], "improved": [], "declined": [], "new_top10": [],
                "lost_top10": [], "summary": "No tracked keywords yet."}

    today_cutoff = datetime.utcnow() - timedelta(hours=18)

    rows = []
    for tk in tracked:
        # Latest ranking at any point
        latest = db.query(SerpRankingHistory).filter(
            SerpRankingHistory.website_id == website_id,
            SerpRankingHistory.keyword == tk.keyword,
        ).order_by(desc(SerpRankingHistory.checked_at)).first()

        # Previous ranking (anything older than ~18h)
        prior = db.query(SerpRankingHistory).filter(
            SerpRankingHistory.website_id == website_id,
            SerpRankingHistory.keyword == tk.keyword,
            SerpRankingHistory.checked_at < today_cutoff,
        ).order_by(desc(SerpRankingHistory.checked_at)).first()

        cur = latest.position if latest else tk.current_position
        prv = prior.position if prior else None

        delta = None
        if cur is not None and prv is not None:
            delta = round(prv - cur, 1)  # positive = improved

        rows.append({
            "keyword": tk.keyword,
            "current": cur,
            "previous": prv,
            "delta": delta,
            "ranking_url": (latest.ranking_url if latest else tk.ranking_url) or "",
            "target": tk.target_position or 1,
        })

    improved = [r for r in rows if r["delta"] is not None and r["delta"] > 0]
    declined = [r for r in rows if r["delta"] is not None and r["delta"] < 0]
    new_top10 = [r for r in rows if r["current"] and r["current"] <= 10
                 and (r["previous"] is None or r["previous"] > 10)]
    lost_top10 = [r for r in rows if r["previous"] and r["previous"] <= 10
                  and (r["current"] is None or r["current"] > 10)]

    improved.sort(key=lambda r: -(r["delta"] or 0))
    declined.sort(key=lambda r: (r["delta"] or 0))

    return {
        "keywords": rows,
        "improved": improved,
        "declined": declined,
        "new_top10": new_top10,
        "lost_top10": lost_top10,
    }


# ─── Email rendering ───
def _render_email_html(domain: str, diff: Dict[str, Any], date_str: str) -> str:
    rows = diff["keywords"]
    improved = diff["improved"]
    declined = diff["declined"]
    new_top10 = diff["new_top10"]

    in_top3 = sum(1 for r in rows if r["current"] and r["current"] <= 3)
    in_top10 = sum(1 for r in rows if r["current"] and r["current"] <= 10)

    def _row(r):
        cur = r["current"]
        prv = r["previous"]
        delta = r["delta"]
        if cur is None:
            cur_html = '<span style="color:#94a3b8">not ranked</span>'
        else:
            color = "#0f9164" if cur <= 3 else "#c87e14" if cur <= 10 else "#181b23"
            cur_html = f'<span style="color:{color};font-weight:700">#{int(cur)}</span>'

        if delta is None:
            delta_html = '<span style="color:#94a3b8">first read</span>'
        elif delta > 0:
            delta_html = f'<span style="color:#0f9164;font-weight:600">▲ {delta}</span>'
        elif delta < 0:
            delta_html = f'<span style="color:#c83c3c;font-weight:600">▼ {abs(delta)}</span>'
        else:
            delta_html = '<span style="color:#94a3b8">no change</span>'

        prv_html = f'<span style="color:#586070">#{int(prv)}</span>' if prv else '<span style="color:#94a3b8">—</span>'

        return f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #eef0f4">{r['keyword']}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eef0f4;text-align:center">{prv_html}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eef0f4;text-align:center">{cur_html}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eef0f4;text-align:right">{delta_html}</td>
        </tr>"""

    table_rows = "".join(_row(r) for r in rows[:30])

    movers_block = ""
    if improved or declined:
        movers_block = f"""
        <table style="width:100%;border-collapse:collapse;margin:24px 0">
          <tr>
            <td style="vertical-align:top;width:50%;padding-right:8px">
              <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#0f9164;font-weight:700;margin:0 0 8px 0">▲ Moved up · {len(improved)}</p>
              {''.join(f'<p style="margin:4px 0;font-size:14px;color:#181b23"><strong>{m["keyword"]}</strong> &nbsp; <span style="color:#0f9164">+{m["delta"]}</span> &nbsp; <span style="color:#586070">#{int(m["previous"])} → #{int(m["current"])}</span></p>' for m in improved[:5])}
            </td>
            <td style="vertical-align:top;width:50%;padding-left:8px">
              <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#c83c3c;font-weight:700;margin:0 0 8px 0">▼ Moved down · {len(declined)}</p>
              {''.join(f'<p style="margin:4px 0;font-size:14px;color:#181b23"><strong>{m["keyword"]}</strong> &nbsp; <span style="color:#c83c3c">{m["delta"]}</span> &nbsp; <span style="color:#586070">#{int(m["previous"])} → #{int(m["current"])}</span></p>' for m in declined[:5])}
            </td>
          </tr>
        </table>"""

    new_top10_block = ""
    if new_top10:
        items = "".join(f'<li style="margin:3px 0">{r["keyword"]} — now <strong>#{int(r["current"])}</strong></li>' for r in new_top10[:5])
        new_top10_block = f"""
        <div style="background:#f0fdf4;border-left:3px solid #0f9164;padding:14px 18px;border-radius:6px;margin:20px 0">
          <p style="font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:#0f9164;font-weight:700;margin:0 0 6px 0">New on page 1</p>
          <ul style="margin:0;padding-left:18px;font-size:14px;color:#181b23">{items}</ul>
        </div>"""

    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f6f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#181b23">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f6f7fa;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;max-width:600px">

        <tr><td style="padding:32px 32px 0 32px">
          <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:#94a3b8;font-weight:700;margin:0">Daily ranking update</p>
          <h1 style="font-size:24px;font-weight:700;color:#181b23;margin:6px 0 4px 0;letter-spacing:-0.01em">{domain}</h1>
          <p style="font-size:13px;color:#586070;margin:0">{date_str}</p>
        </td></tr>

        <tr><td style="padding:24px 32px 0 32px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="width:33%;padding:12px 0">
                <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;font-weight:700;margin:0">Tracked</p>
                <p style="font-size:26px;font-weight:700;color:#181b23;margin:4px 0 0 0">{len(rows)}</p>
              </td>
              <td style="width:33%;padding:12px 0">
                <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;font-weight:700;margin:0">In top 10</p>
                <p style="font-size:26px;font-weight:700;color:#0f9164;margin:4px 0 0 0">{in_top10}</p>
              </td>
              <td style="width:33%;padding:12px 0">
                <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;font-weight:700;margin:0">In top 3</p>
                <p style="font-size:26px;font-weight:700;color:#0f9164;margin:4px 0 0 0">{in_top3}</p>
              </td>
            </tr>
          </table>
        </td></tr>

        <tr><td style="padding:0 32px">{movers_block}{new_top10_block}</td></tr>

        <tr><td style="padding:8px 32px 0 32px">
          <p style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;font-weight:700;margin:0 0 8px 0">All tracked keywords</p>
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:13px">
            <thead>
              <tr style="background:#f6f7fa">
                <th style="padding:10px 14px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em">Keyword</th>
                <th style="padding:10px 14px;text-align:center;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em">Yesterday</th>
                <th style="padding:10px 14px;text-align:center;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em">Today</th>
                <th style="padding:10px 14px;text-align:right;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:0.06em">Change</th>
              </tr>
            </thead>
            <tbody>{table_rows}</tbody>
          </table>
        </td></tr>

        <tr><td style="padding:32px;text-align:center;border-top:1px solid #eef0f4;margin-top:24px">
          <p style="font-size:12px;color:#94a3b8;margin:0">Sent by your SEO team. Reply to this email if you'd like to change which keywords are tracked.</p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body></html>"""


def _render_email_text(domain: str, diff: Dict[str, Any], date_str: str) -> str:
    """Plain-text version for email clients that block HTML."""
    rows = diff["keywords"]
    lines = [
        f"Daily ranking update — {domain}",
        date_str,
        "",
        f"Tracked: {len(rows)}    In top 10: {sum(1 for r in rows if r['current'] and r['current'] <= 10)}    In top 3: {sum(1 for r in rows if r['current'] and r['current'] <= 3)}",
        "",
    ]
    if diff["improved"]:
        lines.append(f"MOVED UP ({len(diff['improved'])}):")
        for r in diff["improved"][:8]:
            lines.append(f"  + {r['keyword']}  #{int(r['previous'])} -> #{int(r['current'])}  (+{r['delta']})")
        lines.append("")
    if diff["declined"]:
        lines.append(f"MOVED DOWN ({len(diff['declined'])}):")
        for r in diff["declined"][:8]:
            lines.append(f"  - {r['keyword']}  #{int(r['previous'])} -> #{int(r['current'])}  ({r['delta']})")
        lines.append("")
    lines.append("ALL TRACKED:")
    for r in rows:
        cur = f"#{int(r['current'])}" if r['current'] else "not ranked"
        prv = f"#{int(r['previous'])}" if r['previous'] else "—"
        delta = ""
        if r['delta'] is not None:
            delta = f"  ({'+' if r['delta'] > 0 else ''}{r['delta']})"
        lines.append(f"  {r['keyword']}: {prv} -> {cur}{delta}")
    return "\n".join(lines)


# ─── Send via Resend ───
async def _send_via_resend(to_email: str, subject: str, html: str, text: str) -> Dict[str, Any]:
    if not RESEND_API_KEY:
        return {"success": False, "error": "RESEND_API_KEY not configured"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "from": RESEND_FROM,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                    "text": text,
                },
            )
            if resp.status_code in (200, 202):
                return {"success": True, "id": resp.json().get("id")}
            return {"success": False, "error": f"Resend {resp.status_code}: {resp.text[:300]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Public API ───
async def send_daily_report_for_recipient(recipient_id: int, force: bool = False) -> Dict[str, Any]:
    """Send today's report to a single recipient. Skips if already sent today (unless force)."""
    db = SessionLocal()
    try:
        rec = db.query(ClientRecipient).filter(ClientRecipient.id == recipient_id).first()
        if not rec or not rec.is_active:
            return {"success": False, "error": "Recipient not found or inactive"}

        if not force and rec.last_sent_at:
            hours_since = (datetime.utcnow() - rec.last_sent_at).total_seconds() / 3600
            if hours_since < 18:
                return {"success": False, "skipped": True, "reason": "already sent today"}

        website = db.query(Website).filter(Website.id == rec.website_id).first()
        if not website:
            return {"success": False, "error": "Website not found"}

        diff = _compute_ranking_diff(db, rec.website_id)
        if not diff["keywords"]:
            return {"success": False, "skipped": True, "reason": "no tracked keywords"}

        date_str = datetime.utcnow().strftime("%A, %B %d, %Y")
        subject = f"[{website.domain}] Daily rankings — {datetime.utcnow().strftime('%b %d')}"
        html = _render_email_html(website.domain, diff, date_str)
        text = _render_email_text(website.domain, diff, date_str)

        result = await _send_via_resend(rec.email, subject, html, text)

        log = ClientReportLog(
            website_id=rec.website_id, recipient_id=rec.id, email=rec.email,
            status="sent" if result.get("success") else "failed",
            error=result.get("error"),
            keywords_count=len(diff["keywords"]),
        )
        db.add(log)
        if result.get("success"):
            rec.last_sent_at = datetime.utcnow()
        db.commit()

        return {**result, "keywords": len(diff["keywords"]),
                "improved": len(diff["improved"]), "declined": len(diff["declined"])}
    finally:
        db.close()


async def send_daily_reports_all() -> Dict[str, Any]:
    """Send daily reports to every active recipient. Called by scheduler."""
    db = SessionLocal()
    try:
        recipients = db.query(ClientRecipient).filter(ClientRecipient.is_active == True).all()
    finally:
        db.close()

    results = {"sent": 0, "failed": 0, "skipped": 0, "details": []}
    for rec in recipients:
        try:
            r = await send_daily_report_for_recipient(rec.id, force=False)
            if r.get("success"):
                results["sent"] += 1
            elif r.get("skipped"):
                results["skipped"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"email": rec.email, **r})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"email": rec.email, "error": str(e)})

    print(f"[ClientReports] Daily run: sent={results['sent']} failed={results['failed']} skipped={results['skipped']}")
    return results


# ─── Recipient CRUD ───
def list_recipients(website_id: int) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(ClientRecipient).filter(
            ClientRecipient.website_id == website_id
        ).order_by(ClientRecipient.created_at.desc()).all()
        return [{
            "id": r.id, "email": r.email, "name": r.name,
            "is_active": r.is_active, "send_hour_utc": r.send_hour_utc,
            "last_sent_at": r.last_sent_at.isoformat() if r.last_sent_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
    finally:
        db.close()


def add_recipient(website_id: int, email: str, name: Optional[str] = None,
                   send_hour_utc: int = 8) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        existing = db.query(ClientRecipient).filter(
            ClientRecipient.website_id == website_id,
            ClientRecipient.email == email,
        ).first()
        if existing:
            return {"error": "Recipient already exists for this website"}
        rec = ClientRecipient(
            website_id=website_id, email=email.strip().lower(),
            name=(name or "").strip() or None,
            send_hour_utc=max(0, min(23, send_hour_utc)),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"id": rec.id, "email": rec.email, "name": rec.name, "is_active": rec.is_active}
    finally:
        db.close()


def update_recipient(recipient_id: int, **fields) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rec = db.query(ClientRecipient).filter(ClientRecipient.id == recipient_id).first()
        if not rec:
            return {"error": "Recipient not found"}
        if "is_active" in fields: rec.is_active = bool(fields["is_active"])
        if "name" in fields: rec.name = fields["name"]
        if "send_hour_utc" in fields:
            rec.send_hour_utc = max(0, min(23, int(fields["send_hour_utc"])))
        db.commit()
        return {"id": rec.id, "is_active": rec.is_active, "name": rec.name,
                "send_hour_utc": rec.send_hour_utc}
    finally:
        db.close()


def delete_recipient(recipient_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        rec = db.query(ClientRecipient).filter(ClientRecipient.id == recipient_id).first()
        if not rec:
            return {"error": "Recipient not found"}
        db.delete(rec)
        db.commit()
        return {"success": True}
    finally:
        db.close()


def list_logs(website_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(ClientReportLog).filter(
            ClientReportLog.website_id == website_id
        ).order_by(ClientReportLog.sent_at.desc()).limit(limit).all()
        return [{
            "id": r.id, "email": r.email, "status": r.status, "error": r.error,
            "keywords_count": r.keywords_count,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        } for r in rows]
    finally:
        db.close()
