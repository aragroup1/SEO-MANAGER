# backend/integrations.py - Integration management endpoints
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict
import os
import secrets
import hashlib
import hmac

from database import SessionLocal, get_db, Integration, Website

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

INTEGRATION_DEFINITIONS = {
    "google_search_console": {
        "name": "Google Search Console",
        "description": "Track keyword rankings, impressions, and indexing status",
        "required": True,
        "relevantFor": ["custom", "shopify", "wordpress"],
        "dataProvided": "Keyword rankings, click data, indexing errors",
        "scopes": ["https://www.googleapis.com/auth/webmasters.readonly"]
    },
    "google_analytics": {
        "name": "Google Analytics 4",
        "description": "Monitor traffic, user behavior, and conversions",
        "required": True,
        "relevantFor": ["custom", "shopify", "wordpress"],
        "dataProvided": "Traffic sources, user engagement, conversion tracking",
        "scopes": ["https://www.googleapis.com/auth/analytics.readonly"]
    },
    "shopify": {
        "name": "Shopify",
        "description": "Sync products, manage meta tags, and optimize listings",
        "required": True,
        "relevantFor": ["shopify"],
        "dataProvided": "Product data, collection structure, meta fields",
        "scopes": ["read_products", "write_products", "read_content", "write_content"]
    },
    "wordpress": {
        "name": "WordPress",
        "description": "Sync posts, manage SEO plugin settings, and optimize content",
        "required": True,
        "relevantFor": ["wordpress"],
        "dataProvided": "Posts, pages, plugin settings, sitemap data",
        "scopes": []
    }
}


@router.get("/{website_id}/status")
async def get_integration_status(website_id: int, db: Session = Depends(get_db)):
    connected = db.query(Integration).filter(Integration.website_id == website_id).all()
    connected_map = {i.integration_type: i for i in connected}

    integrations = []
    for int_id, definition in INTEGRATION_DEFINITIONS.items():
        db_record = connected_map.get(int_id)
        integrations.append({
            "id": int_id,
            "name": definition["name"],
            "description": definition["description"],
            "connected": db_record is not None and db_record.status == "active",
            "status": db_record.status if db_record else "not_connected",
            "required": definition["required"],
            "relevantFor": definition["relevantFor"],
            "dataProvided": definition["dataProvided"],
            "connected_at": db_record.connected_at.isoformat() if db_record and db_record.connected_at else None,
            "last_synced": db_record.last_synced.isoformat() if db_record and db_record.last_synced else None,
            "account_name": db_record.account_name if db_record else None,
        })

    return {"integrations": integrations}


@router.get("/{website_id}/connected")
async def get_connected_integrations(website_id: int, db: Session = Depends(get_db)):
    connected = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.status.in_(["active", "error", "expired"])
    ).all()

    integrations = []
    for record in connected:
        definition = INTEGRATION_DEFINITIONS.get(record.integration_type, {})
        integrations.append({
            "id": record.integration_type,
            "name": definition.get("name", record.integration_type),
            "connected": record.status == "active",
            "status": record.status,
            "connected_at": record.connected_at.isoformat() if record.connected_at else None,
            "last_synced": record.last_synced.isoformat() if record.last_synced else None,
            "account_name": record.account_name,
            "scopes": record.scopes or [],
        })

    return {"integrations": integrations}


