# backend/content_writer.py - AI Content Writer
# Generates SEO-optimized blog posts, product descriptions, and landing pages
# Content goes through an approval queue before being published.
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
from dotenv import load_dotenv

from database import SessionLocal, Website, ContentItem, TrackedKeyword, KeywordSnapshot, AuditReport

load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


async def generate_content(
    website_id: int,
    content_type: str = "blog_post",
    topic: str = "",
    target_keywords: List[str] = None,
    word_count: int = 800,
    tone: str = "professional",
    additional_instructions: str = "",
) -> Dict[str, Any]:
    """
    Generate SEO-optimized content using AI.
    Content types: blog_post, product_description, landing_page, faq_page, how_to_guide
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        if not GEMINI_API_KEY:
            return {"error": "AI API key not configured."}

        if not topic:
            return {"error": "Topic is required."}

        domain = website.domain

        # Get existing keyword context
        existing_keywords = []
        latest_snap = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.desc()).first()
        if latest_snap and latest_snap.keyword_data:
            existing_keywords = [kw.get("query", "") for kw in latest_snap.keyword_data[:50]]

        tracked = db.query(TrackedKeyword).filter(
            TrackedKeyword.website_id == website_id
        ).all()
        tracked_keywords = [tk.keyword for tk in tracked]

        type_config = {
            "blog_post": {
                "label": "Blog Post",
                "instructions": f"Write a comprehensive, SEO-optimized blog post of {word_count}+ words.",
                "structure": "Include: engaging introduction, H2/H3 subheadings, bullet points where appropriate, statistics/data, internal linking suggestions, conclusion with CTA.",
            },
            "product_description": {
                "label": "Product Description",
                "instructions": f"Write an SEO-optimized product description of {word_count}+ words.",
                "structure": "Include: compelling opening, key features, benefits, specifications, use cases, FAQ section.",
            },
            "landing_page": {
                "label": "Landing Page",
                "instructions": f"Write SEO-optimized landing page copy of {word_count}+ words.",
                "structure": "Include: headline, subheadline, value proposition, features/benefits, social proof section, FAQ, strong CTA.",
            },
            "faq_page": {
                "label": "FAQ Page",
                "instructions": f"Write a comprehensive FAQ page with 10-15 questions and answers.",
                "structure": "Include: common questions customers ask, detailed answers, internal links, FAQ Schema markup suggestion.",
            },
            "how_to_guide": {
                "label": "How-To Guide",
                "instructions": f"Write a detailed how-to guide of {word_count}+ words.",
                "structure": "Include: step-by-step instructions, images/diagram suggestions, tips, common mistakes, related resources.",
            },
        }

        config = type_config.get(content_type, type_config["blog_post"])

        prompt = f"""You are an expert SEO content writer for {domain} ({website.site_type} website).

TASK: {config['instructions']}

Topic: {topic}
Target Keywords: {', '.join(target_keywords or [topic])}
Tone: {tone}
{f'Additional Instructions: {additional_instructions}' if additional_instructions else ''}

CONTEXT:
- Website: {domain}
- Existing keywords the site ranks for: {', '.join(existing_keywords[:20]) if existing_keywords else 'None yet'}
- Priority keywords being tracked: {', '.join(tracked_keywords) if tracked_keywords else 'None yet'}

CONTENT STRUCTURE:
{config['structure']}

SEO REQUIREMENTS:
1. Use the primary keyword in the title, first paragraph, and 2-3 H2 headings
2. Include LSI keywords naturally throughout
3. Write for humans first, search engines second
4. Include a compelling meta title (30-60 chars) and meta description (120-155 chars)
5. Suggest 3-5 internal linking opportunities (pages that should link TO this content)
6. Include a FAQ section with 3-5 questions (for FAQ Schema)
7. End with a clear call-to-action

