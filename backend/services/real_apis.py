# backend/services/real_apis.py - Actual API integrations
import os
from typing import Dict, List
import httpx
import asyncio
from google.oauth2 import service_account
from googleapiclient.discovery import build
import ahrefs
from serpapi import GoogleSearch

class RealSEODataProvider:
    def __init__(self):
        self.pagespeed_api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY")
        self.serpapi_key = os.getenv("SERPAPI_KEY")
        self.ahrefs_token = os.getenv("AHREFS_API_TOKEN")
        self.semrush_api_key = os.getenv("SEMRUSH_API_KEY")
        
    async def get_real_pagespeed_data(self, url: str) -> Dict:
        """Get real PageSpeed Insights data"""
        async with httpx.AsyncClient() as client:
            params = {
                'url': url,
                'key': self.pagespeed_api_key,
                'category': ['performance', 'accessibility', 'best-practices', 'seo'],
                'strategy': 'mobile'
            }
            
            response = await client.get(
                'https://www.googleapis.com/pagespeedonline/v5/runPagespeed',
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract Core Web Vitals
                metrics = data['lighthouseResult']['audits']
                
                return {
                    'lcp': float(metrics.get('largest-contentful-paint', {}).get('numericValue', 0)) / 1000,
                    'fid': float(metrics.get('max-potential-fid', {}).get('numericValue', 0)),
                    'cls': float(metrics.get('cumulative-layout-shift', {}).get('numericValue', 0)),
                    'fcp': float(metrics.get('first-contentful-paint', {}).get('numericValue', 0)) / 1000,
                    'ttfb': float(metrics.get('server-response-time', {}).get('numericValue', 0)),
                    'speed_index': float(metrics.get('speed-index', {}).get('numericValue', 0)) / 1000,
                    'total_blocking_time': float(metrics.get('total-blocking-time', {}).get('numericValue', 0)),
                    'performance_score': data['lighthouseResult']['categories']['performance']['score'] * 100,
                    'seo_score': data['lighthouseResult']['categories']['seo']['score'] * 100,
                    'accessibility_score': data['lighthouseResult']['categories']['accessibility']['score'] * 100,
                    'page_size': sum([int(r.get('transferSize', 0)) for r in data['lighthouseResult']['audits'].get('network-requests', {}).get('details', {}).get('items', [])]),
                    'opportunities': self._extract_opportunities(data)
                }
            
            return {}
    
    def _extract_opportunities(self, data: Dict) -> List[Dict]:
        """Extract optimization opportunities from PageSpeed data"""
        opportunities = []
        audits = data['lighthouseResult']['audits']
        
        opportunity_keys = [
            'render-blocking-resources',
            'unused-css-rules',
            'unused-javascript',
            'modern-image-formats',
            'uses-optimized-images',
            'uses-text-compression',
            'uses-responsive-images',
            'efficient-animated-content'
        ]
        
        for key in opportunity_keys:
            if key in audits and audits[key]['score'] < 0.9:
                opportunities.append({
                    'id': key,
                    'title': audits[key]['title'],
                    'description': audits[key]['description'],
                    'savings': audits[key].get('details', {}).get('overallSavingsMs', 0),
                    'score': audits[key]['score']
                })
        
        return opportunities
    
    async def get_real_serp_rankings(self, keyword: str, domain: str, location: str = "United States") -> Dict:
        """Get real SERP rankings from SerpAPI"""
        search = GoogleSearch({
            "q": keyword,
            "location": location,
            "api_key": self.serpapi_key,
            "num": 100
        })
        
        results = search.get_dict()
        
        # Find domain position
        position = None
        url = None
        
        for i, result in enumerate(results.get('organic_results', []), 1):
            if domain in result.get('link', ''):
                position = i
                url = result['link']
                break
        
        return {
            'keyword': keyword,
            'position': position,
            'url': url,
            'search_volume': results.get('search_information', {}).get('total_results'),
            'featured_snippet': 'answer_box' in results,
            'people_also_ask': 'people_also_ask' in results,
            'knowledge_graph': 'knowledge_graph' in results,
            'related_searches': results.get('related_searches', []),
            'organic_results': results.get('organic_results', [])[:10]
        }
    
    async def get_real_backlinks(self, domain: str) -> Dict:
        """Get real backlink data from Ahrefs"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'https://api.ahrefs.com/v3/site-explorer/backlinks',
                params={
                    'target': domain,
                    'mode': 'domain',
                    'limit': 1000
                },
                headers={'Authorization': f'Bearer {self.ahrefs_token}'}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'total_backlinks': data['stats']['backlinks'],
                    'referring_domains': data['stats']['refdomains'],
                    'domain_rating': data['domain_rating'],
                    'backlinks': data['backlinks'],
                    'new_backlinks_30d': data['stats']['new_backlinks_30d'],
                    'lost_backlinks_30d': data['stats']['lost_backlinks_30d']
                }
            
            return {}
    
    async def get_search_console_data(self, site_url: str, credentials_json: Dict) -> Dict:
        """Get real Search Console data"""
        credentials = service_account.Credentials.from_service_account_info(
            credentials_json,
            scopes=['https://www.googleapis.com/auth/webmasters.readonly']
        )
        
        service = build('searchconsole', 'v1', credentials=credentials)
        
        # Get search analytics
        request = {
            'startDate': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'endDate': datetime.now().strftime('%Y-%m-%d'),
            'dimensions': ['query', 'page'],
            'rowLimit': 25000
        }
        
        response = service.searchanalytics().query(
            siteUrl=site_url,
            body=request
        ).execute()
        
        # Get index coverage
        coverage = service.urlInspection().index().inspect(
            siteUrl=site_url,
            body={'inspectionUrl': site_url}
        ).execute()
        
        return {
            'queries': response.get('rows', []),
            'total_clicks': sum([r['clicks'] for r in response.get('rows', [])]),
            'total_impressions': sum([r['impressions'] for r in response.get('rows', [])]),
            'average_ctr': sum([r['ctr'] for r in response.get('rows', [])]) / len(response.get('rows', [])) if response.get('rows') else 0,
            'average_position': sum([r['position'] for r in response.get('rows', [])]) / len(response.get('rows', [])) if response.get('rows') else 0,
            'index_status': coverage
        }

class CompetitorTracker:
    def __init__(self):
        self.semrush_api = os.getenv("SEMRUSH_API_KEY")
        
    async def get_competitor_keywords(self, domain: str, competitor: str) -> Dict:
        """Get keyword overlap and gaps"""
        async with httpx.AsyncClient() as client:
            # Keyword gap analysis
            response = await client.get(
                'https://api.semrush.com/analytics/v1/',
                params={
                    'type': 'domain_organic',
                    'key': self.semrush_api,
                    'display_limit': 10000,
                    'export_columns': 'Ph,Po,Nq,Cp,Co',
                    'domain': competitor,
                    'database': 'us'
                }
            )
            
            competitor_keywords = set()
            if response.status_code == 200:
                for line in response.text.split('\n')[1:]:  # Skip header
                    if line:
                        parts = line.split(';')
                        competitor_keywords.add(parts[0])  # Keyword
            
            # Get our keywords
            our_response = await client.get(
                'https://api.semrush.com/analytics/v1/',
                params={
                    'type': 'domain_organic',
                    'key': self.semrush_api,
                    'display_limit': 10000,
                    'export_columns': 'Ph,Po,Nq,Cp,Co',
                    'domain': domain,
                    'database': 'us'
                }
            )
            
            our_keywords = set()
            if our_response.status_code == 200:
                for line in our_response.text.split('\n')[1:]:
                    if line:
                        parts = line.split(';')
                        our_keywords.add(parts[0])
            
            return {
                'competitor': competitor,
                'total_keywords': len(competitor_keywords),
                'our_keywords': len(our_keywords),
                'keyword_gap': list(competitor_keywords - our_keywords)[:100],
                'keyword_overlap': list(competitor_keywords & our_keywords)[:100],
                'unique_to_us': list(our_keywords - competitor_keywords)[:100]
            }
