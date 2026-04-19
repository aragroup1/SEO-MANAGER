# INTEGRATIONS.md — Integration Patterns

## Shopify (per-store, client_credentials)

### How It Works
Each Shopify store needs a custom app created in THAT store's admin (Settings → Apps → Develop apps). The app's client_id + client_secret are entered via the dashboard form — NOT stored as env vars.

### Token Exchange Flow
```
POST https://{shop}.myshopify.com/admin/oauth/access_token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={per_store_client_id}
&client_secret={per_store_client_secret}

→ Response: { "access_token": "shpat_xxx", "scope": "...", "expires_in": 86399 }
```

### Token Refresh
Tokens expire in 24 hours. `_refresh_shopify_token()` in `fix_engine.py` auto-refreshes using stored client_id + client_secret from `Integration.config` JSON before every scan/apply.

### Storage
- `Integration.access_token` = current `shpat_` token
- `Integration.config` = `{ "store_url", "shop_domain", "auth_method": "client_credentials", "client_id", "client_secret", "token_expires_in", "token_obtained_at" }`
- `Website.shopify_store_url` + `Website.shopify_access_token` also updated for fix engine compatibility

### Legacy OAuth (canvas-wallart only)
The global `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` env vars power an OAuth redirect flow that only works for stores in the same Shopify Partners organization. Do NOT use for new stores — always use the per-store client_credentials form.

### Common Issues
- "Organization" error → store not in same org as the OAuth app. Use per-store form instead.
- 401 on token exchange → app not installed, or wrong client_id/secret.
- `site_type` still "custom" → fix engine now checks Integration table regardless of site_type, and connecting Shopify auto-updates site_type.

---

## WordPress (App Password + XML-RPC Fallback)

### How It Works
User enters WordPress URL + admin username + application password (generated in WP Admin → Users → Profile → Application Passwords).

### Auth Issue
barcodemarket.com's security plugin strips the `Authorization` header from REST API requests. This means:
- `GET /wp-json/wp/v2/posts` works (public endpoint, no auth needed)
- `GET /wp-json/wp/v2/users/me` fails with `rest_not_logged_in`
- `POST /wp-json/wp/v2/posts/{id}` fails with `rest_cannot_edit`

### XML-RPC Fallback
`_api_put()` in `fix_engine.py` automatically detects `rest_cannot_edit` and retries via XML-RPC:
```xml
POST /xmlrpc.php
wp.editPost(blog_id=1, username, password, post_id, { post_content, post_excerpt, post_title })
```
XML-RPC auth works because the security plugin doesn't block it.

### Reading Content
`_xmlrpc_get_content()` uses `wp.getPost` to read raw content (needed for alt text fixes where rendered HTML differs from stored content).

### Fix Types Supported
- `alt_text` — reads content via XML-RPC, finds img without alt, updates via XML-RPC
- `meta_title` — updates post title directly
- `meta_description` — updates excerpt field
- `thin_content` — expands content body
- `structured_data` — returns guidance (needs SEO plugin)

### Storage
- `Integration.access_token` = application password
- `Integration.config` = `{ "wp_url", "username" }`

### Potential Fix for REST API
Add to `.htaccess` before WordPress rules: `RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]`

---

## Google OAuth (GSC + GA4)

### Flow
1. Frontend calls `POST /api/integrations/{id}/connect` with `integration_id: "google_search_console"` or `"google_analytics"`
2. Backend returns `authorization_url` → frontend opens popup
3. User authorizes → Google redirects to `/api/integrations/oauth/google/callback`
4. Backend exchanges code for tokens, saves to Integration table
5. User selects GSC property / GA4 property via separate endpoints

### Scopes
- GSC: `https://www.googleapis.com/auth/webmasters.readonly`
- GA4: `https://www.googleapis.com/auth/analytics.readonly`, `https://www.googleapis.com/auth/analytics.edit`

### Storage
- `Integration.access_token` = access token
- `Integration.refresh_token` = refresh token
- `Integration.config` = `{ "property_url" }` for GSC, `{ "ga4_property_id" }` for GA4

### Required Google Cloud Setup
- OAuth consent screen must be PUBLISHED (not test mode)
- Analytics Admin API enabled (for GA4 property listing)
- Analytics Data API enabled (for GA4 data fetching)
- Project ID: 475772626835

---

## DataForSEO

### Usage
Provides search volume, keyword difficulty, CPC for keywords.

### Caching
Search volumes cached MONTHLY per website in `KeywordSnapshot`. Before calling the API, check if data was fetched this month. This prevents unnecessary API costs.

### Auth
Basic auth with `DATAFORSEO_LOGIN` + `DATAFORSEO_PASSWORD` env vars.

### Common Issue
Status 40200 = no balance (not bad credentials). Message: "Add funds at dataforseo.com"

### Endpoint Used
`POST https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live`
