# backend/services/ai_service.py
import os
from typing import List, Dict, Any
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.cluster import KMeans
import httpx
from transformers import pipeline
import asyncio

class SEOAIService:
    def __init__(self):
        # 1. Content Generation - Gemini for cost-effectiveness
        genai.configure(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))
        self.writer_model = genai.GenerativeModel('gemini-1.5-pro')
        
        # 2. Keyword Clustering - Embeddings
        self.embedder = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # 3. Intent Classification - BERT
        self.intent_classifier = pipeline(
            "text-classification",
            model="distilbert-base-uncased",
            device=-1  # CPU, use 0 for GPU
        )
        
        # 4. Search API for RAG
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        
    async def generate_content(self, prompt: str, seo_params: Dict) -> str:
        """
        Use Gemini for content generation - best cost/quality ratio
        """
        seo_prompt = f"""
        As an SEO content expert, create content with these requirements:
        - Target Keywords: {seo_params.get('keywords', [])}
        - Search Intent: {seo_params.get('intent', 'informational')}
        - Content Type: {seo_params.get('type', 'article')}
        - Word Count: {seo_params.get('word_count', 800)}
        
        User Request: {prompt}
        
        Create SEO-optimized content that naturally incorporates the keywords.
        """
        
        response = self.writer_model.generate_content(seo_prompt)
        return response.text
    
    async def cluster_keywords(self, keywords: List[str], num_clusters: int = None) -> Dict:
        """
        Use embeddings for fast, cheap keyword clustering
        """
        # Generate embeddings
        embeddings = self.embedder.encode(keywords)
        
        # Auto-determine optimal clusters if not specified
        if num_clusters is None:
            num_clusters = min(len(keywords) // 5, 20)  # Rule of thumb
        
        # Cluster keywords
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        clusters = kmeans.fit_predict(embeddings)
        
        # Group keywords by cluster
        clustered_keywords = {}
        for keyword, cluster_id in zip(keywords, clusters):
            if cluster_id not in clustered_keywords:
                clustered_keywords[cluster_id] = []
            clustered_keywords[cluster_id].append(keyword)
        
        # Find representative keyword for each cluster (closest to centroid)
        cluster_representatives = {}
        for cluster_id, cluster_keywords in clustered_keywords.items():
            cluster_embeddings = embeddings[[i for i, c in enumerate(clusters) if c == cluster_id]]
            centroid = kmeans.cluster_centers_[cluster_id]
            distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
            representative_idx = np.argmin(distances)
            cluster_representatives[cluster_id] = cluster_keywords[representative_idx]
        
        return {
            'clusters': clustered_keywords,
            'representatives': cluster_representatives,
            'num_clusters': num_clusters
        }
    
    def classify_intent(self, queries: List[str]) -> List[Dict]:
        """
        Fast intent classification using BERT
        """
        intent_map = {
            'LABEL_0': 'informational',
            'LABEL_1': 'navigational',
            'LABEL_2': 'transactional',
            'LABEL_3': 'commercial'
        }
        
        results = []
        for query in queries:
            # You'd fine-tune this model on SEO intent data
            prediction = self.intent_classifier(query)[0]
            results.append({
                'query': query,
                'intent': intent_map.get(prediction['label'], 'informational'),
                'confidence': prediction['score']
            })
        
        return results
    
    async def analyze_ai_search_optimization(self, url: str, target_query: str) -> Dict:
        """
        RAG-based GEO (Generative Engine Optimization) analysis
        """
        # Step 1: Get top search results
        search_results = await self.fetch_serp_data(target_query)
        
        # Step 2: Simulate AI answer generation
        ai_answer = await self.simulate_ai_answer(target_query, search_results)
        
        # Step 3: Analyze if URL is cited
        is_cited = url in ai_answer['sources']
        
        # Step 4: Generate optimization recommendations
        recommendations = await self.generate_geo_recommendations(
            url, 
            target_query, 
            search_results, 
            ai_answer
        )
        
        return {
            'query': target_query,
            'ai_answer': ai_answer['content'],
            'is_cited': is_cited,
            'citation_position': ai_answer['sources'].index(url) if is_cited else None,
            'recommendations': recommendations
        }
    
    async def fetch_serp_data(self, query: str) -> List[Dict]:
        """
        Fetch live search results for RAG
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                'https://api.serper.dev/search',
                params={'q': query},
                headers={'X-API-KEY': self.serper_api_key}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('organic', [])[:10]
            return []
    
    async def simulate_ai_answer(self, query: str, search_results: List[Dict]) -> Dict:
        """
        Simulate how AI search engines would answer
        """
        # Format search results for context
        context = "\n\n".join([
            f"Source {i+1} ({result['link']}): {result.get('snippet', '')}"
            for i, result in enumerate(search_results)
        ])
        
        prompt = f"""
        Based ONLY on these search results, answer the query: "{query}"
        
        Search Results:
        {context}
        
        Provide a comprehensive answer and list which sources you used.
        Format: 
        ANSWER: [your answer]
        SOURCES: [list of URLs you referenced]
        """
        
        response = self.writer_model.generate_content(prompt)
        
        # Parse response
        text = response.text
        answer_part = text.split('SOURCES:')[0].replace('ANSWER:', '').strip()
        sources_part = text.split('SOURCES:')[1].strip() if 'SOURCES:' in text else ""
        
        return {
            'content': answer_part,
            'sources': [s.strip() for s in sources_part.split('\n') if s.strip()]
        }
    
    async def generate_geo_recommendations(
        self, 
        url: str, 
        query: str, 
        search_results: List[Dict],
        ai_answer: Dict
    ) -> List[str]:
        """
        Generate specific recommendations for AI search optimization
        """
        recommendations = []
        
        # Check if cited
        if url not in ai_answer['sources']:
            recommendations.append(
                "Your page is not being cited by AI. Add more unique data, statistics, or expert quotes."
            )
        
        # Analyze top cited sources
        cited_urls = ai_answer['sources'][:3]
        for cited_url in cited_urls:
            if cited_url != url:
                recommendations.append(
                    f"Analyze {cited_url} - it's being prioritized by AI for this query"
                )
        
        # Content structure recommendations
        prompt = f"""
        Based on this AI answer for "{query}", what content elements are being prioritized?
        AI Answer: {ai_answer['content'][:500]}
        
        List 3 specific content improvements for better AI visibility:
        """
        
        response = self.writer_model.generate_content(prompt)
        recommendations.extend(response.text.split('\n')[:3])
        
        return recommendations

# Integration into main.py
ai_service = SEOAIService()

@app.post("/api/keywords/cluster")
async def cluster_keywords_endpoint(
    keywords: List[str],
    num_clusters: Optional[int] = None
):
    """
    Cluster keywords for content planning
    """
    result = await ai_service.cluster_keywords(keywords, num_clusters)
    return result

@app.post("/api/keywords/intent")
async def classify_intent_endpoint(
    queries: List[str]
):
    """
    Classify search intent for keywords
    """
    result = ai_service.classify_intent(queries)
    return result

@app.post("/api/content/generate")
async def generate_content_endpoint(
    prompt: str,
    keywords: List[str],
    intent: str = "informational",
    word_count: int = 800
):
    """
    Generate SEO-optimized content
    """
    seo_params = {
        'keywords': keywords,
        'intent': intent,
        'word_count': word_count
    }
    content = await ai_service.generate_content(prompt, seo_params)
    return {"content": content}

@app.post("/api/geo/analyze")
async def analyze_geo_endpoint(
    url: str,
    target_query: str
):
    """
    Analyze AI search optimization opportunities
    """
    result = await ai_service.analyze_ai_search_optimization(url, target_query)
    return result
