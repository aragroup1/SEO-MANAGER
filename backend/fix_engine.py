# backend/fix_engine.py - Auto-Fix Engine for Shopify & WordPress
import os
import re
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import httpx
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, Website, AuditReport, ProposedFix, Integration

load_dotenv()

# AI provider for generating fixes
GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class AIFixGenerator:
    """Generates SEO fix suggestions using AI."""

    def __init__(self):
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.anthropic_url = "https://api.anthropic.com/v1/messages"

    async def generate_text(self, prompt: str, max_tokens: int = 300) -> str:
        """Generate text using available AI provider (Gemini Flash preferred for cost)."""

        # Try Gemini Flash first (cheapest)
        if GEMINI_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{self.gemini_url}?key={GEMINI_API_KEY}",
                        json={
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                print(f"[AI] Gemini error: {e}")

        # Fallback to Anthropic
        if ANTHROPIC_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        self.anthropic_url,
                        headers={
                            "x-api-key": ANTHROPIC_API_KEY,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        },
                        json={
                            "model": "claude-sonnet-4-20250514",
                            "max_tokens": max_tokens,
                            "messages": [{"role": "user", "content": prompt}]
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["content"][0]["text"].strip()
            except Exception as e:
                print(f"[AI] Anthropic error: {e}")

        # Final fallback: rule-based (no AI)
        return ""

    async def generate_alt_text(self, image_url: str, page_title: str = "", product_name: str = "") -> str:
        """Generate alt text for an image."""
        prompt = f"""Generate a concise, descriptive alt text for an image. 
The alt text should be 5-15 words, describe what the image likely shows, and include relevant keywords.

Context:
- Page title: {page_title or 'Unknown'}
- Product name: {product_name or 'Unknown'}  
- Image URL: {image_url}

Rules:
- Don't start with "Image of" or "Photo of"
- Be specific and descriptive
- Include the product/subject name if relevant
- Keep under 125 characters

Return ONLY the alt text, nothing else."""

        result = await self.generate_text(prompt, max_tokens=50)
        if result:
            # Clean up: remove quotes, extra whitespace
            result = result.strip('"\'').strip()
            return result[:125]  # Hard cap at 125 chars

        # Fallback: use product name or page title
        if product_name:
            return product_name
        if page_title:
            return page_title
        return "Product image"

    async def generate_meta_title(self, page_content: str, current_title: str = "", keywords: List[str] = None) -> str:
        """Generate an optimized meta title."""
        prompt = f"""Generate an SEO-optimized page title tag.

Current title: {current_title or 'None'}
Target keywords: {', '.join(keywords or [])}
Page content summary: {page_content[:500]}

Rules:
- Must be 30-60 characters
- Include the primary keyword near the beginning
- Make it compelling (users should want to click)
- Include brand name at the end if space allows, separated by |
- Don't use ALL CAPS

Return ONLY the title text, nothing else."""

        result = await self.generate_text(prompt, max_tokens=80)
        if result:
            result = result.strip('"\'').strip()
            if len(result) > 60:
                result = result[:57] + "..."
            return result
        return ""

    async def generate_meta_description(self, page_content: str, current_desc: str = "", keywords: List[str] = None) -> str:
        """Generate an optimized meta description."""
        prompt = f"""Generate an SEO-optimized meta description.

Current description: {current_desc or 'None'}
Target keywords: {', '.join(keywords or [])}
Page content summary: {page_content[:500]}

Rules:
- Must be 120-155 characters
- Include the primary keyword naturally
- Include a call-to-action (Shop now, Learn more, Discover, etc.)
- Make it compelling — this is your ad copy in search results
- Don't use quotes

Return ONLY the meta description text, nothing else."""

        result = await self.generate_text(prompt, max_tokens=200)
        if result:
            result = result.strip('"\'').strip()
            if len(result) > 160:
                result = result[:157] + "..."
            return result
        return ""


class ShopifyFixEngine:
    """Connects to Shopify Admin API to read data and apply fixes."""

    def __init__(self, store_url: str, access_token: str):
        # Normalize store URL
        self.store_url = store_url.rstrip('/')
        if not self.store_url.startswith('https://'):
            self.store_url = f"https://{self.store_url}"
        self.access_token = access_token
        self.api_version = "2024-01"
        self.base_api = f"{self.store_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
        self.ai = AIFixGenerator()

    async def _api_get(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make a GET request to Shopify Admin API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_api}/{endpoint}",
                    headers=self.headers,
                    params=params
                )
                if resp.status_code == 200:
                    return resp.json()
                else:
                    print(f"[Shopify API] GET {endpoint} failed: {resp.status_code} {resp.text[:200]}")
                    return None
        except Exception as e:
            print(f"[Shopify API] GET {endpoint} error: {e}")
            return None

    async def _api_put(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Make a PUT request to Shopify Admin API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    f"{self.base_api}/{endpoint}",
                    headers=self.headers,
                    json=data
                )
                if resp.status_code in [200, 201]:
                    return resp.json()
                else:
                    print(f"[Shopify API] PUT {endpoint} failed: {resp.status_code} {resp.text[:200]}")
                    return None
        except Exception as e:
            print(f"[Shopify API] PUT {endpoint} error: {e}")
            return None

    # ─────────────────────────────────────────
    #  Scan for issues and generate fixes
    # ─────────────────────────────────────────

    async def scan_and_generate_fixes(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan all products and pages, generate fix proposals."""
        fixes = []

        # Scan products
        product_fixes = await self._scan_products(website_id, batch_id)
        fixes.extend(product_fixes)

        # Scan pages
        page_fixes = await self._scan_pages(website_id, batch_id)
        fixes.extend(page_fixes)

        return fixes

    async def _scan_products(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan Shopify products for SEO issues."""
        fixes = []
        page_info = None
        limit = 50  # Products per page

        # Paginate through all products
        params = {"limit": limit, "fields": "id,title,body_html,handle,images,metafields_global_title_tag,metafields_global_description_tag"}

        data = await self._api_get("products.json", params)
        if not data or "products" not in data:
            print("[Shopify] No products found or API error")
            return fixes

        products = data["products"]
        print(f"[Shopify] Scanning {len(products)} products...")

        for product in products:
            product_fixes = await self._analyze_product(product, website_id, batch_id)
            fixes.extend(product_fixes)

            # Rate limiting — Shopify allows 2 requests/second
            await asyncio.sleep(0.5)

        return fixes

    async def _analyze_product(self, product: Dict, website_id: int, batch_id: str) -> List[Dict]:
        """Analyze a single product for SEO issues and generate fixes."""
        fixes = []
        product_id = str(product["id"])
        product_title = product.get("title", "")
        product_handle = product.get("handle", "")
        product_url = f"{self.store_url}/products/{product_handle}"
        body_html = product.get("body_html", "") or ""

        # Strip HTML for content analysis
        from bs4 import BeautifulSoup
        body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

        # --- Check 1: Images missing alt text ---
        images = product.get("images", [])
        for img in images:
            alt = img.get("alt") or ""
            if not alt.strip():
                # Generate AI alt text
                ai_alt = await self.ai.generate_alt_text(
                    image_url=img.get("src", ""),
                    page_title=product_title,
                    product_name=product_title
                )
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "alt_text",
                    "platform": "shopify",
                    "resource_type": "product",
                    "resource_id": product_id,
                    "resource_url": product_url,
                    "resource_title": product_title,
                    "field_name": f"image_{img['id']}_alt",
                    "current_value": alt or "(empty)",
                    "proposed_value": ai_alt,
                    "ai_reasoning": f"Image on product '{product_title}' has no alt text. Alt text improves accessibility and helps search engines understand your images.",
                    "severity": "high",
                    "category": "accessibility",
                    "batch_id": batch_id,
                    "extra": {"image_id": img["id"], "image_src": img.get("src", "")}
                })

        # --- Check 2: Meta title ---
        meta_title = product.get("metafields_global_title_tag") or ""
        if not meta_title or len(meta_title) < 30 or len(meta_title) > 60:
            ai_title = await self.ai.generate_meta_title(
                page_content=body_text or product_title,
                current_title=meta_title or product_title,
                keywords=[product_title.split()[0]] if product_title else []
            )
            if ai_title:
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "meta_title",
                    "platform": "shopify",
                    "resource_type": "product",
                    "resource_id": product_id,
                    "resource_url": product_url,
                    "resource_title": product_title,
                    "field_name": "metafields_global_title_tag",
                    "current_value": meta_title or product_title,
                    "proposed_value": ai_title,
                    "ai_reasoning": f"{'No meta title set — using product name as fallback.' if not meta_title else f'Meta title is {len(meta_title)} chars — {'too short' if len(meta_title) < 30 else 'too long'}.'} An optimized title between 30-60 characters improves click-through rates from search results.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        # --- Check 3: Meta description ---
        meta_desc = product.get("metafields_global_description_tag") or ""
        if not meta_desc or len(meta_desc) < 70 or len(meta_desc) > 160:
            ai_desc = await self.ai.generate_meta_description(
                page_content=body_text or product_title,
                current_desc=meta_desc,
                keywords=[product_title.split()[0]] if product_title else []
            )
            if ai_desc:
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "meta_description",
                    "platform": "shopify",
                    "resource_type": "product",
                    "resource_id": product_id,
                    "resource_url": product_url,
                    "resource_title": product_title,
                    "field_name": "metafields_global_description_tag",
                    "current_value": meta_desc or "(empty)",
                    "proposed_value": ai_desc,
                    "ai_reasoning": f"{'No meta description set.' if not meta_desc else f'Meta description is {len(meta_desc)} chars.'} A compelling meta description between 120-155 characters increases click-through rates from search results.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        # --- Check 4: Thin product description ---
        if body_text and len(body_text.split()) < 50:
            fixes.append({
                "website_id": website_id,
                "fix_type": "thin_content",
                "platform": "shopify",
                "resource_type": "product",
                "resource_id": product_id,
                "resource_url": product_url,
                "resource_title": product_title,
                "field_name": "body_html",
                "current_value": f"({len(body_text.split())} words)",
                "proposed_value": "(content expansion needed — will generate on approval)",
                "ai_reasoning": f"Product description has only {len(body_text.split())} words. Products with detailed descriptions rank better and convert more customers. Aim for 100+ words.",
                "severity": "medium",
                "category": "content",
                "batch_id": batch_id,
            })

        return fixes

    async def _scan_pages(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan Shopify pages for SEO issues."""
        fixes = []
        data = await self._api_get("pages.json", {"limit": 50})
        if not data or "pages" not in data:
            return fixes

        for page in data["pages"]:
            page_id = str(page["id"])
            title = page.get("title", "")
            handle = page.get("handle", "")
            body_html = page.get("body_html", "") or ""
            page_url = f"{self.store_url}/pages/{handle}"

            from bs4 import BeautifulSoup
            body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

            # Check meta title
            meta_title = page.get("metafields_global_title_tag") or ""
            if not meta_title:
                ai_title = await self.ai.generate_meta_title(body_text or title, title)
                if ai_title:
                    fixes.append({
                        "website_id": website_id,
                        "fix_type": "meta_title",
                        "platform": "shopify",
                        "resource_type": "page",
                        "resource_id": page_id,
                        "resource_url": page_url,
                        "resource_title": title,
                        "field_name": "metafields_global_title_tag",
                        "current_value": title,
                        "proposed_value": ai_title,
                        "ai_reasoning": "No custom meta title set for this page. Using an optimized title helps this page rank better.",
                        "severity": "medium",
                        "category": "content",
                        "batch_id": batch_id,
                    })

            # Check meta description
            meta_desc = page.get("metafields_global_description_tag") or ""
            if not meta_desc:
                ai_desc = await self.ai.generate_meta_description(body_text or title, "")
                if ai_desc:
                    fixes.append({
                        "website_id": website_id,
                        "fix_type": "meta_description",
                        "platform": "shopify",
                        "resource_type": "page",
                        "resource_id": page_id,
                        "resource_url": page_url,
                        "resource_title": title,
                        "field_name": "metafields_global_description_tag",
                        "current_value": "(empty)",
                        "proposed_value": ai_desc,
                        "ai_reasoning": "No meta description set. Adding one improves click-through rates from search results.",
                        "severity": "medium",
                        "category": "content",
                        "batch_id": batch_id,
                    })

        return fixes

    # ─────────────────────────────────────────
    #  Apply approved fixes
    # ─────────────────────────────────────────

    async def apply_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        """Apply a single approved fix to Shopify."""

        try:
            if fix.fix_type == "alt_text":
                return await self._apply_alt_text_fix(fix)
            elif fix.fix_type in ["meta_title", "meta_description"]:
                return await self._apply_meta_fix(fix)
            else:
                return False, f"Fix type '{fix.fix_type}' not yet implemented for auto-apply"
        except Exception as e:
            return False, str(e)

    async def _apply_alt_text_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        """Apply an alt text fix to a Shopify product image."""
        # Parse the image ID from field_name (format: image_{id}_alt)
        field_parts = fix.field_name.split("_")
        if len(field_parts) < 3:
            return False, "Could not parse image ID from field name"

        image_id = field_parts[1]
        product_id = fix.resource_id

        result = await self._api_put(
            f"products/{product_id}/images/{image_id}.json",
            {"image": {"id": int(image_id), "alt": fix.proposed_value}}
        )

        if result:
            return True, "Alt text updated successfully"
        return False, "Shopify API rejected the update"

    async def _apply_meta_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        """Apply a meta title or description fix via Shopify metafields."""
        resource_type = fix.resource_type  # product or page
        resource_id = fix.resource_id

        # Shopify uses metafields for SEO title/description
        namespace = "global"
        if fix.fix_type == "meta_title":
            key = "title_tag"
        elif fix.fix_type == "meta_description":
            key = "description_tag"
        else:
            return False, f"Unknown meta fix type: {fix.fix_type}"

        # Create or update metafield
        metafield_data = {
            "metafield": {
                "namespace": namespace,
                "key": key,
                "value": fix.proposed_value,
                "type": "single_line_text_field"
            }
        }

        endpoint = f"{resource_type}s/{resource_id}/metafields.json"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_api}/{endpoint}",
                    headers=self.headers,
                    json=metafield_data
                )
                if resp.status_code in [200, 201]:
                    return True, f"Meta {fix.fix_type.replace('meta_', '')} updated successfully"
                else:
                    return False, f"Shopify API error: {resp.status_code} - {resp.text[:200]}"
        except Exception as e:
            return False, str(e)


class WordPressFixEngine:
    """Connects to WordPress REST API to apply fixes."""

    def __init__(self, wp_url: str, api_key: str = "", username: str = "", app_password: str = ""):
        self.wp_url = wp_url.rstrip('/')
        if not self.wp_url.startswith('https://'):
            self.wp_url = f"https://{self.wp_url}"
        self.api_base = f"{self.wp_url}/wp-json/wp/v2"
        self.auth = (username, app_password) if username and app_password else None
        self.api_key = api_key
        self.ai = AIFixGenerator()

    async def _api_get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """GET request to WordPress REST API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                kwargs = {"params": params}
                if self.auth:
                    kwargs["auth"] = self.auth
                resp = await client.get(f"{self.api_base}/{endpoint}", **kwargs)
                if resp.status_code == 200:
                    return resp.json()
                print(f"[WP API] GET {endpoint} failed: {resp.status_code}")
                return None
        except Exception as e:
            print(f"[WP API] GET {endpoint} error: {e}")
            return None

    async def scan_and_generate_fixes(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan WordPress posts and pages for SEO issues."""
        fixes = []

        # Scan posts
        posts = await self._api_get("posts", {"per_page": 50, "status": "publish"})
        if posts:
            for post in posts:
                post_fixes = await self._analyze_wp_content(post, "post", website_id, batch_id)
                fixes.extend(post_fixes)

        # Scan pages
        pages = await self._api_get("pages", {"per_page": 50, "status": "publish"})
        if pages:
            for page in pages:
                page_fixes = await self._analyze_wp_content(page, "page", website_id, batch_id)
                fixes.extend(page_fixes)

        return fixes

    async def _analyze_wp_content(self, content: Dict, content_type: str, website_id: int, batch_id: str) -> List[Dict]:
        """Analyze a WordPress post or page."""
        fixes = []
        content_id = str(content["id"])
        title = content.get("title", {}).get("rendered", "")
        url = content.get("link", "")
        body_html = content.get("content", {}).get("rendered", "")
        excerpt = content.get("excerpt", {}).get("rendered", "")

        from bs4 import BeautifulSoup
        body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

        # Check for images without alt text in content
        if body_html:
            soup = BeautifulSoup(body_html, 'html.parser')
            images = soup.find_all('img')
            for img in images:
                alt = img.get('alt', '')
                if not alt.strip():
                    src = img.get('src', '')
                    ai_alt = await self.ai.generate_alt_text(src, title)
                    fixes.append({
                        "website_id": website_id,
                        "fix_type": "alt_text",
                        "platform": "wordpress",
                        "resource_type": content_type,
                        "resource_id": content_id,
                        "resource_url": url,
                        "resource_title": title,
                        "field_name": f"content_image_alt",
                        "current_value": "(empty)",
                        "proposed_value": ai_alt,
                        "ai_reasoning": f"Image in {content_type} '{title}' has no alt text.",
                        "severity": "high",
                        "category": "accessibility",
                        "batch_id": batch_id,
                        "extra": {"image_src": src}
                    })

        # Check excerpt (used as meta description by many themes)
        if not excerpt or len(BeautifulSoup(excerpt, 'html.parser').get_text(strip=True)) < 50:
            ai_desc = await self.ai.generate_meta_description(body_text or title, "")
            if ai_desc:
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "meta_description",
                    "platform": "wordpress",
                    "resource_type": content_type,
                    "resource_id": content_id,
                    "resource_url": url,
                    "resource_title": title,
                    "field_name": "excerpt",
                    "current_value": BeautifulSoup(excerpt, 'html.parser').get_text(strip=True) if excerpt else "(empty)",
                    "proposed_value": ai_desc,
                    "ai_reasoning": "No excerpt/meta description set. Most WordPress themes use the excerpt as the meta description.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        return fixes


# ─────────────────────────────────────────
#  Main orchestrator
# ─────────────────────────────────────────

async def generate_fixes_for_website(website_id: int) -> Dict[str, Any]:
    """
    Main entry point: scan a website and generate all proposed fixes.
    Saves them to the database with status='pending'.
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        batch_id = f"batch_{website_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        all_fixes = []

        if website.site_type == "shopify":
            # Get Shopify credentials from integration or website record
            integration = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "shopify",
                Integration.status == "active"
            ).first()

            store_url = website.shopify_store_url or website.domain
            access_token = (integration.access_token if integration else None) or website.shopify_access_token

            if not access_token:
                return {"error": "Shopify access token not configured. Add it in website settings or connect Shopify integration."}

            engine = ShopifyFixEngine(store_url, access_token)
            all_fixes = await engine.scan_and_generate_fixes(website_id, batch_id)

        elif website.site_type == "wordpress":
            integration = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "wordpress",
                Integration.status == "active"
            ).first()

            wp_url = website.domain
            api_key = integration.access_token if integration else ""

            engine = WordPressFixEngine(wp_url, api_key=api_key)
            all_fixes = await engine.scan_and_generate_fixes(website_id, batch_id)

        else:
            return {"error": "Auto-fix is currently supported for Shopify and WordPress sites. Custom sites can use the audit recommendations for manual fixes."}

        # Save fixes to database
        saved_count = 0
        for fix_data in all_fixes:
            extra = fix_data.pop("extra", None)
            proposed_fix = ProposedFix(**fix_data)
            db.add(proposed_fix)
            saved_count += 1

        db.commit()
        print(f"[FixEngine] Generated {saved_count} proposed fixes for website {website_id} (batch: {batch_id})")

        return {
            "batch_id": batch_id,
            "total_fixes": saved_count,
            "fix_types": _count_by_type(all_fixes),
            "message": f"Generated {saved_count} fix proposals. Review and approve them in the Approval Queue."
        }

    except Exception as e:
        print(f"[FixEngine] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


async def apply_approved_fix(fix_id: int) -> Dict[str, Any]:
    """Apply a single approved fix."""
    db = SessionLocal()
    try:
        fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
        if not fix:
            return {"error": "Fix not found"}
        if fix.status != "approved":
            return {"error": f"Fix is not approved (status: {fix.status})"}

        website = db.query(Website).filter(Website.id == fix.website_id).first()
        if not website:
            return {"error": "Website not found"}

        success = False
        message = ""

        if fix.platform == "shopify":
            store_url = website.shopify_store_url or website.domain
            access_token = website.shopify_access_token
            if not access_token:
                integration = db.query(Integration).filter(
                    Integration.website_id == website.id,
                    Integration.integration_type == "shopify",
                    Integration.status == "active"
                ).first()
                access_token = integration.access_token if integration else ""

            if not access_token:
                fix.status = "failed"
                fix.error_message = "No Shopify access token"
                db.commit()
                return {"error": "No Shopify access token configured"}

            engine = ShopifyFixEngine(store_url, access_token)
            success, message = await engine.apply_fix(fix)

        elif fix.platform == "wordpress":
            # WordPress apply logic would go here
            success, message = False, "WordPress auto-apply not yet implemented"

        if success:
            fix.status = "applied"
            fix.applied_at = datetime.utcnow()
            fix.error_message = None
        else:
            fix.status = "failed"
            fix.error_message = message

        db.commit()
        return {"success": success, "message": message, "status": fix.status}

    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


def _count_by_type(fixes: List[Dict]) -> Dict[str, int]:
    """Count fixes by type."""
    counts = {}
    for f in fixes:
        t = f.get("fix_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
