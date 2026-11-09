# Deploying Studeasy on free tiers

| Part | Host | Free-tier catch |
|---|---|---|
| Backend (FastAPI) | Render free web service, Frankfurt | 512 MB / 0.1 CPU; sleeps after 15 min idle (~1 min wake-up), kept warm by a GitHub Action |
| Frontend (React/Vite) | Cloudflare Pages | none relevant for a static site |
| Database + Auth | Supabase free (`stueasy` project) | pauses after a week without activity |
| AI | Mistral (Experiment plan) | free: about 1 request per second; requests may be used for training |

Order matters: backend first (the frontend needs its URL), then frontend, then wire the
two together with CORS and Supabase Auth URLs.

## 1. Backend on Render

1. render.com > sign in with GitHub > **New + > Blueprint** > pick this repo > **Apply**.
   `render.yaml` creates `studeasy-api` (Docker, free plan, Frankfurt).
2. Fill in the prompted secrets:
   - `MISTRAL_API_KEY` (console.mistral.ai → API Keys; `LLM_PROVIDER=mistral` is the default)
   - `SUPABASE_SERVICE_ROLE_KEY` (secret key from Supabase > Project Settings > API Keys)
   - `CORS_ORIGINS`: `["http://localhost:5173"]` for now; updated in step 3.
3. Wait for the deploy, then open `https://<service>.onrender.com/api/health`. It should return
   `{"status":"ok"}`. Note the URL.

## 2. Frontend on Cloudflare Pages

The frontend must be on `main` first (merge the `frontend` branch PR), because Pages
deploys from the production branch.

1. dash.cloudflare.com > **Workers & Pages > Create > Pages > Connect to Git** > pick this repo.
2. Build settings:
   - Framework preset: **Vite** (or none)
   - Root directory: `frontend`
   - Build command: `npm run build`
   - Build output directory: `dist`
3. Environment variables (Production):
   - `VITE_SUPABASE_URL` = `https://vglxdxdrtyicmgcmubqm.supabase.co`
   - `VITE_SUPABASE_ANON_KEY` = the **publishable** key (`sb_publishable_...`)
   - `VITE_API_URL` = the Render URL from step 1 (no trailing slash)
   - `NODE_VERSION` = `22`
4. Deploy, and note the URL (e.g. `https://studeasy.pages.dev`).
   `VITE_*` values are baked in at build time: after changing one, redeploy.

## 3. Wire them together

1. **Render > studeasy-api > Environment**: set
   `CORS_ORIGINS` = `["https://studeasy.pages.dev","http://localhost:5173"]` (your real Pages URL). Save; it redeploys.
2. **Supabase > Authentication > URL Configuration**:
   - Site URL: your Pages URL
   - Redirect URLs: add your Pages URL and `http://localhost:5173`

   Otherwise the sign-up confirmation email links to localhost.

## 4. Keep the backend warm

GitHub repo > **Settings > Secrets and variables > Actions > Variables > New repository variable**:
`BACKEND_URL` = your Render URL. The workflow `.github/workflows/keep-warm.yml` then pings
`/api/health` every 10 minutes. Trigger it once by hand from the **Actions** tab to check.

One always-on service uses ~720 of Render's 750 free hours a month, so this fits.

## Checks after deploying

```bash
cd backend
uv run python scripts/smoke_test.py --api https://<service>.onrender.com
```

(uses your local `.env` for the Supabase admin calls, so run it from `backend/`).
