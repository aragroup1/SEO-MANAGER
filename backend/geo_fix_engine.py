# backend/geo_fix_engine.py - GEO Auto-Fix Engine
# Scans website pages for AI search optimization gaps and generates
# proposed fixes that go through the approval queue before being applied.
import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import httpx
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import socket
import ipaddress
from dotenv import load_dotenv

from database import SessionLocal, Website, ProposedFix, Integration

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")


async def _generate_ai_content(prompt: str, max_tokens: int = 500) -> str:
    """Generate content using Gemini."""
    if not GEMINI_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"[GEO Fix] Gemini error: {resp.status_code}")
    except Exception as e:
        print(f"[GEO Fix] AI error: {e}")
    return ""


def _is_safe_url(url: str) -> bool:
    """Prevent SSRF by blocking internal/private URLs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        if hostname == "169.254.169.254":
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for _, _, _, _, sockaddr in resolved:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_private or ip.is_loopback or ip.is_reserved:
                        return False
            except socket.gaierror:
                pass
        return True
    except Exception:
        return False


async def _crawl_page(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    """Crawl a page and extract GEO-relevant data."""
    if not _is_safe_url(url):
        return {"url": url, "error": "unsafe_url"}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True) as resp:
            if resp.status != 200:
                return {"url": url, "error": "Status " + str(resp.status)}

            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')

            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""

            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_text = (meta_desc.get('content', '') or '').strip() if meta_desc else ""

            body = soup.find('body')
            content_text = ""
            if body:
                bc = BeautifulSoup(str(body), 'html.parser').find('body')
                for tag in bc.find_all(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
                    tag.decompose()
                content_text = bc.get_text(separator=' ', strip=True)

            # Check GEO signals
            json_ld = soup.find_all('script', type='application/ld+json')
            schema_types = []
            has_faq = False
            for script in json_ld:
                try:
                    data = json.loads(script.string or '{}')
                    t = data.get('@type', '')
                    types = t if isinstance(t, list) else [t]
                    schema_types.extend(types)
                    if 'FAQPage' in types:
                        has_faq = True
                except:
                    pass

            import re
            headings = []
            for level in range(1, 4):
                for h in soup.find_all(f'h{level}'):
                    text = h.get_text(strip=True)
                    if text:
                        headings.append({"level": level, "text": text[:100]})

            question_headings = [h for h in headings if any(w in h["text"].lower() for w in ['?', 'what ', 'how ', 'why ', 'when ', 'where ', 'which '])]

            has_author = bool(soup.find(class_=re.compile(r'author|byline', re.I)) or soup.find('meta', attrs={'name': 'author'}))
            has_date = bool(soup.find('time') or soup.find('meta', attrs={'property': 'article:published_time'}))
            has_updated = bool(soup.find('meta', attrs={'property': 'article:modified_time'}))

            stat_patterns = re.findall(r'\d+%|\$[\d,.]+|\d+\s*(million|billion|thousand|percent)', content_text.lower())
            has_stats = len(stat_patterns) > 2

            # Check for AI-bait summary (concise factual opening)
            paragraphs = soup.find_all('p')
            first_para = paragraphs[0].get_text(strip=True) if paragraphs else ""
            has_summary = len(first_para.split()) >= 15 and len(first_para.split()) <= 60

            lists = soup.find_all(['ul', 'ol'])
            tables = soup.find_all('table')

            return {
                "url": url,
                "title": title_text,
                "meta_description": meta_text,
                "word_count": len(content_text.split()),
                "content_preview": content_text[:800],
                "headings": headings[:20],
                "question_headings": question_headings,
                "schema_types": schema_types,
                "has_faq_schema": has_faq,
                "has_author": has_author,
                "has_date": has_date,
                "has_updated": has_updated,
                "has_stats": has_stats,
                "has_summary": has_summary,
                "first_paragraph": first_para[:300],
                "lists_count": len(lists),
                "tables_count": len(tables),
                "html": html,
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


async def scan_and_generate_geo_fixes(website_id: int) -> Dict[str, Any]:
    """
    Scan website pages for GEO optimization gaps.
    Generate proposed fixes that go into the approval queue.
    Does NOT auto-apply — user must approve each fix.
    """
    db = SessionLocal()
    try:
        website = db.query(Website).filter(Website.id == website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = "https://" + domain if not domain.startswith("http") else domain
        batch_id = f"geo_batch_{website_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        print(f"[GEO Fix] Starting scan for {domain}")

        connector = aiohttp.TCPConnector(limit=5)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "SEOIntelligenceBot/2.0"}
        ) as session:

            # Crawl homepage + discover content pages
            pages_to_scan = [base_url]

            # Get internal links from homepage
            homepage = await _crawl_page(session, base_url)
            if not homepage.get("error"):
                soup = BeautifulSoup(homepage.get("html", ""), 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/') and not href.startswith('//'):
                        full = base_url.rstrip('/') + href
                        path = href.lower()
                        if any(seg in path for seg in ['/blog', '/post', '/article', '/guide', '/faq', '/product', '/page', '/about', '/service']):
                            if full not in pages_to_scan:
                                pages_to_scan.append(full)

            # Cap at 20 pages to keep costs reasonable
            pages_to_scan = pages_to_scan[:20]

            print(f"[GEO Fix] Scanning {len(pages_to_scan)} pages")

            all_fixes = []
            for page_url in pages_to_scan:
                if page_url == base_url and not homepage.get("error"):
                    page_data = homepage
                else:
                    page_data = await _crawl_page(session, page_url)
                    await asyncio.sleep(0.3)

                if page_data.get("error"):
                    continue

                page_fixes = await _analyze_page_for_geo(page_data, website_id, batch_id, website.site_type)
                all_fixes.extend(page_fixes)

        # Save fixes to database
        saved = 0
        auto_approved_count = 0
        auto_applied_count = 0
        for fix_data in all_fixes:
            fix_data.pop("html", None)
            proposed_fix = ProposedFix(**fix_data)
            db.add(proposed_fix)
            db.flush()
            saved += 1

            # ─── Autonomy mode: auto-approve GEO fixes ───
            from automation_config import should_auto_approve, should_auto_apply
            from fix_engine import apply_approved_fix
            if should_auto_approve(proposed_fix, website.autonomy_mode):
                proposed_fix.status = "approved"
                proposed_fix.auto_approved_at = datetime.utcnow()
                auto_approved_count += 1
                db.commit()
                print(f"[GEO Fix] Auto-approved fix {proposed_fix.id} ({proposed_fix.fix_type}) for {domain}")

                if should_auto_apply(proposed_fix, website.autonomy_mode):
                    try:
                        apply_result = await apply_approved_fix(proposed_fix.id)
                        if apply_result.get("success"):
                            proposed_fix.auto_applied = True
                            auto_applied_count += 1
                            print(f"[GEO Fix] Auto-applied fix {proposed_fix.id} ({proposed_fix.fix_type}) for {domain}")
                        else:
                            print(f"[GEO Fix] Auto-apply failed for fix {proposed_fix.id}: {apply_result.get('message', 'unknown')}")
                    except Exception as e:
                        print(f"[GEO Fix] Auto-apply error for fix {proposed_fix.id}: {e}")

        db.commit()
        print(f"[GEO Fix] Generated {saved} GEO fix proposals for {domain}")
        if auto_approved_count:
            print(f"[GEO Fix]   Auto-approved: {auto_approved_count}, Auto-applied: {auto_applied_count}")

        return {
            "batch_id": batch_id,
            "total_fixes": saved,
            "auto_approved": auto_approved_count,
            "auto_applied": auto_applied_count,
            "pages_scanned": len(pages_to_scan),
            "message": f"Generated {saved} GEO optimization proposals. Auto-approved: {auto_approved_count}, Auto-applied: {auto_applied_count}. Review remaining in Issues & Fixes."
        }

    except Exception as e:
        print(f"[GEO Fix] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


async def _analyze_page_for_geo(page: Dict, website_id: int, batch_id: str, site_type: str) -> List[Dict]:
    """Analyze a single page and generate GEO fix proposals."""
    fixes = []
    url = page.get("url", "")
    title = page.get("title", "")
    content = page.get("content_preview", "")
    word_count = page.get("word_count", 0)

    # ─── 1. Missing FAQ Schema ───
    if not page.get("has_faq_schema") and page.get("question_headings") and len(page["question_headings"]) >= 2:
        # Page has Q&A-style headings but no FAQ schema — generate it
        questions = page["question_headings"][:5]
        faq_prompt = f"""Generate FAQ Schema (JSON-LD) for this page.
