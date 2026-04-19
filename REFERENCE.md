# REFERENCE.md — Full Technical Reference

## Backend Files (`backend/`)

| File | Lines | Purpose |
|---|---|---|
| `main.py` | 884 | FastAPI app, route registration, auth middleware (Bearer token), daily/weekly schedulers, overview endpoint, DB migrations on startup |
| `database.py` | 242 | SQLAlchemy models: User, Website, AuditReport, ContentItem, Integration, ProposedFix, KeywordSnapshot, TrackedKeyword |
| `audit_engine.py` | 1083 | Deep crawl (500 pages max), CWV via PageSpeed Insights, 15+ SEO checks per page |
| `fix_engine.py` | 1338 | AIFixGenerator (Gemini), ShopifyFixEngine, WordPressFixEngine (REST + XML-RPC fallback), token refresh, fix orchestrator |
| `integrations.py` | 1056 | Google OAuth (GSC/GA4), Shopify (client_credentials per-store + legacy OAuth), WordPress (app passwords), connection testing |
| `search_console.py` | 578 | GSC keyword sync, position changes vs previous snapshot, new/lost keyword detection, per-keyword 90-day history |
| `keyword_routes.py` | 518 | Keyword CRUD, tracked keywords, DataForSEO search volumes (monthly cache), keyword research |
| `keyword_research.py` | 253 | AI keyword research via Gemini + DataForSEO enrichment |
| `road_to_one.py` | 417 | Per-keyword strategy: crawls your page + top 3 competitors, AI generates action plan |
| `ai_strategist.py` | 584 | 4 modes: master strategy, weekly plan, keyword portfolio analysis, strategic chat |
| `strategist_routes.py` | 105 | Routes for strategist + cannibalization detection |
| `geo_engine.py` | 465 | GEO audit (5 AI search categories), citation testing |
| `geo_fix_engine.py` | 427 | GEO fix scanner — 6 fix types via approval queue |
| `geo_routes.py` | 101 | GEO audit + citation + scan endpoints |
| `content_writer.py` | 273 | AI content generator: blog posts, product descriptions, landing pages, FAQ, how-to guides |
| `content_decay.py` | 366 | Page freshness monitoring, competitor comparison, refresh recommendations |
| `linking_engine.py` | 352 | Hub & Spoke: crawls site, maps link graph, finds hubs/orphans, AI link suggestions |
| `ga4_data.py` | 286 | GA4 traffic: sessions, users, pageviews, bounce rate, sources, daily trend |
| `reporting.py` | 306 | Monthly report aggregation, since-inception tracking, ranking changes |
| `report_routes.py` | 398 | PDF generation with fpdf2 |
| `ai_overseer.py` | 208 | Weekly automation: audit → keywords → GEO → fixes → strategy |
| `requirements.txt` | 13 | fastapi, uvicorn, sqlalchemy, psycopg2-binary, httpx, beautifulsoup4, fpdf2, google-auth, etc. |

## Frontend Files (`frontend/`)

| File | Lines | Purpose |
|---|---|---|
| `app/page.tsx` | 574 | Auth gate (login screen), sidebar nav, tab routing, global fetch interceptor for Bearer token |
| `app/globals.css` | 75 | Dark theme, `color-scheme: dark`, chart tooltips |
| `components/AuditDashboard.tsx` | 461 | Audit results, issue filters, CWV, integration checklist |
| `components/KeywordTracker.tsx` | 1121 | Rankings table, NEW/lost badges, tracked keywords, country breakdown, search volumes, charts |
| `components/RoadToOne.tsx` | 405 | Per-keyword strategy cards, competitor crawl results |
| `components/AIStrategist.tsx` | 540 | 4 tabs: master strategy, weekly plan, portfolio, chat |
| `components/GEODashboard.tsx` | 333 | GEO scores, citation tester, fix generator |
| `components/ContentWriter.tsx` | 419 | Create content (5 types), AI ideas linked to R2#1, library |
| `components/CompetitorAnalysis.tsx` | 427 | Competitor research (AI crawl+compare), Hub & Spoke, Content Decay |
| `components/ReportingDashboard.tsx` | 579 | Interactive SVG charts (hover tooltips), keyword click-to-trend, PDF |
| `components/IntegrationSetupChecklist.tsx` | 477 | Google OAuth, Shopify form (client_id+secret), WordPress form (app password) |
| `components/OverviewDashboard.tsx` | 214 | Per-website summary cards |

