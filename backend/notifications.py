# backend/notifications.py — Notification Dispatcher (Slack, Discord, Email, Webhook)
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, NotificationChannel, NotificationLog, Website

load_dotenv()

DEFAULT_SMTP_HOST = os.getenv("SMTP_HOST", "")
DEFAULT_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
DEFAULT_SMTP_USER = os.getenv("SMTP_USER", "")
DEFAULT_SMTP_PASS = os.getenv("SMTP_PASS", "")
DEFAULT_FROM_EMAIL = os.getenv("FROM_EMAIL", "alerts@seo-platform.local")


async def send_slack_notification(webhook_url: str, message: str, title: str = "SEO Alert") -> Dict[str, Any]:
    """Send a notification to Slack via incoming webhook."""
    payload = {
        "text": title,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": title}},
            {"type": "section", "text": {"type": "mrkdwn", "text": message}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"}]},
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            return {"success": resp.status_code == 200, "status_code": resp.status_code, "response": resp.text[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_discord_notification(webhook_url: str, message: str, title: str = "SEO Alert") -> Dict[str, Any]:
    """Send a notification to Discord via webhook."""
    payload = {
        "content": None,
        "embeds": [{
            "title": title,
            "description": message,
            "color": 0x7c6cf9,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "SEO Intelligence Platform"},
        }]
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            return {"success": resp.status_code in (200, 204), "status_code": resp.status_code, "response": resp.text[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_webhook_notification(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a generic webhook POST."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            return {"success": resp.status_code in (200, 201, 202, 204), "status_code": resp.status_code, "response": resp.text[:500]}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_email_notification(to_email: str, subject: str, body: str,
                                   smtp_host: str = None, smtp_port: int = None,
                                   smtp_user: str = None, smtp_pass: str = None) -> Dict[str, Any]:
    """Send an email notification via SMTP."""
    host = smtp_host or DEFAULT_SMTP_HOST
    port = smtp_port or DEFAULT_SMTP_PORT
    user = smtp_user or DEFAULT_SMTP_USER
    password = smtp_pass or DEFAULT_SMTP_PASS

    if not host or not user or not password:
        return {"success": False, "error": "SMTP not configured"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = DEFAULT_FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(f"<html><body><pre>{body}</pre></body></html>", "html"))

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(DEFAULT_FROM_EMAIL, [to_email], msg.as_string())

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _dispatch_to_channel(channel: NotificationChannel, event_type: str, message: str, title: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Send notification through a specific channel."""
    config = channel.config or {}
    result = {"success": False, "error": "Unknown channel type"}

    if channel.channel_type == "slack":
        result = await send_slack_notification(config.get("url", ""), message, title)
    elif channel.channel_type == "discord":
        result = await send_discord_notification(config.get("url", ""), message, title)
    elif channel.channel_type == "webhook":
        payload = {
            "event": event_type,
            "title": title,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        result = await send_webhook_notification(config.get("url", ""), payload)
    elif channel.channel_type == "email":
        result = await send_email_notification(
            config.get("email", ""), title, message,
            config.get("smtp_host"), config.get("smtp_port"),
            config.get("smtp_user"), config.get("smtp_pass")
        )

    return result


async def notify_event(website_id: int, event_type: str, title: str, message: str, data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Main notification dispatcher.
    Finds all active channels for a website that subscribe to this event type,
    sends notifications, and logs results.
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        domain = website.domain if website else "unknown"

        channels = db.query(NotificationChannel).filter(
            NotificationChannel.website_id == website_id,
            NotificationChannel.is_active == True
        ).all()

        # Filter channels that subscribe to this event
        matching = [c for c in channels if event_type in (c.events or [])]

        results = []
        for channel in matching:
            result = await _dispatch_to_channel(channel, event_type, message, f"[{domain}] {title}", data or {})

            # Log the attempt
            log = NotificationLog(
                channel_id=channel.id,
                website_id=website_id,
                event_type=event_type,
                status="sent" if result.get("success") else "failed",
                message=message[:500],
                response=json.dumps(result)[:1000],
            )
            db.add(log)
            results.append({"channel_id": channel.id, "channel_name": channel.name, **result})

        db.commit()
        return results
    finally:
        db.close()


# ─── Pre-built notification templates ───

async def notify_audit_complete(website_id: int, domain: str, health_score: float, previous_score: float, issues_count: int):
    """Notify when an audit completes. Trigger if score dropped >10 points."""
    score_change = health_score - previous_score
    if score_change < -10:
        await notify_event(
            website_id, "audit_complete",
            f"🚨 Health Score Dropped {abs(score_change):.1f} Points",
            f"Your website {domain} health score dropped from {previous_score:.1f} to {health_score:.1f}. "
            f"Total issues: {issues_count}. Run a new audit to see details.",
            {"health_score": health_score, "previous_score": previous_score, "issues_count": issues_count}
        )
    elif score_change > 5:
        await notify_event(
            website_id, "audit_complete",
            f"✅ Health Score Improved +{score_change:.1f} Points",
            f"Great news! {domain} health score improved from {previous_score:.1f} to {health_score:.1f}.",
            {"health_score": health_score, "previous_score": previous_score}
        )


async def notify_fix_applied(website_id: int, domain: str, fix_count: int, fix_summary: str):
    """Notify when fixes are applied."""
    await notify_event(
        website_id, "fix_applied",
        f"🔧 {fix_count} Fix{'es' if fix_count != 1 else ''} Applied",
        f"{fix_count} SEO fix{'es' if fix_count != 1 else ''} applied to {domain}.\n\nSummary:\n{fix_summary}",
        {"fix_count": fix_count, "domain": domain}
    )


async def notify_ranking_drop(website_id: int, domain: str, keyword: str, old_pos: float, new_pos: float):
    """Notify when a tracked keyword drops >5 positions."""
    drop = new_pos - old_pos
    if drop > 5:
        await notify_event(
            website_id, "ranking_drop",
            f"📉 Ranking Drop: {keyword}",
            f"Keyword '{keyword}' on {domain} dropped from position {old_pos:.1f} to {new_pos:.1f} (↓{drop:.1f}).",
            {"keyword": keyword, "old_position": old_pos, "new_position": new_pos, "drop": drop}
        )


async def notify_cwv_poor(website_id: int, domain: str, metric: str, value: float, device: str):
    """Notify when a CWV metric goes poor."""
    await notify_event(
        website_id, "cwv_poor",
        f"⚠️ Core Web Vitals Alert: {metric.upper()}",
        f"{metric.upper()} on {domain} ({device}) is now POOR at {value}. "
        f"This affects your Google rankings. Check the Web Vitals panel for details.",
        {"metric": metric, "value": value, "device": device, "domain": domain}
    )


def get_notification_channels(website_id: int) -> List[Dict[str, Any]]:
    """List all notification channels for a website."""
    db = SessionLocal()
    try:
        channels = db.query(NotificationChannel).filter(NotificationChannel.website_id == website_id).all()
        return [
            {
                "id": c.id, "channel_type": c.channel_type, "name": c.name,
                "events": c.events or [], "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in channels
        ]
    finally:
        db.close()


def get_notification_logs(website_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get notification history for a website."""
    db = SessionLocal()
    try:
        logs = db.query(NotificationLog).filter(NotificationLog.website_id == website_id)\
            .order_by(NotificationLog.sent_at.desc()).limit(limit).all()
        return [
            {
                "id": l.id, "event_type": l.event_type, "status": l.status,
                "message": l.message, "sent_at": l.sent_at.isoformat() if l.sent_at else None,
            }
            for l in logs
        ]
    finally:
        db.close()
