# Equinet Academy — SEO Keyword Ranking Dashboard

A simple, self-contained dashboard tracking Google keyword rankings for every
Equinet Academy course landing page, powered by **real Google Search Console
data** with an automatic **weekly refresh every Monday** and permanent weekly
history.

**Open `index.html`** (locally, or via GitHub Pages) to view the dashboard.

## Three real data sources, kept separate

| | Google Search Console | Ahrefs Rank Tracker | Live Google Rank |
|---|---|---|---|
| What it is | **Average** position across impressions (decimal, shown rounded) | **Actual** SERP position from a scheduled real search | **Actual** SERP position from a search run **right now** |
| Freshness | 7-day window, 2–3 day lag | Re-checked weekly (Mondays) | The moment you open the page or hit refresh |
| Also provides | Impressions, clicks, CTR, desktop/mobile | Volume, keyword difficulty, ranking URL | Ranking URL, exact check timestamp |
| Columns | Current, Previous, Change, Desktop, Mobile, Impr., Clicks, CTR | Ahrefs Rank, Volume, KD | Live Google Rank |
| Cost | Free | Free (0 API units) | Paid per search — capped, see below |

They measure the same thing differently and are **never averaged or blended** —
each keeps its own columns. A keyword can legitimately show GSC average 7.3,
Ahrefs #2 and Live #1: GSC averages every impression (including ones where the
result sat lower), Ahrefs reports last Monday's check, and Live is Google right now.

### Live Google Rank

A real Google search, Singapore settings (`google.com.sg`, `gl=sg`, `hl=en`,
location Singapore, chosen device, personalisation off), so it should line up
with what you see searching manually. Each cell shows the position and the exact
time it was checked.

**Every live check is on demand. Nothing searches by itself.** A cell starts as
a **Check** button; clicking it (or ↻ to re-check) runs one Google search for
that one keyword. Opening the dashboard, reloading it, filtering, searching,
paging, switching course or tab, and changing the live device all render from
data already loaded and cost nothing. The Ahrefs Rank column — the weekly
position — is what you see by default.

The toolbar's **↻ Re-check visible rows** is the only bulk path, and it names
the exact number of searches and asks for confirmation before spending. Behind
that, the proxy caches each result for an hour and enforces a hard daily
ceiling, after which it serves cached values instead of spending. Setup:
[`serverless/README.md`](serverless/README.md).

Two things to know: it reports **organic** position (ads, map packs and AI
Overviews aren't counted, so your result may sit lower on the page than the
number implies), and it works on the **GitHub Pages** dashboard, not the
claude.ai artifact snapshot — that sandbox blocks outbound network calls.

When Ahrefs reports a keyword ranking on a *different* page than the course
you're viewing, the Ahrefs Rank cell shows a **↗ other page** flag — a useful
cannibalisation signal rather than a hidden mismatch.

## Cannibalisation view

The **⚠ Cannibalisation** button lists every query where two or more of your
course pages rank at the same time. Search Console counts an impression for
*every* URL of yours that appears for a search, but a searcher can only click
one of them — so when several pages surface for one query, impressions multiply
while clicks cannot. That is a large part of why healthy impression counts sit
next to zero clicks elsewhere in the dashboard.

Each group shows every competing page with its position, impressions and
clicks. The page carrying the **most impressions** is marked `OWNS` — position
alone is a bad owner test, because a trailing-slash URL variant can sit at #1
on a single impression while the page doing the real work ranks #8 on two
hundred. Impressions on the other pages are counted as **trailing**.

Trailing impressions are *not* lost clicks and are never presented as such —
they measure how far a query is split across your pages. `weeks_seen` counts
how many recorded weeks show the same split, so a persistent structural problem
is distinguishable from one noisy week. Groups under
`MIN_CANNIBAL_IMPRESSIONS` (10) total impressions are left out as noise.

## Data policy — no fabricated numbers, ever

- Every ranking, impression, click and CTR figure comes from the Google Search
  Console API. Nothing is estimated, interpolated, or demo data.
- If Search Console has no data for a keyword, the cell is **blank**. It is
  never filled in from another source or guessed at.
- "No impressions in Search Console" is **not** the same as "not ranking".
  Search Console only reports a keyword once somebody has actually seen it in
  the results, so a page can sit at #1 for a low-volume term and still be
  absent from GSC. The dashboard therefore checks Ahrefs Rank Tracker as a
  second source before deciding a keyword is not ranking (see the status table
  below), and says plainly when neither source has checked it.
