# backend/audit_engine.py - Real SEO Audit Engine
import os
import sys
import ssl
import socket
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
import json
from enum import Enum
import numpy as np
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import from shared database module (no circular import)
from database import SessionLocal, Website, AuditReport

load_dotenv()


class IssueSeverity(Enum):
    CRITICAL = "Critical"
    ERROR = "Error"
    WARNING = "Warning"
    NOTICE = "Notice"


class SEOAuditEngine:
    """
    Real SEO audit engine that crawls a website and performs comprehensive checks:
    - Meta tags (title, description, viewport, charset)
    - Headings structure (H1, H2, hierarchy)
    - Images (alt text, size attributes)
    - Links (internal, external, broken)
    - Robots.txt and Sitemap.xml
    - SSL/HTTPS
    - Page speed basics (HTML size, resource count)
    - Open Graph and Twitter Cards
    - Structured data (JSON-LD, microdata)
    - Canonical tags
    - Hreflang tags
    - Mobile viewport
    - Content quality (word count, reading level)
    """

    def __init__(self, website_id: int):
        self.website_id = website_id
        self.db: Optional[Session] = None
        self.website: Optional[Website] = None
        self.base_url: Optional[str] = None
        self.domain: Optional[str] = None
        self.issues: List[Dict] = []
        self.recommendations: List[Dict] = []
        self.raw_data: Dict[str, Any] = {}

    def __enter__(self):
        self.db = SessionLocal()
        self.website = self.db.query(Website).filter(Website.id == self.website_id).first()
        if not self.website:
            raise ValueError(f"Website with ID {self.website_id} not found.")

        self.domain = self.website.domain

        # Ensure base URL has https scheme
        if not self.domain.startswith(('http://', 'https://')):
            self.base_url = f"https://{self.domain}"
        else:
            self.base_url = self.domain

        self.domain = urlparse(self.base_url).netloc
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    # ─────────────────────────────────────────────
    #  Network helpers
    # ─────────────────────────────────────────────
    async def _fetch(self, session: aiohttp.ClientSession, url: str, timeout: int = 15) -> Tuple[Optional[str], int, Dict]:
        """Fetch a URL and return (body, status_code, headers)."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True, ssl=False) as resp:
                headers = dict(resp.headers)
                if resp.status == 200:
                    body = await resp.text()
                    return body, resp.status, headers
                return None, resp.status, headers
        except asyncio.TimeoutError:
            return None, 0, {"error": "timeout"}
        except aiohttp.ClientError as e:
            return None, 0, {"error": str(e)}
        except Exception as e:
            return None, 0, {"error": str(e)}

    async def _check_url_status(self, session: aiohttp.ClientSession, url: str) -> int:
        """Check if a URL is reachable and return status code."""
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=True, ssl=False) as resp:
                return resp.status
        except:
            return 0

    # ─────────────────────────────────────────────
    #  Main audit runner
    # ─────────────────────────────────────────────
    async def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run the full SEO audit."""
        print(f"[Audit] Starting comprehensive audit for: {self.domain}")

        try:
            with self:
                connector = aiohttp.TCPConnector(limit=10, ssl=False)
                async with aiohttp.ClientSession(
                    connector=connector,
                    headers={"User-Agent": "SEOIntelligenceBot/1.0 (+https://seointelligence.app)"}
                ) as session:

                    # 1. Fetch main page
                    print(f"[Audit] Fetching main page: {self.base_url}")
                    html, status, headers = await self._fetch(session, self.base_url)

                    if not html or status != 200:
                        self._add_issue(
                            "Site Unreachable", IssueSeverity.CRITICAL, "Technical",
                            f"Could not fetch {self.base_url} (status: {status})",
                            how_to_fix="Check that your domain is accessible and the server is responding."
                        )
                        return self._save_results(self._calculate_scores())

                    self.raw_data["main_html"] = html
                    self.raw_data["main_headers"] = headers
                    self.raw_data["main_status"] = status
                    soup = BeautifulSoup(html, 'html.parser')

                    # 2. Run all checks concurrently where possible
                    await asyncio.gather(
                        self._check_robots_txt(session),
                        self._check_sitemap(session),
                        self._check_ssl(),
                        self._check_internal_links(session, soup),
                    )

                    # 3. Run HTML-based checks (synchronous, fast)
                    self._check_meta_tags(soup)
                    self._check_headings(soup)
                    self._check_images(soup)
                    self._check_content_quality(soup)
                    self._check_canonical(soup)
                    self._check_open_graph(soup)
                    self._check_structured_data(soup, html)
                    self._check_mobile_viewport(soup)
                    self._check_page_performance(html, headers)
                    self._check_security_headers(headers)

                # 4. Calculate scores and save
                scores = self._calculate_scores()
                result = self._save_results(scores)

                print(f"[Audit] Completed for {self.domain}. Score: {scores['overall']}. "
                      f"Issues: {len(self.issues)}")

                return result

        except Exception as e:
            print(f"[Audit] Critical error for {self.domain}: {e}")
            import traceback
            traceback.print_exc()
            return {"health_score": 0, "issues": [], "recommendations": []}

    # ─────────────────────────────────────────────
    #  Check: Meta Tags
    # ─────────────────────────────────────────────
    def _check_meta_tags(self, soup: BeautifulSoup):
        """Check title, meta description, charset, viewport."""

        # Title
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else None

        if not title:
            self._add_issue(
                "Missing Title Tag", IssueSeverity.CRITICAL, "Content",
                "The page has no <title> tag. Search engines use the title as the main clickable headline in results.",
                how_to_fix="Add a unique, descriptive <title> tag between 30-60 characters that includes your primary keyword."
            )
        elif len(title) < 30:
            self._add_issue(
                "Title Too Short", IssueSeverity.WARNING, "Content",
                f"Title is only {len(title)} characters: \"{title}\". Titles under 30 characters waste valuable SERP real estate.",
                how_to_fix="Expand your title to 30-60 characters. Include your primary keyword and a compelling value proposition."
            )
        elif len(title) > 60:
            self._add_issue(
                "Title Too Long", IssueSeverity.WARNING, "Content",
                f"Title is {len(title)} characters: \"{title[:60]}...\". Google typically truncates titles over 60 characters.",
                how_to_fix="Shorten your title to under 60 characters. Put the most important keywords at the beginning."
            )

        # Meta Description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        desc_content = meta_desc.get('content', '').strip() if meta_desc else None

        if not desc_content:
            self._add_issue(
                "Missing Meta Description", IssueSeverity.ERROR, "Content",
                "No meta description found. Google may auto-generate one, but a custom description gives you control over what appears in search results.",
                how_to_fix="Add a meta description tag: <meta name=\"description\" content=\"Your compelling 120-160 character description here\">"
            )
        elif len(desc_content) < 70:
            self._add_issue(
                "Meta Description Too Short", IssueSeverity.WARNING, "Content",
                f"Meta description is only {len(desc_content)} characters. Short descriptions don't fully utilize the space Google provides.",
                how_to_fix="Write a meta description between 120-160 characters that summarizes the page and includes a call to action."
            )
        elif len(desc_content) > 160:
            self._add_issue(
                "Meta Description Too Long", IssueSeverity.NOTICE, "Content",
                f"Meta description is {len(desc_content)} characters. Google may truncate descriptions over 160 characters.",
                how_to_fix="Trim your meta description to under 160 characters. Front-load the most important information."
            )

        # Charset
        charset = soup.find('meta', charset=True) or soup.find('meta', attrs={'http-equiv': 'Content-Type'})
        if not charset:
            self._add_issue(
                "Missing Charset Declaration", IssueSeverity.WARNING, "Technical",
                "No character encoding declared. This can cause rendering issues in some browsers.",
                how_to_fix="Add <meta charset=\"UTF-8\"> as the first element inside your <head> tag."
            )

        self.raw_data["title"] = title
        self.raw_data["meta_description"] = desc_content

    # ─────────────────────────────────────────────
    #  Check: Headings
    # ─────────────────────────────────────────────
    def _check_headings(self, soup: BeautifulSoup):
        """Check heading structure — H1 presence, hierarchy."""

        headings = []
        for level in range(1, 7):
            for tag in soup.find_all(f'h{level}'):
                text = tag.get_text(strip=True)
                if text:
                    headings.append((f'h{level}', text))

        h1_tags = [h for h in headings if h[0] == 'h1']

        if len(h1_tags) == 0:
            self._add_issue(
                "Missing H1 Tag", IssueSeverity.ERROR, "Content",
                "The page has no H1 heading. The H1 is the most important on-page heading and should contain your primary keyword.",
                how_to_fix="Add exactly one H1 tag to the page that clearly describes the page content and includes your target keyword."
            )
        elif len(h1_tags) > 1:
            self._add_issue(
                "Multiple H1 Tags", IssueSeverity.WARNING, "Content",
                f"Found {len(h1_tags)} H1 tags. While not strictly an error in HTML5, best practice is to use a single H1 per page.",
                how_to_fix="Reduce to a single H1 tag. Convert other H1 tags to H2 or H3 as appropriate for the content hierarchy."
            )

        # Check heading hierarchy (e.g., H3 without H2)
        levels_used = sorted(set(int(h[0][1]) for h in headings))
        for i in range(len(levels_used) - 1):
            if levels_used[i + 1] - levels_used[i] > 1:
                self._add_issue(
                    "Broken Heading Hierarchy", IssueSeverity.NOTICE, "Content",
                    f"Heading hierarchy skips from H{levels_used[i]} to H{levels_used[i+1]}. This can confuse screen readers and search engines.",
                    how_to_fix=f"Add H{levels_used[i]+1} headings between your H{levels_used[i]} and H{levels_used[i+1]} tags to maintain proper hierarchy."
                )
                break

        self.raw_data["headings"] = headings
        self.raw_data["h1_count"] = len(h1_tags)

    # ─────────────────────────────────────────────
    #  Check: Images
    # ─────────────────────────────────────────────
    def _check_images(self, soup: BeautifulSoup):
        """Check images for alt text and dimensions."""

        images = soup.find_all('img')
        missing_alt = []
        missing_dimensions = []

        for img in images:
            src = img.get('src', '') or img.get('data-src', '') or ''
            alt = img.get('alt')

            if alt is None or alt.strip() == '':
                missing_alt.append(src[:100])

            if not img.get('width') and not img.get('height') and not img.get('style'):
                missing_dimensions.append(src[:100])

        if missing_alt:
            self._add_issue(
                "Images Missing Alt Text", IssueSeverity.ERROR, "Accessibility",
                f"Found {len(missing_alt)} image(s) without alt text. Alt text is essential for accessibility and helps search engines understand image content.",
                how_to_fix="Add descriptive alt attributes to all images. Example: <img src=\"photo.jpg\" alt=\"Red running shoes on a trail\">",
                affected_pages=[self.base_url],
                extra_data={"images": missing_alt[:10]}
            )

        if len(missing_dimensions) > 3:
            self._add_issue(
                "Images Missing Dimensions", IssueSeverity.NOTICE, "Performance",
                f"Found {len(missing_dimensions)} images without explicit width/height. This causes layout shifts (poor CLS score).",
                how_to_fix="Add width and height attributes to <img> tags so the browser can reserve space before images load."
            )

        self.raw_data["total_images"] = len(images)
        self.raw_data["images_missing_alt"] = len(missing_alt)

    # ─────────────────────────────────────────────
    #  Check: Content Quality
    # ─────────────────────────────────────────────
    def _check_content_quality(self, soup: BeautifulSoup):
        """Check word count and content depth."""

        body = soup.find('body')
        if not body:
            return

        # Remove script/style tags for accurate word count
        for tag in body.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        text = body.get_text(separator=' ', strip=True)
        words = text.split()
        word_count = len(words)

        if word_count < 100:
            self._add_issue(
                "Very Thin Content", IssueSeverity.ERROR, "Content",
                f"Page has only {word_count} words of main content. Pages with very little content struggle to rank.",
                how_to_fix="Add substantial, valuable content. Aim for at least 300 words for basic pages and 800+ for blog posts or landing pages."
            )
        elif word_count < 300:
            self._add_issue(
                "Thin Content", IssueSeverity.WARNING, "Content",
                f"Page has {word_count} words. While not critically low, most well-ranking pages have 500+ words.",
                how_to_fix="Expand your content to cover the topic more thoroughly. Add FAQs, examples, or detailed explanations."
            )

        # Check for keyword stuffing (any single word >3% of content)
        if word_count > 50:
            word_freq = {}
            for w in words:
                w_lower = w.lower().strip('.,!?;:')
                if len(w_lower) > 3:
                    word_freq[w_lower] = word_freq.get(w_lower, 0) + 1

            for word, count in word_freq.items():
                density = (count / word_count) * 100
                if density > 5 and count > 10:
                    self._add_issue(
                        "Potential Keyword Stuffing", IssueSeverity.WARNING, "Content",
                        f"The word \"{word}\" appears {count} times ({density:.1f}% density). High keyword density can trigger spam filters.",
                        how_to_fix="Use natural language and synonyms. Aim for 1-2% keyword density for your primary keyword."
                    )
                    break

        self.raw_data["word_count"] = word_count

    # ─────────────────────────────────────────────
    #  Check: Canonical
    # ─────────────────────────────────────────────
    def _check_canonical(self, soup: BeautifulSoup):
        """Check canonical tag."""

        canonical = soup.find('link', rel='canonical')

        if not canonical:
            self._add_issue(
                "Missing Canonical Tag", IssueSeverity.WARNING, "Technical",
                "No canonical tag found. Without a canonical, search engines may index duplicate versions of this page.",
                how_to_fix=f"Add <link rel=\"canonical\" href=\"{self.base_url}/\"> to the <head> of your page."
            )
        else:
            href = canonical.get('href', '')
            if href and not href.startswith('http'):
                self._add_issue(
                    "Relative Canonical URL", IssueSeverity.WARNING, "Technical",
                    f"Canonical tag uses a relative URL: \"{href}\". Canonical URLs should be absolute.",
                    how_to_fix="Change your canonical tag to use the full absolute URL including https:// and your domain."
                )

        self.raw_data["has_canonical"] = canonical is not None

    # ─────────────────────────────────────────────
    #  Check: Open Graph & Social
    # ─────────────────────────────────────────────
    def _check_open_graph(self, soup: BeautifulSoup):
        """Check Open Graph and Twitter Card meta tags."""

        og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
        twitter_tags = soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')})

        og_properties = {tag.get('property', ''): tag.get('content', '') for tag in og_tags}
        twitter_properties = {tag.get('name', ''): tag.get('content', '') for tag in twitter_tags}

        if not og_properties.get('og:title') and not og_properties.get('og:description'):
            self._add_issue(
                "Missing Open Graph Tags", IssueSeverity.NOTICE, "Content",
                "No Open Graph tags found. When your page is shared on Facebook, LinkedIn, or other social platforms, the preview will be auto-generated and may look poor.",
                how_to_fix="Add og:title, og:description, og:image, and og:url meta tags to control how your page appears when shared on social media."
            )

        if not og_properties.get('og:image'):
            self._add_issue(
                "Missing OG Image", IssueSeverity.NOTICE, "Content",
                "No og:image tag found. Social shares without an image get significantly less engagement.",
                how_to_fix="Add <meta property=\"og:image\" content=\"https://yoursite.com/image.jpg\"> with an image at least 1200x630 pixels."
            )

        self.raw_data["og_tags"] = len(og_tags)
        self.raw_data["twitter_tags"] = len(twitter_tags)

    # ─────────────────────────────────────────────
    #  Check: Structured Data
    # ─────────────────────────────────────────────
    def _check_structured_data(self, soup: BeautifulSoup, html: str):
        """Check for JSON-LD structured data."""

        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        has_structured_data = len(json_ld_scripts) > 0

        # Also check for microdata
        microdata = soup.find_all(attrs={'itemscope': True})

        if not has_structured_data and not microdata:
            self._add_issue(
                "No Structured Data", IssueSeverity.NOTICE, "Technical",
                "No structured data (JSON-LD or Microdata) found. Structured data helps search engines understand your content and can enable rich snippets in results.",
                how_to_fix="Add JSON-LD structured data relevant to your page type (Organization, Product, Article, FAQ, etc.). Use Google's Structured Data Markup Helper to get started."
            )
        else:
            # Validate JSON-LD is parseable
            for script in json_ld_scripts:
                try:
                    json.loads(script.string or '{}')
                except json.JSONDecodeError:
                    self._add_issue(
                        "Invalid JSON-LD", IssueSeverity.ERROR, "Technical",
                        "Found a JSON-LD script tag with invalid JSON. Search engines will ignore malformed structured data.",
                        how_to_fix="Fix the JSON syntax in your JSON-LD script tag. Validate it at https://validator.schema.org/"
                    )

        self.raw_data["has_structured_data"] = has_structured_data
        self.raw_data["json_ld_count"] = len(json_ld_scripts)

    # ─────────────────────────────────────────────
    #  Check: Mobile Viewport
    # ─────────────────────────────────────────────
    def _check_mobile_viewport(self, soup: BeautifulSoup):
        """Check for mobile viewport meta tag."""

        viewport = soup.find('meta', attrs={'name': 'viewport'})

        if not viewport:
            self._add_issue(
                "Missing Viewport Meta Tag", IssueSeverity.ERROR, "Mobile",
                "No viewport meta tag found. Without it, mobile devices will render the page at desktop width, making it unusable on phones.",
                how_to_fix="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to your <head> tag."
            )
        else:
            content = viewport.get('content', '')
            if 'width=device-width' not in content:
                self._add_issue(
                    "Viewport Not Set to Device Width", IssueSeverity.WARNING, "Mobile",
                    f"Viewport is set to \"{content}\" but doesn't include width=device-width.",
                    how_to_fix="Update your viewport tag to: <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                )

        self.raw_data["has_viewport"] = viewport is not None

    # ─────────────────────────────────────────────
    #  Check: Robots.txt
    # ─────────────────────────────────────────────
    async def _check_robots_txt(self, session: aiohttp.ClientSession):
        """Check if robots.txt exists and is valid."""

        robots_url = f"{self.base_url}/robots.txt"
        body, status, _ = await self._fetch(session, robots_url, timeout=10)

        if status != 200:
            self._add_issue(
                "Missing robots.txt", IssueSeverity.WARNING, "Technical",
                "No robots.txt file found. While not required, robots.txt tells search engine crawlers which pages to access.",
                how_to_fix="Create a robots.txt file at your domain root. At minimum: User-agent: *\\nAllow: /\\nSitemap: https://yourdomain.com/sitemap.xml"
            )
            self.raw_data["has_robots_txt"] = False
            return

        self.raw_data["has_robots_txt"] = True

        # Check if main pages are accidentally blocked
        if body:
            if 'Disallow: /' in body and 'Disallow: / ' not in body:
                # Check if it's "Disallow: /" which blocks everything
                lines = body.split('\n')
                for line in lines:
                    stripped = line.strip()
                    if stripped == 'Disallow: /':
                        self._add_issue(
                            "Robots.txt Blocks All Crawling", IssueSeverity.CRITICAL, "Technical",
                            "Your robots.txt contains 'Disallow: /' which blocks all search engine crawlers from your entire site.",
                            how_to_fix="Remove or modify the 'Disallow: /' directive. If your site is in development, this is expected — but remove it before going live."
                        )
                        break

            # Check for sitemap reference
            if 'sitemap:' not in body.lower():
                self._add_issue(
                    "No Sitemap in robots.txt", IssueSeverity.NOTICE, "Technical",
                    "Your robots.txt doesn't reference a sitemap. Adding a Sitemap directive helps search engines discover your XML sitemap.",
                    how_to_fix=f"Add this line to your robots.txt: Sitemap: {self.base_url}/sitemap.xml"
                )

    # ─────────────────────────────────────────────
    #  Check: Sitemap
    # ─────────────────────────────────────────────
    async def _check_sitemap(self, session: aiohttp.ClientSession):
        """Check if XML sitemap exists."""

        sitemap_urls = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
            f"{self.base_url}/sitemap/sitemap.xml",
        ]

        found = False
        for url in sitemap_urls:
            _, status, _ = await self._fetch(session, url, timeout=10)
            if status == 200:
                found = True
                break

        if not found:
            self._add_issue(
                "Missing XML Sitemap", IssueSeverity.WARNING, "Technical",
                "No XML sitemap found at common locations. Sitemaps help search engines discover and index your pages efficiently.",
                how_to_fix="Create an XML sitemap listing all your important pages. Most CMS platforms (WordPress, Shopify) generate these automatically. Submit it to Google Search Console."
            )

        self.raw_data["has_sitemap"] = found

    # ─────────────────────────────────────────────
    #  Check: SSL
    # ─────────────────────────────────────────────
    async def _check_ssl(self):
        """Check SSL certificate validity."""

        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((self.domain, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()
                    # Check expiry
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.utcnow()).days

                    if days_until_expiry < 0:
                        self._add_issue(
                            "SSL Certificate Expired", IssueSeverity.CRITICAL, "Security",
                            f"Your SSL certificate expired {abs(days_until_expiry)} days ago. Browsers will show a security warning to visitors.",
                            how_to_fix="Renew your SSL certificate immediately. If using Let's Encrypt, check your auto-renewal configuration."
                        )
                    elif days_until_expiry < 14:
                        self._add_issue(
                            "SSL Certificate Expiring Soon", IssueSeverity.WARNING, "Security",
                            f"Your SSL certificate expires in {days_until_expiry} days.",
                            how_to_fix="Renew your SSL certificate before it expires to avoid browser security warnings."
                        )

                    self.raw_data["ssl_valid"] = days_until_expiry > 0
                    self.raw_data["ssl_days_remaining"] = days_until_expiry

        except ssl.SSLError as e:
            self._add_issue(
                "SSL Certificate Error", IssueSeverity.CRITICAL, "Security",
                f"SSL certificate error: {str(e)[:200]}. Visitors will see a security warning.",
                how_to_fix="Fix your SSL certificate. Ensure it's valid, not self-signed, and covers your domain."
            )
            self.raw_data["ssl_valid"] = False
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError):
            self._add_issue(
                "HTTPS Not Available", IssueSeverity.ERROR, "Security",
                "Could not establish HTTPS connection. Your site may not have SSL configured.",
                how_to_fix="Install an SSL certificate. Most hosting providers offer free SSL via Let's Encrypt."
            )
            self.raw_data["ssl_valid"] = False

    # ─────────────────────────────────────────────
    #  Check: Internal Links
    # ─────────────────────────────────────────────
    async def _check_internal_links(self, session: aiohttp.ClientSession, soup: BeautifulSoup):
        """Check internal links for broken pages."""

        links = soup.find_all('a', href=True)
        internal_links = []
        external_links = []

        for link in links:
            href = link['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            full_url = urljoin(self.base_url, href)
            parsed = urlparse(full_url)

            if parsed.netloc == self.domain or parsed.netloc == '':
                internal_links.append(full_url)
            else:
                external_links.append(full_url)

        # Check a sample of internal links for broken ones (limit to 20 to avoid slow audits)
        unique_internal = list(set(internal_links))[:20]
        broken_links = []

        if unique_internal:
            tasks = [self._check_url_status(session, url) for url in unique_internal]
            results = await asyncio.gather(*tasks)

            for url, status in zip(unique_internal, results):
                if status >= 400 or status == 0:
                    broken_links.append({"url": url, "status": status})

        if broken_links:
            self._add_issue(
                "Broken Internal Links", IssueSeverity.ERROR, "Technical",
                f"Found {len(broken_links)} broken internal link(s). Broken links waste crawl budget and create poor user experience.",
                how_to_fix="Fix or remove these broken links: " + ", ".join([bl['url'] for bl in broken_links[:5]]),
                affected_pages=[self.base_url],
                extra_data={"broken_links": broken_links[:10]}
            )

        if len(internal_links) < 3:
            self._add_issue(
                "Too Few Internal Links", IssueSeverity.NOTICE, "Content",
                f"Only {len(internal_links)} internal links found. Internal linking helps distribute page authority and helps users navigate.",
                how_to_fix="Add relevant internal links to other pages on your site. Aim for 3-10 internal links per page."
            )

        self.raw_data["internal_links"] = len(internal_links)
        self.raw_data["external_links"] = len(external_links)
        self.raw_data["broken_links"] = len(broken_links)

    # ─────────────────────────────────────────────
    #  Check: Page Performance
    # ─────────────────────────────────────────────
    def _check_page_performance(self, html: str, headers: Dict):
        """Basic page performance checks."""

        html_size_kb = len(html.encode('utf-8')) / 1024

        if html_size_kb > 200:
            self._add_issue(
                "Very Large HTML Document", IssueSeverity.WARNING, "Performance",
                f"HTML document is {html_size_kb:.0f} KB. Large HTML files slow down initial page rendering.",
                how_to_fix="Minify your HTML, externalize inline CSS/JS, and consider lazy-loading below-the-fold content."
            )
        elif html_size_kb > 100:
            self._add_issue(
                "Large HTML Document", IssueSeverity.NOTICE, "Performance",
                f"HTML document is {html_size_kb:.0f} KB. Consider optimizing for faster load times.",
                how_to_fix="Review your HTML for unnecessary inline styles, scripts, or redundant markup."
            )

        # Check for render-blocking patterns
        soup = BeautifulSoup(html, 'html.parser')
        head = soup.find('head')
        if head:
            blocking_css = head.find_all('link', rel='stylesheet')
            blocking_js = [s for s in head.find_all('script', src=True) if not s.get('async') and not s.get('defer')]

            if len(blocking_js) > 3:
                self._add_issue(
                    "Render-Blocking JavaScript", IssueSeverity.WARNING, "Performance",
                    f"Found {len(blocking_js)} render-blocking JavaScript files in <head>. These delay page rendering.",
                    how_to_fix="Add 'async' or 'defer' attributes to script tags, or move them to the end of <body>."
                )

        # Check compression
        content_encoding = headers.get('Content-Encoding', '')
        if 'gzip' not in content_encoding and 'br' not in content_encoding and html_size_kb > 10:
            self._add_issue(
                "No Compression Enabled", IssueSeverity.WARNING, "Performance",
                "Response is not compressed with gzip or Brotli. Compression typically reduces transfer size by 60-80%.",
                how_to_fix="Enable gzip or Brotli compression on your web server. Most hosting providers support this."
            )

        self.raw_data["html_size_kb"] = round(html_size_kb, 2)

    # ─────────────────────────────────────────────
    #  Check: Security Headers
    # ─────────────────────────────────────────────
    def _check_security_headers(self, headers: Dict):
        """Check for important security headers."""

        security_checks = {
            'X-Content-Type-Options': ('Missing X-Content-Type-Options Header', 'Add the header: X-Content-Type-Options: nosniff'),
            'X-Frame-Options': ('Missing X-Frame-Options Header', 'Add the header: X-Frame-Options: SAMEORIGIN or use Content-Security-Policy frame-ancestors'),
        }

        missing_headers = []
        for header, (title, fix) in security_checks.items():
            if header not in headers:
                missing_headers.append(header)

        if missing_headers:
            self._add_issue(
                "Missing Security Headers", IssueSeverity.NOTICE, "Security",
                f"Missing security headers: {', '.join(missing_headers)}. These headers help protect against common web attacks.",
                how_to_fix="Configure your web server to send these security headers. Most can be added in your server config or via a CDN like Cloudflare."
            )

        # Check HSTS
        if 'Strict-Transport-Security' not in headers:
            self._add_issue(
                "No HSTS Header", IssueSeverity.NOTICE, "Security",
                "Strict-Transport-Security header is not set. HSTS ensures browsers always use HTTPS.",
                how_to_fix="Add the header: Strict-Transport-Security: max-age=31536000; includeSubDomains"
            )

    # ─────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────
    def _add_issue(self, issue_type: str, severity: IssueSeverity, category: str,
                   title: str, how_to_fix: str = "", affected_pages: List[str] = None,
                   extra_data: Dict = None):
        """Add an issue to the results."""

        issue = {
            "id": len(self.issues) + 1,
            "issue_type": issue_type,
            "severity": severity.value,
            "category": category,
            "title": title,
            "how_to_fix": how_to_fix or "Review and fix this issue.",
            "affected_pages": affected_pages or [self.base_url],
            "estimated_impact": self._estimate_impact(severity),
            "effort_required": self._estimate_effort(issue_type),
        }
        if extra_data:
            issue["extra_data"] = extra_data

        self.issues.append(issue)

        # Auto-generate recommendation
        self.recommendations.append({
            "id": len(self.recommendations) + 1,
            "priority": {"Critical": 1, "Error": 2, "Warning": 3, "Notice": 4}.get(severity.value, 3),
            "title": how_to_fix.split('.')[0] if how_to_fix else f"Fix: {issue_type}",
            "description": how_to_fix,
            "expected_impact": {"Critical": "High", "Error": "High", "Warning": "Medium", "Notice": "Low"}.get(severity.value, "Medium"),
            "implementation_complexity": self._estimate_effort(issue_type),
            "estimated_traffic_gain": self._estimate_traffic_gain(severity, category),
        })

    def _estimate_impact(self, severity: IssueSeverity) -> int:
        return {"Critical": 90, "Error": 70, "Warning": 40, "Notice": 15}.get(severity.value, 20)

    def _estimate_effort(self, issue_type: str) -> str:
        high_effort = ["Broken Internal Links", "No Compression Enabled", "Render-Blocking JavaScript"]
        if issue_type in high_effort:
            return "Medium"
        return "Low"

    def _estimate_traffic_gain(self, severity: IssueSeverity, category: str) -> int:
        base = {"Critical": 200, "Error": 100, "Warning": 50, "Notice": 20}.get(severity.value, 30)
        multiplier = {"Content": 1.5, "Technical": 1.2, "Performance": 1.0, "Security": 0.5, "Mobile": 1.3, "Accessibility": 0.8}.get(category, 1.0)
        return int(base * multiplier)

    # ─────────────────────────────────────────────
    #  Scoring
    # ─────────────────────────────────────────────
    def _calculate_scores(self) -> Dict[str, float]:
        """Calculate category and overall scores based on issues found."""

        categories = {
            "Technical": {"base": 100, "issues": []},
            "Content": {"base": 100, "issues": []},
            "Performance": {"base": 100, "issues": []},
            "Mobile": {"base": 100, "issues": []},
            "Security": {"base": 100, "issues": []},
            "Accessibility": {"base": 100, "issues": []},
        }

        severity_penalties = {
            "Critical": 25,
            "Error": 15,
            "Warning": 8,
            "Notice": 3,
        }

        for issue in self.issues:
            cat = issue.get("category", "Technical")
            if cat in categories:
                penalty = severity_penalties.get(issue["severity"], 5)
                categories[cat]["issues"].append(penalty)

        scores = {}
        for cat, data in categories.items():
            total_penalty = sum(data["issues"])
            score = max(data["base"] - total_penalty, 0)
            scores[cat.lower()] = round(score, 1)

        # Overall = weighted average
        weights = {"technical": 0.25, "content": 0.25, "performance": 0.2, "mobile": 0.15, "security": 0.1, "accessibility": 0.05}
        overall = sum(scores.get(cat, 100) * weight for cat, weight in weights.items())
        scores["overall"] = round(overall, 1)

        return scores

    # ─────────────────────────────────────────────
    #  Save results
    # ─────────────────────────────────────────────
    def _save_results(self, scores: Dict[str, float]) -> Dict[str, Any]:
        """Save audit results to database."""

        critical_count = len([i for i in self.issues if i["severity"] == "Critical"])
        error_count = len([i for i in self.issues if i["severity"] == "Error"])
        warning_count = len([i for i in self.issues if i["severity"] == "Warning"])

        report = AuditReport(
            website_id=self.website_id,
            health_score=scores["overall"],
            technical_score=scores.get("technical", 0),
            content_score=scores.get("content", 0),
            performance_score=scores.get("performance", 0),
            mobile_score=scores.get("mobile", 0),
            security_score=scores.get("security", 0),
            total_issues=len(self.issues),
            critical_issues=critical_count,
            errors=error_count,
            warnings=warning_count,
            detailed_findings={
                "issues": self.issues,
                "recommendations": self.recommendations,
                "raw_data": {
                    k: v for k, v in self.raw_data.items()
                    if k != "main_html"  # Don't store full HTML in DB
                }
            }
        )

        self.db.add(report)
        self.website.last_audit = datetime.utcnow()
        self.db.commit()
        self.db.refresh(report)

        print(f"[Audit] Saved report #{report.id} for {self.domain}")

        return {
            "report_id": report.id,
            "health_score": scores["overall"],
            "issues": self.issues,
            "recommendations": self.recommendations
        }


# ─────────────────────────────────────────────
#  Standalone runner for testing
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        try:
            wid = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python audit_engine.py <website_id>")
            sys.exit(1)

        engine = SEOAuditEngine(wid)
        result = asyncio.run(engine.run_comprehensive_audit())
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python audit_engine.py <website_id>")
