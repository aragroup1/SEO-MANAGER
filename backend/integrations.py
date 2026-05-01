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
        "scopes": ["https://www.googleapis.com/auth/analytics.readonly", "https://www.googleapis.com/auth/analytics.edit"]
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


@router.get("/{website_id}/debug-wp")
async def debug_wordpress(website_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to check WordPress integration state."""
    integration = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == "wordpress"
    ).first()

    if not integration:
        return {"exists": False, "message": "No WordPress integration record found"}

    config = integration.config or {}
    return {
        "exists": True,
        "status": integration.status,
        "has_access_token": bool(integration.access_token),
        "access_token_length": len(integration.access_token) if integration.access_token else 0,
        "account_name": integration.account_name,
        "config_wp_url": config.get("wp_url", "NOT SET"),
        "config_username": config.get("username", "NOT SET"),
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
    }


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

        # Support multiple connection methods:
        # 1. API key + secret (custom app created in the store's admin)
        # 2. Direct access token (if the store still provides one)
        # 3. OAuth flow (for stores in the same organization)
        api_key = data.get("api_key", "").strip()
        api_secret = data.get("api_secret", "").strip()
        direct_token = data.get("access_token", "").strip()
        shop_domain = data.get("shop_domain", "")

        print(f"[Shopify] Connect attempt: shop_domain='{shop_domain}', has_api_key={bool(api_key)}, has_api_secret={bool(api_secret)}, has_direct_token={bool(direct_token)}, has_client_id={bool(shopify_client_id)}")

        # ─── Method 1: API Key + Secret (Custom App — client_credentials grant) ───
        if api_key and api_secret:
            if not shop_domain:
                return {"connected": False, "message": "Shop domain is required."}

            shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
            if not shop_domain.endswith(".myshopify.com"):
                shop_domain = shop_domain + ".myshopify.com"

            # Use Shopify's client_credentials OAuth flow to get an access token
            # POST https://{shop}.myshopify.com/admin/oauth/access_token
            # Content-Type: application/x-www-form-urlencoded
            # grant_type=client_credentials&client_id={key}&client_secret={secret}
            try:
                import httpx as httpx_lib
                async with httpx_lib.AsyncClient(timeout=15) as tc:
                    token_resp = await tc.post(
                        f"https://{shop_domain}/admin/oauth/access_token",
                        data={
                            "grant_type": "client_credentials",
                            "client_id": api_key,
                            "client_secret": api_secret,
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
                    print(f"[Shopify] Token exchange response: {token_resp.status_code} {token_resp.text[:200]}")

                    if token_resp.status_code != 200:
                        return {"connected": False, "message": f"Shopify rejected credentials ({token_resp.status_code}). Make sure the app is installed and the client ID + secret are correct."}

                    token_data = token_resp.json()
                    access_token = token_data.get("access_token", "")
                    granted_scopes = token_data.get("scope", "")
                    expires_in = token_data.get("expires_in", 0)

                    if not access_token:
                        return {"connected": False, "message": "Shopify returned no access token. Check your app credentials."}

                    print(f"[Shopify] Got token for {shop_domain}, scopes: {granted_scopes}, expires_in: {expires_in}")

                    # Verify the token works
                    shop_resp = await tc.get(
                        f"https://{shop_domain}/admin/api/2024-01/shop.json",
                        headers={"X-Shopify-Access-Token": access_token}
                    )
                    shop_name = shop_domain
                    if shop_resp.status_code == 200:
                        shop_name = shop_resp.json().get("shop", {}).get("name", shop_domain)
                    else:
                        print(f"[Shopify] Shop info failed: {shop_resp.status_code}")

            except Exception as e:
                return {"connected": False, "message": f"Cannot reach {shop_domain}: {str(e)[:100]}"}

            # Save — store the client_id + secret so we can refresh the token (expires in 24h)
            website = db.query(Website).filter(Website.id == website_id).first()
            if website:
                website.shopify_store_url = shop_domain
                website.shopify_access_token = access_token

            existing = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "shopify"
            ).first()

            config_data = {
                "store_url": shop_domain,
                "shop_domain": shop_domain,
                "auth_method": "client_credentials",
                "client_id": api_key,
                "client_secret": api_secret,
                "token_expires_in": expires_in,
                "token_obtained_at": datetime.utcnow().isoformat(),
            }

            if existing:
                existing.status = "active"
                existing.access_token = access_token
                existing.connected_at = datetime.utcnow()
                existing.account_name = shop_name
                existing.config = config_data
                existing.scopes = granted_scopes.split(",") if granted_scopes else []
            else:
                new_integration = Integration(
                    website_id=website_id, integration_type="shopify", status="active",
                    access_token=access_token, connected_at=datetime.utcnow(),
                    account_name=shop_name, config=config_data,
                    scopes=granted_scopes.split(",") if granted_scopes else []
                )
                db.add(new_integration)
            db.commit()
            return {"connected": True, "message": f"Shopify connected: {shop_name} ✓ (token expires in {expires_in//3600}h — auto-refreshes)"}

        # ─── Method 2: Direct access token ───
        if direct_token:
            # Direct connection with Admin API access token or API key+secret
            if not shop_domain:
                return {"connected": False, "message": "Shop domain is required."}

            shop_domain = shop_domain.replace("https://", "").replace("http://", "").rstrip("/")
            if not shop_domain.endswith(".myshopify.com"):
                shop_domain = shop_domain + ".myshopify.com"

            # Determine auth method based on token format
            api_key = data.get("api_key", "").strip()

            if direct_token.startswith("shpss_") and api_key:
                # API key + secret method (for custom apps before install)
                print(f"[Shopify] Using API key + secret auth for {shop_domain}")
                auth_headers = {
                    "Content-Type": "application/json",
                }
                # Use HTTP Basic auth with API key as user and secret as password
                import base64 as b64
                basic_auth = b64.b64encode(f"{api_key}:{direct_token}".encode()).decode()
                auth_headers["Authorization"] = f"Basic {basic_auth}"
                auth_method = "api_key_secret"
                effective_token = direct_token  # store the secret
            elif direct_token.startswith("shpss_") and not api_key:
                # User pasted the secret key but no API key
                return {
                    "connected": False,
                    "message": "That's the API Secret Key (shpss_), not the Admin API access token. "
                               "Go to your app in Shopify → API credentials → click 'Install app' button → "
                               "the Admin API access token (shpat_...) will appear. Copy it IMMEDIATELY — "
                               "it's only shown once. If you already installed, you'll need to uninstall and reinstall, "
                               "or create a new custom app."
                }
            else:
                # Standard shpat_ token or any other token
                auth_headers = {"X-Shopify-Access-Token": direct_token}
                auth_method = "access_token"
                effective_token = direct_token

            # Verify the token works
            try:
                import httpx as httpx_lib
                async with httpx_lib.AsyncClient(timeout=15) as tc:
                    test_r = await tc.get(
                        f"https://{shop_domain}/admin/api/2024-01/shop.json",
                        headers=auth_headers
                    )
                    if test_r.status_code == 200:
                        shop_name = test_r.json().get("shop", {}).get("name", shop_domain)
                    elif test_r.status_code == 401:
                        return {"connected": False, "message": "Invalid token/credentials (401). Make sure you've installed the app and copied the Admin API access token (shpat_...)."}
                    elif test_r.status_code == 403:
                        return {"connected": False, "message": "Access denied (403). The app may not have the required API scopes. Edit the app → Admin API access scopes → enable read_products, write_products, read_content, write_content → Save → Reinstall."}
                    else:
                        return {"connected": False, "message": f"Shopify returned {test_r.status_code}. Check the store URL and token."}
            except Exception as e:
                return {"connected": False, "message": f"Cannot reach {shop_domain}: {str(e)[:100]}"}

            # Also save to the Website record for the fix engine
            website = db.query(Website).filter(Website.id == website_id).first()
            if website:
                website.shopify_store_url = shop_domain
                website.shopify_access_token = effective_token
                if auth_method == "api_key_secret":
                    # Store API key in config for future auth
                    pass

            existing = db.query(Integration).filter(
                Integration.website_id == website_id,
                Integration.integration_type == "shopify"
            ).first()
            config_data = {"store_url": shop_domain, "shop_domain": shop_domain, "auth_method": auth_method}
            if api_key:
                config_data["api_key"] = api_key

            if existing:
                existing.status = "active"
                existing.access_token = effective_token
                existing.connected_at = datetime.utcnow()
                existing.account_name = shop_name
                existing.config = config_data
            else:
                new_integration = Integration(
                    website_id=website_id, integration_type="shopify", status="active",
                    access_token=effective_token, connected_at=datetime.utcnow(),
                    account_name=shop_name, config=config_data, scopes=[]
                )
                db.add(new_integration)
            db.commit()
            return {"connected": True, "message": f"Shopify connected: {shop_name} ✓"}

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
        wp_url = data.get("wordpress_url", "").strip()
        wp_username = data.get("username", "").strip()
        wp_app_password = data.get("app_password", "").strip()

        print(f"[WordPress] Connect attempt: url='{wp_url}', username='{wp_username}', has_password={bool(wp_app_password)}")

        if not wp_url or not wp_username or not wp_app_password:
            print(f"[WordPress] REJECTED: missing fields - url={bool(wp_url)}, user={bool(wp_username)}, pass={bool(wp_app_password)}")
            return {"connected": False, "message": "WordPress URL, username, and application password are all required. Fill in all three fields."}

        # Normalize URL
        if not wp_url.startswith("http"):
            wp_url = "https://" + wp_url
        wp_url = wp_url.rstrip("/")

        # Remove spaces from app password (WordPress displays them with spaces but they should be stripped)
        wp_app_password = wp_app_password.replace(" ", "")

        # Test the connection — both READ and WRITE
        test_url = f"{wp_url}/wp-json/wp/v2/posts?per_page=1"
        print(f"[WordPress] Testing connection: {test_url}")
        try:
            import httpx as httpx_lib
            import base64
            # Use explicit Authorization header instead of auth tuple
            auth_string = base64.b64encode(f"{wp_username}:{wp_app_password}".encode()).decode()
            headers = {"Authorization": f"Basic {auth_string}"}

            async with httpx_lib.AsyncClient(timeout=15, follow_redirects=True) as test_client:
                # Test 1: Read
                test_resp = await test_client.get(test_url, headers=headers)
                print(f"[WordPress] Read test response: {test_resp.status_code}")
                if test_resp.status_code == 401:
                    return {"connected": False, "message": "Authentication failed (401). Check username and application password. Make sure there are no extra spaces."}
                elif test_resp.status_code == 403:
                    return {"connected": False, "message": "Access forbidden (403). The user may not have REST API access."}
                elif test_resp.status_code == 404:
                    return {"connected": False, "message": "WordPress REST API not found. Check the URL is correct."}
                elif test_resp.status_code != 200:
                    return {"connected": False, "message": f"WordPress returned status {test_resp.status_code}."}

                # Test 2: Check user capabilities via /wp/v2/users/me
                me_resp = await test_client.get(f"{wp_url}/wp-json/wp/v2/users/me?context=edit", headers=headers)
                user_role = "unknown"
                can_edit = False
                if me_resp.status_code == 200:
                    me_data = me_resp.json()
                    user_role = ", ".join(me_data.get("roles", ["unknown"]))
                    caps = me_data.get("capabilities", {})
                    can_edit = caps.get("edit_pages", False) or caps.get("edit_posts", False)
                    print(f"[WordPress] User roles: {user_role}, can_edit_pages: {caps.get('edit_pages')}, can_edit_posts: {caps.get('edit_posts')}")
                else:
                    print(f"[WordPress] /users/me failed: {me_resp.status_code} {me_resp.text[:200]}")

                # Test 3: Try a harmless write test — read a post and write it back unchanged
                write_ok = False
                write_msg = ""
                if test_resp.status_code == 200:
                    posts = test_resp.json()
                    if posts:
                        test_post = posts[0]
                        test_post_id = test_post["id"]
                        test_post_type = "posts"
                        # Try updating the post with its own title (no-op)
                        write_resp = await test_client.post(
                            f"{wp_url}/wp-json/wp/v2/{test_post_type}/{test_post_id}",
                            headers=headers,
                            json={"title": test_post.get("title", {}).get("raw", test_post.get("title", {}).get("rendered", "Test"))}
                        )
                        print(f"[WordPress] Write test response: {write_resp.status_code} {write_resp.text[:200]}")
                        if write_resp.status_code in [200, 201]:
                            write_ok = True
                        else:
                            try:
                                err = write_resp.json()
                                write_msg = err.get("message", str(write_resp.status_code))
                            except Exception:
                                write_msg = f"Status {write_resp.status_code}"

                print(f"[WordPress] Connection test PASSED (read=OK, write={'OK' if write_ok else 'FAILED: ' + write_msg})")

                if not write_ok:
                    # Try XML-RPC as fallback
                    xmlrpc_ok = False
                    try:
                        xmlrpc_url = f"{wp_url}/xmlrpc.php"
                        # Escape XML special chars in credentials (avoids "not well formed" faults)
                        from xml.sax.saxutils import escape as _xml_escape
                        u_esc = _xml_escape(wp_username)
                        p_esc = _xml_escape(wp_app_password)
                        # Test with wp.getUsersBlogs (lightweight read that confirms XML-RPC auth works)
                        xml_test = f"""<?xml version="1.0"?>
<methodCall>
  <methodName>wp.getUsersBlogs</methodName>
  <params>
    <param><value><string>{u_esc}</string></value></param>
    <param><value><string>{p_esc}</string></value></param>
  </params>
</methodCall>"""
                        xmlrpc_resp = await test_client.post(xmlrpc_url, content=xml_test.encode(),
                            headers={"Content-Type": "text/xml; charset=utf-8"})
                        xmlrpc_fault = None
                        if xmlrpc_resp.status_code == 200 and "<name>blogid</name>" in xmlrpc_resp.text:
                            xmlrpc_ok = True
                            print(f"[WordPress] XML-RPC fallback available (auth verified) OK")
                        elif xmlrpc_resp.status_code == 200 and "faultString" in xmlrpc_resp.text:
                            import re as _re
                            m = _re.search(r"faultString.*?<string>(.*?)</string>", xmlrpc_resp.text, _re.DOTALL)
                            xmlrpc_fault = m.group(1).strip() if m else "Unknown XML-RPC fault"
                            print(f"[WordPress] XML-RPC auth FAILED: {xmlrpc_fault}")
                        elif xmlrpc_resp.status_code == 403:
                            xmlrpc_fault = "XML-RPC blocked by security plugin (403)"
                            print(f"[WordPress] XML-RPC also blocked (403)")
                        elif xmlrpc_resp.status_code == 404 or "xmlrpc" in xmlrpc_resp.text.lower() and "disabled" in xmlrpc_resp.text.lower():
                            xmlrpc_fault = f"XML-RPC disabled on this site ({xmlrpc_resp.status_code})"
                            print(f"[WordPress] XML-RPC disabled: {xmlrpc_resp.status_code}")
                        else:
                            xmlrpc_fault = f"XML-RPC unexpected response ({xmlrpc_resp.status_code})"
                            print(f"[WordPress] XML-RPC test: {xmlrpc_resp.status_code} {xmlrpc_resp.text[:200]}")
                    except Exception as xe:
                        xmlrpc_fault = f"XML-RPC error: {xe}"
                        print(f"[WordPress] XML-RPC test error: {xe}")

                    if xmlrpc_ok:
                        _save_wp_integration(db, website_id, wp_url, wp_username, wp_app_password)
                        return {"connected": True, "message": f"WordPress connected: {wp_url}. REST API blocked by security plugin — will use XML-RPC fallback for fixes (auth verified)."}

                    # Neither REST write nor XML-RPC auth works — refuse to save a broken integration
                    print(f"[WordPress] Connection REJECTED: REST write failed ({write_msg}) AND XML-RPC failed ({xmlrpc_fault})")
                    rest_lower = (write_msg or "").lower()
                    # REST authenticated but user lacks edit capability -> role issue, not credentials
                    if "not allowed" in rest_lower or "rest_cannot_edit" in rest_lower or "rest_forbidden" in rest_lower:
                        return {"connected": False, "message": f"The WordPress user '{wp_username}' is logged in, but does NOT have permission to edit posts. Fix: in WP Admin -> Users -> {wp_username} -> set Role to 'Administrator' (or 'Editor'). Then regenerate the application password and reconnect. (REST said: '{write_msg}'. XML-RPC: {xmlrpc_fault}.)"}
                    if xmlrpc_fault and ("username" in xmlrpc_fault.lower() or "password" in xmlrpc_fault.lower() or "incorrect" in xmlrpc_fault.lower()):
                        return {"connected": False, "message": f"WordPress credentials rejected. XML-RPC says: '{xmlrpc_fault}'. Verify the username is an admin, and the application password is freshly generated (Users -> Profile -> Application Passwords). Paste it with or without spaces - we strip them."}
                    return {"connected": False, "message": f"Cannot write to WordPress. REST API: {write_msg}. XML-RPC: {xmlrpc_fault}. Either whitelist /wp-json/ in your security plugin, or enable XML-RPC and verify the application password."}

        except Exception as e:
            print(f"[WordPress] Connection test FAILED: {e}")
            return {"connected": False, "message": f"Could not reach WordPress at {wp_url}: {str(e)[:100]}"}

        _save_wp_integration(db, website_id, wp_url, wp_username, wp_app_password)
        return {"connected": True, "message": f"WordPress connected: {wp_url} (read + write verified ✓)"}

    return {"connected": False, "message": "Integration type not handled"}


def _save_wp_integration(db, website_id, wp_url, wp_username, wp_app_password):
    """Save WordPress integration credentials."""
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


@router.post("/{website_id}/set-ga4-property")
async def set_ga4_property(website_id: int, request: Request, db: Session = Depends(get_db)):
    """Save the user's selected GA4 property for this website."""
    data = await request.json()
    property_id = data.get("property_id", "")
    property_name = data.get("property_name", "")

    integration = db.query(Integration).filter(
        Integration.website_id == website_id,
        Integration.integration_type == "google_analytics"
    ).first()

    if not integration:
        raise HTTPException(status_code=404, detail="GA4 integration not found")

    config = integration.config or {}
    config["ga4_property_id"] = property_id
    config["ga4_property_name"] = property_name
    integration.config = config
    integration.account_name = (integration.account_name or "Google") + " — " + property_name
    db.commit()

    return {"saved": True, "property_id": property_id, "property_name": property_name}


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

    # For GA4: fetch properties and show picker
    if integration_type == "google_analytics":
        ga4_html = ""
        try:
            async with httpx.AsyncClient() as client:
                # GA4 uses Admin API to list accounts and properties
                accounts_resp = await client.get(
                    "https://analyticsadmin.googleapis.com/v1beta/accounts",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                if accounts_resp.status_code == 200:
                    accounts_data = accounts_resp.json()
                    for account in accounts_data.get("accounts", []):
                        account_name = account.get("displayName", "Unknown")
                        account_id = account.get("name", "")  # e.g. "accounts/12345"

                        # List properties under each account
                        props_resp = await client.get(
                            f"https://analyticsadmin.googleapis.com/v1beta/properties",
                            params={"filter": f"parent:{account_id}"},
                            headers={"Authorization": f"Bearer {access_token}"}
                        )
                        if props_resp.status_code == 200:
                            props_data = props_resp.json()
                            for prop in props_data.get("properties", []):
                                prop_name = prop.get("displayName", "")
                                prop_id = prop.get("name", "")  # e.g. "properties/123456"
                                prop_num = prop_id.split("/")[-1] if "/" in prop_id else prop_id
                                ga4_html += f'<button class="prop-btn" onclick="selectGA4(\'{prop_num}\', \'{prop_name}\')">{prop_name}<span class="perm">{account_name} · {prop_id}</span></button>'
                else:
                    print(f"[GA4] Accounts API error: {accounts_resp.status_code} {accounts_resp.text[:200]}")
        except Exception as e:
            print(f"[GA4] Error listing properties: {e}")

        if not ga4_html:
            ga4_html = '<p style="color:#aaa;text-align:center;padding:20px;">No GA4 properties found. Make sure you have access to a GA4 property.</p>'

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
            .perm {{ display:block; color:#888; font-size:11px; margin-top:2px; }}
            .skip {{ display:block; text-align:center; color:#888; font-size:12px; margin-top:16px; cursor:pointer; text-decoration:underline; }}
        </style></head>
        <body>
            <div class="container">
                <div style="text-align:center;font-size:32px;margin-bottom:12px;">&#9989;</div>
                <h2>Google Analytics Connected</h2>
                <p class="sub">Select the GA4 property for this website:</p>
                <div id="props">{ga4_html}</div>
                <a class="skip" onclick="selectGA4('', '')">Skip</a>
            </div>
            <script>
                function selectGA4(propId, propName) {{
                    if (propId) {{
                        fetch('/api/integrations/{website_id}/set-ga4-property', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{property_id: propId, property_name: propName}})
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

    # For other integrations: just close
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
