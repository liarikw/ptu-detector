# P图 Detector 9000

A quirky, playful web app that inspects photos for signs of Photoshop / Facetune /
AI touch-ups and returns a **Sus Score** with a mock-forensic roast. Powered by
Google Gemini's free vision API.

**Meant as a joke.** It roasts the *pixels* (bent doorframes, warped tiles,
over-smoothed skin, mismatched shadows) — never the person. Don't use it to be
mean to anyone.

## Features

- **📁 Upload** — drag & drop up to 8 images. Bulletproof, no scraping.
- **🔗 Post URL** — paste an Instagram post/reel URL. Tries `instaloader`, falls back
  to `og:image` scraping.
- **👤 Profile** — pass an `@handle` and it audits their most recent posts. Flakiest
  option (Instagram may rate-limit).

Each image gets a Sus Score (0–100), a verdict (`Certified Raw Dog` →
`Uncanny Valley Alert`), a short roast, and a list of tells.

## Setup

Requires Python 3.9+.

```sh
cd ~/claudecode/ptu-detector
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Get a free Gemini API key

1. Go to <https://aistudio.google.com/apikey>
2. Sign in with any Google account
3. Click **Create API key** → pick a project (any) → **Copy the key**

No credit card required. Free-tier limits are ~15 requests per minute for
`gemini-2.5-flash` and 1500 requests per day — plenty for a joke tool.

Export the key or drop it in `.env`:

```sh
export GOOGLE_API_KEY=your-key-here
```

Or copy `.env.example` → `.env` and fill it in — the app auto-loads `.env` on start.

## Run locally

```sh
.venv/bin/uvicorn api.index:app --port 8123
```

Open <http://127.0.0.1:8123>.

## Notes and caveats

- **Model:** defaults to `gemini-2.5-flash`. To try Gemini Pro (slower, better),
  set `PTU_MODEL=gemini-2.5-pro` (still free tier, but lower rate limits).
- **Instagram scraping is fragile.** Instagram actively fights scrapers. URL and
  profile modes may break without notice. If IG is grumpy, use upload.
- **Do not** use profile crawl with a logged-in account you care about —
  `instaloader` can trigger checkpoints. This app doesn't log in.
- Aggregate score is a simple average of per-image scores.
- Requests are serialized (not parallel) to stay under the free-tier rate limit.
  A 5-image upload takes ~15–25s.

## Abuse protection (when you share it)

Two knobs (both are optional):

- `PTU_MAX_PER_HOUR` — per-IP rate limit (default `20`).
- `PTU_PASSCODE` — if set, all `/api/analyze/*` calls need `?passcode=…` in the URL
  or an `X-Passcode` header. Simplest way to keep a shared URL friends-only.

## Deploying so you can text friends a link

The included `Dockerfile` serves the whole app on one container. Vercel is the
easiest path if you know GitHub already.

### Vercel (via GitHub connection — recommended)

1. Push this project to a new GitHub repo (private or public — both work).
2. Go to <https://vercel.com/new>, log in with your GitHub account.
3. **Import** the repo. Framework preset: **Other**. Root Directory: `./`.
4. Under **Environment Variables**, add:
   - `GOOGLE_API_KEY` = your Gemini key
   - (optional) `PTU_PASSCODE` = a shared secret
5. **Deploy**. First build takes ~2 min.

Your URL: `https://<project-name>.vercel.app`.

Iterating later: edit code locally → `git push` → Vercel auto-deploys in ~60s.

### Vercel (via CLI — no GitHub needed)

```sh
npm i -g vercel
cd ~/claudecode/ptu-detector
vercel login
vercel
vercel env add GOOGLE_API_KEY
vercel --prod
```

### Hugging Face Spaces (also free, no card, no GitHub required)

1. <https://huggingface.co/new-space> → SDK: **Docker** → name it.
2. Upload the project files (web UI or `git push` to the space).
3. **Settings → Variables and secrets** → add `GOOGLE_API_KEY` as a secret.
4. Space auto-builds. URL: `https://<user>-<space>.hf.space`.

### Ngrok tunnel (zero-deploy, only up while your Mac is on)

```sh
# Terminal 1
export GOOGLE_API_KEY=your-key
.venv/bin/uvicorn api.index:app --port 8123

# Terminal 2
brew install ngrok/ngrok/ngrok
ngrok http 8123
```

Ngrok prints a temporary `https://xxxx.ngrok-free.app` URL. Text that to a
friend. URL changes each time you restart ngrok.

## Project layout

```
ptu-detector/
├── api/
│   ├── index.py       # FastAPI: /api/analyze/upload, /url, /profile, /health
│   ├── analyzer.py    # Gemini vision call + JSON schema
│   ├── scraper.py     # Instagram fetching (instaloader + og:image fallback)
│   └── ratelimit.py
├── public/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── Dockerfile
├── vercel.json
├── requirements.txt
├── .env.example
└── README.md
```

## Tone rules baked into the system prompt

The analyzer prompt in `api/analyzer.py` explicitly instructs the model to:

1. Never comment on the person's appearance, weight, or identity.
2. Only roast technical editing tells — bent lines, warped textures, weird shadows.
3. Celebrate low-sus photos with a compliment on their integrity.

If you tweak that prompt, keep those rules.