@router.post("/{website_id}/connect")
async def connect_integration(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    integration_id = data.get("integration_id")

    if integration_id not in INTEGRATION_DEFINITIONS:
        raise HTTPException(status_code=400, detail=f"Unknown integration: {integration_id}")

    definition = INTEGRATION_DEFINITIONS[integration_id]

    # ─── Google OAuth (Search Console / GA4) ───
    if integration_id in ["google_search_console", "google_analytics"]:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/integrations/oauth/google/callback")

        if not client_id:
            existing = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == integration_id
            ).first()

            if existing:
                existing.status = "active"
                existing.connected_at = datetime.utcnow()
                existing.last_synced = datetime.utcnow()
                existing.account_name = "Demo Account"
            else:
                new_integration = Integration(
                    website_id=website_id,
                    integration_type=integration_id,
                    status="active",
                    connected_at=datetime.utcnow(),
                    last_synced=datetime.utcnow(),
                    account_name="Demo Account",
                    scopes=definition.get("scopes", [])
                )
                db.add(new_integration)

            db.commit()
            return {"connected": True, "message": f"{definition['name']} connected (demo mode)"}

        state = secrets.token_urlsafe(32)
        scopes = " ".join(definition.get("scopes", []))
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes}"
            f"&state={state}|{website_id}|{integration_id}"
            f"&access_type=offline"
            f"&prompt=consent"
        )
        return {"authorization_url": auth_url}

    # ─── Shopify OAuth ───
    elif integration_id == "shopify":
        shopify_client_id = os.getenv("SHOPIFY_CLIENT_ID")
        shopify_redirect_uri = os.getenv(
            "SHOPIFY_REDIRECT_URI",
            "https://backend-production-6104.up.railway.app/api/integrations/oauth/shopify/callback"
        )

        # Get the shop domain from the request or from the website record
        shop_domain = data.get("shop_domain", "")

        if not shop_domain:
            website = db.query(Website).filter(Website.id == website_id).first()
            if website:
                shop_domain = website.shopify_store_url or website.domain
            if not shop_domain:
                return {
                    "needs_shop_domain": True,
                    "message": "Please provide your myshopify.com store URL to connect Shopify."
                }

        # Normalize shop domain
        shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
        if not shop_domain.endswith(".myshopify.com"):
            shop_domain = shop_domain + ".myshopify.com"

        if not shopify_client_id:
            # Demo mode
            existing = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "shopify"
            ).first()

            if existing:
                existing.status = "active"
                existing.connected_at = datetime.utcnow()
                existing.last_synced = datetime.utcnow()
                existing.account_name = shop_domain
            else:
                new_integration = Integration(
                    website_id=website_id,
                    integration_type="shopify",
                    status="active",
                    connected_at=datetime.utcnow(),
                    last_synced=datetime.utcnow(),
                    account_name=shop_domain,
                    config={"store_url": shop_domain, "shop_domain": shop_domain},
                    scopes=definition.get("scopes", [])
                )
                db.add(new_integration)

            db.commit()
            return {"connected": True, "message": "Shopify connected (demo mode)"}

        # Real Shopify OAuth flow
        scopes = ",".join(definition.get("scopes", []))
        state = secrets.token_urlsafe(32)
        state_value = f"{state}|{website_id}|{shop_domain}"

        auth_url = (
            f"https://{shop_domain}/admin/oauth/authorize"
            f"?client_id={shopify_client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={shopify_redirect_uri}"
            f"&state={state_value}"
        )
        return {"authorization_url": auth_url}

    # ─── WordPress (app password based) ───
    elif integration_id == "wordpress":
        wp_url = data.get("wordpress_url")
        wp_username = data.get("username", "")
        wp_app_password = data.get("app_password", "")

        existing = db.query(Integration).filter(
            Integration.website_id == website_id,
            Integration.integration_type == "wordpress"
        ).first()

        if existing:
            existing.status = "active"
            existing.connected_at = datetime.utcnow()
            existing.account_name = wp_url
            existing.access_token = wp_app_password
            existing.config = {"wp_url": wp_url, "username": wp_username}
        else:
            new_integration = Integration(
                website_id=website_id,
                integration_type="wordpress",
                status="active",
                connected_at=datetime.utcnow(),
                account_name=wp_url,
                access_token=wp_app_password,
                config={"wp_url": wp_url, "username": wp_username},
                scopes=[]
            )
            db.add(new_integration)

        db.commit()
        return {"connected": True, "message": "WordPress connected"}

    return {"connected": False, "message": "Integration type not handled"}


@router.post("/{website_id}/set-gsc-property")
async def set_gsc_property(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Save the user's selected GSC property for this website."""
    data = await request.json()
    property_url = data.get("property_url", "")

    integration = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == "google_search_console"
    ).first()

    if not integration:
        raise HTTPException(status_code=404, detail="GSC integration not found")

    config = integration.config or {}
    config["gsc_property"] = property_url
    integration.config = config
    integration.account_name = (integration.account_name or "Google") + " — " + property_url
    db.commit()

    return {"saved": True, "property": property_url}


