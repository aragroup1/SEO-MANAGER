# backend/image_optimizer.py — Image Optimization Audit Engine
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database import SessionLocal, Website, ImageAudit


class ImageOptimizer:
    """Crawls a website and audits all images for SEO and performance issues."""

    REQUEST_TIMEOUT = 15
    MAX_IMAGES = 500

    def __init__(self, website_id: int):
        self.website_id = website_id
        self.db = SessionLocal()
        self.issues_found = []

    def __del__(self):
        if hasattr(self, "db"):
            self.db.close()

    async def analyze_images(self, start_url: str = None) -> Dict[str, Any]:
        """Main entry: crawl site and audit all images."""
        website = self.db.query(Website).filter(Website.id == self.website_id).first()
        if not website:
            return {"error": "Website not found"}

        domain = website.domain
        base_url = start_url or (f"https://{domain}" if not domain.startswith("http") else domain)

        # Clear old audits for this website
        self.db.query(ImageAudit).filter(ImageAudit.website_id == self.website_id).delete()
        self.db.commit()

        # Crawl and collect images
        images = await self._crawl_for_images(base_url)

        # Analyze each image
        results = []
        for img_data in images[:self.MAX_IMAGES]:
            analysis = self._analyze_single_image(img_data)
            results.append(analysis)

            # Store in DB
            audit = ImageAudit(
                website_id=self.website_id,
                page_url=img_data["page_url"],
                image_url=img_data["src"],
                alt_text=img_data.get("alt"),
                has_dimensions=bool(img_data.get("width") and img_data.get("height")),
                file_size_kb=img_data.get("file_size_kb"),
                format=img_data.get("format"),
                is_lazy_loaded=img_data.get("lazy_loaded", False),
                is_above_fold=img_data.get("above_fold", False),
                issues=analysis["issues"],
            )
            self.db.add(audit)

        self.db.commit()

        # Summary stats
        total = len(results)
        missing_alt = sum(1 for r in results if any("missing_alt" in i["code"] for i in r["issues"]))
        no_dimensions = sum(1 for r in results if any("no_dimensions" in i["code"] for i in r["issues"]))
        oversized = sum(1 for r in results if any("oversized" in i["code"] for i in r["issues"]))
        wrong_format = sum(1 for r in results if any("wrong_format" in i["code"] for i in r["issues"]))
        no_lazy = sum(1 for r in results if any("no_lazy_loading" in i["code"] for i in r["issues"]))

        return {
            "total_images": total,
            "missing_alt": missing_alt,
            "no_dimensions": no_dimensions,
            "oversized": oversized,
            "wrong_format": wrong_format,
            "no_lazy_loading": no_lazy,
            "score": max(0, 100 - (missing_alt * 3) - (no_dimensions * 2) - (oversized * 2) - (wrong_format * 1) - (no_lazy * 1)),
            "images": results[:50],  # Return first 50 for UI
        }

    async def _crawl_for_images(self, base_url: str) -> List[Dict[str, Any]]:
        """Fetch the homepage and extract all image tags."""
        images = []
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)) as session:
                async with session.get(base_url, headers={"User-Agent": "SEO-ImageBot/1.0"}) as resp:
                    if resp.status != 200:
                        return images
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Find all images
                    for img in soup.find_all("img"):
                        src = img.get("src", "")
                        if not src:
                            continue
                        # Resolve relative URLs
                        if src.startswith("/") or not src.startswith("http"):
                            src = urljoin(base_url, src)

                        # Skip data URIs
                        if src.startswith("data:"):
                            continue

                        img_data = {
                            "page_url": base_url,
                            "src": src,
                            "alt": img.get("alt"),
                            "width": img.get("width"),
                            "height": img.get("height"),
                            "lazy_loaded": "lazy" in (img.get("loading", "")).lower(),
                            "above_fold": False,  # Would need viewport analysis
                        }

                        # Try to detect format from URL
                        parsed = urlparse(src)
                        path = parsed.path.lower()
                        if path.endswith(".webp"):
                            img_data["format"] = "webp"
                        elif path.endswith(".avif"):
                            img_data["format"] = "avif"
                        elif path.endswith(".png"):
                            img_data["format"] = "png"
                        elif path.endswith(".jpg") or path.endswith(".jpeg"):
                            img_data["format"] = "jpg"
                        elif path.endswith(".gif"):
                            img_data["format"] = "gif"
                        elif path.endswith(".svg"):
                            img_data["format"] = "svg"
                        else:
                            img_data["format"] = "unknown"

                        images.append(img_data)

        except Exception as e:
            print(f"[ImageOptimizer] Crawl error: {e}")

        return images

    def _analyze_single_image(self, img_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single image and return issues."""
        issues = []
        src = img_data.get("src", "")
        alt = img_data.get("alt")
        width = img_data.get("width")
        height = img_data.get("height")
        fmt = img_data.get("format", "unknown")
        lazy = img_data.get("lazy_loaded", False)

        # Missing alt text
        if not alt or alt.strip() == "":
            issues.append({
                "code": "missing_alt",
                "severity": "error",
                "message": "Image has no alt text — hurts accessibility and SEO",
                "fix": "Add descriptive alt text",
            })
        elif len(alt) > 125:
            issues.append({
                "code": "alt_too_long",
                "severity": "warning",
                "message": f"Alt text is {len(alt)} chars (max 125 recommended)",
                "fix": "Shorten alt text to under 125 characters",
            })

        # Missing dimensions
        if not width or not height:
            issues.append({
                "code": "no_dimensions",
                "severity": "warning",
                "message": "Image missing width/height attributes — causes CLS",
                "fix": "Add width and height attributes",
            })

        # Wrong format
        modern_formats = {"webp", "avif", "svg"}
        if fmt not in modern_formats and fmt != "unknown":
            issues.append({
                "code": "wrong_format",
                "severity": "warning",
                "message": f"Image is {fmt.upper()} — consider converting to WebP/AVIF",
                "fix": "Convert to WebP or AVIF for better compression",
            })

        # No lazy loading for below-fold images (simplified — assume all are below fold except first few)
        if not lazy and not img_data.get("is_above_fold", False):
            issues.append({
                "code": "no_lazy_loading",
                "severity": "notice",
                "message": "Image not using lazy loading",
                "fix": "Add loading='lazy' attribute",
            })

        # Filename SEO check
        parsed = urlparse(src)
        filename = parsed.path.split("/")[-1] if parsed.path else ""
        if filename and re.match(r'^[0-9]+\.(jpg|png|webp)$', filename, re.I):
            issues.append({
                "code": "bad_filename",
                "severity": "warning",
                "message": f"Image filename '{filename}' is not descriptive",
                "fix": "Use descriptive, keyword-rich filenames",
            })

        return {
            "src": src,
            "alt": alt,
            "format": fmt,
            "issues": issues,
            "issue_count": len(issues),
        }


def get_image_stats(website_id: int) -> Dict[str, Any]:
    """Get summarized image audit stats for a website."""
    db = SessionLocal()
    try:
        audits = db.query(ImageAudit).filter(ImageAudit.website_id == website_id).all()
        if not audits:
            return {"has_data": False, "message": "No image audit data. Run an audit first."}

        total = len(audits)
        missing_alt = sum(1 for a in audits if any(i.get("code") == "missing_alt" for i in (a.issues or [])))
        no_dims = sum(1 for a in audits if any(i.get("code") == "no_dimensions" for i in (a.issues or [])))
        wrong_fmt = sum(1 for a in audits if any(i.get("code") == "wrong_format" for i in (a.issues or [])))
        no_lazy = sum(1 for a in audits if any(i.get("code") == "no_lazy_loading" for i in (a.issues or [])))
        bad_names = sum(1 for a in audits if any(i.get("code") == "bad_filename" for i in (a.issues or [])))

        score = max(0, 100 - (missing_alt * 3) - (no_dims * 2) - (wrong_fmt * 2) - (no_lazy * 1) - (bad_names * 1))

        return {
            "has_data": True,
            "total_images": total,
            "missing_alt": missing_alt,
            "no_dimensions": no_dims,
            "wrong_format": wrong_fmt,
            "no_lazy_loading": no_lazy,
            "bad_filenames": bad_names,
            "score": score,
            "last_checked": max((a.checked_at.isoformat() for a in audits if a.checked_at), default=None),
        }
    finally:
        db.close()


def get_image_issues(website_id: int, severity: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Get detailed image issues for a website."""
    db = SessionLocal()
    try:
        audits = db.query(ImageAudit).filter(ImageAudit.website_id == website_id).all()
        issues = []
        for audit in audits:
            for issue in (audit.issues or []):
                if severity and issue.get("severity") != severity:
                    continue
                issues.append({
                    "page_url": audit.page_url,
                    "image_url": audit.image_url,
                    "alt_text": audit.alt_text,
                    "format": audit.format,
                    **issue,
                })
        return issues[:limit]
    finally:
        db.close()