- If a weekly refresh fails, the dashboard shows an **explicit error banner**
  and labels the last successful week — it never presents old data as current.
- Weekly snapshots are **immutable**: the collector refuses to overwrite an
  existing week, so history is preserved forever.

## How it works

```
GitHub Actions (every Monday 08:15 SGT)
  └─ scripts/collect_gsc.py      query+page+device rows from the GSC API
       └─ data/snapshots/gsc-YYYY-MM-DD.json          (immutable weekly snapshot)
  └─ scripts/collect_ahrefs.py   SERP positions + volume/KD from Ahrefs Rank Tracker
       └─ data/ahrefs-snapshots/ahrefs-YYYY-MM-DD.json (immutable weekly snapshot)
  └─ scripts/build_dashboard_data.py
       └─ data/dashboard-data.js  (comparisons, statuses, history, both sources)
  └─ commit + push
index.html reads data/dashboard-data.js  →  the dashboard
```

Each Monday-labelled snapshot covers the **7-day window ending 3 days before
the run** (Search Console data takes ~2–3 days to finalise). Example: the run
on Monday 24 Aug 2026 covers Sat 15 – Fri 21 Aug.

### Ranking statuses (computed on whole-number positions)

| Status | Meaning |
|---|---|
| Improved | Ranked both weeks, better (lower) position this week |
| Dropped | Ranked both weeks, worse position this week |
| Stable | Same rounded position both weeks |
| Newly Ranking | Has a position this week, none last week |
| Lost | Ranked in a previous week (shown with "since"), no position this week |
| Ranking (first week) | Only one snapshot exists, so there is no baseline yet |
| Ranking · no impressions | No GSC data, but Ahrefs Rank Tracker has a real SERP position — it ranks, nobody has searched it yet |
| Not Ranking | Ahrefs checked this keyword and found no position — genuinely not ranking |
| Not Checked | Neither GSC nor Ahrefs has data. Usually a target keyword that isn't in the Rank Tracker project yet |

Positions are GSC average positions displayed as whole numbers (e.g. `#7`,
never `7.3`). Desktop and mobile are shown separately as `10 → 7 (↑3)` where
device data exists.

The first six statuses all mean **currently ranking**, and the dashboard opens
filtered to exactly those. Not-Ranking and Not-Checked keywords are hidden by
default to keep the table focused, but they are still tracked and one chip
click away — the Primary and Secondary keywords sitting in there are the
optimisation backlog, which is why they are hidden rather than deleted.

## One-time setup (required before the first data pull)

The pipeline needs a Google service account that can read the Search Console
property. This takes ~10 minutes:

