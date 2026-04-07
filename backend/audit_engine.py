# backend/audit_engine.py - Deep SEO Audit Engine (Screaming Frog style)
# Crawls up to 500 pages, audits each one individually, aggregates site-wide issues
import os
import sys
import ssl
import socket
import re
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, urlunparse
import json
from enum import Enum
from collections import defaultdict
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal, Website, AuditReport

load_dotenv()


class IssueSeverity(Enum):
    CRITICAL = "Critical"
    ERROR = "Error"
    WARNING = "Warning"
    NOTICE = "Notice"


class PageData:
    """Stores audit data for a single crawled page."""
    def __init__(self, url: str):
        self.url = url
        self.status_code = 0
        self.redirect_url = None
        self.response_time_ms = 0
        self.html_size_kb = 0
        self.content_type = ""

        # Meta
        self.title = ""
        self.title_length = 0
        self.meta_description = ""
        self.meta_description_length = 0
        self.has_canonical = False
        self.canonical_url = ""
        self.has_viewport = False
        self.has_charset = False

        # Headings
        self.h1_count = 0
        self.h1_text = []
        self.heading_hierarchy_ok = True

        # Content
        self.word_count = 0

        # Images
        self.total_images = 0
        self.images_missing_alt = 0
        self.images_missing_alt_srcs = []
        self.images_missing_dimensions = 0

        # Links
        self.internal_links = 0
        self.external_links = 0
        self.internal_link_urls = []

        # Social / Structured
        self.has_og_tags = False
        self.has_og_image = False
        self.has_twitter_card = False
        self.has_structured_data = False
        self.structured_data_types = []
        self.has_invalid_json_ld = False

        # Performance
        self.render_blocking_js = 0
        self.has_compression = False

        # Issues found on this page
        self.issues = []