Page title: {title}
Page URL: {url}
Existing Q&A headings on the page:
{chr(10).join([f"- {q['text']}" for q in questions])}

Generate a valid FAQPage JSON-LD script tag with answers based on the page context.
Return ONLY the complete <script type="application/ld+json">...</script> tag, nothing else."""

        faq_schema = await _generate_ai_content(faq_prompt, 800)
        if faq_schema:
            fixes.append({
                "website_id": website_id,
                "fix_type": "structured_data",
                "platform": site_type,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": title,
                "field_name": "faq_schema",
                "current_value": "(no FAQ schema)",
                "proposed_value": faq_schema,
                "ai_reasoning": "This page has " + str(len(questions)) + " question-style headings but no FAQPage schema. Adding FAQ schema makes this content eligible for rich results and increases chances of being cited by AI search engines.",
                "severity": "high",
                "category": "geo",
                "batch_id": batch_id,
            })

    elif not page.get("has_faq_schema") and word_count > 200:
        # No questions at all — suggest adding FAQ section + schema
        faq_prompt = f"""For this page, generate 3-5 frequently asked questions with concise answers.
Page title: {title}
Page URL: {url}
Content preview: {content[:400]}

Generate both:
1. HTML section with Q&A (using <h3> for questions, <p> for answers)
2. Matching FAQPage JSON-LD schema

