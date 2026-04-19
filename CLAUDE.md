# CLAUDE.md — SEO Intelligence Platform

## What This Is
Personal SEO platform for monitoring and optimizing unlimited e-commerce websites (Shopify, WordPress, custom). Single user (Arman), NOT a SaaS. FastAPI backend + Next.js frontend on Railway, PostgreSQL, Gemini 2.0 Flash for all AI.

Backend: `backend/` → deployed at `https://backend-production-6104.up.railway.app`
Frontend: `frontend/` → uses `NEXT_PUBLIC_API_URL` env var
DB: Railway PostgreSQL, auto-deploys from GitHub main branch.

## Critical Rules

### Token Preservation
- **NEVER rewrite entire files.** Only edit the specific lines that need changing.
- Read files with targeted line ranges before editing.
- Don't add comments to existing code unless asked.
- Don't regenerate working code to "improve" it.

### Verification Before Editing
- Before applying a fix, use a Sonnet sub-agent to verify the change is correct.
- Check for: syntax errors, missing imports, broken references, unintended side effects.
- Read the surrounding code context first — don't edit blind.

### Commit + Push Workflow
- **Batch all changes across a full turn before pushing.** Do NOT commit-and-push after each individual edit. Wait until every change the user asked for in the current turn is complete, then do ONE `git add -A && git commit -m "<short>" && git push` at the very end.
- Keep commit messages short: "fix shopify token refresh" not "Updated integrations.py to improve the Shopify token refresh mechanism"
- Group related changes into one commit.

### Code Style
- **Backend:** Python, `print()` logging with `[Module]` prefix, no verbose type hints on simple functions.
- **Frontend:** TypeScript React, Tailwind CSS, `lucide-react` icons, functional components.
- **UI:** Dark theme — `bg-white/5`, `border-white/10`, purple/pink gradients, glassmorphism.
- Don't add `framer-motion` to new components unless asked.
- when you have made a mistake, log it and add it to the .md for things not to try next time. essentially I want this to act like an experimenters or researchers journal of what a future claude instance should not to while working on this project

## Architecture Quick Ref

| Layer | Stack |
|---|---|
| Backend | FastAPI, SQLAlchemy, httpx, BeautifulSoup, fpdf2 |
| Frontend | Next.js, Tailwind, lucide-react, framer-motion |
| AI | Gemini 2.0 Flash (`GOOGLE_GEMINI_API_KEY`) |
| DB | PostgreSQL (Railway) |
| Auth | Bearer token middleware, 72h sessions, localStorage |

## Active Gotchas

**Shopify multi-store:** Each store needs its OWN custom app (created in that store's admin). Per-store `client_id` + `client_secret` entered via dashboard form → backend does `client_credentials` grant → gets 24h `shpat_` token that auto-refreshes. The global `SHOPIFY_CLIENT_ID` env var is LEGACY (canvas-wallart only) — do NOT use it for new stores.

**WordPress REST API blocked:** Security plugin strips Authorization header. Fixes use XML-RPC fallback (`wp.editPost`). Connection test confirms this automatically. Don't try to "fix" the REST API auth — XML-RPC is the working path.

**Fix engine checks integrations, not site_type:** A website added as `site_type: 'custom'` can still use Shopify/WordPress fixes if the integration is connected. The fix engine queries the Integration table.

**Database migrations:** New columns MUST use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in `main.py` startup. Never use `Base.metadata.create_all()` for schema changes — it won't add columns to existing tables.

**DataForSEO:** Search volumes cached MONTHLY to control costs. Always check cache before calling API.

**Gemini rate limits:** Free tier hits 429 fast during fix scans (generates alt text per image). Need billing enabled or batch requests.

## What NOT to Do

- Don't add multi-tenancy, user registration, or billing.
- Don't swap Gemini for GPT-4/Claude — cost decision.
- Don't add `torch`, `sklearn`, `transformers` — too heavy for Railway.
- Don't use global `SHOPIFY_CLIENT_ID` for new store connections.
- Don't hardcode anything to specific websites — platform handles unlimited sites.
- Don't change Railway deployment config.
- Don't create new DB tables without migration in `main.py` startup.

## Reference Docs

- `docs/REFERENCE.md` — Full file map, env vars, API endpoints, DB schema
- `docs/INTEGRATIONS.md` — Shopify, WordPress, Google OAuth, DataForSEO patterns
- `docs/ISSUES.md` — Current blockers and pending items

## User Context

Arman runs multiple e-commerce businesses. Prefers working code over explanations. Tests on deployed frontend. Values speed and getting it right first time. Don't over-explain — just fix and commit.