1. **Create a service account.** In [Google Cloud Console](https://console.cloud.google.com/)
   create (or pick) a project → *APIs & Services → Enable APIs* → enable
   **Google Search Console API** → *IAM & Admin → Service Accounts → Create*.
   No project roles are needed. Create a **JSON key** and download it.
2. **Grant it Search Console access.** In
   [Search Console → Settings → Users and permissions](https://search.google.com/search-console/users)
   for the **`equinetacademy.com` domain property**, add the service account's
   email (`…@….iam.gserviceaccount.com`) with **Full** permission.
   (If you use the `https://www.equinetacademy.com/` URL-prefix property
   instead, set `settings.gsc_property` in `data/keywords-config.json` to that
   URL.)
3. **Add the repo secret.** GitHub → repo → *Settings → Secrets and variables →
   Actions* → new secret **`GSC_SERVICE_ACCOUNT_JSON`** with the entire JSON
   key file content as the value.
4. **First pull with history backfill.** GitHub → *Actions → Weekly GSC
   refresh → Run workflow*, set `backfill_weeks` to `8` (or up to ~65 — GSC
   keeps 16 months). This creates real historical weekly snapshots, so
   week-over-week comparisons and trends appear immediately.
5. **Enable the Monday schedule.** GitHub only runs scheduled workflows from
   the **default branch**, so merge this branch to `main`. The job then runs
   every Monday 00:15 UTC (08:15 Singapore) automatically.
6. *(Optional)* **GitHub Pages.** Repo *Settings → Pages* → deploy from the
   default branch root. The dashboard is a static page; `data/dashboard-data.js`
   keeps it working both on Pages and opened directly from disk.

### Ahrefs Rank Tracker (for the Ahrefs Rank / Volume / KD columns)

Add one more repository secret, **`AHREFS_API_KEY`** — an Ahrefs API key with
read access to Rank Tracker project `369315` ("Equinet Academy Courses").
Generate it at *Ahrefs → Account settings → API keys*.

Notes:
- **Never commit the key.** This repository is public; the key belongs only in
  GitHub Actions secrets.
- Rank Tracker calls did **not** consume API units on the current Ahrefs plan,
  so the weekly pull is effectively free. (The Ahrefs workspace was over its
  monthly unit limit when this was built and Rank Tracker still worked, while
  unit-billed endpoints such as Site Explorer were refused.)
- If the secret is absent the weekly job logs a warning and continues with
  Search Console data only — the Ahrefs columns simply stay blank. A missing
  or broken Ahrefs pull never fails the GSC refresh.
- The API caps responses at 500 rows with no offset parameter, so
  `scripts/collect_ahrefs.py` paginates by position range and **splits any
  bucket that comes back full**, which stops coverage silently degrading as the
  tracked keyword list grows.

## Configuration

`data/keywords-config.json` is the single editable config:

- `settings` — GSC property, country filter (`"sgp"` = Singapore positions, the
  market the team tracks; set to `null` for worldwide), refresh window rules.
- `courses[]` — every course landing page (name, URL, legacy URL aliases) with
  its keywords. Keyword `type` is `primary` / `secondary` / `supporting`
  (see rules below); the dashboard groups the table in the fixed order
  **Primary → Secondary → Supporting → Discovered**, skipping any type a course
  has none of. Queries found in GSC that aren't configured are added
  automatically as **discovered** — but only once they accumulate 5+ total
  impressions across recorded weeks (`MIN_DISCOVERED_IMPRESSIONS` in
  `scripts/build_dashboard_data.py`). Course pages naturally pick up dozens of
  one-off, single-impression long-tail queries that are statistical noise, not
  real opportunities; this threshold is a *display* filter only — every raw
  GSC row stays in `data/snapshots/`, untouched, so lowering the threshold
  later re-surfaces the same real history rather than losing anything.
  Configured (primary/secondary/supporting) keywords are always shown regardless
  of impressions. The dashboard also paginates each course's table at 100 rows
  to keep large courses fast to browse.
- `unassigned_keywords` — tracked keywords with no current course page
  (legacy e-commerce course, agency-intent terms, etc.). Assign or delete as
  you see fit.

The initial keyword classification was generated by
`scripts/build_config_from_ahrefs.py` from the team's own curated Ahrefs Rank
Tracker list (`data/sources/ahrefs-tracked-keywords-2026-08-17.json` —
keyword text and tags only, no ranking metrics). Rules: bottom-funnel keyword
with course wording → `primary`; bottom-funnel without → `secondary`;
top-funnel → `supporting`. Entries with `mapping_review: true` are mappings worth
a human check (Web Design → WordPress course, UI/UX → Landing Page Design).
Course names and URLs were taken from the live site's course catalogue on
2026-08-17.

## Check Live Rank

Rankings on the dashboard come from weekly GSC data by design (accurate,
free, no API credits). The **Check live** button on each keyword opens a
Google search for that keyword with Singapore settings and personalisation
off, for manual spot-verification of the current SERP. The dashboard never
scrapes Google automatically.

## Running locally

```bash
pip install -r requirements.txt
export GSC_SERVICE_ACCOUNT_FILE=/path/to/key.json   # or GSC_SERVICE_ACCOUNT_JSON='{"…"}'
python scripts/collect_gsc.py --backfill 8   # real historical weekly snapshots
python scripts/build_dashboard_data.py
open index.html
```

Tests (`pip install pytest && python -m pytest tests/`) cover the comparison
engine: every status transition, device splits, rounding, window maths, lost
keyword tracking, and the no-data / stale / error states. Test fixtures are
clearly synthetic (`example.com`) and are never read by the dashboard, which
only consumes `data/snapshots/`.

## Data-access notes (as of 17 Aug 2026)

- The Ahrefs project "Equinet Academy Courses" has **no GSC connection**, so
  its `gsc-*` API endpoints return no data (the team's Make.com scenario
  "Equinet SEO: Weekly rank drop alert" already flags this). Connecting GSC
  inside Ahrefs would enable those endpoints, but this dashboard doesn't need
  it — it talks to the GSC API directly.
- This dashboard intentionally replaces Ahrefs Rank Tracker *modelled*
  positions with real Search Console data.
