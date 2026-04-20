# backend/manual_issues.py
# Turns audit findings into ProposedFix rows for issues the platform engines can't auto-fix.
# Rows are created with status="manual" and a clear instructions payload in proposed_value.

from typing import List, Dict
from sqlalchemy import desc
from database import AuditReport


# Already handled by ShopifyFixEngine / WordPressFixEngine per-resource scans
ALREADY_COVERED = {
    "Missing Title Tags", "Title Tags Too Short", "Title Tags Too Long", "Duplicate Title Tags",
    "Missing Meta Descriptions", "Meta Descriptions Too Short", "Meta Descriptions Too Long",
    "Duplicate Meta Descriptions",
    "Missing H1 Tags",
    "Images Missing Alt Text",
    "Thin Content Pages", "Very Thin Content",
}

# Issue type -> (fix_type, instructions). These require theme/server/plugin work we can't do via API.
MANUAL_INSTRUCTIONS = {
    "Missing robots.txt": (
        "manual_robots",
        "Create a robots.txt at the site root. Shopify: edit robots.txt.liquid in your theme. WordPress: Yoast SEO creates one automatically; or add via a plugin / functions.php.",
    ),
    "Robots.txt Blocks All Crawling": (
        "manual_robots",
        "Your robots.txt blocks all crawlers. Remove 'Disallow: /' and only disallow specific paths (/admin, /cart, etc).",
    ),
    "Missing XML Sitemap": (
        "manual_sitemap",
        "Shopify: /sitemap.xml is auto-generated at the root — verify it loads. WordPress: install Yoast SEO, RankMath, or a dedicated sitemap plugin.",
    ),
    "SSL Certificate Issue": (
        "manual_ssl",
        "Re-issue the certificate via Let's Encrypt or your hosting panel. Shopify manages SSL automatically — contact Shopify support if this appears.",
    ),
    "SSL Certificate Expiring Soon": (
        "manual_ssl",
        "Renew your SSL certificate before it expires. Most hosts auto-renew — check renewal settings.",
    ),
    "Missing Viewport Meta Tag": (
        "manual_viewport",
        "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to the theme <head>. Shopify: edit theme.liquid. WordPress: edit header.php or use theme customizer.",
    ),
    "Missing Open Graph Tags": (
        "manual_og",
        "Add og:title, og:description, og:image to the theme <head>. Shopify: edit theme.liquid. WordPress: install Yoast SEO or RankMath — both add OG tags automatically.",
    ),
    "Missing Canonical Tags": (
        "manual_canonical",
        "Add <link rel=\"canonical\" href=\"{url}\"> to <head>. Shopify: theme.liquid includes this by default. WordPress: Yoast / RankMath handles this automatically.",
    ),
    "Invalid JSON-LD": (
        "manual_schema",
        "JSON-LD has syntax errors. Test each affected page with Google's Rich Results Test (https://search.google.com/test/rich-results) and fix the reported errors.",
    ),
    "Low Structured Data Coverage": (
        "manual_schema",
        "Add JSON-LD structured data (Product, Article, FAQ). Shopify: theme.liquid or apps like Schema Plus. WordPress: Yoast/RankMath or Schema Pro.",
    ),
    "Broken Internal Links/Pages": (
        "manual_broken_links",
        "Review each broken URL. Restore the page, add a 301 redirect to a relevant page, or remove the link. Shopify: URL Redirects in admin. WordPress: Redirection plugin.",
    ),
    "Poor LCP (Largest Contentful Paint)": (
        "manual_performance",
        "Compress hero images, use modern formats (WebP/AVIF), preload critical resources, reduce server response time.",
    ),
    "Needs Improvement: LCP": (
        "manual_performance",
        "LCP can be improved. Compress hero images, use WebP/AVIF, preload critical resources.",
    ),
    "Poor CLS (Cumulative Layout Shift)": (
        "manual_performance",
        "Add explicit width/height to <img> and reserve space for ads, embeds, and late-loading content.",
    ),
    "Needs Improvement: CLS": (
        "manual_performance",
        "Reserve space for dynamic content (images, ads, embeds) to reduce layout shift.",
    ),
    "Poor TBT (Total Blocking Time)": (
        "manual_performance",
        "Defer non-critical JavaScript, remove unused scripts, code-split heavy bundles.",
    ),
    "Needs Improvement: TBT": (
        "manual_performance",
        "Defer non-critical JavaScript and split heavy bundles.",
    ),
    "Slow Loading Pages": (
        "manual_performance",
        "Server response time > 3s. Enable caching, use a CDN (Cloudflare), upgrade hosting if needed.",
    ),
    "Very Large HTML Pages": (
        "manual_performance",
        "HTML > 200KB. Minify HTML, externalize inline CSS/JS, lazy-load below-fold content.",
    ),
    "No Compression": (
        "manual_compression",
        "Enable gzip or Brotli compression on your server/CDN. Shopify: enabled by default. WordPress: via host cPanel, Cloudflare, or caching plugin.",
    ),
    "Render-Blocking JavaScript": (
        "manual_performance",
        "Add 'async' or 'defer' to non-critical <script> tags so they don't block initial render.",
    ),
}

SEVERITY_MAP = {"Critical": "critical", "Error": "high", "Warning": "medium", "Notice": "low"}


def generate_manual_fixes(db, website_id: int, batch_id: str, platform: str) -> List[Dict]:
    """Return ProposedFix dicts for audit issues that require manual (server/theme/plugin) work."""
    latest = (
        db.query(AuditReport)
        .filter(AuditReport.website_id == website_id)
        .order_by(desc(AuditReport.audit_date))
        .first()
    )
    if not latest or not latest.detailed_findings:
        return []

    issues = (latest.detailed_findings or {}).get("issues", []) or []
    fixes: List[Dict] = []

    for issue in issues:
        itype = issue.get("issue_type", "")
        if itype in ALREADY_COVERED or itype not in MANUAL_INSTRUCTIONS:
            continue

        fix_type, instructions = MANUAL_INSTRUCTIONS[itype]
        severity = SEVERITY_MAP.get(issue.get("severity", ""), "medium")
        category = (issue.get("category") or "technical").lower()
        how_to_fix = issue.get("how_to_fix") or ""
        summary = issue.get("title") or itype
        affected_pages = issue.get("affected_pages") or []

        # Site-wide issues (SSL, robots, sitemap, compression) — one row total
        site_wide_types = {"manual_ssl", "manual_robots", "manual_sitemap", "manual_compression"}
        if fix_type in site_wide_types or not affected_pages:
            fixes.append({
                "website_id": website_id,
                "fix_type": fix_type,
                "platform": platform,
                "resource_type": "site",
                "resource_id": "",
                "resource_url": "",
                "resource_title": itype,
                "field_name": itype,
                "current_value": summary,
                "proposed_value": instructions,
                "ai_reasoning": how_to_fix,
                "status": "manual",
                "severity": severity,
                "category": category,
                "batch_id": batch_id,
            })
            continue

        # Per-URL issues — one row per affected page (capped)
        for url in affected_pages[:20]:
            fixes.append({
                "website_id": website_id,
                "fix_type": fix_type,
                "platform": platform,
                "resource_type": "page",
                "resource_id": "",
                "resource_url": url,
                "resource_title": itype,
                "field_name": itype,
                "current_value": summary,
                "proposed_value": instructions,
                "ai_reasoning": how_to_fix,
                "status": "manual",
                "severity": severity,
                "category": category,
                "batch_id": batch_id,
            })

    return fixes
