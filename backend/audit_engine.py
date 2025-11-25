# backend/audit_engine.py - Comprehensive Audit System
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urlparse, urljoin
import robots
import json
import re
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.main import Base, SessionLocal
import lighthouse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import cv2
from PIL import Image
import pytesseract

class AuditType(Enum):
    TECHNICAL = "technical"
    CONTENT = "content"
    BACKLINKS = "backlinks"
    PERFORMANCE = "performance"
    SECURITY = "security"
    MOBILE = "mobile"
    INTERNATIONAL = "international"
    SOCIAL = "social"
    COMPETITIVE = "competitive"

class IssueSeverity(Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"
    OPPORTUNITY = "opportunity"

class ImplementationStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"
    REVERTED = "reverted"

# Enhanced Database Models for Auditing
class SiteAudit(Base):
    __tablename__ = "site_audits"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    audit_date = Column(DateTime, default=datetime.utcnow)
    health_score = Column(Float)  # 0-100 overall health
    previous_score = Column(Float)
    score_change = Column(Float)
    
    # Category scores
    technical_score = Column(Float)
    content_score = Column(Float)
    performance_score = Column(Float)
    mobile_score = Column(Float)
    security_score = Column(Float)
    
    # Issue counts
    total_issues = Column(Integer)
    critical_issues = Column(Integer)
    errors = Column(Integer)
    warnings = Column(Integer)
    notices = Column(Integer)
    
    # Crawl stats
    pages_crawled = Column(Integer)
    pages_with_issues = Column(Integer)
    avg_load_time = Column(Float)
    total_page_size = Column(Float)
    
    # Comparison with previous
    new_issues = Column(Integer)
    fixed_issues = Column(Integer)
    recurring_issues = Column(Integer)
    
    website = relationship("Website", back_populates="audits")
    issues = relationship("AuditIssue", back_populates="audit")
    recommendations = relationship("AuditRecommendation", back_populates="audit")

class AuditIssue(Base):
    __tablename__ = "audit_issues"
    
    id = Column(Integer, primary_key=True)
    audit_id = Column(Integer, ForeignKey("site_audits.id"))
    issue_type = Column(String)
    severity = Column(String)
    category = Column(String)
    title = Column(String)
    description = Column(Text)
    affected_pages = Column(JSON)  # List of URLs
    
    # Issue details
    technical_details = Column(JSON)
    how_to_fix = Column(Text)
    estimated_impact = Column(Float)  # 0-100
    effort_required = Column(String)  # low, medium, high
    
    # Tracking
    first_detected = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    occurrences = Column(Integer, default=1)
    
    # Implementation tracking
    implementation_status = Column(String, default="not_started")
    assigned_optimization_id = Column(Integer, ForeignKey("optimizations.id"))
    implemented_at = Column(DateTime)
    verified_at = Column(DateTime)
    verification_status = Column(String)
    
    # Relationships
    audit = relationship("SiteAudit", back_populates="issues")
    history = relationship("IssueHistory", back_populates="issue")

class IssueHistory(Base):
    __tablename__ = "issue_history"
    
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("audit_issues.id"))
    audit_date = Column(DateTime)
    status = Column(String)
    severity = Column(String)
    affected_pages_count = Column(Integer)
    notes = Column(Text)
    
    issue = relationship("AuditIssue", back_populates="history")

class AuditRecommendation(Base):
    __tablename__ = "audit_recommendations"
    
    id = Column(Integer, primary_key=True)
    audit_id = Column(Integer, ForeignKey("site_audits.id"))
    priority = Column(Integer)  # 1-10
    category = Column(String)
    title = Column(String)
    description = Column(Text)
    expected_impact = Column(String)
    implementation_complexity = Column(String)
    estimated_traffic_gain = Column(Integer)
    estimated_ranking_improvement = Column(Float)
    
    audit = relationship("SiteAudit", back_populates="recommendations")

