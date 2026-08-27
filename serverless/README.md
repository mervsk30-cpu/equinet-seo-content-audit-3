# Live Google rank proxy

Gives the dashboard a **Live Google Rank** column: a real Google search run at
the moment you look, using Singapore search settings, so the number should match
what you see searching Google yourself.

## Why a proxy is required

The dashboard is a static page in a **public** repo, served from a **public**
GitHub Pages site. A SERP API key placed in it would be readable by anyone
viewing source, and browsers would block the cross-origin call regardless. This
Worker keeps the key server-side and returns only a position number.

## What it costs, and why it can't run away

Fetching live ranks "on open" is the expensive pattern — every page view, every
team member, every keyword. Three brakes keep it bounded:

| Brake | Default | Effect |
|---|---|---|
| `CACHE_TTL_SECONDS` | 3600 (1h) | Five people opening the same course in an hour = **1** search per keyword, not five |
| `DAILY_BUDGET` | 500/day | Atomic hard stop. Past it, last-known values still serve (flagged `stale cache`); **nothing further is billed** |
| `RATE_LIMIT_PER_MIN` | 60/IP | Strongly consistent per-IP limit stops the public endpoint being hammered |
| `STALE_TTL_SECONDS` | 30 days | Keeps a last-known value available after the one-hour fresh cache expires |

The dashboard also only requests live ranks for the **rows currently on screen**
(100 max per page), never all 2,808 keywords. It sends them in 25-key batches:
10 visible rows use one request; a full 100-row page uses four. The Worker runs
at most five provider requests concurrently and stays below the Workers Free
external-subrequest limit.

Workers KV holds the result caches. A SQLite-backed Durable Object coordinates
the daily budget and rate limit because KV counters are eventually consistent
and cannot guarantee a hard ceiling under concurrent requests.

Realistic weekly usage: a few team members reviewing a handful of courses ≈
100–400 searches/week. Tune `DAILY_BUDGET` to whatever your SerpAPI plan allows.

## Deploy (~10 minutes)

1. **Get a SERP API key.** [serpapi.com](https://serpapi.com) → API key. (You
   already have a SerpAPI credential in your n8n workspace — the same account
   may work.)

2. **Install Wrangler and log in:**
   ```bash
   npm install -g wrangler
   wrangler login
   ```

3. **Create the KV namespace** (holds only search-result caches):
   ```bash
   cd serverless
   npx wrangler kv namespace create LIVE_RANK
   ```
   Paste the printed `id` into `wrangler.toml` under `[[kv_namespaces]]`.

   The atomic coordinator is declared in `wrangler.toml` and is provisioned
   automatically on the first deploy; there is no ID to paste for it.

4. **Set the SerpAPI secret** (never commit it or place it in dashboard data):
   ```bash
   npx wrangler secret put SERP_API_KEY
   ```

5. **Deploy:**
   ```bash
   npx wrangler deploy
   ```
   Note the URL, e.g. `https://equinet-live-rank.<subdomain>.workers.dev`.

6. **Point the dashboard at it** — in `data/keywords-config.json`:
   ```json
   "settings": {
     "live_rank": {
       "endpoint": "https://equinet-live-rank.<subdomain>.workers.dev",
       "token": "",
       "device": "desktop"
     }
   }
   ```
   Then `python scripts/build_dashboard_data.py`, commit and push. The Live
   Google Rank column activates automatically.

   There is deliberately no auto-fetch setting. Live checks are on demand only:
   the dashboard never searches on open, reload, filter, paging or navigation,
   so a credit is spent only when someone clicks Check / ↻ on a keyword, or
   confirms the bulk re-check.

Until step 6 is done the column simply shows a "not configured" note — the rest
of the dashboard is unaffected.

## Accuracy notes

- **Organic position only.** Ads, local packs, "People also ask" and AI
  Overviews are excluded, matching how Ahrefs counts. On a real SERP your result
  may appear further down the page than the number suggests.
- **Not in top 100** (`DEPTH`) is reported as *not found*, never guessed.
- Google personalises by signed-in history and precise location. The Worker
  pins country, language, location and device and disables personalisation, so
  it matches a clean/incognito Singapore search more closely than a signed-in one.
- Google results genuinely fluctuate through the day; two checks minutes apart
  can differ by a position. That is Google, not a bug.

## Testing without spending

```bash
cd serverless
npm test                               # Worker contract and cost-control tests
node mock-live-rank.js                 # fake UI results on :8787
```
Point `live_rank.endpoint` at `http://localhost:8787` to exercise the UI with no
API spend. Mock values are obviously fake and clearly flagged.

The automated tests cover success, not-in-top-100, fresh cache, stale cache,
concurrent hard-cap enforcement, rate limiting, provider errors, origin checks,
and malformed requests without making any external calls.