FORMAT YOUR RESPONSE AS JSON:
{{
  "title": "The page/post title",
  "meta_title": "SEO title tag (30-60 chars)",
  "meta_description": "Meta description (120-155 chars)",
  "content_html": "<h1>Title</h1><p>Content in HTML format...</p>",
  "word_count": 850,
  "target_keywords": ["primary", "secondary", "tertiary"],
  "internal_link_suggestions": [
    {{"anchor_text": "text to link", "suggested_page": "/relevant-page", "reason": "why this link"}}
  ],
  "faq": [
    {{"question": "Q?", "answer": "A."}}
  ],
  "estimated_traffic_potential": "low/medium/high with reasoning"
}}"""

        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 8000, "temperature": 0.5}
                }
            )

            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()

                try:
                    content_data = json.loads(text)
                except:
                    content_data = {"title": topic, "content_html": text, "meta_title": topic[:60], "meta_description": topic[:155]}

                # Save to database
                content_item = ContentItem(
                    website_id=website_id,
                    title=content_data.get("title", topic),
                    content_type=config["label"],
                    status="Draft",
                    keywords_target=target_keywords or [topic],
                    ai_generated_content=json.dumps(content_data),
                )
                db.add(content_item)
                db.commit()
                db.refresh(content_item)

                return {
                    "content_id": content_item.id,
                    "content": content_data,
                    "status": "draft",
                    "message": f"{config['label']} generated. Review and edit before publishing."
                }
            elif resp.status_code == 429:
                return {"error": "AI rate limited. Try again in a minute or enable Gemini billing."}
            else:
                return {"error": f"AI API error: {resp.status_code}"}

    except Exception as e:
        import traceback; traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def suggest_content_ideas(website_id: int) -> Dict[str, Any]:
    """Use AI to suggest content ideas based on keyword gaps and competitor analysis."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        if not GEMINI_API_KEY:
            return {"error": "AI API key not configured."}

        # Gather context
        latest_snap = db.query(KeywordSnapshot).filter(
            KeywordSnapshot.website_id == website_id
        ).order_by(KeywordSnapshot.snapshot_date.desc()).first()

        keywords = []
        if latest_snap and latest_snap.keyword_data:
            keywords = [{"query": kw.get("query",""), "position": kw.get("position",0), "impressions": kw.get("impressions",0)} for kw in latest_snap.keyword_data[:30]]

        tracked = db.query(TrackedKeyword).filter(TrackedKeyword.website_id == website_id).all()
        tracked_kws = []
        road_to_one_context = []
        for tk in tracked:
            tracked_kws.append(tk.keyword)
            # Include position context for Road to #1 connection
            if tk.current_position:
                road_to_one_context.append(f"- '{tk.keyword}' (pos #{tk.current_position}, target URL: {tk.target_url or 'not set'})")

        # Get latest audit issues for content-related problems
        latest_audit = db.query(AuditReport).filter(
            AuditReport.website_id == website_id
        ).order_by(AuditReport.audit_date.desc()).first()

        thin_content_pages = []
        if latest_audit and latest_audit.detailed_findings:
            for issue in latest_audit.detailed_findings.get("issues", []):
                if issue.get("issue_type") in ("thin_content", "missing_content", "low_word_count"):
                    thin_content_pages.extend(issue.get("affected_pages", [])[:3])

        prompt = f"""You are a content strategist for {website.domain}.

Current keywords ranking:
{json.dumps(keywords[:20], indent=1) if keywords else 'No keyword data yet'}

Priority keywords (Road to #1 campaigns): {', '.join(tracked_kws) if tracked_kws else 'None set'}

{'Road to #1 content gaps identified:' + chr(10) + chr(10).join(road_to_one_context) if road_to_one_context else ''}

{'Pages with thin/missing content that need improvement: ' + ', '.join(thin_content_pages[:5]) if thin_content_pages else ''}

Suggest 10 content ideas that would:
1. PRIORITIZE content that Road to #1 campaigns have identified as needed
2. Target keywords the site doesn't rank for yet
3. Support existing ranking keywords (hub & spoke — create supporting content that links to priority pages)
4. Answer questions customers likely search for
5. Fill content gaps vs competitors
6. Expand thin content pages identified in audits

Return JSON:
[
  {{
    "title": "Suggested blog post title",
    "content_type": "blog_post|how_to_guide|faq_page|landing_page",
    "target_keyword": "primary keyword to target",
    "estimated_volume": "low/medium/high",
    "difficulty": "easy/medium/hard",
    "why": "brief reason this content would help rankings",
    "supports_keywords": ["existing keywords this would boost"],
    "road_to_one_connection": "which Road to #1 keyword this supports, if any"
  }}
]"""

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 3000, "temperature": 0.5}
                }
            )
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.replace("```json", "").replace("```", "").strip()
                try:
                    ideas = json.loads(text)
                    return {"ideas": ideas}
                except:
                    return {"ideas": [], "raw": text}
            return {"error": f"AI error: {resp.status_code}"}

    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-PUBLISH: Shopify / WordPress
# ═══════════════════════════════════════════════════════════════════════════════