## Environment Variables (Railway Backend)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL (Railway provides) |
| `GOOGLE_CLIENT_ID` | Google OAuth for GSC + GA4 |
| `GOOGLE_CLIENT_SECRET` | Google OAuth |
| `GOOGLE_REDIRECT_URI` | `https://backend-production-6104.up.railway.app/api/integrations/oauth/google/callback` |
| `GOOGLE_GEMINI_API_KEY` | Gemini 2.0 Flash — ALL AI features |
| `GOOGLE_PAGESPEED_API_KEY` | PageSpeed Insights CWV data |
| `SHOPIFY_CLIENT_ID` | LEGACY — canvas-wallart OAuth only |
| `SHOPIFY_CLIENT_SECRET` | LEGACY — canvas-wallart OAuth only |
| `DATAFORSEO_LOGIN` | Search volume API |
| `DATAFORSEO_PASSWORD` | Search volume API |
| `AUTH_USERNAME` | Dashboard login |
| `AUTH_PASSWORD` | Dashboard password |
| `ANTHROPIC_API_KEY` | Optional fallback AI |
| `PORT` | Server port (Railway sets this) |

## Database Schema (SQLAlchemy models in `database.py`)

**User** — id, email, name, created_at
**Website** — id, user_id, domain (unique), site_type, shopify_store_url, shopify_access_token, monthly_traffic, api_key, last_audit, is_active
**AuditReport** — id, website_id, audit_date, health_score, technical/content/performance/mobile/security scores, total_issues, critical_issues, errors, warnings, detailed_findings (JSON)
**ContentItem** — id, website_id, title, content_type, publish_date, status, keywords_target (JSON), ai_generated_content (Text)
**Integration** — id, website_id, integration_type, status, access_token, refresh_token, connected_at, last_synced, account_name, scopes (JSON), config (JSON)
**ProposedFix** — id, website_id, fix_type, platform, resource_type, resource_id, resource_url, resource_title, field_name, current_value, proposed_value, ai_reasoning, severity, category, status, batch_id, applied_at, error_message
**KeywordSnapshot** — id, website_id, snapshot_date, date_from, date_to, total_keywords, total_clicks, total_impressions, avg_position, avg_ctr, gsc_property, keyword_data (JSON)
**TrackedKeyword** — id, website_id, keyword, current_position, current_clicks, current_impressions, current_ctr, target_url

## API Endpoints (key ones)

**Auth:** POST `/api/auth/login`, GET `/api/auth/check`, POST `/api/auth/logout`
**Websites:** GET/POST `/websites`, DELETE `/websites/{id}`
**Audit:** GET `/api/audit/{id}`, POST `/api/audit/{id}/start`, GET `/api/audit/{id}/history`
**Keywords:** GET `/api/keywords/{id}`, POST `/api/keywords/{id}/sync`, GET `/api/keywords/{id}/history`, GET `/api/keywords/{id}/keyword-history?keyword=X`
**Tracked:** GET `/api/keywords/{id}/tracked`, POST `/api/keywords/{id}/track`
**Road to #1:** POST `/api/keywords/{id}/track/{kw_id}/strategy`
**Fixes:** POST `/api/fixes/{id}/scan`, GET `/api/fixes/{id}?status=pending`, POST `/api/fixes/{fix_id}/approve`, POST `/api/fixes/{id}/batch/apply`
**Strategist:** POST `/api/strategist/{id}/generate-strategy`, POST `/api/strategist/{id}/weekly-plan`, GET `/api/strategist/{id}/portfolio`, POST `/api/strategist/{id}/chat`
**Content:** POST `/api/content/{id}/generate`, POST `/api/content/{id}/ideas`, GET `/api/content/{id}/list`
**GEO:** POST `/api/geo/{id}/audit`, POST `/api/geo/{id}/test-citation`, POST `/api/geo/{id}/scan-fixes`
**Competitors:** POST `/api/competitors/{id}/research`
**Reports:** GET `/api/reports/{id}`, GET `/api/reports/{id}/pdf`
**Integrations:** POST `/api/integrations/{id}/connect`, GET `/api/integrations/{id}/status`
**GA4:** GET `/api/ga4/{id}/traffic?days=30`
**Linking:** POST `/api/linking/{id}/analyze`
**Decay:** POST `/api/decay/{id}/analyze`

## Automation

- **Daily audits:** 3 AM UTC, daemon thread in `main.py`
- **Weekly overseer:** Monday 4 AM UTC — audit → keywords → GEO → fixes → strategy for all sites
- **Shopify token refresh:** Auto on every fix scan/apply (24h expiry)
- **DataForSEO cache:** Monthly — check `last_fetched` before calling