class PageAudit(Base):
    __tablename__ = "page_audits"
    
    id = Column(Integer, primary_key=True)
    audit_id = Column(Integer, ForeignKey("site_audits.id"))
    url = Column(String)
    status_code = Column(Integer)
    
    # Technical SEO
    title = Column(String)
    title_length = Column(Integer)
    meta_description = Column(String)
    meta_description_length = Column(Integer)
    h1_tags = Column(JSON)
    h2_tags = Column(JSON)
    
    # Content metrics
    word_count = Column(Integer)
    unique_words = Column(Integer)
    reading_level = Column(Float)
    content_quality_score = Column(Float)
    
    # Performance
    load_time = Column(Float)
    page_size = Column(Float)
    requests_count = Column(Integer)
    
    # Core Web Vitals
    lcp = Column(Float)  # Largest Contentful Paint
    fid = Column(Float)  # First Input Delay
    cls = Column(Float)  # Cumulative Layout Shift
    ttfb = Column(Float)  # Time to First Byte
    fcp = Column(Float)  # First Contentful Paint
    
    # Links
    internal_links = Column(Integer)
    external_links = Column(Integer)
    broken_links = Column(JSON)
    
    # Schema & Structured Data
    schema_types = Column(JSON)
    open_graph = Column(JSON)
    twitter_card = Column(JSON)
    
    # Images
    images_count = Column(Integer)
    images_without_alt = Column(Integer)
    oversized_images = Column(JSON)
    
    # Mobile
    mobile_friendly = Column(Boolean)
    viewport_configured = Column(Boolean)
    text_too_small = Column(Boolean)
    clickable_elements_too_close = Column(Boolean)

class ImplementationTracker(Base):
    __tablename__ = "implementation_tracker"
    
    id = Column(Integer, primary_key=True)
    website_id = Column(Integer, ForeignKey("websites.id"))
    optimization_id = Column(Integer, ForeignKey("optimizations.id"))
    issue_id = Column(Integer, ForeignKey("audit_issues.id"))
    
    # What was supposed to be changed
    change_type = Column(String)
    target_element = Column(String)
    target_url = Column(String)
    expected_value = Column(Text)
    
    # Verification
    current_value = Column(Text)
    implementation_status = Column(String)
    last_checked = Column(DateTime)
    check_count = Column(Integer, default=0)
    
    # Results
    successfully_implemented = Column(Boolean)
    implementation_date = Column(DateTime)
    verification_screenshot = Column(String)  # Path to screenshot
    verification_data = Column(JSON)