class SEOAuditEngine:
    """
    Deep SEO audit engine that crawls multiple pages of a website.
    Like Screaming Frog — follows internal links, audits each page individually,
    then aggregates into a site-wide report.
    """

    MAX_PAGES = 500  # Maximum pages to crawl
    CRAWL_DELAY = 0.3  # Seconds between requests (polite crawling)
    REQUEST_TIMEOUT = 15  # Seconds per request

    def __init__(self, website_id: int):
        self.website_id = website_id
        self.db: Optional[Session] = None
        self.website: Optional[Website] = None
        self.base_url: Optional[str] = None
        self.domain: Optional[str] = None

        # Crawl state
        self.crawled_urls: Set[str] = set()
        self.urls_to_crawl: List[str] = []
        self.page_data: Dict[str, PageData] = {}
        self.broken_links: List[Dict] = []
        self.redirect_chains: List[Dict] = []

        # Aggregated issues
        self.issues: List[Dict] = []
        self.recommendations: List[Dict] = []

        # Site-wide stats
        self.site_stats = {
            "pages_crawled": 0,
            "total_images": 0,
            "total_internal_links": 0,
            "total_external_links": 0,
            "avg_word_count": 0,
            "avg_response_time_ms": 0,
            "avg_page_size_kb": 0,
        }

        # Robots.txt and sitemap
        self.has_robots_txt = False
        self.robots_blocks_all = False
        self.has_sitemap = False
        self.ssl_valid = None
        self.ssl_days_remaining = 0

    def __enter__(self):
        self.db = SessionLocal()
        self.website = self.db.query(Website).filter(Website.id == self.website_id).first()
        if not self.website:
            raise ValueError("Website with ID " + str(self.website_id) + " not found.")

        self.domain = self.website.domain
        if not self.domain.startswith(('http://', 'https://')):
            self.base_url = "https://" + self.domain
        else:
            self.base_url = self.domain
        self.domain = urlparse(self.base_url).netloc
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    # ─────────────────────────────────────────────
    #  URL helpers
    # ─────────────────────────────────────────────
    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalize a URL for deduplication."""
        try:
            parsed = urlparse(url)
            # Only crawl same domain
            if parsed.netloc and parsed.netloc != self.domain:
                return None
            # Remove fragments
            normalized = urlunparse((
                parsed.scheme or 'https',
                parsed.netloc or self.domain,
                parsed.path.rstrip('/') or '/',
                parsed.params,
                parsed.query,
                ''  # Remove fragment
            ))
            return normalized
        except Exception:
            return None

    def _is_crawlable(self, url: str) -> bool:
        """Check if a URL should be crawled."""
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Skip non-HTML resources
        skip_extensions = (
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico',
            '.css', '.js', '.pdf', '.zip', '.mp4', '.mp3', '.woff',
            '.woff2', '.ttf', '.eot', '.map', '.xml', '.json'
        )
        if any(path.endswith(ext) for ext in skip_extensions):
            return False

        # Skip common non-content paths
        skip_paths = (
            '/cdn-cgi/', '/wp-admin/', '/wp-includes/', '/wp-json/',
            '/admin/', '/cart', '/checkout', '/account',
            '/search', '?variant=', '?v='
        )
        full = url.lower()
        if any(skip in full for skip in skip_paths):
            return False

        return True

    def _extract_links(self, soup: BeautifulSoup, current_url: str) -> Tuple[List[str], List[str]]:
        """Extract internal and external links from a page."""
        internal = []
        external = []

        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'data:')):
                continue

            full_url = urljoin(current_url, href)
            parsed = urlparse(full_url)

            if parsed.netloc == self.domain or not parsed.netloc:
                normalized = self._normalize_url(full_url)
                if normalized:
                    internal.append(normalized)
            else:
                external.append(full_url)

        return internal, external

    # ─────────────────────────────────────────────
    #  Network
    # ─────────────────────────────────────────────
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], int, Dict, float, Optional[str]]:
        """Fetch a URL. Returns (html, status, headers, response_time_ms, final_url)."""
        start = time.time()
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT),
                allow_redirects=True,
                ssl=False
            ) as resp:
                elapsed = (time.time() - start) * 1000
                headers = dict(resp.headers)
                final_url = str(resp.url)

                content_type = headers.get('Content-Type', '')
                if 'text/html' not in content_type and resp.status == 200:
                    return None, resp.status, headers, elapsed, final_url

                if resp.status == 200:
                    body = await resp.text()
                    return body, resp.status, headers, elapsed, final_url
                return None, resp.status, headers, elapsed, final_url
        except asyncio.TimeoutError:
            elapsed = (time.time() - start) * 1000
            return None, 0, {"error": "timeout"}, elapsed, None
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return None, 0, {"error": str(e)}, elapsed, None

    # ─────────────────────────────────────────────
    #  Main audit runner
    # ─────────────────────────────────────────────
    async def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Run full site crawl and audit."""
        print("[Audit] Starting deep audit for: " + str(self.domain))

        try:
            with self:
                connector = aiohttp.TCPConnector(limit=5, ssl=False)
                async with aiohttp.ClientSession(
                    connector=connector,
                    headers={"User-Agent": "SEOIntelligenceBot/2.0 (+https://seointelligence.app)"}
                ) as session:

                    # Phase 1: Site-level checks (concurrent)
                    print("[Audit] Phase 1: Site-level checks...")
                    await asyncio.gather(
                        self._check_robots_txt(session),
                        self._check_sitemap(session),
                        self._check_ssl(),
                    )

                    # Phase 2: Crawl pages
                    print("[Audit] Phase 2: Crawling pages (max " + str(self.MAX_PAGES) + ")...")
                    self.urls_to_crawl = [self.base_url]
                    await self._crawl_site(session)

                    # Phase 3: Aggregate issues from all pages
                    print("[Audit] Phase 3: Analyzing " + str(len(self.page_data)) + " crawled pages...")
                    self._aggregate_issues()

                # Phase 4: Calculate scores and save
                scores = self._calculate_scores()
                result = self._save_results(scores)

                print("[Audit] Completed for " + self.domain + ". Score: " + str(scores['overall'])
                      + ". Pages: " + str(len(self.page_data))
                      + ". Issues: " + str(len(self.issues)))

                return result

        except Exception as e:
            print("[Audit] Critical error for " + str(self.domain) + ": " + str(e))
            import traceback
            traceback.print_exc()
            return {"health_score": 0, "issues": [], "recommendations": []}

    # ─────────────────────────────────────────────
    #  Crawl loop
    # ─────────────────────────────────────────────
    async def _crawl_site(self, session: aiohttp.ClientSession):
        """Breadth-first crawl of the site."""
        while self.urls_to_crawl and len(self.crawled_urls) < self.MAX_PAGES:
            url = self.urls_to_crawl.pop(0)

            # Skip if already crawled
            normalized = self._normalize_url(url)
            if not normalized or normalized in self.crawled_urls:
                continue
            if not self._is_crawlable(normalized):
                continue

            self.crawled_urls.add(normalized)

            # Fetch the page
            html, status, headers, response_time, final_url = await self._fetch_page(session, normalized)

            # Create page data object
            page = PageData(normalized)
            page.status_code = status
            page.response_time_ms = round(response_time)
            page.content_type = headers.get('Content-Type', '')

            # Track redirects
            if final_url and final_url != normalized:
                page.redirect_url = final_url

            # Track broken pages
            if status >= 400 or status == 0:
                self.broken_links.append({
                    "url": normalized,
                    "status": status,
                    "source": "crawl"
                })
                self.page_data[normalized] = page
                await asyncio.sleep(self.CRAWL_DELAY)
                continue

            if not html:
                self.page_data[normalized] = page
                await asyncio.sleep(self.CRAWL_DELAY)
                continue

            # Parse and analyze
            page.html_size_kb = round(len(html.encode('utf-8')) / 1024, 1)
            page.has_compression = 'gzip' in headers.get('Content-Encoding', '') or 'br' in headers.get('Content-Encoding', '')

            soup = BeautifulSoup(html, 'html.parser')

            # Run all per-page checks
            self._check_page_meta(page, soup)
            self._check_page_headings(page, soup)
            self._check_page_images(page, soup)
            self._check_page_content(page, soup)
            self._check_page_canonical(page, soup)
            self._check_page_social(page, soup)
            self._check_page_structured_data(page, soup, html)
            self._check_page_performance(page, soup, headers)

            # Extract links and add new ones to crawl queue
            internal_links, external_links = self._extract_links(soup, normalized)
            page.internal_links = len(internal_links)
            page.external_links = len(external_links)
            page.internal_link_urls = internal_links[:50]  # Store first 50

            # Add discovered internal links to crawl queue
            for link_url in internal_links:
                norm_link = self._normalize_url(link_url)
                if norm_link and norm_link not in self.crawled_urls and norm_link not in self.urls_to_crawl:
                    self.urls_to_crawl.append(norm_link)

            self.page_data[normalized] = page

            # Progress logging
            if len(self.crawled_urls) % 25 == 0:
                print("[Audit]   Crawled " + str(len(self.crawled_urls)) + " pages, "
                      + str(len(self.urls_to_crawl)) + " in queue...")

            await asyncio.sleep(self.CRAWL_DELAY)

        print("[Audit] Crawl complete. " + str(len(self.crawled_urls)) + " pages crawled.")

    # ─────────────────────────────────────────────
    #  Per-page checks
    # ─────────────────────────────────────────────
    def _check_page_meta(self, page: PageData, soup: BeautifulSoup):
        """Check meta tags on a single page."""
        # Title
        title_tag = soup.find('title')
        if title_tag:
            page.title = title_tag.get_text(strip=True)
            page.title_length = len(page.title)

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            page.meta_description = (meta_desc.get('content') or '').strip()
            page.meta_description_length = len(page.meta_description)

        # Charset
        page.has_charset = bool(soup.find('meta', charset=True) or soup.find('meta', attrs={'http-equiv': 'Content-Type'}))

        # Viewport
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        page.has_viewport = bool(viewport)

    def _check_page_headings(self, page: PageData, soup: BeautifulSoup):
        """Check heading structure on a single page."""
        h1_tags = soup.find_all('h1')
        page.h1_count = len(h1_tags)
        page.h1_text = [h.get_text(strip=True) for h in h1_tags if h.get_text(strip=True)]

        # Check heading hierarchy
        headings = []
        for level in range(1, 7):
            for tag in soup.find_all('h' + str(level)):
                if tag.get_text(strip=True):
                    headings.append(level)

        levels_used = sorted(set(headings))
        for i in range(len(levels_used) - 1):
            if levels_used[i + 1] - levels_used[i] > 1:
                page.heading_hierarchy_ok = False
                break

    def _check_page_images(self, page: PageData, soup: BeautifulSoup):
        """Check images on a single page."""
        images = soup.find_all('img')
        page.total_images = len(images)

        for img in images:
            src = img.get('src', '') or img.get('data-src', '') or ''
            alt = img.get('alt')
            if alt is None or alt.strip() == '':
                page.images_missing_alt += 1
                if src:
                    page.images_missing_alt_srcs.append(src[:150])

            if not img.get('width') and not img.get('height'):
                page.images_missing_dimensions += 1

    def _check_page_content(self, page: PageData, soup: BeautifulSoup):
        """Check content quality on a single page."""
        body = soup.find('body')
        if not body:
            return

        # Clone body so we don't modify the original soup
        body_clone = BeautifulSoup(str(body), 'html.parser').find('body')
        for tag in body_clone.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()

        text = body_clone.get_text(separator=' ', strip=True)
        page.word_count = len(text.split())

    def _check_page_canonical(self, page: PageData, soup: BeautifulSoup):
        """Check canonical tag on a single page."""
        canonical = soup.find('link', rel='canonical')
        page.has_canonical = bool(canonical)
        if canonical:
            page.canonical_url = canonical.get('href', '')

    def _check_page_social(self, page: PageData, soup: BeautifulSoup):
        """Check Open Graph and Twitter Card tags."""
        og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
        page.has_og_tags = len(og_tags) > 0

        og_image = soup.find('meta', property='og:image')
        page.has_og_image = bool(og_image and og_image.get('content'))

        twitter_card = soup.find('meta', attrs={'name': 'twitter:card'})
        page.has_twitter_card = bool(twitter_card)

    def _check_page_structured_data(self, page: PageData, soup: BeautifulSoup, html: str):
        """Check for JSON-LD structured data."""
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        microdata = soup.find_all(attrs={'itemscope': True})
        page.has_structured_data = len(json_ld_scripts) > 0 or len(microdata) > 0

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string or '{}')
                schema_type = data.get('@type', 'Unknown')
                if isinstance(schema_type, list):
                    page.structured_data_types.extend(schema_type)
                else:
                    page.structured_data_types.append(schema_type)
            except json.JSONDecodeError:
                page.has_invalid_json_ld = True

    def _check_page_performance(self, page: PageData, soup: BeautifulSoup, headers: Dict):
        """Check performance indicators on a single page."""
        head = soup.find('head')
        if head:
            blocking_js = [s for s in head.find_all('script', src=True)
                          if not s.get('async') and not s.get('defer')]
            page.render_blocking_js = len(blocking_js)

    # ─────────────────────────────────────────────
    #  Site-level checks
    # ─────────────────────────────────────────────
    async def _check_robots_txt(self, session: aiohttp.ClientSession):
        """Check robots.txt."""
        url = self.base_url + "/robots.txt"
        html, status, _, _, _ = await self._fetch_page(session, url)

        if status != 200:
            self.has_robots_txt = False
            return

        self.has_robots_txt = True
        if html:
            lines = html.split('\n')
            for line in lines:
                if line.strip() == 'Disallow: /':
                    self.robots_blocks_all = True
                    break

            if 'sitemap:' not in html.lower():
                self._add_issue(
                    "No Sitemap in robots.txt", IssueSeverity.NOTICE, "Technical",
                    "Your robots.txt doesn't reference a sitemap.",
                    how_to_fix="Add: Sitemap: " + self.base_url + "/sitemap.xml"
                )

    async def _check_sitemap(self, session: aiohttp.ClientSession):
        """Check for XML sitemap."""
        for path in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/sitemap.xml"]:
            url = self.base_url + path
            _, status, _, _, _ = await self._fetch_page(session, url)
            if status == 200:
                self.has_sitemap = True
                return
        self.has_sitemap = False

    async def _check_ssl(self):
        """Check SSL certificate."""
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((self.domain, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    self.ssl_days_remaining = (not_after - datetime.utcnow()).days
                    self.ssl_valid = self.ssl_days_remaining > 0
        except ssl.SSLError:
            self.ssl_valid = False
            self.ssl_days_remaining = 0
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError):
            self.ssl_valid = False
            self.ssl_days_remaining = 0

    # ─────────────────────────────────────────────
    #  Aggregate issues from all crawled pages
    # ─────────────────────────────────────────────
    def _aggregate_issues(self):
        """Analyze all crawled pages and create site-wide issues."""

        pages = [p for p in self.page_data.values() if p.status_code == 200]
        all_pages = list(self.page_data.values())

        if not pages:
            self._add_issue("Site Unreachable", IssueSeverity.CRITICAL, "Technical",
                          "Could not crawl any pages on this site.",
                          how_to_fix="Check that your domain is accessible.")
            return

        # ─── Site-level issues ───
        if not self.has_robots_txt:
            self._add_issue("Missing robots.txt", IssueSeverity.WARNING, "Technical",
                          "No robots.txt file found.",
                          how_to_fix="Create a robots.txt file at your domain root.")

        if self.robots_blocks_all:
            self._add_issue("Robots.txt Blocks All Crawling", IssueSeverity.CRITICAL, "Technical",
                          "Your robots.txt contains 'Disallow: /' which blocks search engines.",
                          how_to_fix="Remove 'Disallow: /' from your robots.txt.")

        if not self.has_sitemap:
            self._add_issue("Missing XML Sitemap", IssueSeverity.WARNING, "Technical",
                          "No XML sitemap found.",
                          how_to_fix="Create an XML sitemap and submit to Google Search Console.")

        if self.ssl_valid is False:
            self._add_issue("SSL Certificate Issue", IssueSeverity.CRITICAL, "Security",
                          "SSL certificate is invalid or not configured.",
                          how_to_fix="Install or renew your SSL certificate.")
        elif self.ssl_valid and self.ssl_days_remaining < 14:
            self._add_issue("SSL Certificate Expiring Soon", IssueSeverity.WARNING, "Security",
                          "SSL certificate expires in " + str(self.ssl_days_remaining) + " days.",
                          how_to_fix="Renew your SSL certificate before it expires.")

        # ─── Per-page aggregated issues ───

        # Missing titles
        pages_missing_title = [p.url for p in pages if not p.title]
        if pages_missing_title:
            self._add_issue("Missing Title Tags", IssueSeverity.CRITICAL, "Content",
                          str(len(pages_missing_title)) + " page(s) have no title tag.",
                          how_to_fix="Add unique, descriptive title tags (30-60 chars) to each page.",
                          affected_pages=pages_missing_title[:20])

        # Title too short
        pages_short_title = [p.url for p in pages if p.title and p.title_length < 30]
        if pages_short_title:
            self._add_issue("Title Tags Too Short", IssueSeverity.WARNING, "Content",
                          str(len(pages_short_title)) + " page(s) have titles under 30 characters.",
                          how_to_fix="Expand titles to 30-60 characters with relevant keywords.",
                          affected_pages=pages_short_title[:20])

        # Title too long
        pages_long_title = [p.url for p in pages if p.title_length > 60]
        if pages_long_title:
            self._add_issue("Title Tags Too Long", IssueSeverity.WARNING, "Content",
                          str(len(pages_long_title)) + " page(s) have titles over 60 characters.",
                          how_to_fix="Shorten titles to under 60 characters.",
                          affected_pages=pages_long_title[:20])

        # Duplicate titles
        title_map = defaultdict(list)
        for p in pages:
            if p.title:
                title_map[p.title].append(p.url)
        duplicate_titles = {t: urls for t, urls in title_map.items() if len(urls) > 1}
        if duplicate_titles:
            dup_count = sum(len(urls) for urls in duplicate_titles.values())
            sample_urls = []
            for urls in list(duplicate_titles.values())[:5]:
                sample_urls.extend(urls[:2])
            self._add_issue("Duplicate Title Tags", IssueSeverity.ERROR, "Content",
                          str(dup_count) + " pages share duplicate titles across " + str(len(duplicate_titles)) + " unique titles.",
                          how_to_fix="Make each page title unique and descriptive of that specific page's content.",
                          affected_pages=sample_urls[:20])

        # Missing meta descriptions
        pages_missing_desc = [p.url for p in pages if not p.meta_description]
        if pages_missing_desc:
            self._add_issue("Missing Meta Descriptions", IssueSeverity.ERROR, "Content",
                          str(len(pages_missing_desc)) + " page(s) have no meta description.",
                          how_to_fix="Add unique meta descriptions (120-155 chars) to each page.",
                          affected_pages=pages_missing_desc[:20])

        # Meta description too short
        pages_short_desc = [p.url for p in pages if p.meta_description and p.meta_description_length < 70]
        if pages_short_desc:
            self._add_issue("Meta Descriptions Too Short", IssueSeverity.WARNING, "Content",
                          str(len(pages_short_desc)) + " page(s) have meta descriptions under 70 characters.",
                          how_to_fix="Expand meta descriptions to 120-155 characters.",
                          affected_pages=pages_short_desc[:20])

        # Meta description too long
        pages_long_desc = [p.url for p in pages if p.meta_description_length > 160]
        if pages_long_desc:
            self._add_issue("Meta Descriptions Too Long", IssueSeverity.NOTICE, "Content",
                          str(len(pages_long_desc)) + " page(s) have meta descriptions over 160 characters.",
                          how_to_fix="Trim meta descriptions to under 160 characters.",
                          affected_pages=pages_long_desc[:20])

        # Duplicate meta descriptions
        desc_map = defaultdict(list)
        for p in pages:
            if p.meta_description and len(p.meta_description) > 10:
                desc_map[p.meta_description].append(p.url)
        dup_descs = {d: urls for d, urls in desc_map.items() if len(urls) > 1}
        if dup_descs:
            dup_desc_count = sum(len(urls) for urls in dup_descs.values())
            sample = []
            for urls in list(dup_descs.values())[:5]:
                sample.extend(urls[:2])
            self._add_issue("Duplicate Meta Descriptions", IssueSeverity.WARNING, "Content",
                          str(dup_desc_count) + " pages share duplicate meta descriptions.",
                          how_to_fix="Write unique meta descriptions for each page.",
                          affected_pages=sample[:20])

        # Missing H1
        pages_missing_h1 = [p.url for p in pages if p.h1_count == 0]
        if pages_missing_h1:
            self._add_issue("Missing H1 Tags", IssueSeverity.ERROR, "Content",
                          str(len(pages_missing_h1)) + " page(s) have no H1 heading.",
                          how_to_fix="Add exactly one H1 tag to each page.",
                          affected_pages=pages_missing_h1[:20])

        # Multiple H1s
        pages_multi_h1 = [p.url for p in pages if p.h1_count > 1]
        if pages_multi_h1:
            self._add_issue("Multiple H1 Tags", IssueSeverity.WARNING, "Content",
                          str(len(pages_multi_h1)) + " page(s) have more than one H1.",
                          how_to_fix="Use a single H1 per page.",
                          affected_pages=pages_multi_h1[:20])

        # Images missing alt text
        total_missing_alt = sum(p.images_missing_alt for p in pages)
        pages_with_missing_alt = [p.url for p in pages if p.images_missing_alt > 0]
        if total_missing_alt > 0:
            self._add_issue("Images Missing Alt Text", IssueSeverity.ERROR, "Accessibility",
                          str(total_missing_alt) + " image(s) across " + str(len(pages_with_missing_alt)) + " pages are missing alt text.",
                          how_to_fix="Add descriptive alt text to all images.",
                          affected_pages=pages_with_missing_alt[:20])

        # Thin content
        pages_thin = [p.url for p in pages if 0 < p.word_count < 300]
        if pages_thin:
            self._add_issue("Thin Content Pages", IssueSeverity.WARNING, "Content",
                          str(len(pages_thin)) + " page(s) have less than 300 words.",
                          how_to_fix="Expand content to at least 300 words per page.",
                          affected_pages=pages_thin[:20])

        # Very thin content
        pages_very_thin = [p.url for p in pages if 0 < p.word_count < 100]
        if pages_very_thin:
            self._add_issue("Very Thin Content", IssueSeverity.ERROR, "Content",
                          str(len(pages_very_thin)) + " page(s) have less than 100 words.",
                          how_to_fix="These pages need substantial content expansion.",
                          affected_pages=pages_very_thin[:20])

        # Missing canonical tags
        pages_no_canonical = [p.url for p in pages if not p.has_canonical]
        if pages_no_canonical:
            self._add_issue("Missing Canonical Tags", IssueSeverity.WARNING, "Technical",
                          str(len(pages_no_canonical)) + " page(s) have no canonical tag.",
                          how_to_fix="Add self-referencing canonical tags to all pages.",
                          affected_pages=pages_no_canonical[:20])

        # Missing viewport (mobile)
        pages_no_viewport = [p.url for p in pages if not p.has_viewport]
        if pages_no_viewport:
            self._add_issue("Missing Viewport Meta Tag", IssueSeverity.ERROR, "Mobile",
                          str(len(pages_no_viewport)) + " page(s) have no viewport meta tag.",
                          how_to_fix="Add viewport meta tag for mobile responsiveness.",
                          affected_pages=pages_no_viewport[:20])

        # No structured data
        pages_no_schema = [p.url for p in pages if not p.has_structured_data]
        if len(pages_no_schema) > len(pages) * 0.5:  # Only flag if majority lack it
            self._add_issue("Low Structured Data Coverage", IssueSeverity.NOTICE, "Technical",
                          str(len(pages_no_schema)) + " of " + str(len(pages)) + " pages lack structured data.",
                          how_to_fix="Add JSON-LD structured data (Product, Article, FAQ, etc.).",
                          affected_pages=pages_no_schema[:10])

        # Invalid JSON-LD
        pages_invalid_jsonld = [p.url for p in pages if p.has_invalid_json_ld]
        if pages_invalid_jsonld:
            self._add_issue("Invalid JSON-LD", IssueSeverity.ERROR, "Technical",
                          str(len(pages_invalid_jsonld)) + " page(s) have invalid JSON-LD structured data.",
                          how_to_fix="Fix JSON syntax errors in your structured data.",
                          affected_pages=pages_invalid_jsonld[:20])

        # Missing OG tags
        pages_no_og = [p.url for p in pages if not p.has_og_tags]
        if len(pages_no_og) > len(pages) * 0.5:
            self._add_issue("Missing Open Graph Tags", IssueSeverity.NOTICE, "Content",
                          str(len(pages_no_og)) + " page(s) lack Open Graph tags for social sharing.",
                          how_to_fix="Add og:title, og:description, og:image to all pages.",
                          affected_pages=pages_no_og[:10])

        # Broken internal links
        broken = [bl for bl in self.broken_links if bl.get("status", 0) >= 400 or bl.get("status", 0) == 0]
        if broken:
            self._add_issue("Broken Internal Links/Pages", IssueSeverity.ERROR, "Technical",
                          str(len(broken)) + " broken URL(s) found during crawl.",
                          how_to_fix="Fix or redirect these broken URLs.",
                          affected_pages=[b["url"] for b in broken[:20]],
                          extra_data={"broken_links": broken[:20]})

        # Slow pages
        slow_pages = [p.url for p in pages if p.response_time_ms > 3000]
        if slow_pages:
            self._add_issue("Slow Loading Pages", IssueSeverity.WARNING, "Performance",
                          str(len(slow_pages)) + " page(s) take over 3 seconds to respond.",
                          how_to_fix="Optimize server response time. Consider caching, CDN, or server upgrades.",
                          affected_pages=slow_pages[:20])

        # Large pages
        large_pages = [p.url for p in pages if p.html_size_kb > 200]
        if large_pages:
            self._add_issue("Very Large HTML Pages", IssueSeverity.WARNING, "Performance",
                          str(len(large_pages)) + " page(s) have HTML over 200KB.",
                          how_to_fix="Minify HTML, externalize CSS/JS, lazy-load content.",
                          affected_pages=large_pages[:20])

        # No compression
        pages_no_compression = [p.url for p in pages if not p.has_compression and p.html_size_kb > 10]
        if len(pages_no_compression) > len(pages) * 0.5:
            self._add_issue("No Compression", IssueSeverity.WARNING, "Performance",
                          "Most pages are not compressed with gzip/Brotli.",
                          how_to_fix="Enable gzip or Brotli compression on your server.")

        # Render-blocking JS
        pages_blocking_js = [p.url for p in pages if p.render_blocking_js > 3]
        if pages_blocking_js:
            self._add_issue("Render-Blocking JavaScript", IssueSeverity.WARNING, "Performance",
                          str(len(pages_blocking_js)) + " page(s) have 4+ render-blocking scripts.",
                          how_to_fix="Add 'async' or 'defer' to script tags.",
                          affected_pages=pages_blocking_js[:20])

        # Missing security headers (check from homepage only)
        homepage = self.page_data.get(self._normalize_url(self.base_url))
        if homepage and homepage.status_code == 200:
            # HSTS check would need headers stored — simplified for now
            pass

        # ─── Calculate site-wide stats ───
        if pages:
            self.site_stats["pages_crawled"] = len(self.crawled_urls)
            self.site_stats["total_images"] = sum(p.total_images for p in pages)
            self.site_stats["total_internal_links"] = sum(p.internal_links for p in pages)
            self.site_stats["total_external_links"] = sum(p.external_links for p in pages)
            self.site_stats["avg_word_count"] = round(sum(p.word_count for p in pages) / len(pages))
            self.site_stats["avg_response_time_ms"] = round(sum(p.response_time_ms for p in pages) / len(pages))
            self.site_stats["avg_page_size_kb"] = round(sum(p.html_size_kb for p in pages) / len(pages), 1)

    # ─────────────────────────────────────────────
    #  Issue helpers
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
            "affected_count": len(affected_pages) if affected_pages else 1,
            "estimated_impact": self._estimate_impact(severity),
            "effort_required": self._estimate_effort(issue_type),
        }
        if extra_data:
            issue["extra_data"] = extra_data

        self.issues.append(issue)

        self.recommendations.append({
            "id": len(self.recommendations) + 1,
            "priority": {"Critical": 1, "Error": 2, "Warning": 3, "Notice": 4}.get(severity.value, 3),
            "title": how_to_fix.split('.')[0] if how_to_fix else "Fix: " + issue_type,
            "description": how_to_fix,
            "expected_impact": {"Critical": "High", "Error": "High", "Warning": "Medium", "Notice": "Low"}.get(severity.value, "Medium"),
            "implementation_complexity": self._estimate_effort(issue_type),
            "estimated_traffic_gain": self._estimate_traffic_gain(severity, category),
        })

    def _estimate_impact(self, severity: IssueSeverity) -> int:
        return {"Critical": 90, "Error": 70, "Warning": 40, "Notice": 15}.get(severity.value, 20)

    def _estimate_effort(self, issue_type: str) -> str:
        high_effort = ["Broken Internal Links/Pages", "No Compression", "Render-Blocking JavaScript", "Slow Loading Pages"]
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
        """Calculate scores based on issues found."""
        categories = {
            "Technical": {"base": 100, "issues": []},
            "Content": {"base": 100, "issues": []},
            "Performance": {"base": 100, "issues": []},
            "Mobile": {"base": 100, "issues": []},
            "Security": {"base": 100, "issues": []},
            "Accessibility": {"base": 100, "issues": []},
        }

        severity_penalties = {"Critical": 25, "Error": 15, "Warning": 8, "Notice": 3}

        for issue in self.issues:
            cat = issue.get("category", "Technical")
            if cat in categories:
                penalty = severity_penalties.get(issue["severity"], 5)
                categories[cat]["issues"].append(penalty)

        scores = {}
        for cat, data in categories.items():
            total_penalty = sum(data["issues"])
            scores[cat.lower()] = round(max(data["base"] - total_penalty, 0), 1)

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

        # Build per-page summary for the report (without storing full HTML)
        page_summaries = []
        for url, page in self.page_data.items():
            if page.status_code == 200:
                page_summaries.append({
                    "url": page.url,
                    "status": page.status_code,
                    "title": page.title[:100] if page.title else "",
                    "title_length": page.title_length,
                    "meta_desc_length": page.meta_description_length,
                    "h1_count": page.h1_count,
                    "word_count": page.word_count,
                    "images_missing_alt": page.images_missing_alt,
                    "has_canonical": page.has_canonical,
                    "has_structured_data": page.has_structured_data,
                    "response_time_ms": page.response_time_ms,
                    "html_size_kb": page.html_size_kb,
                })

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
                "site_stats": self.site_stats,
                "page_summaries": page_summaries[:500],  # Cap at 500 pages
                "raw_data": {
                    "has_robots_txt": self.has_robots_txt,
                    "has_sitemap": self.has_sitemap,
                    "ssl_valid": self.ssl_valid,
                    "ssl_days_remaining": self.ssl_days_remaining,
                    "pages_crawled": len(self.crawled_urls),
                    "broken_links_count": len(self.broken_links),
                }
            }
        )

        self.db.add(report)
        self.website.last_audit = datetime.utcnow()
        self.db.commit()
        self.db.refresh(report)

        print("[Audit] Saved report #" + str(report.id) + " for " + self.domain)

        return {
            "report_id": report.id,
            "health_score": scores["overall"],
            "issues": self.issues,
            "recommendations": self.recommendations
        }


# ─────────────────────────────────────────────
#  Standalone runner
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            wid = int(sys.argv[1])
        except ValueError:
            print("Usage: python audit_engine.py <website_id>")
            sys.exit(1)

        engine = SEOAuditEngine(wid)
        result = asyncio.run(engine.run_comprehensive_audit())
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python audit_engine.py <website_id>")
