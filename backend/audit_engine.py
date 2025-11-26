# backend/audit_engine.py - Core SEO Logic
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urlparse, urljoin
import json
import re
from enum import Enum
import numpy as np
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Import necessary classes from main.py
# We can import Base, SessionLocal, Website, and AuditReport directly now
from main import Base, SessionLocal, Website, AuditReport, create_engine, DATABASE_URL

load_dotenv()

# --- Utility Classes/Enums ---
class IssueSeverity(PyEnum):
    CRITICAL = "Critical"
    ERROR = "Error"
    WARNING = "Warning"
    NOTICE = "Notice"

# --- Main Audit Engine ---
class SEOAuditEngine:
    def __init__(self, website_id: int):
        self.website_id = website_id
        self.db: Optional[Session] = None
        self.website: Optional[Website] = None
        self.base_url: Optional[str] = None
        self.domain: Optional[str] = None
        self.parsed_domain: Optional[str] = None

    def __enter__(self):
        self.db = SessionLocal()
        self.website = self.db.query(Website).filter(Website.id == self.website_id).first()
        if not self.website:
            raise ValueError(f"Website with ID {self.website_id} not found.")

        self.domain = self.website.domain
        
        # Ensure base URL has a scheme for aiohttp
        if not self.domain.startswith(('http://', 'https://')):
            self.base_url = f"https://{self.domain}"
        else:
            self.base_url = self.domain
        
        self.parsed_domain = urlparse(self.base_url).netloc

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
            
    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetches the content of a single URL."""
        try:
            async with session.get(url, timeout=10, allow_redirects=True) as response:
                if response.status != 200:
                    print(f"Failed to fetch {url}: Status {response.status}")
                    return None
                return await response.text()
        except aiohttp.ClientError as e:
            print(f"Error fetching {url}: {e}")
            return None
        except asyncio.TimeoutError:
            print(f"Timeout fetching {url}")
            return None

    async def run_comprehensive_audit(self) -> Dict[str, Any]:
        """Runs the full SEO audit process."""
        print(f"Starting comprehensive audit for: {self.domain}")
        try:
            # Context manager handles setup and teardown
            with self:
                # 1. Fetch the main page
                async with aiohttp.ClientSession() as session:
                    html_content = await self.fetch_url(session, self.base_url)
                
                if not html_content:
                    raise Exception("Could not fetch main page content.")

                # 2. Run analysis
                analysis_results = self._analyze_html(html_content)
                
                # 3. Generate scores and aggregate results
                scores, issues, recommendations = self._generate_report(analysis_results)
                
                # 4. Save results to the database
                new_report = AuditReport(
                    website_id=self.website_id,
                    health_score=scores['overall'],
                    technical_score=scores['technical'],
                    content_score=scores['content'],
                    performance_score=scores['performance'],
                    mobile_score=scores['mobile'],
                    security_score=scores['security'],
                    total_issues=len(issues),
                    critical_issues=len([i for i in issues if i['severity'] == IssueSeverity.CRITICAL.value]),
                    errors=len([i for i in issues if i['severity'] == IssueSeverity.ERROR.value]),
                    warnings=len([i for i in issues if i['severity'] == IssueSeverity.WARNING.value]),
                    detailed_findings={"issues": issues, "recommendations": recommendations}
                )
                
                self.db.add(new_report)
                self.website.last_audit = datetime.utcnow()
                self.db.commit()
                self.db.refresh(new_report)
                
                print(f"Audit completed for {self.domain}. Score: {scores['overall']}. Report ID: {new_report.id}")

                return {
                    "health_score": scores['overall'],
                    "issues": issues,
                    "recommendations": recommendations
                }

        except Exception as e:
            print(f"Critical error during audit for {self.domain}: {e}")
            return {"health_score": 0, "issues": [], "recommendations": []}


    def _analyze_html(self, html_content: str) -> Dict[str, Any]:
        """Performs structured analysis on the main page's HTML."""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # --- Core Tags ---
        title = soup.find('title').text if soup.find('title') else None
        meta_description = soup.find('meta', attrs={'name': 'description'})
        meta_description_content = meta_description['content'] if meta_description and 'content' in meta_description.attrs else None
        canonical_link = soup.find('link', rel='canonical')
        
        # --- Headings ---
        headings = [
            (tag.name, tag.text.strip()) 
            for tag in soup.find_all(['h1', 'h2', 'h3', 'h4'])
        ]
        
        # --- Images ---
        images_without_alt = [
            img['src'] for img in soup.find_all('img') if not img.get('alt')
        ]
        
        # --- Word Count (Simplified) ---
        text_content = soup.find('body').get_text(separator=' ', strip=True) if soup.find('body') else ""
        word_count = len(text_content.split())
        
        return {
            "title": title,
            "meta_description": meta_description_content,
            "canonical": canonical_link,
            "headings": headings,
            "images_without_alt": images_without_alt,
            "word_count": word_count,
            "html_size_kb": len(html_content.encode('utf-8')) / 1024
        }

    def _generate_report(self, results: Dict[str, Any]) -> (Dict[str, float], List[Dict], List[Dict]):
        """Generates scores, issues, and recommendations from analysis results."""
        issues = []
        recommendations = []
        
        # --- Content Checks ---
        if not results['title']:
            issues.append({"issue_type": "Missing Title Tag", "severity": IssueSeverity.CRITICAL.value, "category": "Content", "title": "Page is missing a title tag."})
            recommendations.append({"title": "Add a descriptive title tag.", "expected_impact": "High"})
        
        if not results['meta_description'] or len(results['meta_description']) < 50 or len(results['meta_description']) > 160:
            issues.append({"issue_type": "Meta Description Length", "severity": IssueSeverity.WARNING.value, "category": "Content", "title": "Meta description is too short or too long."})
            recommendations.append({"title": "Write a meta description between 50 and 160 characters.", "expected_impact": "Medium"})
            
        if results['word_count'] < 300:
            issues.append({"issue_type": "Low Word Count", "severity": IssueSeverity.NOTICE.value, "category": "Content", "title": f"Page content is thin ({results['word_count']} words)."})
            recommendations.append({"title": "Expand content to at least 500 words for better topical authority.", "expected_impact": "Medium"})

        # --- Technical Checks ---
        if not any(h[0] == 'h1' for h in results['headings']):
            issues.append({"issue_type": "Missing H1 Tag", "severity": IssueSeverity.ERROR.value, "category": "Technical", "title": "Page is missing an H1 heading."})
            recommendations.append({"title": "Add a single, descriptive H1 tag to the page.", "expected_impact": "High"})

        if results['images_without_alt']:
            issues.append({"issue_type": "Missing Alt Text", "severity": IssueSeverity.ERROR.value, "category": "Accessibility", "title": f"Found {len(results['images_without_alt'])} images without alt text."})
            recommendations.append({"title": "Add descriptive alt text to all images for accessibility and SEO.", "expected_impact": "Medium"})
            
        # --- Performance Check (Simplified) ---
        if results['html_size_kb'] > 100:
            issues.append({"issue_type": "Large HTML Size", "severity": IssueSeverity.WARNING.value, "category": "Performance", "title": f"Main HTML document is large ({results['html_size_kb']:.2f} KB)."})
            recommendations.append({"title": "Minify HTML and consider externalizing CSS/JS to reduce main document size.", "expected_impact": "Low"})

        # --- Score Calculation (Simplified based on issue count) ---
        technical_issues = len([i for i in issues if i['category'] == 'Technical'])
        content_issues = len([i for i in issues if i['category'] == 'Content'])
        
        # Base scores
        technical_score = max(100 - technical_issues * 5, 50)
        content_score = max(100 - content_issues * 4, 50)
        
        # Mock scores for other categories (PageSpeed API would fill these in the real version)
        performance_score = 75 
        mobile_score = 85
        security_score = 90
        
        overall_score = np.mean([technical_score, content_score, performance_score, mobile_score, security_score])
        
        scores = {
            "overall": round(float(overall_score), 2),
            "technical": round(float(technical_score), 2),
            "content": round(float(content_score), 2),
            "performance": performance_score,
            "mobile": mobile_score,
            "security": security_score
        }
        
        # Add mock fields to recommendations for frontend consistency
        for i, rec in enumerate(recommendations):
            rec['id'] = i + 1
            rec['priority'] = i % 3 + 1 # 1=High, 3=Low
            rec['description'] = f"Suggested action for: {rec['title']}"
            rec['implementation_complexity'] = 'Low' if i < 2 else 'Medium'
            rec['estimated_traffic_gain'] = 50 + (i * 20)
            
        # Add mock fields to issues for frontend consistency
        for i, issue in enumerate(issues):
            issue['id'] = i + 1
            issue['affected_pages'] = [self.base_url]
            issue['how_to_fix'] = "Detailed steps to resolve this issue."
            issue['estimated_impact'] = (5 - i) * 10 
            issue['effort_required'] = 'Low' if i < 2 else 'Medium'

        return scores, issues, recommendations

if __name__ == "__main__":
    # Example usage:
    # engine = SEOAuditEngine(website_id=1)
    # asyncio.run(engine.run_comprehensive_audit())
    pass