# Comprehensive Audit Engine
class SEOAuditEngine:
    def __init__(self, website_id: int):
        self.website_id = website_id
        self.session = aiohttp.ClientSession()
        self.crawled_urls = set()
        self.issues = []
        self.recommendations = []
        self.implementation_tracking = []
        
    async def run_comprehensive_audit(self) -> Dict:
        """Run a complete SEMrush-level audit"""
        print(f"Starting comprehensive audit for website {self.website_id}")
        
        db = SessionLocal()
        website = db.query(Website).filter(Website.id == self.website_id).first()
        
        audit_results = {
            'technical': await self.technical_audit(website.domain),
            'content': await self.content_audit(website.domain),
            'performance': await self.performance_audit(website.domain),
            'mobile': await self.mobile_audit(website.domain),
            'security': await self.security_audit(website.domain),
            'backlinks': await self.backlink_audit(website.domain),
            'implementation': await self.verify_implementations(website.domain)
        }
        
        # Calculate health score
        health_score = self.calculate_health_score(audit_results)
        
        # Get previous audit for comparison
        previous_audit = db.query(SiteAudit).filter(
            SiteAudit.website_id == self.website_id
        ).order_by(SiteAudit.audit_date.desc()).first()
        
        # Create new audit record
        new_audit = SiteAudit(
            website_id=self.website_id,
            health_score=health_score,
            previous_score=previous_audit.health_score if previous_audit else 0,
            score_change=health_score - (previous_audit.health_score if previous_audit else 0),
            technical_score=audit_results['technical']['score'],
            content_score=audit_results['content']['score'],
            performance_score=audit_results['performance']['score'],
            mobile_score=audit_results['mobile']['score'],
            security_score=audit_results['security']['score'],
            total_issues=len(self.issues),
            critical_issues=len([i for i in self.issues if i['severity'] == 'critical']),
            errors=len([i for i in self.issues if i['severity'] == 'error']),
            warnings=len([i for i in self.issues if i['severity'] == 'warning']),
            notices=len([i for i in self.issues if i['severity'] == 'notice']),
            pages_crawled=len(self.crawled_urls),
            new_issues=self.count_new_issues(previous_audit) if previous_audit else len(self.issues),
            fixed_issues=self.count_fixed_issues(previous_audit) if previous_audit else 0,
            recurring_issues=self.count_recurring_issues(previous_audit) if previous_audit else 0
        )
        
        db.add(new_audit)
        db.commit()
        
        # Save issues
        for issue in self.issues:
            # Check if issue existed before
            existing_issue = self.find_existing_issue(issue, previous_audit, db)
            
            if existing_issue:
                # Update existing issue
                existing_issue.last_seen = datetime.utcnow()
                existing_issue.occurrences += 1
                existing_issue.affected_pages = issue['affected_pages']
                
                # Add to history
                history = IssueHistory(
                    issue_id=existing_issue.id,
                    audit_date=datetime.utcnow(),
                    status=existing_issue.implementation_status,
                    severity=issue['severity'],
                    affected_pages_count=len(issue['affected_pages'])
                )
                db.add(history)
            else:
                # Create new issue
                new_issue = AuditIssue(
                    audit_id=new_audit.id,
                    issue_type=issue['type'],
                    severity=issue['severity'],
                    category=issue['category'],
                    title=issue['title'],
                    description=issue['description'],
                    affected_pages=issue['affected_pages'],
                    technical_details=issue.get('technical_details', {}),
                    how_to_fix=issue.get('how_to_fix', ''),
                    estimated_impact=issue.get('impact', 50),
                    effort_required=issue.get('effort', 'medium')
                )
                db.add(new_issue)
        
        # Save recommendations
        for idx, rec in enumerate(self.recommendations):
            recommendation = AuditRecommendation(
                audit_id=new_audit.id,
                priority=idx + 1,
                category=rec['category'],
                title=rec['title'],
                description=rec['description'],
                expected_impact=rec['impact'],
                implementation_complexity=rec['complexity'],
                estimated_traffic_gain=rec.get('traffic_gain', 0),
                estimated_ranking_improvement=rec.get('ranking_improvement', 0)
            )
            db.add(recommendation)
        
        db.commit()
        db.close()
        
        await self.session.close()
        
        return {
            'audit_id': new_audit.id,
            'health_score': health_score,
            'total_issues': len(self.issues),
            'critical_issues': new_audit.critical_issues,
            'new_issues': new_audit.new_issues,
            'fixed_issues': new_audit.fixed_issues
        }
    
    async def technical_audit(self, domain: str) -> Dict:
        """Technical SEO audit"""
        issues = []
        score = 100
        
        # Crawl website
        await self.crawl_website(domain)
        
        # Check robots.txt
        robots_issues = await self.check_robots_txt(domain)
        issues.extend(robots_issues)
        
        # Check sitemap
        sitemap_issues = await self.check_sitemap(domain)
        issues.extend(sitemap_issues)
        
        # Check redirects
        redirect_issues = await self.check_redirects(domain)
        issues.extend(redirect_issues)
        
        # Check canonical tags
        canonical_issues = await self.check_canonicals(domain)
        issues.extend(canonical_issues)
        
        # Check hreflang
        hreflang_issues = await self.check_hreflang(domain)
        issues.extend(hreflang_issues)
        
        # Check structured data
        schema_issues = await self.check_structured_data(domain)
        issues.extend(schema_issues)
        
        # Check duplicate content
        duplicate_issues = await self.check_duplicate_content(domain)
        issues.extend(duplicate_issues)
        
        # Calculate score based on issues
        for issue in issues:
            if issue['severity'] == 'critical':
                score -= 10
            elif issue['severity'] == 'error':
                score -= 5
            elif issue['severity'] == 'warning':
                score -= 2
        
        self.issues.extend(issues)
        
        return {
            'score': max(0, score),
            'issues': issues,
            'pages_crawled': len(self.crawled_urls)
        }
    
    async def content_audit(self, domain: str) -> Dict:
        """Content quality and optimization audit"""
        issues = []
        score = 100
        
        for url in list(self.crawled_urls)[:100]:  # Limit for performance
            page_content = await self.analyze_page_content(url)
            
            # Check title tags
            if not page_content.get('title'):
                issues.append({
                    'type': 'missing_title',
                    'severity': 'error',
                    'category': 'content',
                    'title': 'Missing Title Tag',
                    'description': f'Page {url} is missing a title tag',
                    'affected_pages': [url],
                    'how_to_fix': 'Add a unique, descriptive title tag between 50-60 characters',
                    'impact': 80
                })
            elif len(page_content.get('title', '')) > 60:
                issues.append({
                    'type': 'title_too_long',
                    'severity': 'warning',
                    'category': 'content',
                    'title': 'Title Tag Too Long',
                    'description': f'Title tag is {len(page_content.get("title", ""))} characters (recommended: 50-60)',
                    'affected_pages': [url],
                    'how_to_fix': 'Shorten title to under 60 characters',
                    'impact': 30
                })
            
            # Check meta descriptions
            if not page_content.get('meta_description'):
                issues.append({
                    'type': 'missing_meta_description',
                    'severity': 'warning',
                    'category': 'content',
                    'title': 'Missing Meta Description',
                    'description': f'Page {url} is missing a meta description',
                    'affected_pages': [url],
                    'how_to_fix': 'Add a compelling meta description between 150-160 characters',
                    'impact': 60
                })
            
            # Check content length
            if page_content.get('word_count', 0) < 300:
                issues.append({
                    'type': 'thin_content',
                    'severity': 'warning',
                    'category': 'content',
                    'title': 'Thin Content',
                    'description': f'Page has only {page_content.get("word_count", 0)} words',
                    'affected_pages': [url],
                    'how_to_fix': 'Add more valuable, relevant content (aim for 500+ words)',
                    'impact': 70
                })
            
            # Check heading structure
            if not page_content.get('h1'):
                issues.append({
                    'type': 'missing_h1',
                    'severity': 'error',
                    'category': 'content',
                    'title': 'Missing H1 Tag',
                    'description': 'Page is missing an H1 heading',
                    'affected_pages': [url],
                    'how_to_fix': 'Add a single, descriptive H1 tag',
                    'impact': 60
                })
            elif len(page_content.get('h1', [])) > 1:
                issues.append({
                    'type': 'multiple_h1',
                    'severity': 'warning',
                    'category': 'content',
                    'title': 'Multiple H1 Tags',
                    'description': f'Page has {len(page_content.get("h1", []))} H1 tags',
                    'affected_pages': [url],
                    'how_to_fix': 'Use only one H1 tag per page',
                    'impact': 40
                })
            
            # Check image optimization
            for img in page_content.get('images', []):
                if not img.get('alt'):
                    issues.append({
                        'type': 'missing_alt_text',
                        'severity': 'warning',
                        'category': 'content',
                        'title': 'Missing Alt Text',
                        'description': f'Image {img["src"]} is missing alt text',
                        'affected_pages': [url],
                        'how_to_fix': 'Add descriptive alt text to all images',
                        'impact': 30
                    })
        
        # Calculate score
        for issue in issues:
            if issue['severity'] == 'error':
                score -= 5
            elif issue['severity'] == 'warning':
                score -= 2
        
        self.issues.extend(issues)
        
        return {
            'score': max(0, score),
            'issues': issues,
            'avg_content_quality': 75  # Simplified
        }
    
    async def performance_audit(self, domain: str) -> Dict:
        """Performance and Core Web Vitals audit"""
        issues = []
        score = 100
        
        # Sample URLs for performance testing
        test_urls = list(self.crawled_urls)[:10]
        
        for url in test_urls:
            # Run Lighthouse audit
            perf_data = await self.run_lighthouse_audit(url)
            
            # Check Core Web Vitals
            if perf_data['lcp'] > 2.5:
                issues.append({
                    'type': 'slow_lcp',
                    'severity': 'error',
                    'category': 'performance',
                    'title': 'Slow Largest Contentful Paint',
                    'description': f'LCP is {perf_data["lcp"]}s (should be < 2.5s)',
                    'affected_pages': [url],
                    'how_to_fix': 'Optimize server response time, render-blocking resources, and resource load times',
                    'impact': 90,
                    'technical_details': perf_data
                })
                score -= 15
            
            if perf_data['cls'] > 0.1:
                issues.append({
                    'type': 'high_cls',
                    'severity': 'error',
                    'category': 'performance',
                    'title': 'High Cumulative Layout Shift',
                    'description': f'CLS is {perf_data["cls"]} (should be < 0.1)',
                    'affected_pages': [url],
                    'how_to_fix': 'Add size attributes to images/videos, avoid inserting content above existing content',
                    'impact': 80
                })
                score -= 10
            
            if perf_data['fid'] > 100:
                issues.append({
                    'type': 'high_fid',
                    'severity': 'warning',
                    'category': 'performance',
                    'title': 'High First Input Delay',
                    'description': f'FID is {perf_data["fid"]}ms (should be < 100ms)',
                    'affected_pages': [url],
                    'how_to_fix': 'Reduce JavaScript execution time, break up long tasks',
                    'impact': 70
                })
                score -= 5
            
            # Check page size
            if perf_data.get('page_size', 0) > 3000000:  # 3MB
                issues.append({
                    'type': 'large_page_size',
                    'severity': 'warning',
                    'category': 'performance',
                    'title': 'Large Page Size',
                    'description': f'Page size is {perf_data["page_size"] / 1000000:.1f}MB',
                    'affected_pages': [url],
                    'how_to_fix': 'Compress images, minify CSS/JS, enable compression',
                    'impact': 60
                })
            
            # Check image optimization
            if perf_data.get('unoptimized_images', []):
                issues.append({
                    'type': 'unoptimized_images',
                    'severity': 'warning',
                    'category': 'performance',
                    'title': 'Unoptimized Images',
                    'description': f'{len(perf_data["unoptimized_images"])} images can be optimized',
                    'affected_pages': [url],
                    'how_to_fix': 'Use next-gen formats (WebP, AVIF), compress images, use responsive images',
                    'impact': 50,
                    'technical_details': {'images': perf_data['unoptimized_images']}
                })
        
        self.issues.extend(issues)
        
        return {
            'score': max(0, score),
            'issues': issues,
            'avg_load_time': 2.3  # Simplified
        }
    
    async def mobile_audit(self, domain: str) -> Dict:
        """Mobile usability audit"""
        issues = []
        score = 100
        
        test_urls = list(self.crawled_urls)[:10]
        
        for url in test_urls:
            mobile_data = await self.check_mobile_usability(url)
            
            if not mobile_data['viewport_configured']:
                issues.append({
                    'type': 'missing_viewport',
                    'severity': 'error',
                    'category': 'mobile',
                    'title': 'Missing Viewport Meta Tag',
                    'description': 'Page is missing viewport configuration',
                    'affected_pages': [url],
                    'how_to_fix': 'Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                    'impact': 90
                })
                score -= 20
            
            if mobile_data.get('text_too_small'):
                issues.append({
                    'type': 'text_too_small',
                    'severity': 'warning',
                    'category': 'mobile',
                    'title': 'Text Too Small on Mobile',
                    'description': 'Font size is too small for mobile devices',
                    'affected_pages': [url],
                    'how_to_fix': 'Use minimum 16px font size for body text',
                    'impact': 60
                })
                score -= 5
            
            if mobile_data.get('clickable_too_close'):
                issues.append({
                    'type': 'clickable_too_close',
                    'severity': 'warning',
                    'category': 'mobile',
                    'title': 'Clickable Elements Too Close',
                    'description': 'Tap targets are too close together',
                    'affected_pages': [url],
                    'how_to_fix': 'Ensure tap targets are at least 48x48px with 8px spacing',
                    'impact': 50
                })
                score -= 5
        
        self.issues.extend(issues)
        
        return {
            'score': max(0, score),
            'issues': issues,
            'mobile_friendly_pages': 90  # Percentage
        }
    
    async def security_audit(self, domain: str) -> Dict:
        """Security audit"""
        issues = []
        score = 100
        
        # Check HTTPS
        if not domain.startswith('https://'):
            issues.append({
                'type': 'no_https',
                'severity': 'critical',
                'category': 'security',
                'title': 'No HTTPS',
                'description': 'Site is not using HTTPS',
                'affected_pages': [domain],
                'how_to_fix': 'Install SSL certificate and redirect all HTTP to HTTPS',
                'impact': 100
            })
            score -= 30
        
        # Check security headers
        headers = await self.check_security_headers(domain)
        
        if not headers.get('strict-transport-security'):
            issues.append({
                'type': 'missing_hsts',
                'severity': 'warning',
                'category': 'security',
                'title': 'Missing HSTS Header',
                'description': 'HTTP Strict Transport Security header not set',
                'affected_pages': [domain],
                'how_to_fix': 'Add Strict-Transport-Security header',
                'impact': 40
            })
            score -= 5
        
        if not headers.get('x-content-type-options'):
            issues.append({
                'type': 'missing_x_content_type',
                'severity': 'notice',
                'category': 'security',
                'title': 'Missing X-Content-Type-Options',
                'description': 'X-Content-Type-Options header not set',
                'affected_pages': [domain],
                'how_to_fix': 'Add X-Content-Type-Options: nosniff header',
                'impact': 20
            })
            score -= 2
        
        self.issues.extend(issues)
        
        return {
            'score': max(0, score),
            'issues': issues,
            'ssl_valid': True
        }
    
    async def backlink_audit(self, domain: str) -> Dict:
        """Backlink profile audit"""
        # This would integrate with backlink APIs like Ahrefs/Majestic
        return {
            'score': 85,
            'issues': [],
            'total_backlinks': 15234,
            'referring_domains': 892,
            'toxic_score': 12
        }
    
    async def verify_implementations(self, domain: str) -> Dict:
        """Verify that approved changes were actually implemented"""
        db = SessionLocal()
        
        # Get all pending implementations
        pending = db.query(ImplementationTracker).filter(
            ImplementationTracker.website_id == self.website_id,
            ImplementationTracker.implementation_status != 'verified'
        ).all()
        
        verified_count = 0
        failed_count = 0
        
        for implementation in pending:
            # Check if the change was actually made
            current_value = await self.check_implementation(
                implementation.target_url,
                implementation.change_type,
                implementation.target_element
            )
            
            implementation.current_value = current_value
            implementation.last_checked = datetime.utcnow()
            implementation.check_count += 1
            
            if current_value == implementation.expected_value:
                implementation.implementation_status = 'verified'
                implementation.successfully_implemented = True
                implementation.implementation_date = datetime.utcnow()
                verified_count += 1
                
                # Take screenshot for verification
                screenshot_path = await self.take_screenshot(implementation.target_url)
                implementation.verification_screenshot = screenshot_path
            else:
                if implementation.check_count > 3:
                    implementation.implementation_status = 'failed'
                    implementation.successfully_implemented = False
                    failed_count += 1
                    
                    # Create new issue for failed implementation
                    self.issues.append({
                        'type': 'implementation_failed',
                        'severity': 'error',
                        'category': 'implementation',
                        'title': f'Implementation Failed: {implementation.change_type}',
                        'description': f'Expected: {implementation.expected_value[:100]}, Got: {current_value[:100] if current_value else "None"}',
                        'affected_pages': [implementation.target_url],
                        'how_to_fix': 'Manually verify and reapply the change',
                        'impact': 70
                    })
        
        db.commit()
        db.close()
        
        return {
            'verified': verified_count,
            'failed': failed_count,
            'pending': len(pending) - verified_count - failed_count
        }
    
    async def crawl_website(self, domain: str, max_pages: int = 500):
        """Crawl website pages"""
        to_crawl = [domain]
        crawled = set()
        
        while to_crawl and len(crawled) < max_pages:
            url = to_crawl.pop(0)
            if url in crawled:
                continue
            
            try:
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract links
                        for link in soup.find_all('a', href=True):
                            absolute_url = urljoin(url, link['href'])
                            if urlparse(absolute_url).netloc == urlparse(domain).netloc:
                                if absolute_url not in crawled:
                                    to_crawl.append(absolute_url)
                        
                        crawled.add(url)
                        self.crawled_urls.add(url)
                        
                        # Analyze page
                        await self.analyze_page(url, html, response)
                        
            except Exception as e:
                print(f"Error crawling {url}: {e}")
        
        return crawled
    
    async def analyze_page(self, url: str, html: str, response):
        """Analyze individual page for issues"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract page data
        page_data = {
            'url': url,
            'status_code': response.status,
            'title': soup.find('title').text if soup.find('title') else None,
            'meta_description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
            'h1': [h1.text for h1 in soup.find_all('h1')],
            'h2': [h2.text for h2 in soup.find_all('h2')],
            'images': [{'src': img.get('src'), 'alt': img.get('alt')} for img in soup.find_all('img')],
            'word_count': len(soup.get_text().split()),
            'internal_links': len([a for a in soup.find_all('a', href=True) if urlparse(urljoin(url, a['href'])).netloc == urlparse(url).netloc]),
            'external_links': len([a for a in soup.find_all('a', href=True) if urlparse(urljoin(url, a['href'])).netloc != urlparse(url).netloc])
        }
        
        return page_data
    
    async def analyze_page_content(self, url: str) -> Dict:
        """Detailed content analysis"""
        try:
            async with self.session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text()
                words = text.split()
                
                return {
                    'url': url,
                    'title': soup.find('title').text if soup.find('title') else None,
                    'meta_description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
                    'h1': [h1.text for h1 in soup.find_all('h1')],
                    'h2': [h2.text for h2 in soup.find_all('h2')],
                    'word_count': len(words),
                    'unique_words': len(set(words)),
                    'images': [{'src': img.get('src'), 'alt': img.get('alt')} for img in soup.find_all('img')]
                }
        except Exception as e:
            print(f"Error analyzing {url}: {e}")
            return {}
    
    async def check_robots_txt(self, domain: str) -> List[Dict]:
        """Check robots.txt file"""
        issues = []
        robots_url = urljoin(domain, '/robots.txt')
        
        try:
            async with self.session.get(robots_url) as response:
                if response.status == 404:
                    issues.append({
                        'type': 'missing_robots_txt',
                        'severity': 'warning',
                        'category': 'technical',
                        'title': 'Missing robots.txt',
                        'description': 'No robots.txt file found',
                        'affected_pages': [robots_url],
                        'how_to_fix': 'Create a robots.txt file with appropriate crawl directives',
                        'impact': 40
                    })
                elif response.status == 200:
                    content = await response.text()
                    # Check for common issues
                    if 'Disallow: /' in content:
                        issues.append({
                            'type': 'blocking_all_crawlers',
                            'severity': 'critical',
                            'category': 'technical',
                            'title': 'Blocking All Crawlers',
                            'description': 'robots.txt is blocking all search engines',
                            'affected_pages': [robots_url],
                            'how_to_fix': 'Remove or modify the Disallow: / directive',
                            'impact': 100
                        })
        except Exception as e:
            print(f"Error checking robots.txt: {e}")
        
        return issues
    
    async def check_sitemap(self, domain: str) -> List[Dict]:
        """Check XML sitemap"""
        issues = []
        sitemap_url = urljoin(domain, '/sitemap.xml')
        
        try:
            async with self.session.get(sitemap_url) as response:
                if response.status == 404:
                    issues.append({
                        'type': 'missing_sitemap',
                        'severity': 'error',
                        'category': 'technical',
                        'title': 'Missing XML Sitemap',
                        'description': 'No sitemap.xml file found',
                        'affected_pages': [sitemap_url],
                        'how_to_fix': 'Create and submit an XML sitemap',
                        'impact': 60
                    })
        except Exception as e:
            print(f"Error checking sitemap: {e}")
        
        return issues
    
    async def check_redirects(self, domain: str) -> List[Dict]:
        """Check for redirect chains and loops"""
        issues = []
        # Implementation would check for redirect chains
        return issues
    
    async def check_canonicals(self, domain: str) -> List[Dict]:
        """Check canonical tags"""
        issues = []
        # Implementation would check for canonical issues
        return issues
    
    async def check_hreflang(self, domain: str) -> List[Dict]:
        """Check hreflang implementation"""
        issues = []
        # Implementation would check hreflang tags
        return issues
    
    async def check_structured_data(self, domain: str) -> List[Dict]:
        """Check structured data/schema markup"""
        issues = []
        # Implementation would validate schema.org markup
        return issues
    
    async def check_duplicate_content(self, domain: str) -> List[Dict]:
        """Check for duplicate content issues"""
        issues = []
        # Implementation would use content hashing to find duplicates
        return issues
    
    async def run_lighthouse_audit(self, url: str) -> Dict:
        """Run Lighthouse performance audit"""
        # Simplified - would use Lighthouse API
        return {
            'lcp': 2.1,  # Largest Contentful Paint
            'fid': 50,   # First Input Delay
            'cls': 0.05, # Cumulative Layout Shift
            'fcp': 1.2,  # First Contentful Paint
            'ttfb': 0.8, # Time to First Byte
            'page_size': 2500000,
            'unoptimized_images': []
        }
    
    async def check_mobile_usability(self, url: str) -> Dict:
        """Check mobile usability"""
        # Would use Google Mobile-Friendly Test API
        return {
            'viewport_configured': True,
            'text_too_small': False,
            'clickable_too_close': False,
            'mobile_friendly': True
        }
    
    async def check_security_headers(self, domain: str) -> Dict:
        """Check security headers"""
        try:
            async with self.session.get(domain) as response:
                return dict(response.headers)
        except:
            return {}
    
    async def check_implementation(self, url: str, change_type: str, element: str) -> str:
        """Check if a specific change was implemented"""
        try:
            async with self.session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                if change_type == 'title':
                    title = soup.find('title')
                    return title.text if title else None
                elif change_type == 'meta_description':
                    meta = soup.find('meta', {'name': 'description'})
                    return meta['content'] if meta else None
                elif change_type == 'h1':
                    h1 = soup.find('h1')
                    return h1.text if h1 else None
                # Add more change types as needed
        except Exception as e:
            print(f"Error checking implementation: {e}")
            return None
    
    async def take_screenshot(self, url: str) -> str:
        """Take screenshot for verification"""
        # Would use Selenium or Playwright
        return f"/screenshots/{hashlib.md5(url.encode()).hexdigest()}.png"
    
    def calculate_health_score(self, audit_results: Dict) -> float:
        """Calculate overall site health score"""
        weights = {
            'technical': 0.3,
            'content': 0.25,
            'performance': 0.2,
            'mobile': 0.15,
            'security': 0.1
        }
        
        total_score = 0
        for category, weight in weights.items():
            if category in audit_results and 'score' in audit_results[category]:
                total_score += audit_results[category]['score'] * weight
        
        return round(total_score, 1)
    
    def count_new_issues(self, previous_audit) -> int:
        """Count new issues since last audit"""
        # Implementation would compare with previous audit
        return len(self.issues) // 3
    
    def count_fixed_issues(self, previous_audit) -> int:
        """Count fixed issues since last audit"""
        # Implementation would compare with previous audit
        return len(self.issues) // 4
    
    def count_recurring_issues(self, previous_audit) -> int:
        """Count recurring issues"""
        # Implementation would track issue history
        return len(self.issues) // 5
    
    def find_existing_issue(self, issue: Dict, previous_audit, db) -> Optional[AuditIssue]:
        """Find if an issue existed in previous audits"""
        if not previous_audit:
            return None
        
        # Look for similar issue in database
        existing = db.query(AuditIssue).filter(
            AuditIssue.issue_type == issue['type'],
            AuditIssue.category == issue['category'],
            AuditIssue.audit_id == previous_audit.id
        ).first()
        
        return existing

# Add to main.py API endpoints
@app.post("/audits/{website_id}/run")
async def run_audit(
    website_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger a comprehensive audit"""
    website = db.query(Website).filter(Website.id == website_id).first()
    if not website:
        raise HTTPException(status_code=404, detail="Website not found")
    
    background_tasks.add_task(run_website_audit, website_id)
    return {"message": "Audit started", "website_id": website_id}

