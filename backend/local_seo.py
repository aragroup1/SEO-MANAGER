# backend/local_seo.py — Local SEO / Google Business Profile Engine
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import httpx
from bs4 import BeautifulSoup

from database import SessionLocal, Website, LocalSEOPresence

load_dotenv()


def get_or_create_presence(website_id: int) -> LocalSEOPresence:
    """Get or create a LocalSEO record for a website."""
    db = SessionLocal()
    try:
        presence = db.query(LocalSEOPresence).filter(LocalSEOPresence.website_id == website_id).first()
        if not presence:
            presence = LocalSEOPresence(website_id=website_id)
            db.add(presence)
            db.commit()
            db.refresh(presence)
        return presence
    finally:
        db.close()


def update_local_seo(website_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update Local SEO settings for a website."""
    db = SessionLocal()
    try:
        presence = db.query(LocalSEOPresence).filter(LocalSEOPresence.website_id == website_id).first()
        if not presence:
            presence = LocalSEOPresence(website_id=website_id)
            db.add(presence)

        fields = ["business_name", "address", "city", "postcode", "country",
                  "phone", "category", "gbp_url", "gbp_status"]
        for field in fields:
            if field in data:
                setattr(presence, field, data[field])

        db.commit()
        db.refresh(presence)
        return {
            "success": True,
            "local_seo": {
                "business_name": presence.business_name,
                "address": presence.address,
                "city": presence.city,
                "postcode": presence.postcode,
                "country": presence.country,
                "phone": presence.phone,
                "category": presence.category,
                "gbp_url": presence.gbp_url,
                "gbp_status": presence.gbp_status,
            }
        }
    finally:
        db.close()


def get_local_seo_status(website_id: int) -> Dict[str, Any]:
    """Get Local SEO status for a website."""
    db = SessionLocal()
    try:
        presence = db.query(LocalSEOPresence).filter(LocalSEOPresence.website_id == website_id).first()
        if not presence:
            return {"has_data": False, "message": "Local SEO not configured"}

        # Check completeness
        required = ["business_name", "address", "city", "postcode", "phone", "category"]
        filled = sum(1 for f in required if getattr(presence, f))
        completeness = round((filled / len(required)) * 100)

        return {
            "has_data": True,
            "completeness": completeness,
            "business_name": presence.business_name,
            "address": presence.address,
            "city": presence.city,
            "postcode": presence.postcode,
            "country": presence.country,
            "phone": presence.phone,
            "category": presence.category,
            "gbp_url": presence.gbp_url,
            "gbp_status": presence.gbp_status,
            "review_count": presence.review_count,
            "avg_rating": presence.avg_rating,
            "last_checked": presence.last_checked.isoformat() if presence.last_checked else None,
            "recommendations": _generate_local_recommendations(presence, completeness),
        }
    finally:
        db.close()


def _generate_local_recommendations(presence: LocalSEOPresence, completeness: int) -> List[Dict[str, Any]]:
    """Generate recommendations for improving local SEO."""
    recs = []
    if completeness < 100:
        recs.append({
            "priority": "high",
            "message": f"Local SEO profile is {completeness}% complete. Fill in all business details.",
            "action": "Complete all required fields in Local SEO settings",
        })
    if presence.gbp_status == "not_claimed":
        recs.append({
            "priority": "high",
            "message": "Google Business Profile not claimed",
            "action": "Claim your GBP at https://business.google.com",
        })
    elif presence.gbp_status == "claimed":
        recs.append({
            "priority": "medium",
            "message": "Google Business Profile claimed but not fully optimized",
            "action": "Add photos, business hours, services, and posts to GBP",
        })
    if not presence.gbp_url:
        recs.append({
            "priority": "medium",
            "message": "No GBP URL linked",
            "action": "Add your Google Business Profile URL",
        })
    return recs


def generate_local_schema(website_id: int) -> Dict[str, Any]:
    """Generate LocalBusiness Schema.org JSON-LD for a website."""
    db = SessionLocal()
    try:
        presence = db.query(LocalSEOPresence).filter(LocalSEOPresence.website_id == website_id).first()
        website = db.query(Website).filter(Website.id == website_id).first()

        if not presence or not presence.business_name:
            return {"error": "Local SEO data not configured"}

        schema = {
            "@context": "https://schema.org",
            "@type": presence.category or "LocalBusiness",
            "name": presence.business_name,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": presence.address or "",
                "addressLocality": presence.city or "",
                "postalCode": presence.postcode or "",
                "addressCountry": presence.country or "GB",
            },
            "telephone": presence.phone or "",
            "url": f"https://{website.domain}" if website else "",
        }

        # Remove empty values
        schema["address"] = {k: v for k, v in schema["address"].items() if v}
        if not schema["address"]:
            del schema["address"]
        if not schema.get("telephone"):
            del schema["telephone"]

        return {
            "schema": schema,
            "json_ld": f'<script type="application/ld+json">\n{__import__("json").dumps(schema, indent=2)}\n</script>',
        }
    finally:
        db.close()


async def check_citations(website_id: int) -> Dict[str, Any]:
    """Check NAP (Name, Address, Phone) consistency across the website."""
    db = SessionLocal()
    try:
        presence = db.query(LocalSEOPresence).filter(LocalSEOPresence.website_id == website_id).first()
        website = db.query(Website).filter(Website.id == website_id).first()

        if not presence or not website:
            return {"error": "Local SEO or website not found"}

        domain = website.domain
        url = f"https://{domain}" if not domain.startswith("http") else domain

        citations = []
        issues = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "SEO-Bot/1.0"})
                if resp.status_code == 200:
                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")
                    text = soup.get_text()

                    # Check if NAP appears on homepage
                    if presence.business_name and presence.business_name in text:
                        citations.append({"location": "Homepage", "found": True, "element": "text"})
                    else:
                        issues.append({"severity": "warning", "message": "Business name not found on homepage"})

                    if presence.phone and presence.phone in text:
                        citations.append({"location": "Homepage", "found": True, "element": "phone"})
                    else:
                        issues.append({"severity": "notice", "message": "Phone number not found on homepage"})

                    # Check for structured data
                    scripts = soup.find_all("script", type="application/ld+json")
                    has_local_schema = any("LocalBusiness" in (s.string or "") for s in scripts)
                    if has_local_schema:
                        citations.append({"location": "Homepage", "found": True, "element": "schema.org/LocalBusiness"})
                    else:
                        issues.append({"severity": "warning", "message": "No LocalBusiness schema found on homepage"})

        except Exception as e:
            issues.append({"severity": "error", "message": f"Could not crawl website: {str(e)}"})

        return {
            "citations_found": len(citations),
            "citations": citations,
            "issues": issues,
            "nap_consistency_score": max(0, 100 - len(issues) * 20),
        }
    finally:
        db.close()