async def publish_content(content_id: int) -> Dict[str, Any]:
    """Publish a ContentItem to the connected platform (Shopify or WordPress)."""
    db = SessionLocal()
    try:
        content = db.query(ContentItem).filter(ContentItem.id == content_id).first()
        if not content:
            return {"error": "Content not found"}

        website = db.query(Website).filter(Website.id == content.website_id).first()
        if not website:
            return {"error": "Website not found"}

        from database import Integration
        integration = db.query(Integration).filter(
            Integration.website_id == website.id,
            Integration.integration_type.in_(["shopify", "wordpress"]),
            Integration.status == "active"
        ).first()

        if not integration:
            return {"error": f"No active {'Shopify' if website.site_type == 'shopify' else 'WordPress'} integration found"}

        # Parse content
        content_data = {}
        if content.ai_generated_content:
            try:
                content_data = json.loads(content.ai_generated_content)
            except:
                content_data = {"content_html": content.ai_generated_content, "title": content.title}

        title = content_data.get("title", content.title)
        body = content_data.get("content_html", content.ai_generated_content or "")

        if integration.integration_type == "shopify":
            return await _publish_to_shopify(integration, title, body, content)
        elif integration.integration_type == "wordpress":
            return await _publish_to_wordpress(integration, title, body, content)

        return {"error": "Unsupported platform"}
    finally:
        db.close()


async def _publish_to_shopify(integration, title: str, body: str, content: ContentItem) -> Dict[str, Any]:
    """Publish as a Shopify blog article."""
    config = integration.config or {}
    store_url = config.get("shopify_store_url") or integration.account_name
    if not store_url:
        return {"error": "Shopify store URL not configured"}

    token = integration.access_token
    if not token:
        return {"error": "Shopify access token not available"}

    # Shopify GraphQL mutation to create a blog article
    # First, get or create a blog
    blog_id = config.get("default_blog_id")
    if not blog_id:
        # Try to find existing blog
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://{store_url}/admin/api/2024-01/blogs.json",
                    headers={"X-Shopify-Access-Token": token}
                )
                if resp.status_code == 200:
                    blogs = resp.json().get("blogs", [])
                    if blogs:
                        blog_id = blogs[0]["id"]
        except Exception as e:
            print(f"[Publish] Shopify blog fetch error: {e}")

    if not blog_id:
        return {"error": "No Shopify blog found. Create a blog first."}

    # Create article
    article_data = {
        "article": {
            "title": title,
            "body_html": body,
            "blog_id": blog_id,
            "published": True,
            "tags": ", ".join(content.keywords_target or []),
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{store_url}/admin/api/2024-01/blogs/{blog_id}/articles.json",
                headers={
                    "X-Shopify-Access-Token": token,
                    "Content-Type": "application/json"
                },
                json=article_data
            )
            if resp.status_code in (200, 201):
                data = resp.json().get("article", {})
                # Update content status
                db = SessionLocal()
                try:
                    content.status = "Published"
                    db.commit()
                finally:
                    db.close()
                return {
                    "success": True,
                    "platform": "shopify",
                    "published_url": f"https://{store_url}/blogs/news/{data.get('handle', '')}",
                    "article_id": data.get("id"),
                }
            return {"error": f"Shopify API error: {resp.status_code}", "details": resp.text[:500]}
    except Exception as e:
        return {"error": f"Shopify publish failed: {str(e)}"}


async def _publish_to_wordpress(integration, title: str, body: str, content: ContentItem) -> Dict[str, Any]:
    """Publish as a WordPress post."""
    config = integration.config or {}
    wp_url = config.get("wp_url")
    if not wp_url:
        return {"error": "WordPress URL not configured"}

    username = config.get("username")
    password = config.get("password") or integration.access_token
    if not username or not password:
        return {"error": "WordPress credentials not available"}

    post_data = {
        "title": title,
        "content": body,
        "status": "publish",
        "tags": content.keywords_target or [],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts",
                json=post_data,
                auth=(username, password)
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                db = SessionLocal()
                try:
                    content.status = "Published"
                    db.commit()
                finally:
                    db.close()
                return {
                    "success": True,
                    "platform": "wordpress",
                    "published_url": data.get("link"),
                    "post_id": data.get("id"),
                }
            return {"error": f"WordPress API error: {resp.status_code}", "details": resp.text[:500]}
    except Exception as e:
        return {"error": f"WordPress publish failed: {str(e)}"}
