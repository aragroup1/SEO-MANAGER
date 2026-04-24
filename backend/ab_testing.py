# backend/ab_testing.py — A/B Testing Engine for Meta Titles/Descriptions
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import httpx

from database import SessionLocal, Website, MetaABTest, TrackedKeyword, KeywordSnapshot

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


async def _generate_variant(page_url: str, element_type: str, current_value: str, keywords: List[str] = None) -> str:
    """Generate an AI variant B for a meta title or description."""
    if not GEMINI_API_KEY:
        return ""

    kw_text = ", ".join(keywords[:5]) if keywords else "relevant keywords"

    if element_type == "title":
        prompt = f"""Generate an SEO-optimized page title (meta title tag) as a variant B for A/B testing.

Current title: "{current_value}"
Page: {page_url}
Target keywords: {kw_text}

Rules:
- 50-60 characters
- Include primary keyword near the beginning
- Compelling and clickable
- Unique from the current title
- No brand name at the end (we'll append it)

Return ONLY the title text, nothing else."""
        max_tokens = 100
    else:
        prompt = f"""Generate an SEO-optimized meta description as a variant B for A/B testing.

Current description: "{current_value}"
Page: {page_url}
Target keywords: {kw_text}

Rules:
- 150-160 characters
- Include primary keyword naturally
- Compelling CTA (call to action)
- Unique from the current description
- Action-oriented language

Return ONLY the description text, nothing else."""
        max_tokens = 200

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                result = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Clean up
                result = result.strip('"').strip("'")
                return result
    except Exception as e:
        print(f"[AB Test] AI generation error: {e}")

    return ""


async def create_test(website_id: int, page_url: str, element_type: str,
                      variant_a: str, keywords: List[str] = None) -> Dict[str, Any]:
    """Create a new A/B test with AI-generated variant B."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        # Generate variant B
        variant_b = await _generate_variant(page_url, element_type, variant_a, keywords)
        if not variant_b:
            return {"error": "Failed to generate variant B. Check AI API key."}

        test = MetaABTest(
            website_id=website_id,
            page_url=page_url,
            element_type=element_type,
            variant_a=variant_a,
            variant_b=variant_b,
            status="draft",
        )
        db.add(test)
        db.commit()
        db.refresh(test)

        return {
            "test_id": test.id,
            "page_url": page_url,
            "element_type": element_type,
            "variant_a": variant_a,
            "variant_b": variant_b,
            "status": "draft",
        }
    finally:
        db.close()


def start_test(test_id: int) -> Dict[str, Any]:
    """Mark a test as running."""
    db = SessionLocal()
    try:
        test = db.query(MetaABTest).filter(MetaABTest.id == test_id).first()
        if not test:
            return {"error": "Test not found"}
        if test.status != "draft":
            return {"error": f"Test cannot be started from status: {test.status}"}

        test.status = "running"
        test.start_date = datetime.utcnow()
        db.commit()
        return {"success": True, "test_id": test.id, "status": "running", "start_date": test.start_date.isoformat()}
    finally:
        db.close()


def end_test(test_id: int, winner: str, notes: str = None) -> Dict[str, Any]:
    """End a test and record the winner."""
    db = SessionLocal()
    try:
        test = db.query(MetaABTest).filter(MetaABTest.id == test_id).first()
        if not test:
            return {"error": "Test not found"}
        if test.status != "running":
            return {"error": f"Test must be running to end. Current status: {test.status}"}
        if winner not in ("a", "b", "tie"):
            return {"error": "Winner must be 'a', 'b', or 'tie'"}

        test.status = "completed"
        test.winner = winner
        test.end_date = datetime.utcnow()
        if notes:
            test.notes = notes
        db.commit()
        return {"success": True, "test_id": test.id, "winner": winner, "end_date": test.end_date.isoformat()}
    finally:
        db.close()


def get_test_results(test_id: int) -> Dict[str, Any]:
    """Get results for a test (placeholder — would integrate GSC CTR data)."""
    db = SessionLocal()
    try:
        test = db.query(MetaABTest).filter(MetaABTest.id == test_id).first()
        if not test:
            return {"error": "Test not found"}

        # In a real implementation, we'd compare CTR from GSC before/after
        # For now, return the test data with placeholder metrics
        return {
            "test_id": test.id,
            "page_url": test.page_url,
            "element_type": test.element_type,
            "variant_a": test.variant_a,
            "variant_b": test.variant_b,
            "status": test.status,
            "winner": test.winner,
            "start_date": test.start_date.isoformat() if test.start_date else None,
            "end_date": test.end_date.isoformat() if test.end_date else None,
            "notes": test.notes,
            # Placeholder metrics — would be populated from GSC integration
            "metrics": {
                "variant_a_ctr": None,
                "variant_b_ctr": None,
                "variant_a_impressions": None,
                "variant_b_impressions": None,
                "confidence": None,
            },
            "recommendation": _get_winner_recommendation(test),
        }
    finally:
        db.close()


def _get_winner_recommendation(test: MetaABTest) -> str:
    """Generate a recommendation based on test results."""
    if test.status != "completed":
        return "Test is still running. Let it run for at least 2 weeks to gather sufficient data."
    if test.winner == "a":
        return "The original version (A) performed better. Keep your current meta tag."
    if test.winner == "b":
        return f"The AI-generated variant (B) performed better. Apply this {test.element_type}: '{test.variant_b}'"
    return "Both variants performed similarly. Consider running a new test with different variations."


def list_tests(website_id: int) -> List[Dict[str, Any]]:
    """List all A/B tests for a website."""
    db = SessionLocal()
    try:
        tests = db.query(MetaABTest).filter(MetaABTest.website_id == website_id)\
            .order_by(MetaABTest.created_at.desc()).all()
        return [
            {
                "id": t.id, "page_url": t.page_url, "element_type": t.element_type,
                "status": t.status, "winner": t.winner,
                "variant_a_preview": t.variant_a[:60] + "..." if len(t.variant_a) > 60 else t.variant_a,
                "variant_b_preview": t.variant_b[:60] + "..." if len(t.variant_b) > 60 else t.variant_b,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tests
        ]
    finally:
        db.close()


def delete_test(test_id: int) -> Dict[str, Any]:
    """Delete an A/B test."""
    db = SessionLocal()
    try:
        test = db.query(MetaABTest).filter(MetaABTest.id == test_id).first()
        if not test:
            return {"error": "Test not found"}
        db.delete(test)
        db.commit()
        return {"success": True}
    finally:
        db.close()
