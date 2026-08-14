# Equinet Academy — SEO Command Centre

An interactive SEO dashboard for all Equinet Academy course landing pages, targeting Google Singapore.
It answers one question: **"What should we do next to move each course landing page onto Page 1, and ideally into positions 1–3?"**

## Quick start

Open **`index.html`** in any browser (double-click works — no server needed).

## What's inside

| View | What it shows |
|---|---|
| **Overview** | Courses tracked, target keywords, Page-1 / top-3 counts, improved / declined / new / lost rankings, position distribution, top movers, courses with no organic visibility |
| **Course SEO Opportunities** | Per keyword: course, volume, KD, current + previous rank, change, competitor (+ ranking URL & DR), keyword gap, opportunity, recommended action, priority, ClickUp button |
| **Rank Tracking** | Previous rank, current rank, change, trend (↑/↓/→), date checked, and the full dated history chain (e.g. `14 Jul: #5 → 14 Aug: #5 → 21 Aug: #3`) |
| **Supporting Content** | Blog-content recommendations checked against the existing Equinet blog: existing article(s), cannibalisation risk, Optimise-Existing vs Create-New vs No-Action, internal-linking plan, reason |
| **Action Plan** | Prioritised SEO tasks with action type, expected objective, priority, status, and ClickUp task creation |

Filters (course, keyword search, position bucket, trend, priority, action type, ClickUp status) apply across the table views. Column headers sort.

## Rank tracking & history

Rankings are stored as **dated snapshots, never overwritten**:

- Baseline **14 Jul 2026** and snapshot **14 Aug 2026** come from Ahrefs (embedded in `data/seo-data.js`, also archived under `data/snapshots/`).
- Click **Log rank** on any keyword after a new rank check to append a snapshot. Trend and change recompute automatically.
- Logged snapshots live in the browser's localStorage — use **Export data + history** to back them up / share, and **Import history** to restore on another machine.
- For the next full refresh, re-run the Ahrefs pull and update `data/seo-data.js` (see `scripts/build_data.py` — the dataset is generated from it).

## ClickUp integration

Every recommendation has a **Create ClickUp Task** button that creates the recommendation as a **subtask under the matching course parent task** in
[SEO Content View (list 901814205053)](https://app.clickup.com/90181914545/v/li/901814205053).

- Add your ClickUp personal API token once via **⚙ ClickUp token** (ClickUp → Settings → Apps → API Token). It is stored only in your browser.
- The parent-task mapping (course → existing ClickUp parent task ID) is embedded in the dataset — no new parent tasks are ever created.
- **Duplicate prevention:** before creating, the dashboard checks the parent task's existing subtasks for the same title and links the existing task instead of duplicating. Actions already covered by a pre-existing ClickUp task (e.g. *Optimise Agentic AI SEO Cluster*, *Optimise Digital Marketing Foundations SEO Rankings*, TikTok striking-distance, Canva guide) show that task up-front.
- After creation the row shows **✓ ClickUp Task Created** with the task ID/link.
- Task descriptions include: target keyword, current/previous rank, volume, KD, competitor + URL, current & recommended target URL, recommended changes, expected objective, priority, and the source-dashboard snapshot reference.

## Data sources (snapshot 2026-08-14)

- **Ahrefs Site Explorer** — organic keywords for equinetacademy.com, Google SG, 2026-08-14 vs 2026-07-14 (previous ranks)
- **Ahrefs Keywords Explorer (SG)** — search volume, keyword difficulty, CPC, intent for target keywords
- **Ahrefs SERP Overview (SG)** — competitor positions, URLs and domain ratings for priority course keywords
- **ClickUp** — parent course tasks in the SEO Content View
- Course + blog inventory — equinetacademy.com crawl data (all `/course/` pages and `/blog/` articles)

## Files

```
index.html               the dashboard (self-contained; loads data/seo-data.js)
data/seo-data.js         dataset consumed by the dashboard
data/seo-data.json       same dataset, canonical JSON
data/snapshots/          dated rank snapshots (2026-07-14 baseline, 2026-08-14)
scripts/build_data.py    generates the data files (edit + rerun for refreshes)
```

## Headline findings (14 Aug 2026)

- **Biggest issue:** "digital marketing course" (700/mo) dropped **#1 → #10** and "digital marketing courses singapore" (300/mo) **#1 → #11** — hub/blog cannibalisation; recovery is the single largest traffic win.
- **Biggest untapped gaps (KD 0, zero visibility):** Power BI (350/mo), cybersecurity course (500/mo, KD 2), video editing (250/mo), generative AI (400/mo, KD 7), tableau (150/mo), prompt engineering (300+350/mo).
- **Striking-distance wins:** SEO course #5, social media #6, TikTok #6, Google Ads #8, UX/UI cluster #5–#9 (needs cannibalisation fix first).
- **Defend:** content creation course #2, WordPress #2, seo courses singapore #1, seo certification #1.
