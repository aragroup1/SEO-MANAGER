# backend/schema_generator.py — Schema.org Structured Data Auto-Generator
import os
import json
import re
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SCHEMA_TYPES = {
    "Product": "https://schema.org/Product",
    "Article": "https://schema.org/Article",
    "Organization": "https://schema.org/Organization",
    "LocalBusiness": "https://schema.org/LocalBusiness",
    "FAQPage": "https://schema.org/FAQPage",
    "WebSite": "https://schema.org/WebSite",
    "BreadcrumbList": "https://schema.org/BreadcrumbList",
    "Review": "https://schema.org/Review",
}


async def _generate_with_ai(prompt: str, max_tokens: int = 800) -> str:
    """Generate schema JSON using Gemini Flash."""
    if not GEMINI_API_KEY:
        return ""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1}
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[Schema AI] Error: {e}")
    return ""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from AI response (handles markdown code blocks)."""
    # Try to find JSON in code blocks
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        text = match.group(1).strip()
    else:
        # Try to find JSON object directly
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


async def generate_product_schema(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Product schema with AI enhancement."""
    prompt = f"""Generate a complete Schema.org Product JSON-LD object.

Product info:
- Name: {product_data.get('name', '')}
- Description: {product_data.get('description', '')}
- Brand: {product_data.get('brand', '')}
- Price: {product_data.get('price', '')} {product_data.get('currency', 'USD')}
- SKU: {product_data.get('sku', '')}
- Image URL: {product_data.get('image', '')}
- Availability: {product_data.get('availability', 'InStock')}
- Rating: {product_data.get('rating', '')} (out of 5)
- Review count: {product_data.get('review_count', 0)}

Return ONLY valid JSON-LD with @context, @type, and all required properties. No markdown, no explanation."""

    result = await _generate_with_ai(prompt, 800)
    schema = _extract_json(result)
    if schema:
        return schema

    # Fallback: manual generation
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product_data.get("name", ""),
        "description": product_data.get("description", ""),
        "brand": {"@type": "Brand", "name": product_data.get("brand", "")},
        "sku": product_data.get("sku", ""),
        "image": product_data.get("image", ""),
        "offers": {
            "@type": "Offer",
            "price": product_data.get("price", ""),
            "priceCurrency": product_data.get("currency", "USD"),
            "availability": f"https://schema.org/{product_data.get('availability', 'InStock')}",
        },
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": product_data.get("rating", ""),
            "reviewCount": product_data.get("review_count", 0),
        } if product_data.get("rating") else None,
    }


async def generate_article_schema(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Article schema."""
    prompt = f"""Generate a complete Schema.org Article JSON-LD object.

Article info:
- Headline: {article_data.get('headline', '')}
- Description: {article_data.get('description', '')}
- Author: {article_data.get('author', '')}
- Published: {article_data.get('date_published', '')}
- Modified: {article_data.get('date_modified', '')}
- Image URL: {article_data.get('image', '')}
- Publisher: {article_data.get('publisher', '')}
- Publisher logo: {article_data.get('publisher_logo', '')}

Return ONLY valid JSON-LD. No markdown, no explanation."""

    result = await _generate_with_ai(prompt, 800)
    schema = _extract_json(result)
    if schema:
        return schema

    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article_data.get("headline", ""),
        "description": article_data.get("description", ""),
        "author": {"@type": "Person", "name": article_data.get("author", "")},
        "datePublished": article_data.get("date_published", ""),
        "dateModified": article_data.get("date_modified", article_data.get("date_published", "")),
        "image": article_data.get("image", ""),
        "publisher": {
            "@type": "Organization",
            "name": article_data.get("publisher", ""),
            "logo": {"@type": "ImageObject", "url": article_data.get("publisher_logo", "")},
        } if article_data.get("publisher") else None,
    }


async def generate_organization_schema(org_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Organization schema."""
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": org_data.get("name", ""),
        "url": org_data.get("url", ""),
        "logo": org_data.get("logo", ""),
        "description": org_data.get("description", ""),
        "sameAs": org_data.get("social_links", []),
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": org_data.get("phone", ""),
            "contactType": "customer service",
            "email": org_data.get("email", ""),
        } if org_data.get("phone") or org_data.get("email") else None,
    }


