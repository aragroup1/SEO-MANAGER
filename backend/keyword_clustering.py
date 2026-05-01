# backend/keyword_clustering.py - Keyword clustering + intent classification via Gemini
import os
import json
import re
from typing import List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _extract_json(text: str) -> Any:
    """Pull a JSON value out of Gemini's response (handles ```json fences)."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None


async def _gemini_call(prompt: str, timeout: int = 30) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def cluster_keywords(keywords: List[str], target_clusters: int = None) -> Dict[str, Any]:
    """
    Group keywords into topic clusters with a representative head term per cluster.
    Returns: { clusters: { "0": ["kw", ...], ... }, representatives: { "0": "head term", ... } }
    """
    if not keywords:
        return {"clusters": {}, "representatives": {}, "total_keywords": 0, "total_clusters": 0}

    keywords = [k.strip() for k in keywords if k and k.strip()]
    keywords = list(dict.fromkeys(keywords))[:300]  # de-dupe + cap

    suggested = target_clusters or max(2, min(12, len(keywords) // 6 or 2))

    prompt = f"""You are an SEO topic clustering expert. Group these {len(keywords)} keywords into {suggested} topical clusters.

Each cluster should:
- Group keywords that share search intent and topic
- Have a clear "head term" that summarises the cluster (the broadest/highest-intent keyword in it)
- Contain 2+ keywords (don't make singleton clusters unless absolutely necessary)

Keywords:
{json.dumps(keywords, ensure_ascii=False)}

Return ONLY a JSON object in this exact format, no other text:
{{
  "clusters": {{
    "0": ["kw1", "kw2", ...],
    "1": ["kw3", "kw4", ...]
  }},
  "representatives": {{
    "0": "head term for cluster 0",
    "1": "head term for cluster 1"
  }}
}}"""

    text = await _gemini_call(prompt)
    parsed = _extract_json(text) or {}
    clusters = parsed.get("clusters", {}) or {}
    reps = parsed.get("representatives", {}) or {}

    # Normalize keys to strings
    clusters = {str(k): list(v) for k, v in clusters.items() if isinstance(v, list)}
    reps = {str(k): str(v) for k, v in reps.items()}

    return {
        "clusters": clusters,
        "representatives": reps,
        "total_keywords": sum(len(v) for v in clusters.values()),
        "total_clusters": len(clusters),
    }


async def classify_intent(queries: List[str]) -> Dict[str, Any]:
    """
    Classify each query into one of: informational, navigational, transactional, commercial.
    Returns: { results: [{query, intent, confidence}], distribution: {intent: count} }
    """
    if not queries:
        return {"results": [], "distribution": {}}

    queries = [q.strip() for q in queries if q and q.strip()]
    queries = list(dict.fromkeys(queries))[:200]

    prompt = f"""Classify the search intent of each query into one of:
- informational: user wants to learn ("how to", "what is")
- navigational: user wants a specific site/brand
- transactional: user wants to buy / convert
- commercial: user is researching products before buying ("best X", "X vs Y", "X review")

Queries:
{json.dumps(queries, ensure_ascii=False)}

Return ONLY a JSON array, no other text. One object per query in the same order:
[
  {{"query": "...", "intent": "informational|navigational|transactional|commercial", "confidence": 0.0-1.0}}
]"""

    text = await _gemini_call(prompt)
    parsed = _extract_json(text) or []
    if not isinstance(parsed, list):
        parsed = []

    valid_intents = {"informational", "navigational", "transactional", "commercial"}
    results = []
    distribution: Dict[str, int] = {k: 0 for k in valid_intents}

    for item in parsed:
        if not isinstance(item, dict):
            continue
        intent = str(item.get("intent", "")).lower().strip()
        if intent not in valid_intents:
            intent = "informational"
        results.append({
            "query": item.get("query", ""),
            "intent": intent,
            "confidence": float(item.get("confidence", 0.7) or 0.7),
        })
        distribution[intent] += 1

    return {"results": results, "distribution": distribution, "total": len(results)}
