# backend/keyword_research.py - AI-powered keyword research
import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN", "")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD", "")


class KeywordResearcher:
    """AI-powered keyword research with optional DataForSEO enrichment."""

    def __init__(self):
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    async def research_keywords(
        self,
        seed_keyword: str,
        domain: str = "",
        country: str = "GB",
        niche: str = "",
        current_keywords: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate keyword research from a seed keyword.
        Returns suggested keywords with estimated metrics.
        """
        suggestions = await self._ai_keyword_expansion(seed_keyword, domain, country, niche, current_keywords)

        # If DataForSEO is configured, enrich with real search volumes
        if DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD and suggestions:
            enriched = await self._dataforseo_enrich(suggestions, country)
            if enriched:
                suggestions = enriched

        # Score and categorize
        for kw in suggestions:
            kw["opportunity_score"] = self._calculate_opportunity_score(kw)
            kw["difficulty_label"] = self._difficulty_label(kw.get("difficulty", 50))

        # Sort by opportunity score
        suggestions.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)

        return {
            "seed_keyword": seed_keyword,
            "country": country,
            "total_suggestions": len(suggestions),
            "keywords": suggestions,
        }

    async def _ai_keyword_expansion(
        self, seed: str, domain: str, country: str, niche: str, current_keywords: List[str] = None
    ) -> List[Dict]:
        """Use Gemini to generate keyword ideas with estimated metrics."""
        current_kw_text = ""
        if current_keywords:
            current_kw_text = "\n\nKeywords this site already ranks for (DO NOT repeat these):\n" + ", ".join(current_keywords[:50])

        prompt = f"""You are an SEO keyword research expert. Generate 30 keyword suggestions based on this seed keyword.

Seed keyword: "{seed}"
Website domain: {domain or 'not specified'}
Target country: {country}
Niche/industry: {niche or 'not specified'}
{current_kw_text}

For each keyword, provide:
- keyword: the search term
- search_volume: estimated monthly search volume (be realistic for the {country} market)
- difficulty: SEO difficulty score 1-100 (100 = hardest)
- intent: search intent (informational, transactional, commercial, navigational)
- cpc: estimated cost per click in USD
- category: keyword category/theme

Mix of:
- 10 high-volume head terms (1000+ searches/month)
- 10 medium-volume terms (100-1000 searches/month)  
- 10 long-tail terms (10-100 searches/month, lower difficulty)

Return ONLY a JSON array, no other text. Example format:
[
  {{"keyword": "buy barcodes online", "search_volume": 2400, "difficulty": 45, "intent": "transactional", "cpc": 1.50, "category": "purchase"}},
  {{"keyword": "how to get a barcode for my product", "search_volume": 880, "difficulty": 30, "intent": "informational", "cpc": 0.80, "category": "guide"}}
]"""

        if not GEMINI_API_KEY:
            return self._fallback_suggestions(seed)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.gemini_url}?key={GEMINI_API_KEY}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.4}
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    # Parse JSON from response
                    text = text.replace("```json", "").replace("```", "").strip()
                    keywords = json.loads(text)
                    if isinstance(keywords, list):
                        return keywords
                else:
                    print(f"[KWResearch] Gemini error: {resp.status_code}")
        except json.JSONDecodeError as e:
            print(f"[KWResearch] JSON parse error: {e}")
        except Exception as e:
            print(f"[KWResearch] AI error: {e}")

        return self._fallback_suggestions(seed)

    async def _dataforseo_enrich(self, keywords: List[Dict], country: str = "GB") -> Optional[List[Dict]]:
        """Enrich keyword suggestions with real DataForSEO search volume data."""
        try:
            kw_list = [kw["keyword"] for kw in keywords[:50]]  # Limit to 50 to control costs

            # Map country codes to DataForSEO location codes
            location_map = {
                "GB": 2826, "US": 2840, "CA": 2124, "AU": 2036,
                "DE": 2276, "FR": 2250, "IN": 2356, "BR": 2076,
            }
            location_code = location_map.get(country, 2826)

            import base64
            auth = base64.b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json"
                    },
                    json=[{
                        "keywords": kw_list,
                        "location_code": location_code,
                        "language_code": "en",
                    }]
                )

                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("tasks", [{}])[0].get("result", [])

                    # Build lookup map
                    volume_map = {}
                    for r in results:
                        if r and r.get("keyword"):
                            volume_map[r["keyword"].lower()] = {
                                "search_volume": r.get("search_volume", 0),
                                "competition": r.get("competition", 0),
                                "cpc": r.get("cpc", 0),
                            }

                    # Enrich original keywords
                    for kw in keywords:
                        real_data = volume_map.get(kw["keyword"].lower())
                        if real_data:
                            kw["search_volume"] = real_data["search_volume"] or kw.get("search_volume", 0)
                            kw["cpc"] = real_data["cpc"] or kw.get("cpc", 0)
                            kw["difficulty"] = int((real_data["competition"] or 0) * 100)
                            kw["data_source"] = "dataforseo"
                        else:
                            kw["data_source"] = "ai_estimate"

                    return keywords
                else:
                    print(f"[KWResearch] DataForSEO error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"[KWResearch] DataForSEO error: {e}")

        return None

    def _calculate_opportunity_score(self, kw: Dict) -> int:
        """Score 0-100 based on volume, difficulty, and intent."""
        volume = kw.get("search_volume", 0) or 0
        difficulty = kw.get("difficulty", 50) or 50
        intent = kw.get("intent", "informational")

        # Volume score (0-40)
        if volume >= 5000: vol_score = 40
        elif volume >= 1000: vol_score = 30
        elif volume >= 500: vol_score = 25
        elif volume >= 100: vol_score = 20
        elif volume >= 50: vol_score = 15
        else: vol_score = 10

        # Difficulty score inverted (0-40)
        diff_score = int((100 - difficulty) * 0.4)

        # Intent score (0-20)
        intent_scores = {"transactional": 20, "commercial": 15, "informational": 10, "navigational": 5}
        intent_score = intent_scores.get(intent, 10)

        return min(vol_score + diff_score + intent_score, 100)

    def _difficulty_label(self, difficulty: int) -> str:
        if difficulty <= 20: return "Very Easy"
        if difficulty <= 40: return "Easy"
        if difficulty <= 60: return "Medium"
        if difficulty <= 80: return "Hard"
        return "Very Hard"

    def _fallback_suggestions(self, seed: str) -> List[Dict]:
        """Basic fallback when AI is unavailable."""
        modifiers = [
            "buy", "best", "cheap", "how to", "what is",
            "near me", "online", "uk", "for sale", "review",
            "vs", "alternative", "price", "guide", "tips"
        ]
        suggestions = []
        for mod in modifiers:
            suggestions.append({
                "keyword": f"{mod} {seed}",
                "search_volume": 0,
                "difficulty": 50,
                "intent": "informational",
                "cpc": 0,
                "category": "general",
                "data_source": "fallback"
            })
        return suggestions


# Module-level instance
researcher = KeywordResearcher()


async def run_keyword_research(
    seed_keyword: str,
    domain: str = "",
    country: str = "GB",
    niche: str = "",
    current_keywords: List[str] = None,
) -> Dict[str, Any]:
    """Entry point for keyword research."""
    return await researcher.research_keywords(
        seed_keyword=seed_keyword,
        domain=domain,
        country=country,
        niche=niche,
        current_keywords=current_keywords,
    )