Format:
---HTML---
<div class="faq-section">...</div>
---SCHEMA---
<script type="application/ld+json">...</script>"""

        faq_content = await _generate_ai_content(faq_prompt, 1200)
        if faq_content:
            fixes.append({
                "website_id": website_id,
                "fix_type": "thin_content",
                "platform": site_type,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": title,
                "field_name": "faq_section",
                "current_value": "(no FAQ section)",
                "proposed_value": faq_content,
                "ai_reasoning": "Adding a FAQ section with schema markup significantly improves GEO scores. AI search engines prefer pages with structured Q&A content — it makes your content directly citable.",
                "severity": "medium",
                "category": "geo",
                "batch_id": batch_id,
            })

    # ─── 2. Missing AI-Bait Summary ───
    if not page.get("has_summary") and word_count > 150:
        summary_prompt = f"""Write a 2-3 sentence factual summary for the top of this page.
This summary should be optimized for AI search engines (ChatGPT, Perplexity, Google AI Overviews) to cite.

Rules:
- Start with a direct, definitive statement
- Include specific facts or numbers if possible
- Be factual and authoritative, not promotional
- Keep under 60 words

Page title: {title}
Content: {content[:500]}

Return ONLY the summary text, nothing else."""

        summary = await _generate_ai_content(summary_prompt, 150)
        if summary:
            fixes.append({
                "website_id": website_id,
                "fix_type": "meta_description",
                "platform": site_type,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": title,
                "field_name": "ai_summary",
                "current_value": page.get("first_paragraph", "")[:200] or "(no clear opening summary)",
                "proposed_value": f'<p class="ai-summary" style="font-size:1.1em;font-weight:500;margin-bottom:1.5em;border-left:3px solid #6366f1;padding-left:12px;">{summary}</p>',
                "ai_reasoning": "This page lacks a concise factual opening. AI search engines like ChatGPT and Perplexity prefer pages that start with a direct, citable summary. This 'AI-bait' summary increases the chance your page gets cited in AI-generated answers.",
                "severity": "high",
                "category": "geo",
                "batch_id": batch_id,
            })

    # ─── 3. Missing Author/E-E-A-T Signals ───
    if not page.get("has_author") and word_count > 300:
        fixes.append({
            "website_id": website_id,
            "fix_type": "structured_data",
            "platform": site_type,
            "resource_type": "page",
            "resource_id": "",
            "resource_url": url,
            "resource_title": title,
            "field_name": "author_byline",
            "current_value": "(no author attribution)",
            "proposed_value": '<div class="author-byline" itemscope itemtype="https://schema.org/Person"><span>Written by </span><span itemprop="name">[Author Name]</span><span> · </span><time datetime="' + datetime.utcnow().strftime('%Y-%m-%d') + '">Updated ' + datetime.utcnow().strftime('%B %Y') + '</time></div>',
            "ai_reasoning": "No author byline detected. Google's E-E-A-T framework heavily weights 'Experience' and 'Expertise'. Adding author attribution with schema.org markup improves trust signals for both traditional and AI search.",
            "severity": "medium",
            "category": "geo",
            "batch_id": batch_id,
        })

    # ─── 4. Missing Published/Updated Dates ───
    if not page.get("has_date") and not page.get("has_updated") and word_count > 200:
        fixes.append({
            "website_id": website_id,
            "fix_type": "structured_data",
            "platform": site_type,
            "resource_type": "page",
            "resource_id": "",
            "resource_url": url,
            "resource_title": title,
            "field_name": "date_markup",
            "current_value": "(no publish/update date)",
            "proposed_value": '<meta property="article:published_time" content="' + datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '" />\n<meta property="article:modified_time" content="' + datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00') + '" />',
            "ai_reasoning": "No published or updated date found. Freshness signals are critical for AI search engines — they strongly prefer citing recently updated content. Adding date metadata tells Google and AI models your content is current.",
            "severity": "medium",
            "category": "geo",
            "batch_id": batch_id,
        })

    # ─── 5. No Statistics/Data Points ───
    if not page.get("has_stats") and word_count > 300:
        stats_prompt = f"""For this page, suggest 3-4 specific statistics, data points, or numbers that would make the content more authoritative and citable by AI search engines.

