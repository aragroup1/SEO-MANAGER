# backend/sitemap_generator.py - Sitemap XML Generator
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urljoin, urlparse
import asyncio
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database import SessionLocal, Website, Integration

# ─── Constants ───
MAX_URLS = 10000
DEFAULT_HEADERS = {
    "User-Agent": "SEOIntelligenceBot/1.0 (+https://example.com/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SITEMAP_NS = "http://www.s3.org/2001/XMLSchema-instance"
SITEMAP_SCHEMA = "http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"


# ═══════════════════════════════════════════════════════════════════════════════
#  ROBOTS.TXT PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class RobotsParser:
    def __init__(self, base_url: str, user_agent: str = "*"):
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.rules: List[Dict[str, Any]] = []
        self.sitemaps: List[str] = []
        self.crawl_delay: Optional[float] = None
        self._parsed = False

    async def fetch(self):
        try:
            robots_url = f"{self.base_url}/robots.txt"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(robots_url, headers=DEFAULT_HEADERS)
                if resp.status_code == 200:
                    self._parse(resp.text)
                else:
                    print(f"[Sitemap] robots.txt not found ({resp.status_code}), allowing all")
        except Exception as e:
            print(f"[Sitemap] robots.txt fetch error: {e}")
        self._parsed = True

    def _parse(self, text: str):
        current_agent = "*"
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()

            if key == "user-agent":
                current_agent = val
            elif key == "disallow" and current_agent in (self.user_agent, "*"):
                self.rules.append({"type": "disallow", "path": val})
            elif key == "allow" and current_agent in (self.user_agent, "*"):
                self.rules.append({"type": "allow", "path": val})
            elif key == "crawl-delay" and current_agent in (self.user_agent, "*"):
                try:
                    self.crawl_delay = float(val)
                except ValueError:
                    pass
            elif key == "sitemap":
                self.sitemaps.append(val)

    def is_allowed(self, url_path: str) -> bool:
        if not self._parsed:
            return True
        allowed = True
        for rule in self.rules:
            if rule["path"] == "/" or url_path.startswith(rule["path"]):
                allowed = rule["type"] == "allow"
        return allowed


# ═══════════════════════════════════════════════════════════════════════════════
#  WEB CRAWLER
# ═══════════════════════════════════════════════════════════════════════════════

class SitemapCrawler:
    def __init__(self, domain: str, max_urls: int = MAX_URLS):
        self.domain = domain.lower().replace("http://", "").replace("https://", "").rstrip("/")
        self.base_url = f"https://{self.domain}"
        self.max_urls = max_urls
        self.visited: Set[str] = set()
        self.results: List[Dict[str, Any]] = []
        self.robots = RobotsParser(self.base_url)

    async def crawl(self) -> List[Dict[str, Any]]:
        await self.robots.fetch()
        await self._crawl_page("/")
        print(f"[Sitemap] Crawled {len(self.results)} URLs for {self.domain}")
        return self.results

    async def _crawl_page(self, path: str):
        if len(self.visited) >= self.max_urls:
            return
        if path in self.visited:
            return
        if not self.robots.is_allowed(path):
            print(f"[Sitemap] robots.txt blocked: {path}")
            return

        self.visited.add(path)
        url = urljoin(self.base_url, path)

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return
                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return

                soup = BeautifulSoup(resp.text, "html.parser")

                # Extract page metadata
                title = ""
                if soup.title:
                    title = soup.title.get_text(strip=True)

                lastmod = ""
                # Try to find last modified from meta tags
                for meta in soup.find_all("meta"):
                    prop = (meta.get("property") or "").lower()
                    name = (meta.get("name") or "").lower()
                    if prop in ("article:modified_time", "og:updated_time") or name in ("last-modified", "date-modified"):
                        lastmod = meta.get("content", "")
                        break

                # Determine changefreq and priority heuristically
                changefreq = self._guess_changefreq(path)
                priority = self._guess_priority(path)

                self.results.append({
                    "loc": url,
                    "path": path,
                    "lastmod": lastmod,
                    "changefreq": changefreq,
                    "priority": priority,
                    "title": title,
                })

                # Find internal links
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full = urljoin(self.base_url, href)
                    parsed = urlparse(full)
                    if parsed.netloc.lower().replace("www.", "") != self.domain.replace("www.", ""):
                        continue
                    next_path = parsed.path or "/"
                    if parsed.query:
                        next_path += "?" + parsed.query
                    # Skip fragments, common non-page URLs
                    if "#" in next_path:
                        next_path = next_path.split("#")[0]
                    if any(next_path.lower().endswith(ext) for ext in [
                        ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".css", ".js",
                        ".mp4", ".mp3", ".svg", ".woff", ".woff2", ".ttf", ".eot",
                    ]):
                        continue
                    if next_path not in self.visited:
                        await self._crawl_page(next_path)
                        if self.robots.crawl_delay:
                            await asyncio.sleep(self.robots.crawl_delay)

        except Exception as e:
            print(f"[Sitemap] Crawl error for {url}: {e}")

    def _guess_changefreq(self, path: str) -> str:
        path_lower = path.lower()
        if path == "/":
            return "daily"
        if "/blog/" in path_lower or "/news/" in path_lower or "/article/" in path_lower:
            return "weekly"
        if "/product/" in path_lower or "/collection/" in path_lower or "/category/" in path_lower:
            return "weekly"
        if "/about" in path_lower or "/contact" in path_lower or "/privacy" in path_lower or "/terms" in path_lower:
            return "monthly"
        return "weekly"

    def _guess_priority(self, path: str) -> str:
        if path == "/":
            return "1.0"
        depth = path.count("/")
        if depth <= 1:
            return "0.8"
        if depth == 2:
            return "0.6"
        return "0.4"


# ═══════════════════════════════════════════════════════════════════════════════
#  PLATFORM-SPECIFIC FETCHERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_shopify_pages(shopify_store_url: str, access_token: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch pages from Shopify Storefront API or sitemap.xml."""
    pages: List[Dict[str, Any]] = []
    domain = shopify_store_url.replace("https://", "").replace("http://", "").rstrip("/")
    base = f"https://{domain}"

    # Try sitemap.xml first (fastest)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(f"{base}/sitemap.xml", headers=DEFAULT_HEADERS)
            if resp.status_code == 200:
                parsed = _parse_sitemap_xml(resp.text)
                if parsed:
                    print(f"[Sitemap] Shopify sitemap.xml found with {len(parsed)} URLs")
                    return parsed
    except Exception as e:
        print(f"[Sitemap] Shopify sitemap.xml error: {e}")

    # Try Storefront API
    if access_token:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # Products
                resp = await client.get(
                    f"{base}/admin/api/2024-01/products.json?limit=250",
                    headers={"X-Shopify-Access-Token": access_token}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for p in data.get("products", []):
                        pages.append({
                            "loc": f"{base}/products/{p.get('handle', '')}",
                            "lastmod": p.get("updated_at", "")[:10],
                            "changefreq": "weekly",
                            "priority": "0.8",
                            "title": p.get("title", ""),
                        })
                # Collections
                resp2 = await client.get(
                    f"{base}/admin/api/2024-01/custom_collections.json?limit=250",
                    headers={"X-Shopify-Access-Token": access_token}
                )
                if resp2.status_code == 200:
                    for c in resp2.json().get("custom_collections", []):
                        pages.append({
                            "loc": f"{base}/collections/{c.get('handle', '')}",
                            "lastmod": c.get("updated_at", "")[:10],
                            "changefreq": "weekly",
                            "priority": "0.7",
                            "title": c.get("title", ""),
                        })
                # Pages
                resp3 = await client.get(
                    f"{base}/admin/api/2024-01/pages.json?limit=250",
                    headers={"X-Shopify-Access-Token": access_token}
                )
                if resp3.status_code == 200:
                    for pg in resp3.json().get("pages", []):
                        pages.append({
                            "loc": f"{base}/pages/{pg.get('handle', '')}",
                            "lastmod": pg.get("updated_at", "")[:10],
                            "changefreq": "monthly",
                            "priority": "0.6",
                            "title": pg.get("title", ""),
                        })
                print(f"[Sitemap] Shopify API returned {len(pages)} pages")
                return pages
        except Exception as e:
            print(f"[Sitemap] Shopify API error: {e}")

    # Fallback to basic crawl
    print(f"[Sitemap] Falling back to crawl for Shopify store {domain}")
    crawler = SitemapCrawler(domain, max_urls=MAX_URLS)
    return await crawler.crawl()


async def _fetch_wordpress_pages(wp_url: str, username: Optional[str] = None, app_password: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch pages from WordPress REST API or wp-sitemap.xml."""
    pages: List[Dict[str, Any]] = []
    domain = wp_url.replace("https://", "").replace("http://", "").rstrip("/")
    base = f"https://{domain}"

    # Try wp-sitemap.xml first
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(f"{base}/wp-sitemap.xml", headers=DEFAULT_HEADERS)
            if resp.status_code == 200:
                parsed = _parse_sitemap_xml(resp.text)
                if parsed:
                    print(f"[Sitemap] WordPress wp-sitemap.xml found with {len(parsed)} URLs")
                    return parsed
    except Exception as e:
        print(f"[Sitemap] WordPress wp-sitemap.xml error: {e}")

    # Try REST API
    headers = DEFAULT_HEADERS.copy()
    if username and app_password:
        import base64
        auth = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        headers["Authorization"] = f"Basic {auth}"

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            # Posts
            page = 1
            while len(pages) < MAX_URLS and page <= 20:
                resp = await client.get(
                    f"{base}/wp-json/wp/v2/posts?per_page=100&page={page}&_fields=id,link,modified,title",
                    headers=headers
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                for post in data:
                    pages.append({
                        "loc": post.get("link", ""),
                        "lastmod": (post.get("modified") or "")[:10],
                        "changefreq": "weekly",
                        "priority": "0.7",
                        "title": post.get("title", {}).get("rendered", ""),
                    })
                page += 1

            # Pages
            page = 1
            while len(pages) < MAX_URLS and page <= 10:
                resp = await client.get(
                    f"{base}/wp-json/wp/v2/pages?per_page=100&page={page}&_fields=id,link,modified,title",
                    headers=headers
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                for pg in data:
                    pages.append({
                        "loc": pg.get("link", ""),
                        "lastmod": (pg.get("modified") or "")[:10],
                        "changefreq": "monthly",
                        "priority": "0.8" if pg.get("link", "").rstrip("/").endswith(domain) else "0.6",
                        "title": pg.get("title", {}).get("rendered", ""),
                    })
                page += 1

            print(f"[Sitemap] WordPress API returned {len(pages)} pages")
            return pages
    except Exception as e:
        print(f"[Sitemap] WordPress API error: {e}")

    # Fallback to basic crawl
    print(f"[Sitemap] Falling back to crawl for WordPress site {domain}")
    crawler = SitemapCrawler(domain, max_urls=MAX_URLS)
    return await crawler.crawl()


def _parse_sitemap_xml(xml_text: str) -> List[Dict[str, Any]]:
    """Parse an existing sitemap XML and extract URL entries."""
    pages: List[Dict[str, Any]] = []
    try:
        # Handle sitemap index files
        if "<sitemapindex" in xml_text.lower():
            # For simplicity, return empty to trigger fallback (or could recurse)
            return []

        root = ET.fromstring(xml_text.encode("utf-8"))
        # Handle namespace
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for url_elem in root.findall("sm:url", ns) or root.findall("url"):
            loc = ""
            lastmod = ""
            changefreq = "weekly"
            priority = "0.5"
            for child in url_elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "loc":
                    loc = child.text or ""
                elif tag == "lastmod":
                    lastmod = child.text or ""
                elif tag == "changefreq":
                    changefreq = child.text or "weekly"
                elif tag == "priority":
                    priority = child.text or "0.5"
            if loc:
                pages.append({
                    "loc": loc,
                    "lastmod": lastmod,
                    "changefreq": changefreq,
                    "priority": priority,
                    "title": "",
                })
    except Exception as e:
        print(f"[Sitemap] XML parse error: {e}")
    return pages


# ═══════════════════════════════════════════════════════════════════════════════
#  XML GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

def build_sitemap_xml(urls: List[Dict[str, Any]]) -> str:
    """Build a valid sitemap.xml string from URL entries."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for entry in urls:
        url_elem = ET.SubElement(root, "url")
        loc = ET.SubElement(url_elem, "loc")
        loc.text = entry.get("loc", "")

        lastmod = entry.get("lastmod", "")
        if lastmod:
            # Normalize to YYYY-MM-DD
            clean = lastmod[:10]
            if re.match(r"\d{4}-\d{2}-\d{2}", clean):
                lm = ET.SubElement(url_elem, "lastmod")
                lm.text = clean
            else:
                lm = ET.SubElement(url_elem, "lastmod")
                lm.text = today
        else:
            lm = ET.SubElement(url_elem, "lastmod")
            lm.text = today

        cf = ET.SubElement(url_elem, "changefreq")
        cf.text = entry.get("changefreq", "weekly")

        pr = ET.SubElement(url_elem, "priority")
        pr.text = entry.get("priority", "0.5")

    # Pretty-print
    ET.indent(root, space="  ")
    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return xml_bytes


def validate_sitemap(sitemap_xml: str) -> Dict[str, Any]:
    """Basic XML validation for sitemap."""
    result = {"valid": False, "errors": [], "warnings": [], "url_count": 0}
    if not sitemap_xml or not sitemap_xml.strip():
        result["errors"].append("Sitemap is empty")
        return result

    try:
        root = ET.fromstring(sitemap_xml.encode("utf-8"))
    except ET.ParseError as e:
        result["errors"].append(f"XML parse error: {e}")
        return result

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url", ns) or root.findall("url")
    result["url_count"] = len(urls)

    if len(urls) == 0:
        result["warnings"].append("No URL entries found")
    if len(urls) > MAX_URLS:
        result["errors"].append(f"Too many URLs: {len(urls)} (max {MAX_URLS})")

    # Check each URL
    for i, url_elem in enumerate(urls):
        loc = None
        for child in url_elem:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "loc":
                loc = child.text
                break
        if not loc:
            result["errors"].append(f"URL #{i+1} missing <loc>")
        elif not loc.startswith("http"):
            result["errors"].append(f"URL #{i+1} invalid <loc>: {loc}")

    result["valid"] = len(result["errors"]) == 0
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  GOOGLE SEARCH CONSOLE SUBMISSION
# ═══════════════════════════════════════════════════════════════════════════════

async def submit_to_gsc(website_id: int, sitemap_url: str) -> Dict[str, Any]:
    """Submit sitemap URL to Google Search Console via API."""
    db = SessionLocal()
    try:
        integration = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "google_search_console",
            Integration.status == "active"
        ).first()

        if not integration:
            return {"success": False, "error": "Google Search Console not connected"}

        token = integration.access_token
        if not token:
            return {"success": False, "error": "No access token"}

        config = integration.config or {}
        gsc_property = config.get("gsc_property", "")
        if not gsc_property:
            return {"success": False, "error": "No GSC property configured"}

        import urllib.parse
        encoded = urllib.parse.quote(gsc_property, safe="")
        api_url = f"https://www.googleapis.com/webmasters/v3/sites/{encoded}/sitemaps/{urllib.parse.quote(sitemap_url, safe='')}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(api_url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code in (200, 201, 204):
                print(f"[Sitemap] Submitted to GSC: {sitemap_url}")
                return {"success": True, "message": "Sitemap submitted to Google Search Console"}
            elif resp.status_code == 401:
                return {"success": False, "error": "Unauthorized — token expired"}
            elif resp.status_code == 403:
                return {"success": False, "error": "Forbidden — insufficient GSC permissions"}
            else:
                return {"success": False, "error": f"GSC API error {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        print(f"[Sitemap] GSC submission error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_sitemap(website_id: int) -> Dict[str, Any]:
    """Generate a sitemap for a website. Returns metadata + XML."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain.replace("http://", "").replace("https://", "").rstrip("/")
        site_type = (website.site_type or "custom").lower()

        urls: List[Dict[str, Any]] = []

        if site_type == "shopify" and website.shopify_store_url:
            urls = await _fetch_shopify_pages(
                website.shopify_store_url,
                website.shopify_access_token
            )
        elif site_type == "wordpress":
            # Look for WordPress integration credentials
            wp_integration = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "wordpress"
            ).first()
            wp_url = ""
            wp_user = None
            wp_pass = None
            if wp_integration:
                cfg = wp_integration.config or {}
                wp_url = cfg.get("wp_url", "")
                wp_user = cfg.get("username")
                wp_pass = wp_integration.access_token
            if not wp_url:
                wp_url = f"https://{domain}"
            urls = await _fetch_wordpress_pages(wp_url, wp_user, wp_pass)
        else:
            # Generic crawl
            crawler = SitemapCrawler(domain, max_urls=MAX_URLS)
            urls = await crawler.crawl()

        if not urls:
            return {"error": "No URLs found. Check the website is accessible."}

        # Limit to max
        if len(urls) > MAX_URLS:
            print(f"[Sitemap] Truncating from {len(urls)} to {MAX_URLS} URLs")
            urls = urls[:MAX_URLS]

        sitemap_xml = build_sitemap_xml(urls)
        validation = validate_sitemap(sitemap_xml)

        # Store in DB
        website.sitemap_xml = sitemap_xml
        website.sitemap_generated_at = datetime.utcnow()
        db.commit()

        print(f"[Sitemap] Generated sitemap for {domain}: {len(urls)} URLs, valid={validation['valid']}")

        return {
            "success": True,
            "domain": domain,
            "url_count": len(urls),
            "generated_at": datetime.utcnow().isoformat(),
            "valid": validation["valid"],
            "validation": validation,
            "urls": urls[:100],  # Return first 100 for preview
            "sitemap_xml": sitemap_xml,
        }

    except Exception as e:
        print(f"[Sitemap] Generation error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        db.close()


async def get_sitemap(website_id: int) -> Dict[str, Any]:
    """Get the stored sitemap for a website."""
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        if not website.sitemap_xml:
            return {
                "exists": False,
                "message": "No sitemap generated yet. Click Generate to create one.",
            }

        validation = validate_sitemap(website.sitemap_xml)
        # Parse URLs for preview
        urls = _parse_sitemap_xml(website.sitemap_xml)

        return {
            "exists": True,
            "domain": website.domain,
            "url_count": validation["url_count"],
            "generated_at": website.sitemap_generated_at.isoformat() if website.sitemap_generated_at else None,
            "valid": validation["valid"],
            "validation": validation,
            "urls": urls[:100],
            "sitemap_xml": website.sitemap_xml,
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