@router.post("/{website_id}/disconnect")
async def disconnect_integration(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    integration_id = data.get("integration_id")

    record = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == integration_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Integration not found")

    db.delete(record)
    db.commit()
    return {"disconnected": True, "message": f"{integration_id} disconnected"}


@router.post("/{website_id}/sync")
async def sync_integration(website_id: int, request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    integration_id = data.get("integration_id")

    record = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == integration_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Integration not found")

    if record.status != "active":
        raise HTTPException(status_code=400, detail="Integration is not active. Please reconnect.")

    record.last_synced = datetime.utcnow()
    db.commit()
    return {"synced": True, "message": f"{integration_id} sync initiated"}


# ─────────────────────────────────────────────────
#  Google OAuth Callback
# ─────────────────────────────────────────────────
@router.get("/oauth/google/callback")
async def google_oauth_callback(code: str, state: str, db: Session = Depends(get_db)):
    import httpx

    try:
        parts = state.split("|")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts")
        website_id = int(parts[1])
        integration_type = parts[2]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/integrations/oauth/google/callback")

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
        )

    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    tokens = token_response.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    account_name = "Google Account"
    try:
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if user_response.status_code == 200:
                user_info = user_response.json()
                account_name = user_info.get("email", "Google Account")
    except Exception:
        pass

    definition = INTEGRATION_DEFINITIONS.get(integration_type, {})
    existing = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == integration_type
    ).first()

    if existing:
        existing.status = "active"
        existing.access_token = access_token
        existing.refresh_token = refresh_token
        existing.token_expiry = datetime.utcnow()
        existing.connected_at = datetime.utcnow()
        existing.last_synced = datetime.utcnow()
        existing.account_name = account_name
        existing.scopes = definition.get("scopes", [])
    else:
        new_integration = Integration(
            website_id=website_id,
            integration_type=integration_type,
            status="active",
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=datetime.utcnow(),
            connected_at=datetime.utcnow(),
            last_synced=datetime.utcnow(),
            account_name=account_name,
            scopes=definition.get("scopes", [])
        )
        db.add(new_integration)

    db.commit()

    # For Search Console: fetch available properties and show picker
    if integration_type == "google_search_console":
        properties_html = ""
        try:
            async with httpx.AsyncClient() as client:
                props_response = await client.get(
                    "https://www.googleapis.com/webmasters/v3/sites",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if props_response.status_code == 200:
                    props_data = props_response.json()
                    for entry in props_data.get("siteEntry", []):
                        site_url = entry.get("siteUrl", "")
                        perm = entry.get("permissionLevel", "")
                        properties_html += f'<button class="prop-btn" onclick="selectProperty(\'{site_url}\')">{site_url}<span class="perm">{perm}</span></button>'
        except Exception as e:
            print(f"[GSC] Error fetching properties: {e}")

        if not properties_html:
            properties_html = '<p style="color:#aaa;text-align:center;padding:20px;">No properties found. Add your site in Google Search Console first.</p>'

        return HTMLResponse(content=f"""
        <html>
        <head><style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ font-family:system-ui; background:#1a1a2e; color:white; display:flex; align-items:center; justify-content:center; height:100vh; }}
            .container {{ max-width:420px; width:100%; padding:32px; }}
            h2 {{ margin-bottom:8px; font-size:20px; }}
            p.sub {{ color:#a0a0c0; font-size:13px; margin-bottom:20px; }}
            .prop-btn {{ display:block; width:100%; text-align:left; padding:12px 16px; margin-bottom:8px; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:10px; color:white; font-size:14px; cursor:pointer; transition:all 0.2s; }}
            .prop-btn:hover {{ background:rgba(168,85,247,0.2); border-color:rgba(168,85,247,0.4); }}
            .perm {{ display:block; color:#888; font-size:11px; margin-top:2px; text-transform:capitalize; }}
            .skip {{ display:block; text-align:center; color:#888; font-size:12px; margin-top:16px; cursor:pointer; text-decoration:underline; }}
        </style></head>
        <body>
            <div class="container">
                <div style="text-align:center;font-size:32px;margin-bottom:12px;">&#9989;</div>
                <h2>Google Account Connected</h2>
                <p class="sub">Select the Search Console property for this website:</p>
                <div id="props">{properties_html}</div>
                <a class="skip" onclick="selectProperty('')">Skip — auto-detect later</a>
            </div>
            <script>
                function selectProperty(siteUrl) {{
                    if (siteUrl) {{
                        fetch('/api/integrations/{website_id}/set-gsc-property', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{property_url: siteUrl}})
                        }}).then(() => {{
                            window.opener && window.opener.postMessage('integration_connected', '*');
                            window.close();
                        }});
                    }} else {{
                        window.opener && window.opener.postMessage('integration_connected', '*');
                        window.close();
                    }}
                }}
            </script>
        </body>
        </html>
        """)

    # For GA4 and others: just close
    return HTMLResponse(content="""
    <html>
    <body>
        <script>
            window.opener && window.opener.postMessage('integration_connected', '*');
            window.close();
        </script>
        <p>Connected successfully! This window will close automatically.</p>
    </body>
    </html>
    """)


# ─────────────────────────────────────────────────
#  Shopify OAuth Callback
# ─────────────────────────────────────────────────
@router.get("/oauth/shopify/callback")
async def shopify_oauth_callback(
    code: str,
    state: str,
    shop: str,
    hmac: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle Shopify OAuth callback — exchange code for offline access token."""
    import httpx

    # Parse state to get website_id and shop_domain
    try:
        parts = state.split("|")
        if len(parts) != 3:
            raise ValueError("Expected 3 parts in state")
        website_id = int(parts[1])
        shop_domain = parts[2]
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    shopify_client_id = os.getenv("SHOPIFY_CLIENT_ID")
    shopify_client_secret = os.getenv("SHOPIFY_CLIENT_SECRET")

    if not shopify_client_id or not shopify_client_secret:
        raise HTTPException(status_code=500, detail="Shopify OAuth credentials not configured")

    # Exchange the authorization code for an offline access token
    token_url = f"https://{shop}/admin/oauth/access_token"

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            token_url,
            json={
                "client_id": shopify_client_id,
                "client_secret": shopify_client_secret,
                "code": code
            }
        )

    if token_response.status_code != 200:
        print(f"[Shopify OAuth] Token exchange failed: {token_response.status_code} {token_response.text[:500]}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get Shopify access token: {token_response.text[:200]}"
        )

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    granted_scopes = token_data.get("scope", "")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token in Shopify response")

    print(f"[Shopify OAuth] Got access token for {shop}, scopes: {granted_scopes}")

    # Get shop info for display name
    shop_name = shop
    try:
        async with httpx.AsyncClient() as client:
            shop_response = await client.get(
                f"https://{shop}/admin/api/2024-01/shop.json",
                headers={"X-Shopify-Access-Token": access_token}
            )
            if shop_response.status_code == 200:
                shop_data = shop_response.json()
                shop_name = shop_data.get("shop", {}).get("name", shop)
    except Exception as e:
        print(f"[Shopify OAuth] Could not fetch shop info: {e}")

    # Save to database
    existing = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == "shopify"
    ).first()

    if existing:
        existing.status = "active"
        existing.access_token = access_token
        existing.connected_at = datetime.utcnow()
        existing.last_synced = datetime.utcnow()
        existing.account_name = shop_name
        existing.scopes = granted_scopes.split(",") if granted_scopes else []
        existing.config = {"store_url": shop, "shop_domain": shop_domain}
    else:
        new_integration = Integration(
            website_id=website_id,
            integration_type="shopify",
            status="active",
            access_token=access_token,
            connected_at=datetime.utcnow(),
            last_synced=datetime.utcnow(),
            account_name=shop_name,
            scopes=granted_scopes.split(",") if granted_scopes else [],
            config={"store_url": shop, "shop_domain": shop_domain}
        )
        db.add(new_integration)

    # Also update the website record so the fix engine can find credentials
    website = db.query(Website).filter(Website.id == website_id).first()
    if website:
        website.shopify_store_url = shop
        website.shopify_access_token = access_token

    db.commit()

    return HTMLResponse(content="""
    <html>
    <body style="font-family: system-ui; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #1a1a2e; color: white;">
        <div style="text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">&#10004;</div>
            <h2>Shopify Connected!</h2>
            <p style="color: #a0a0a0;">This window will close automatically...</p>
        </div>
        <script>
            window.opener && window.opener.postMessage('integration_connected', '*');
            setTimeout(() => window.close(), 2000);
        </script>
    </body>
    </html>
    """)