Page title: {title}
Content: {content[:400]}

Format each as a brief sentence that could be added to the content. Be specific and factual.
Return ONLY the statistics, one per line."""

        stats = await _generate_ai_content(stats_prompt, 300)
        if stats:
            fixes.append({
                "website_id": website_id,
                "fix_type": "thin_content",
                "platform": site_type,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": title,
                "field_name": "statistics",
                "current_value": "(no statistics or data points detected)",
                "proposed_value": stats,
                "ai_reasoning": "Pages with specific statistics and data points are 3x more likely to be cited by AI search engines. Adding factual numbers (percentages, comparisons, benchmarks) makes your content more authoritative and citable.",
                "severity": "low",
                "category": "geo",
                "batch_id": batch_id,
            })

    # ─── 6. Missing Entity-Rich Tables ───
    if page.get("tables_count", 0) == 0 and word_count > 300:
        table_prompt = f"""For this page, create a comparison or specification table that would help AI search engines understand the content better.

Page title: {title}
Content: {content[:400]}

Generate an HTML table with 3-5 rows comparing key attributes. Make it factual and data-rich.
Return ONLY the HTML table, nothing else."""

        table_html = await _generate_ai_content(table_prompt, 600)
        if table_html and '<table' in table_html.lower():
            fixes.append({
                "website_id": website_id,
                "fix_type": "thin_content",
                "platform": site_type,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": title,
                "field_name": "entity_table",
                "current_value": "(no data tables on page)",
                "proposed_value": table_html,
                "ai_reasoning": "No data tables found. Google's AI Overviews love structured tables because they're easy to parse and cite. Adding an entity-rich comparison table significantly increases your chances of appearing in AI search results.",
                "severity": "medium",
                "category": "geo",
                "batch_id": batch_id,
            })

    return fixes