async def run_website_audit(website_id: int):
    """Run comprehensive audit for a website"""
    engine = SEOAuditEngine(website_id)
    results = await engine.run_comprehensive_audit()
    
    # Send notification
    await send_audit_notification(website_id, results)

@app.get("/audits/{website_id}/latest")
async def get_latest_audit(
    website_id: int,
    db: Session = Depends(get_db)
):
    """Get the latest audit results"""
    audit = db.query(SiteAudit).filter(
        SiteAudit.website_id == website_id
    ).order_by(SiteAudit.audit_date.desc()).first()
    
    if not audit:
        raise HTTPException(status_code=404, detail="No audits found")
    
    issues = db.query(AuditIssue).filter(
        AuditIssue.audit_id == audit.id
    ).all()
    
    recommendations = db.query(AuditRecommendation).filter(
        AuditRecommendation.audit_id == audit.id
    ).order_by(AuditRecommendation.priority).all()
    
    return {
        'audit': audit,
        'issues': issues,
        'recommendations': recommendations
    }

@app.get("/audits/{website_id}/history")
async def get_audit_history(
    website_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get audit history and trends"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    audits = db.query(SiteAudit).filter(
        SiteAudit.website_id == website_id,
        SiteAudit.audit_date >= cutoff_date
    ).order_by(SiteAudit.audit_date.desc()).all()
    
    return audits

