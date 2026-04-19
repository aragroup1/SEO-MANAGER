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
                    else:
                        print(f"[AI] Gemini error: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                print(f"[AI] Gemini error: {e}")

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

        return ""

    async def generate_alt_text(self, image_url: str, page_title: str = "", product_name: str = "") -> str:
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
            return result.strip('"\'').strip()[:125]
        if product_name:
            return product_name
        if page_title:
            return page_title
        return "Product image"

    async def generate_meta_title(self, page_content: str, current_title: str = "", keywords: List[str] = None) -> str:
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
- Don't wrap in quotes

Return ONLY the title text, nothing else."""

        result = await self.generate_text(prompt, max_tokens=80)
        if result:
            result = result.strip('"\'').strip()
            if len(result) > 60:
                result = result[:57] + "..."
            return result
        if current_title and len(current_title) > 60:
            return current_title[:57] + "..."
        return ""

    async def generate_meta_description(self, page_content: str, current_desc: str = "", keywords: List[str] = None) -> str:
        prompt = f"""Generate an SEO-optimized meta description.

Current description: {current_desc or 'None'}
Target keywords: {', '.join(keywords or [])}
Page content summary: {page_content[:500]}

Rules:
- Must be 120-155 characters
- Include the primary keyword naturally
- Include a call-to-action (Shop now, Learn more, Discover, etc.)
- Make it compelling - this is your ad copy in search results
- Don't wrap in quotes

Return ONLY the meta description text, nothing else."""

        result = await self.generate_text(prompt, max_tokens=200)
        if result:
            result = result.strip('"\'').strip()
            if len(result) > 160:
                result = result[:157] + "..."
            return result
        return ""

    async def generate_product_description(self, product_title: str, current_desc: str = "", word_target: int = 150) -> str:
        prompt = f"""Write an SEO-optimized product description for: {product_title}

Current description: {current_desc or 'None'}

Rules:
- Write {word_target} words minimum
- Include the product name naturally 2-3 times
- Highlight key features and benefits
- Use bullet points for key specs if appropriate
- Include a call to action
- Write in HTML format (use <p>, <ul>, <li> tags)
- Don't wrap in code blocks

Return ONLY the HTML description, nothing else."""

        result = await self.generate_text(prompt, max_tokens=500)
        if result:
            result = result.strip('`').strip()
            if result.startswith('html'):
                result = result[4:].strip()
            return result
        return ""


class ShopifyFixEngine:
    """Connects to Shopify Admin API to read data and apply fixes."""

    def __init__(self, store_url: str, access_token: str):
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

    async def _api_request(self, method: str, endpoint: str, params: Dict = None, json_data: Dict = None, max_retries: int = 5) -> Optional[Dict]:
        """Make a Shopify API request with automatic retry on 429 rate limits."""
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    kwargs = {"headers": self.headers}
                    if params:
                        kwargs["params"] = params
                    if json_data:
                        kwargs["json"] = json_data

                    if method == "GET":
                        resp = await client.get(f"{self.base_api}/{endpoint}", **kwargs)
                    elif method == "PUT":
                        resp = await client.put(f"{self.base_api}/{endpoint}", **kwargs)
                    elif method == "POST":
                        resp = await client.post(f"{self.base_api}/{endpoint}", **kwargs)
                    else:
                        return None

                    if resp.status_code in [200, 201]:
                        return resp.json()
                    elif resp.status_code == 429:
                        # Rate limited — wait and retry with exponential backoff
                        wait_time = 2.0 * (attempt + 1)
                        print(f"[Shopify API] Rate limited on {endpoint}, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"[Shopify API] {method} {endpoint} failed: {resp.status_code} {resp.text[:200]}")
                        return None
            except Exception as e:
                print(f"[Shopify API] {method} {endpoint} error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                return None
        print(f"[Shopify API] {method} {endpoint} failed after {max_retries} retries")
        return None

    async def _api_get(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        return await self._api_request("GET", endpoint, params=params)

    async def _api_put(self, endpoint: str, data: Dict) -> Optional[Dict]:
        return await self._api_request("PUT", endpoint, json_data=data)

    async def _api_post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        return await self._api_request("POST", endpoint, json_data=data)

    async def _get_product_metafields(self, product_id: str) -> Dict[str, str]:
        """Fetch SEO metafields (title_tag, description_tag) for a product."""
        data = await self._api_get(f"products/{product_id}/metafields.json", {"namespace": "global"})
        if not data:
            return {}
        result = {}
        for mf in data.get("metafields", []):
            if mf.get("namespace") == "global":
                if mf.get("key") == "title_tag":
                    result["title_tag"] = mf.get("value", "")
                    result["title_tag_id"] = mf.get("id")
                elif mf.get("key") == "description_tag":
                    result["description_tag"] = mf.get("value", "")
                    result["description_tag_id"] = mf.get("id")
        return result

    async def _get_page_metafields(self, page_id: str) -> Dict[str, str]:
        """Fetch SEO metafields for a page."""
        data = await self._api_get(f"pages/{page_id}/metafields.json", {"namespace": "global"})
        if not data:
            return {}
        result = {}
        for mf in data.get("metafields", []):
            if mf.get("namespace") == "global":
                if mf.get("key") == "title_tag":
                    result["title_tag"] = mf.get("value", "")
                    result["title_tag_id"] = mf.get("id")
                elif mf.get("key") == "description_tag":
                    result["description_tag"] = mf.get("value", "")
                    result["description_tag_id"] = mf.get("id")
        return result

    # ─────────────────────────────────────────
    #  Scan for issues and generate fixes
    # ─────────────────────────────────────────

    async def scan_and_generate_fixes(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan all products, pages, and collections. Generate fix proposals."""
        fixes = []

        print(f"[Shopify Scan] Starting product scan...")
        product_fixes = await self._scan_all_products(website_id, batch_id)
        fixes.extend(product_fixes)
        print(f"[Shopify Scan] Found {len(product_fixes)} product fixes")

        print(f"[Shopify Scan] Starting page scan...")
        page_fixes = await self._scan_all_pages(website_id, batch_id)
        fixes.extend(page_fixes)
        print(f"[Shopify Scan] Found {len(page_fixes)} page fixes")

        print(f"[Shopify Scan] Starting collection scan...")
        collection_fixes = await self._scan_collections(website_id, batch_id)
        fixes.extend(collection_fixes)
        print(f"[Shopify Scan] Found {len(collection_fixes)} collection fixes")

        print(f"[Shopify Scan] Total fixes found: {len(fixes)}")
        return fixes

    async def _scan_all_products(self, website_id: int, batch_id: str) -> List[Dict]:
        """Paginate through ALL products and scan each one."""
        fixes = []
        since_id = 0
        page = 0
        limit = 250

        while True:
            page += 1
            params = {"limit": limit, "fields": "id,title,body_html,handle,images"}
            if since_id > 0:
                params["since_id"] = since_id

            data = await self._api_get("products.json", params)
            if not data or "products" not in data:
                break

            products = data["products"]
            if not products:
                break

            print(f"[Shopify Scan] Page {page}: scanning {len(products)} products")

            for i, product in enumerate(products):
                product_fixes = await self._analyze_product(product, website_id, batch_id)
                fixes.extend(product_fixes)
                if (i + 1) % 25 == 0:
                    print(f"[Shopify Scan]   Progress: {i + 1}/{len(products)} products on page {page} ({len(fixes)} fixes so far)")
                # 1.5s between products to stay well under Shopify's 2 req/sec limit
                # (each product makes 2 API calls: product data already fetched + metafields)
                await asyncio.sleep(1.5)

            since_id = products[-1]["id"]
            if len(products) < limit:
                break

        return fixes

    async def _analyze_product(self, product: Dict, website_id: int, batch_id: str) -> List[Dict]:
        """Analyze a single product for SEO issues."""
        fixes = []
        product_id = str(product["id"])
        product_title = product.get("title", "")
        product_handle = product.get("handle", "")
        product_url = f"{self.store_url}/products/{product_handle}"
        body_html = product.get("body_html", "") or ""

        from bs4 import BeautifulSoup
        body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

        # Fetch SEO metafields via separate API call
        metafields = await self._get_product_metafields(product_id)
        meta_title = metafields.get("title_tag", "")
        meta_desc = metafields.get("description_tag", "")

        # --- Check 1: Images missing alt text ---
        images = product.get("images", [])
        for img in images:
            alt = img.get("alt") or ""
            if not alt.strip():
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
                    "current_value": "(empty)",
                    "proposed_value": ai_alt,
                    "ai_reasoning": f"Image on product '{product_title}' has no alt text. Alt text improves accessibility and helps search engines understand your images.",
                    "severity": "high",
                    "category": "accessibility",
                    "batch_id": batch_id,
                })

        # --- Check 2: Missing or bad meta title ---
        if not meta_title:
            ai_title = await self.ai.generate_meta_title(
                page_content=body_text or product_title,
                current_title=product_title,
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
                    "current_value": product_title + " (using product name as fallback)",
                    "proposed_value": ai_title,
                    "ai_reasoning": "No custom SEO title set. Shopify defaults to the product name, which is often not optimized for search. A title between 30-60 characters improves click-through rates.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })
        elif len(meta_title) < 30 or len(meta_title) > 60:
            length_issue = "too short" if len(meta_title) < 30 else "too long"
            ai_title = await self.ai.generate_meta_title(
                page_content=body_text or product_title,
                current_title=meta_title,
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
                    "current_value": meta_title,
                    "proposed_value": ai_title,
                    "ai_reasoning": "Meta title is " + str(len(meta_title)) + " characters (" + length_issue + "). Optimal length is 30-60 characters for best display in search results.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        # --- Check 3: Missing or bad meta description ---
        if not meta_desc:
            ai_desc = await self.ai.generate_meta_description(
                page_content=body_text or product_title,
                current_desc="",
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
                    "current_value": "(empty - Google will auto-generate from page content)",
                    "proposed_value": ai_desc,
                    "ai_reasoning": "No meta description set. A custom description gives you control over what appears in search results and typically improves click-through rates.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })
        elif len(meta_desc) < 70 or len(meta_desc) > 160:
            length_issue = "too short" if len(meta_desc) < 70 else "too long"
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
                    "current_value": meta_desc,
                    "proposed_value": ai_desc,
                    "ai_reasoning": "Meta description is " + str(len(meta_desc)) + " characters (" + length_issue + "). Optimal length is 120-155 characters.",
                    "severity": "low",
                    "category": "content",
                    "batch_id": batch_id,
                })

        # --- Check 4: Thin product description ---
        word_count = len(body_text.split()) if body_text else 0
        if word_count < 50:
            ai_desc = await self.ai.generate_product_description(product_title, body_text)
            if ai_desc:
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "thin_content",
                    "platform": "shopify",
                    "resource_type": "product",
                    "resource_id": product_id,
                    "resource_url": product_url,
                    "resource_title": product_title,
                    "field_name": "body_html",
                    "current_value": "(" + str(word_count) + " words) " + body_text[:200] if body_text else "(empty)",
                    "proposed_value": ai_desc,
                    "ai_reasoning": "Product description has only " + str(word_count) + " words. Products with detailed descriptions (100+ words) rank better and convert more customers.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        return fixes

    async def _scan_all_pages(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan all Shopify pages with pagination."""
        fixes = []
        since_id = 0

        while True:
            params = {"limit": 250}
            if since_id > 0:
                params["since_id"] = since_id

            data = await self._api_get("pages.json", params)
            if not data or "pages" not in data:
                break

            pages = data["pages"]
            if not pages:
                break

            for page in pages:
                page_id = str(page["id"])
                title = page.get("title", "")
                handle = page.get("handle", "")
                body_html = page.get("body_html", "") or ""
                page_url = f"{self.store_url}/pages/{handle}"

                from bs4 import BeautifulSoup
                body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

                metafields = await self._get_page_metafields(page_id)
                meta_title = metafields.get("title_tag", "")
                meta_desc = metafields.get("description_tag", "")

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
                            "current_value": title + " (using page name as fallback)",
                            "proposed_value": ai_title,
                            "ai_reasoning": "No custom SEO title set for this page.",
                            "severity": "medium",
                            "category": "content",
                            "batch_id": batch_id,
                        })

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
                            "ai_reasoning": "No meta description set for this page.",
                            "severity": "medium",
                            "category": "content",
                            "batch_id": batch_id,
                        })

                word_count = len(body_text.split()) if body_text else 0
                if 0 < word_count < 100:
                    fixes.append({
                        "website_id": website_id,
                        "fix_type": "thin_content",
                        "platform": "shopify",
                        "resource_type": "page",
                        "resource_id": page_id,
                        "resource_url": page_url,
                        "resource_title": title,
                        "field_name": "body_html",
                        "current_value": "(" + str(word_count) + " words)",
                        "proposed_value": "(content expansion recommended - approve to generate)",
                        "ai_reasoning": "Page has only " + str(word_count) + " words. Pages with 300+ words rank better.",
                        "severity": "low",
                        "category": "content",
                        "batch_id": batch_id,
                    })

                await asyncio.sleep(1.5)

            since_id = pages[-1]["id"]
            if len(pages) < 250:
                break

        return fixes

    async def _scan_collections(self, website_id: int, batch_id: str) -> List[Dict]:
        """Scan Shopify collections for SEO issues."""
        fixes = []

        for col_type in ["smart_collections", "custom_collections"]:
            data = await self._api_get(f"{col_type}.json", {"limit": 250})
            if data and col_type in data:
                for col in data[col_type]:
                    col_id = str(col["id"])
                    title = col.get("title", "")
                    handle = col.get("handle", "")
                    body_html = col.get("body_html", "") or ""
                    col_url = f"{self.store_url}/collections/{handle}"

                    from bs4 import BeautifulSoup
                    body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

                    if not body_text or len(body_text.split()) < 50:
                        word_count = len(body_text.split()) if body_text else 0
                        fixes.append({
                            "website_id": website_id,
                            "fix_type": "thin_content",
                            "platform": "shopify",
                            "resource_type": "collection",
                            "resource_id": col_id,
                            "resource_url": col_url,
                            "resource_title": title,
                            "field_name": "body_html",
                            "current_value": "(" + str(word_count) + " words)" if body_text else "(empty)",
                            "proposed_value": "(collection description recommended - approve to generate)",
                            "ai_reasoning": "Collection '" + title + "' has little or no description. Collection pages with 100+ words of unique content rank significantly better.",
                            "severity": "medium",
                            "category": "content",
                            "batch_id": batch_id,
                        })

                    await asyncio.sleep(0.5)

        return fixes

    # ─────────────────────────────────────────
    #  Apply approved fixes
    # ─────────────────────────────────────────

    async def apply_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        try:
            if fix.fix_type == "alt_text":
                return await self._apply_alt_text_fix(fix)
            elif fix.fix_type in ["meta_title", "meta_description"]:
                return await self._apply_meta_fix(fix)
            elif fix.fix_type == "thin_content":
                return await self._apply_content_fix(fix)
            else:
                return False, "Fix type '" + fix.fix_type + "' not yet implemented"
        except Exception as e:
            return False, str(e)

    async def _apply_alt_text_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
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
        resource_type = fix.resource_type
        resource_id = fix.resource_id
        key = "title_tag" if fix.fix_type == "meta_title" else "description_tag"

        endpoint_map = {
            "product": f"products/{resource_id}/metafields.json",
            "page": f"pages/{resource_id}/metafields.json",
            "collection": f"collections/{resource_id}/metafields.json",
        }
        endpoint = endpoint_map.get(resource_type)
        if not endpoint:
            return False, "Unknown resource type: " + resource_type

        metafield_data = {
            "metafield": {
                "namespace": "global",
                "key": key,
                "value": fix.proposed_value,
                "type": "single_line_text_field"
            }
        }
        result = await self._api_post(endpoint, metafield_data)
        if result:
            return True, "SEO " + fix.fix_type.replace("meta_", "") + " updated successfully"
        return False, "Shopify API error when updating " + fix.fix_type

    async def _apply_content_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        resource_type = fix.resource_type
        resource_id = fix.resource_id
        if resource_type == "product":
            result = await self._api_put(
                f"products/{resource_id}.json",
                {"product": {"id": int(resource_id), "body_html": fix.proposed_value}}
            )
        elif resource_type == "page":
            result = await self._api_put(
                f"pages/{resource_id}.json",
                {"page": {"id": int(resource_id), "body_html": fix.proposed_value}}
            )
        else:
            return False, "Content fix not supported for " + resource_type
        if result:
            return True, "Content updated successfully"
        return False, "Shopify API rejected the content update"


class WordPressFixEngine:
    """Connects to WordPress REST API to apply fixes."""

    def __init__(self, wp_url: str, username: str = "", app_password: str = ""):
        self.wp_url = wp_url.rstrip('/')
        if not self.wp_url.startswith('https://'):
            self.wp_url = f"https://{self.wp_url}"
        self.api_base = f"{self.wp_url}/wp-json/wp/v2"
        # Use explicit Authorization header — more reliable than auth tuple
        import base64
        app_password = app_password.replace(" ", "")  # Strip spaces WordPress adds
        auth_string = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {auth_string}"} if username and app_password else {}
        self.ai = AIFixGenerator()

    async def _api_get(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(f"{self.api_base}/{endpoint}", params=params, headers=self.headers)
                if resp.status_code == 200:
                    return resp.json()
                print(f"[WP API] GET {endpoint} failed: {resp.status_code}")
                return None
        except Exception as e:
            print(f"[WP API] GET {endpoint} error: {e}")
            return None

    async def scan_and_generate_fixes(self, website_id: int, batch_id: str) -> List[Dict]:
        fixes = []

        # Scan posts (paginated)
        page_num = 1
        while True:
            posts = await self._api_get("posts", {"per_page": 100, "page": page_num, "status": "publish"})
            if not posts:
                break
            for post in posts:
                post_fixes = await self._analyze_wp_content(post, "post", website_id, batch_id)
                fixes.extend(post_fixes)
            if len(posts) < 100:
                break
            page_num += 1

        # Scan pages (paginated)
        page_num = 1
        while True:
            pages = await self._api_get("pages", {"per_page": 100, "page": page_num, "status": "publish"})
            if not pages:
                break
            for page in pages:
                page_fixes = await self._analyze_wp_content(page, "page", website_id, batch_id)
                fixes.extend(page_fixes)
            if len(pages) < 100:
                break
            page_num += 1

        return fixes

    async def _analyze_wp_content(self, content: Dict, content_type: str, website_id: int, batch_id: str) -> List[Dict]:
        fixes = []
        content_id = str(content["id"])
        title = content.get("title", {}).get("rendered", "")
        url = content.get("link", "")
        body_html = content.get("content", {}).get("rendered", "")
        excerpt = content.get("excerpt", {}).get("rendered", "")

        from bs4 import BeautifulSoup
        body_text = BeautifulSoup(body_html, 'html.parser').get_text(strip=True) if body_html else ""

        # Check for images without alt text
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
                        "field_name": "content_image_alt",
                        "current_value": "(empty)",
                        "proposed_value": ai_alt,
                        "ai_reasoning": "Image in " + content_type + " '" + title + "' has no alt text.",
                        "severity": "high",
                        "category": "accessibility",
                        "batch_id": batch_id,
                    })

        # Check excerpt/meta description
        excerpt_text = BeautifulSoup(excerpt, 'html.parser').get_text(strip=True) if excerpt else ""
        if not excerpt_text or len(excerpt_text) < 50:
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
                    "current_value": excerpt_text if excerpt_text else "(empty)",
                    "proposed_value": ai_desc,
                    "ai_reasoning": "No excerpt/meta description set. Most themes use the excerpt as the meta description.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        # Check thin content (posts only)
        word_count = len(body_text.split()) if body_text else 0
        if 0 < word_count < 300 and content_type == "post":
            fixes.append({
                "website_id": website_id,
                "fix_type": "thin_content",
                "platform": "wordpress",
                "resource_type": content_type,
                "resource_id": content_id,
                "resource_url": url,
                "resource_title": title,
                "field_name": "content",
                "current_value": "(" + str(word_count) + " words)",
                "proposed_value": "(content expansion recommended)",
                "ai_reasoning": "Blog post has only " + str(word_count) + " words. Posts with 800+ words tend to rank significantly better.",
                "severity": "low",
                "category": "content",
                "batch_id": batch_id,
            })

        # Check title — too short, too long, or generic
        clean_title = BeautifulSoup(title, 'html.parser').get_text(strip=True) if title else ""
        if clean_title and (len(clean_title) < 20 or len(clean_title) > 70):
            ai_title = await self.ai.generate_meta_title(body_text or clean_title, clean_title)
            if ai_title and ai_title != clean_title:
                fixes.append({
                    "website_id": website_id,
                    "fix_type": "meta_title",
                    "platform": "wordpress",
                    "resource_type": content_type,
                    "resource_id": content_id,
                    "resource_url": url,
                    "resource_title": clean_title,
                    "field_name": "title",
                    "current_value": clean_title + " (" + str(len(clean_title)) + " chars)",
                    "proposed_value": ai_title,
                    "ai_reasoning": "Title is " + ("too short" if len(clean_title) < 20 else "too long") + " (" + str(len(clean_title)) + " chars). Optimal: 30-60 characters.",
                    "severity": "medium",
                    "category": "content",
                    "batch_id": batch_id,
                })

        return fixes

    # ─── Apply fixes via WP REST API (with XML-RPC fallback) ───

    async def _api_put(self, endpoint: str, data: Dict) -> Optional[Any]:
        """Try REST API first, fall back to XML-RPC if blocked by security plugin."""
        # Try REST API
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.post(f"{self.api_base}/{endpoint}", json=data, headers=self.headers)
                if resp.status_code in [200, 201]:
                    return resp.json()
                error_msg = resp.text[:200]
                print(f"[WP API] REST PUT {endpoint} failed: {resp.status_code} {error_msg}")

                # If REST API blocked (401/403 with rest_cannot_edit), try XML-RPC
                if resp.status_code in [401, 403] and "rest_cannot_edit" in error_msg:
                    print(f"[WP API] REST blocked by security plugin, trying XML-RPC...")
                    return await self._xmlrpc_edit(endpoint, data)
        except Exception as e:
            print(f"[WP API] REST PUT {endpoint} error: {e}")
        return None

    async def _xmlrpc_edit(self, endpoint: str, data: Dict) -> Optional[Any]:
        """Edit a WordPress post/page via XML-RPC (works when REST API is blocked by security plugins)."""
        try:
            import base64
            # Parse endpoint like "posts/123" or "pages/456"
            parts = endpoint.split("/")
            if len(parts) < 2:
                print(f"[WP XML-RPC] Cannot parse endpoint: {endpoint}")
                return None
            post_id = parts[1]

            # Extract username and password from Basic auth header
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Basic "):
                return None
            decoded = base64.b64decode(auth_header.split(" ")[1]).decode()
            username, password = decoded.split(":", 1)

            # Build XML-RPC payload for wp.editPost
            # Map REST API fields to XML-RPC struct
            content_struct = ""
            if "content" in data:
                escaped = data["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                content_struct += f"<member><name>post_content</name><value><string>{escaped}</string></value></member>"
            if "excerpt" in data:
                escaped = data["excerpt"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                content_struct += f"<member><name>post_excerpt</name><value><string>{escaped}</string></value></member>"
            if "title" in data:
                escaped = data["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                content_struct += f"<member><name>post_title</name><value><string>{escaped}</string></value></member>"

            if not content_struct:
                return None

            xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>wp.editPost</methodName>
  <params>
    <param><value><int>1</int></value></param>
    <param><value><string>{username}</string></value></param>
    <param><value><string>{password}</string></value></param>
    <param><value><int>{post_id}</int></value></param>
    <param><value><struct>{content_struct}</struct></value></param>
  </params>
</methodCall>"""

            xmlrpc_url = f"{self.wp_url}/xmlrpc.php"
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.post(xmlrpc_url, content=xml_payload.encode(),
                    headers={"Content-Type": "text/xml; charset=utf-8"})

                if resp.status_code == 200 and "<boolean>1</boolean>" in resp.text:
                    print(f"[WP XML-RPC] Successfully edited post {post_id}")
                    return {"id": int(post_id), "status": "updated via XML-RPC"}
                elif resp.status_code == 200 and "<name>faultString</name>" in resp.text:
                    # Parse error
                    import re
                    fault = re.search(r"<string>(.*?)</string>", resp.text)
                    error = fault.group(1) if fault else "Unknown XML-RPC error"
                    print(f"[WP XML-RPC] Edit post {post_id} failed: {error}")
                    return None
                elif resp.status_code == 403:
                    print(f"[WP XML-RPC] XML-RPC also blocked (403). Security plugin blocks both REST and XML-RPC.")
                    return None
                else:
                    print(f"[WP XML-RPC] Unexpected: {resp.status_code} {resp.text[:200]}")
                    return None
        except Exception as e:
            print(f"[WP XML-RPC] Error: {e}")
            return None

    async def apply_fix(self, fix: ProposedFix) -> Tuple[bool, str]:
        try:
            if fix.fix_type == "alt_text":
                return await self._apply_wp_alt_text(fix)
            elif fix.fix_type == "meta_description":
                return await self._apply_wp_excerpt(fix)
            elif fix.fix_type == "meta_title":
                return await self._apply_wp_meta_title(fix)
            elif fix.fix_type == "thin_content":
                return await self._apply_wp_content(fix)
            elif fix.fix_type == "structured_data":
                return await self._apply_wp_structured_data(fix)
            else:
                return False, "Fix type '" + fix.fix_type + "' not yet supported for WordPress"
        except Exception as e:
            return False, str(e)

    async def _apply_wp_alt_text(self, fix: ProposedFix) -> Tuple[bool, str]:
        resource_id = fix.resource_id
        endpoint = "posts/" + resource_id if fix.resource_type == "post" else "pages/" + resource_id

        # Get content via XML-RPC first (returns raw content), fall back to REST
        content = None
        try:
            content = await self._xmlrpc_get_content(resource_id)
            if content:
                print(f"[WP Fix] Got raw content via XML-RPC for {fix.resource_type} {resource_id}")
        except:
            pass

        if not content:
            data = await self._api_get(endpoint)
            if not data:
                return False, "Could not fetch " + fix.resource_type
            content = data.get("content", {}).get("raw", data.get("content", {}).get("rendered", ""))

        if not content:
            return False, "No content found in " + fix.resource_type

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        updated = False

        # Find images with empty or missing alt text — be lenient
        for img in soup.find_all('img'):
            alt = img.get('alt')
            if alt is None or not alt.strip():
                img['alt'] = fix.proposed_value
                updated = True
                break  # Fix one at a time

        if not updated:
            # Try matching by src URL from the fix's current_value or resource info
            for img in soup.find_all('img'):
                img['alt'] = fix.proposed_value
                updated = True
                break  # Just fix the first image if none matched

        if not updated:
            return False, "No images found in content"

        result = await self._api_put(endpoint, {"content": str(soup)})
        if result:
            return True, "Alt text updated in WordPress"
        return False, "WordPress API rejected the update"

    async def _apply_wp_meta_title(self, fix: ProposedFix) -> Tuple[bool, str]:
        """Update meta title via Yoast SEO or RankMath post meta, or fall back to post title."""
        resource_id = fix.resource_id
        endpoint = "posts/" + resource_id if fix.resource_type == "post" else "pages/" + resource_id

        # Try updating the post title directly (works without SEO plugins)
        print(f"[WP Fix] Applying meta title fix to {endpoint}: '{fix.proposed_value}'")
        result = await self._api_put(endpoint, {"title": fix.proposed_value})
        if result:
            return True, "Title updated in WordPress"

        # If REST failed, XML-RPC will have been tried via _api_put
        return False, "WordPress rejected the title update"

    async def _apply_wp_structured_data(self, fix: ProposedFix) -> Tuple[bool, str]:
        """Structured data fixes need manual implementation or plugin — provide guidance."""
        return False, "Structured data (Schema) fixes require a WordPress SEO plugin like Yoast or RankMath. Apply manually in the page editor."

    async def _xmlrpc_get_content(self, post_id: str) -> Optional[str]:
        """Get post content via XML-RPC (works when REST API auth is blocked)."""
        try:
            import base64
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Basic "):
                return None
            decoded = base64.b64decode(auth_header.split(" ")[1]).decode()
            username, password = decoded.split(":", 1)

            xml_payload = f"""<?xml version="1.0"?>
<methodCall>
  <methodName>wp.getPost</methodName>
  <params>
    <param><value><int>1</int></value></param>
    <param><value><string>{username}</string></value></param>
    <param><value><string>{password}</string></value></param>
    <param><value><int>{post_id}</int></value></param>
  </params>
</methodCall>"""

            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.post(f"{self.wp_url}/xmlrpc.php", content=xml_payload.encode(),
                    headers={"Content-Type": "text/xml; charset=utf-8"})
                if resp.status_code == 200 and "post_content" in resp.text:
                    import re
                    match = re.search(r"<name>post_content</name>\s*<value><string>(.*?)</string></value>", resp.text, re.DOTALL)
                    if match:
                        content = match.group(1)
                        # Unescape XML entities
                        content = content.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                        return content
        except Exception as e:
            print(f"[WP XML-RPC] getPost error: {e}")
        return None

    async def _apply_wp_excerpt(self, fix: ProposedFix) -> Tuple[bool, str]:
        resource_id = fix.resource_id
        endpoint = "posts/" + resource_id if fix.resource_type == "post" else "pages/" + resource_id
        print(f"[WP Fix] Applying excerpt fix to {endpoint}")
        result = await self._api_put(endpoint, {"excerpt": fix.proposed_value})
        if result:
            return True, "Excerpt/meta description updated"
        return False, "WordPress API rejected the update"

    async def _apply_wp_content(self, fix: ProposedFix) -> Tuple[bool, str]:
        resource_id = fix.resource_id
        endpoint = "posts/" + resource_id if fix.resource_type == "post" else "pages/" + resource_id
        print(f"[WP Fix] Applying content fix to {endpoint}")
        result = await self._api_put(endpoint, {"content": fix.proposed_value})
        if result:
            return True, "Content updated in WordPress"
        return False, "WordPress API rejected the update"


# ─────────────────────────────────────────
#  Shopify token refresh (client_credentials tokens expire in 24h)
# ─────────────────────────────────────────

async def _refresh_shopify_token(db, integration) -> str:
    """Refresh a Shopify access token using client_credentials grant."""
    config = integration.config or {}
    client_id = config.get("client_id", "")
    client_secret = config.get("client_secret", "")
    shop_domain = config.get("shop_domain", "")

    if not client_id or not client_secret or not shop_domain:
        return integration.access_token or ""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://{shop_domain}/admin/oauth/access_token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if resp.status_code == 200:
                token_data = resp.json()
                new_token = token_data.get("access_token", "")
                if new_token:
                    integration.access_token = new_token
                    config["token_obtained_at"] = datetime.utcnow().isoformat()
                    config["token_expires_in"] = token_data.get("expires_in", 86399)
                    integration.config = config
                    # Propagate to Website record so apply_approved_fix doesn't use stale token
                    website = db.query(Website).filter(Website.id == integration.website_id).first()
                    if website:
                        website.shopify_access_token = new_token
                    db.commit()
                    print(f"[Shopify] Token refreshed for {shop_domain}")
                    return new_token
            else:
                print(f"[Shopify] Token refresh failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[Shopify] Token refresh error: {e}")

    return integration.access_token or ""


# ─────────────────────────────────────────
#  Main orchestrator
# ─────────────────────────────────────────

async def generate_fixes_for_website(website_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        batch_id = "batch_" + str(website_id) + "_" + datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        all_fixes = []

        # Determine which platform to use — check integrations first, then site_type
        shopify_integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "shopify",
            Integration.status == "active"
        ).first()

        wordpress_integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "wordpress",
            Integration.status == "active"
        ).first()

        if website.site_type == "shopify" or shopify_integration:
            store_url = website.shopify_store_url or website.domain
            access_token = website.shopify_access_token

            if shopify_integration:
                access_token = shopify_integration.access_token or access_token
                config = shopify_integration.config or {}
                store_url = config.get("store_url", store_url)

                # Auto-refresh token if using client_credentials flow (token expires in 24h)
                if config.get("auth_method") == "client_credentials" and config.get("client_id") and config.get("client_secret"):
                    access_token = await _refresh_shopify_token(db, shopify_integration)

            if not access_token:
                return {"error": "Shopify access token not configured. Connect Shopify via the integration checklist."}

            engine = ShopifyFixEngine(store_url, access_token)
            all_fixes = await engine.scan_and_generate_fixes(website_id, batch_id)

        elif website.site_type == "wordpress" or wordpress_integration:
            wp_url = website.domain
            username = ""
            app_password = ""

            if wordpress_integration:
                app_password = wordpress_integration.access_token or ""
                config = wordpress_integration.config or {}
                username = config.get("username", "")
                wp_url = config.get("wp_url", wp_url)

            engine = WordPressFixEngine(wp_url, username=username, app_password=app_password)
            all_fixes = await engine.scan_and_generate_fixes(website_id, batch_id)

        else:
            return {"error": "No Shopify or WordPress integration connected. Connect one via the integration checklist to enable auto-fixes."}

        # Save fixes to database
        saved_count = 0
        for fix_data in all_fixes:
            fix_data.pop("extra", None)
            proposed_fix = ProposedFix(**fix_data)
            db.add(proposed_fix)
            saved_count += 1

        db.commit()
        print(f"[FixEngine] Generated {saved_count} proposed fixes for website {website_id} (batch: {batch_id})")

        return {
            "batch_id": batch_id,
            "total_fixes": saved_count,
            "fix_types": _count_by_type(all_fixes),
            "message": "Generated " + str(saved_count) + " fix proposals. Review and approve them in the Approval Queue."
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
    db = SessionLocal()
    try:
        fix = db.query(ProposedFix).filter(ProposedFix.id == fix_id).first()
        if not fix:
            return {"error": "Fix not found"}
        if fix.status != "approved":
            return {"error": "Fix is not approved (status: " + fix.status + ")"}

        website = db.query(Website).filter(Website.id == fix.website_id).first()
        if not website:
            return {"error": "Website not found"}

        success = False
        message = ""

        if fix.platform == "shopify":
            store_url = website.shopify_store_url or website.domain
            access_token = website.shopify_access_token

            # Always prefer the Integration record — the token there is refreshed; the
            # Website record's copy can be stale after the 24h client_credentials expiry.
            integration = db.query(Integration).filter(
                Integration.website_id == website.id,
                Integration.integration_type == "shopify",
                Integration.status == "active"
            ).first()
            if integration:
                config = integration.config or {}
                store_url = config.get("store_url", store_url)
                if config.get("auth_method") == "client_credentials" and config.get("client_id") and config.get("client_secret"):
                    access_token = await _refresh_shopify_token(db, integration)
                else:
                    access_token = integration.access_token or access_token

            if not access_token:
                fix.status = "failed"
                fix.error_message = "No Shopify access token"
                db.commit()
                return {"error": "No Shopify access token configured"}

            engine = ShopifyFixEngine(store_url, access_token)
            success, message = await engine.apply_fix(fix)

        elif fix.platform == "wordpress":
            integration = db.query(Integration).filter(
                Integration.website_id == website.id,
                Integration.integration_type == "wordpress",
                Integration.status == "active"
            ).first()

            wp_url = website.domain
            username = ""
            app_password = ""

            if integration:
                app_password = integration.access_token or ""
                config = integration.config or {}
                username = config.get("username", "")
                wp_url = config.get("wp_url", wp_url)

            if not app_password:
                fix.status = "failed"
                fix.error_message = "No WordPress credentials configured"
                db.commit()
                return {"error": "WordPress not connected. Add app password in integrations."}

            engine = WordPressFixEngine(wp_url, username=username, app_password=app_password)
            success, message = await engine.apply_fix(fix)

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
    counts = {}
    for f in fixes:
        t = f.get("fix_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