async def generate_localbusiness_schema(business_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate LocalBusiness schema."""
    schema = {
        "@context": "https://schema.org",
        "@type": business_data.get("business_type", "LocalBusiness"),
        "name": business_data.get("name", ""),
        "description": business_data.get("description", ""),
        "url": business_data.get("url", ""),
        "telephone": business_data.get("phone", ""),
        "email": business_data.get("email", ""),
        "image": business_data.get("image", ""),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": business_data.get("address", ""),
            "addressLocality": business_data.get("city", ""),
            "addressRegion": business_data.get("region", ""),
            "postalCode": business_data.get("postcode", ""),
            "addressCountry": business_data.get("country", "GB"),
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": business_data.get("latitude", ""),
            "longitude": business_data.get("longitude", ""),
        } if business_data.get("latitude") else None,
        "openingHoursSpecification": business_data.get("opening_hours", []),
        "priceRange": business_data.get("price_range", "$$"),
    }
    # Remove None values
    return {k: v for k, v in schema.items() if v is not None}


async def generate_faq_schema(faqs: List[Dict[str, str]]) -> Dict[str, Any]:
    """Generate FAQPage schema from list of Q&A."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq.get("question", ""),
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq.get("answer", ""),
                },
            }
            for faq in faqs
        ],
    }


async def generate_website_schema(site_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate WebSite schema with SearchAction (Sitelinks searchbox)."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site_data.get("name", ""),
        "url": site_data.get("url", ""),
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{site_data.get('url', '')}/search?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        } if site_data.get("has_search", False) else None,
    }


async def generate_breadcrumb_schema(items: List[Dict[str, str]]) -> Dict[str, Any]:
    """Generate BreadcrumbList schema."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": item.get("name", ""),
                "item": item.get("url", ""),
            }
            for i, item in enumerate(items)
        ],
    }


def validate_schema(json_ld: Dict[str, Any]) -> Dict[str, Any]:
    """Basic validation of Schema.org JSON-LD."""
    errors = []
    warnings = []

    if "@context" not in json_ld:
        errors.append("Missing @context (should be 'https://schema.org')")
    elif json_ld.get("@context") != "https://schema.org":
        warnings.append("@context should be 'https://schema.org'")

    if "@type" not in json_ld:
        errors.append("Missing @type")
    elif json_ld.get("@type") not in SCHEMA_TYPES and json_ld.get("@type") not in [
        "Restaurant", "Store", "Dentist", "Physician", "LegalService", "Plumber", "Electrician"
    ]:
        warnings.append(f"Uncommon @type: {json_ld.get('@type')}")

    # Type-specific checks
    schema_type = json_ld.get("@type", "")
    if schema_type == "Product":
        if not json_ld.get("name"):
            errors.append("Product schema missing 'name'")
        if not json_ld.get("offers") and not json_ld.get("aggregateRating"):
            warnings.append("Product schema should have 'offers' or 'aggregateRating'")
    elif schema_type == "Article":
        if not json_ld.get("headline"):
            errors.append("Article schema missing 'headline'")
        if not json_ld.get("datePublished"):
            warnings.append("Article schema should have 'datePublished'")
    elif schema_type == "LocalBusiness":
        if not json_ld.get("address"):
            errors.append("LocalBusiness schema missing 'address'")
        if not json_ld.get("telephone"):
            warnings.append("LocalBusiness schema should have 'telephone'")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


async def generate_schema(schema_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point — generate any supported schema type."""
    generators = {
        "Product": generate_product_schema,
        "Article": generate_article_schema,
        "Organization": generate_organization_schema,
        "LocalBusiness": generate_localbusiness_schema,
        "FAQPage": generate_faq_schema,
        "WebSite": generate_website_schema,
        "BreadcrumbList": generate_breadcrumb_schema,
    }

    generator = generators.get(schema_type)
    if not generator:
        return {"error": f"Unsupported schema type: {schema_type}. Supported: {list(generators.keys())}"}

    try:
        schema = await generator(data)
        validation = validate_schema(schema)
        return {
            "schema": schema,
            "validation": validation,
            "json_ld": json.dumps(schema, indent=2),
        }
    except Exception as e:
        return {"error": f"Schema generation failed: {str(e)}"}