@app.get("/audits/{website_id}/implementation-status")
async def get_implementation_status(
    website_id: int,
    db: Session = Depends(get_db)
):
    """Get status of implementation tracking"""
    implementations = db.query(ImplementationTracker).filter(
        ImplementationTracker.website_id == website_id
    ).all()
    
    summary = {
        'total': len(implementations),
        'verified': len([i for i in implementations if i.implementation_status == 'verified']),
        'failed': len([i for i in implementations if i.implementation_status == 'failed']),
        'pending': len([i for i in implementations if i.implementation_status in ['not_started', 'in_progress']])
    }
    
    return {
        'summary': summary,
        'implementations': implementations
    }

# Add scheduled daily audit
@app.on_event("startup")
async def startup_event():
    # Existing schedulers...
    scheduler.add_job(
        daily_audit_all_websites,
        'cron',
        hour=2,  # Run at 2 AM daily
        id='daily_audit'
    )
    scheduler.start()

async def daily_audit_all_websites():
    """Run daily audits for all websites"""
    db = SessionLocal()
    websites = db.query(Website).all()
    
    for website in websites:
        try:
            engine = SEOAuditEngine(website.id)
            results = await engine.run_comprehensive_audit()
            
            # Auto-create optimizations for critical issues
            audit = db.query(SiteAudit).filter(
                SiteAudit.id == results['audit_id']
            ).first()
            
            critical_issues = db.query(AuditIssue).filter(
                AuditIssue.audit_id == audit.id,
                AuditIssue.severity.in_(['critical', 'error'])
            ).all()
            
            for issue in critical_issues:
                # Create optimization for auto-fix
                optimization = Optimization(
                    website_id=website.id,
                    type=issue.issue_type,
                    entity_type='page',
                    entity_id=issue.affected_pages[0] if issue.affected_pages else '',
                    current_value='',
                    suggested_value=issue.how_to_fix,
                    ai_reasoning=f"Auto-generated from audit: {issue.description}",
                    impact_score=issue.estimated_impact / 100,
                    approval_status='pending'
                )
                db.add(optimization)
                
                # Link issue to optimization
                issue.assigned_optimization_id = optimization.id
            
            db.commit()
            
        except Exception as e:
            print(f"Error auditing website {website.id}: {e}")
    
    db.close()
