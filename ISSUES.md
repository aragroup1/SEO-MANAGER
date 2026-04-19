# ISSUES.md — Current Blockers & Pending Items

> Update this file as issues are resolved. Remove fixed items, add new ones.

## Active Blockers

### Gemini 429 — Rate Limited
- **Impact:** Fix scans fail (can't generate alt text), content writer fails, strategist fails
- **Fix:** Enable billing at https://aistudio.google.com → Settings → Billing → enable pay-as-you-go
- **Cost:** Gemini Flash ~$0.075/M input tokens. Full fix scan of 50 pages costs ~$0.01

### DataForSEO — $0 Balance
- **Impact:** No search volume data for keywords
- **Fix:** Add funds at https://app.dataforseo.com/
- **Workaround:** Keywords still sync from GSC (positions, clicks, impressions) — just no monthly search volume

### GA4 APIs Not Enabled
- **Impact:** GA4 property picker returns empty, no traffic data in reports
- **Fix:** Enable on Google Cloud project 475772626835:
  - https://console.developers.google.com/apis/api/analyticsadmin.googleapis.com/overview?project=475772626835
  - https://console.developers.google.com/apis/api/analyticsdata.googleapis.com/overview?project=475772626835

### Google OAuth in Test Mode
- **Impact:** Only test users can connect Google accounts
- **Fix:** Google Cloud Console → APIs & Services → OAuth consent screen → Publish App

## Known Limitations

### WordPress REST API Auth Stripped
- **Status:** WORKAROUND IN PLACE — XML-RPC fallback works
- **Root cause:** Security plugin strips Authorization header
- **Optional fix:** Add to `.htaccess`: `RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]`

### Shopify Token Expiry
- **Status:** HANDLED — auto-refresh on every fix scan/apply
- **Note:** 24h token from client_credentials grant. Stored client_id+secret in Integration.config enables refresh.

## Recently Fixed

- ✅ Shopify multi-store — per-store client_credentials form (no more "organization" error)
- ✅ Fix engine site_type dependency — now checks Integration table, not website.site_type
- ✅ WordPress meta_title fix type — was returning "not supported", now updates post title
- ✅ Alt text fix "no image found" — improved matching, reads raw content via XML-RPC
- ✅ Auth system — login screen, Bearer tokens, global fetch interceptor
- ✅ Chart axis labels invisible — changed from #555 to #bbb
- ✅ Dropdown white-on-white — added color-scheme: dark to :root
