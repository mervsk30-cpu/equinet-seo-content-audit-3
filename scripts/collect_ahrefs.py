#!/usr/bin/env python3
"""Weekly Ahrefs Rank Tracker collector.

Pulls real tracked-keyword rankings from the Ahrefs Rank Tracker API for the
team's project and writes an immutable weekly snapshot to
data/ahrefs-snapshots/ahrefs-<run-date>.json.

Why alongside Google Search Console:
  - GSC gives *average position* across impressions (a decimal, e.g. 7.3) plus
    the impressions/clicks/CTR that only Search Console knows.
  - Ahrefs Rank Tracker gives the *actual SERP position* (a whole number) that
    a checked search returned, plus search volume and keyword difficulty,
    which Search Console does not provide at all.
They are different measurements of the same thing and are kept in separate
fields - never averaged or blended together.

Data policy (same as the GSC collector):
  - Only rows the Ahrefs API returns are written. Nothing is estimated.
  - Existing snapshots are never overwritten (unless --force).
  - Failures are recorded in data/meta.json so the dashboard can show an
    explicit error rather than passing stale data off as current.

The API caps each response at 500 rows and offers no offset parameter, so this
paginates by position range and SPLITS ANY BUCKET THAT COMES BACK FULL - a
full bucket means rows were silently dropped. Without that, coverage would
quietly degrade as the tracked keyword list grows.

Auth: AHREFS_API_KEY (an Ahrefs API key with read access to the project).

Usage:
  python scripts/collect_ahrefs.py                     # this week's snapshot
  python scripts/collect_ahrefs.py --run-date 2026-08-31
  python scripts/collect_ahrefs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "data" / "keywords-config.json"
SNAPSHOT_DIR = ROOT / "data" / "ahrefs-snapshots"
META_PATH = ROOT / "data" / "meta.json"

API_URL = "https://api.ahrefs.com/v3/rank-tracker/overview"
ROW_CAP = 500  # server-side cap per response
SCHEMA_VERSION = 1
DEVICES = ("desktop", "mobile")
SELECT = "keyword,position,position_prev,url,volume,keyword_difficulty,tags,serp_updated"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def normalize_path(url_or_path: str | None) -> str | None:
    """Normalised URL path: lowercase, no query/fragment, trailing slash."""
    if not url_or_path:
        return None
    from urllib.parse import urlsplit
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        path = urlsplit(url_or_path).path
    else:
        path = url_or_path.split("?", 1)[0].split("#", 1)[0]
    path = (path or "/").lower()
    if not path.endswith("/"):
        path += "/"
    return path


def build_page_index(config: dict) -> dict[str, str]:
    index: dict[str, str] = {}
    for course in config["courses"]:
        for candidate in [course["url"], *course.get("aliases", [])]:
            p = normalize_path(candidate)
            if p:
                index[p] = course["code"]
    return index


def api_get(params: dict, key: str) -> list[dict]:
    import requests

    for attempt in range(5):
        try:
            resp = requests.get(
                API_URL,
                params=params,
                headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
                timeout=120,
            )
        except requests.exceptions.RequestException as exc:
            if attempt == 4:
                raise RuntimeError(f"Ahrefs API unreachable after retries: {exc}") from exc
            time.sleep(2 ** attempt)
            continue
        if resp.status_code in (408, 429, 500, 502, 503, 504):
            if attempt == 4:
                raise RuntimeError(f"Ahrefs API error {resp.status_code}: {resp.text[:300]}")
            time.sleep(2 ** attempt)
            continue
        if resp.status_code != 200:
            raise RuntimeError(f"Ahrefs API error {resp.status_code}: {resp.text[:300]}")
        return resp.json().get("overviews", [])
    raise RuntimeError("unreachable")


def fetch_range(lo: int, hi: int | None, base: dict, key: str) -> list[dict]:
    """Fetch one position range, splitting recursively if the response is full."""
    clauses: list[dict] = [{"field": "position", "is": ["gte", lo]}]
    if hi is not None:
        clauses.append({"field": "position", "is": ["lte", hi]})
    where = clauses[0] if len(clauses) == 1 else {"and": clauses}
    rows = api_get(dict(base, where=json.dumps(where), limit=ROW_CAP), key)

    if len(rows) < ROW_CAP:
        return rows
    # Response was full: rows were dropped. Split and recurse.
    if hi is None:
        # open-ended tail: bound it and recurse, then take everything above
        mid = lo + 50
        return fetch_range(lo, mid - 1, base, key) + fetch_range(mid, None, base, key)
    if lo >= hi:
        # cannot split further (a single position with 500+ keywords) - report loudly
        print(
            f"WARNING: position {lo} returned the full {ROW_CAP}-row cap and cannot be "
            "split further; some rows for this position were not retrieved.",
            file=sys.stderr,
        )
        return rows
    mid = lo + (hi - lo) // 2
    return fetch_range(lo, mid, base, key) + fetch_range(mid + 1, hi, base, key)


def fetch_unranked(base: dict, key: str) -> list[dict]:
    where = json.dumps({"field": "position", "is": "is_null"})
    rows = api_get(dict(base, where=where, limit=ROW_CAP), key)
    if len(rows) >= ROW_CAP:
        print(
            f"NOTE: unranked (no position) keywords hit the {ROW_CAP}-row cap; the list of "
            "not-currently-ranking keywords is partial. Ranked keywords are unaffected.",
            file=sys.stderr,
        )
    return rows


def collect_device(device: str, run_date: date, compare_date: date, config: dict, key: str) -> list[dict]:
    settings = config["settings"]
    base = {
        "project_id": settings["ahrefs_project_id"],
        "date": run_date.isoformat(),
        "date_compared": compare_date.isoformat(),
        "device": device,
        "select": SELECT,
        "output": "json",
    }
    rows = fetch_range(1, None, base, key) + fetch_unranked(base, key)

    page_index = build_page_index(config)
    out, seen = [], set()
    for r in rows:
        kw = " ".join((r.get("keyword") or "").lower().split())
        if not kw or (kw, device) in seen:
            continue
        seen.add((kw, device))
        path = normalize_path(r.get("url"))
        out.append({
            "keyword": kw,
            "device": device,
            "position": r.get("position"),
            "position_prev": r.get("position_prev"),
            "url": r.get("url"),
            "course": page_index.get(path) if path else None,
            "volume": r.get("volume"),
            "keyword_difficulty": r.get("keyword_difficulty"),
            "tags": r.get("tags") or [],
            "serp_updated": r.get("serp_updated"),
        })
    return out


def snapshot_path(run_date: date) -> Path:
    return SNAPSHOT_DIR / f"ahrefs-{run_date.isoformat()}.json"


def update_meta(**patch) -> None:
    meta = {}
    if META_PATH.exists():
        try:
            meta = json.loads(META_PATH.read_text())
        except json.JSONDecodeError:
            meta = {}
    meta.update(patch)
    tmp = META_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2) + "\n")
    tmp.replace(META_PATH)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-date", help="Run date (YYYY-MM-DD); defaults to today (UTC), normalised to that week's Monday.")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing snapshot for the same week (repair only).")
    ap.add_argument("--dry-run", action="store_true", help="Query Ahrefs and report counts without writing files.")
    args = ap.parse_args()

    try:
        config = load_config()
        settings = config["settings"]
        if not settings.get("ahrefs_project_id"):
            raise RuntimeError("settings.ahrefs_project_id is not set in data/keywords-config.json")

        key = os.environ.get("AHREFS_API_KEY")
        if not key:
            raise RuntimeError(
                "AHREFS_API_KEY is not set. Add it as a GitHub Actions secret "
                "(Settings -> Secrets and variables -> Actions). See README.md."
            )

        raw_date = date.fromisoformat(args.run_date) if args.run_date else datetime.now(timezone.utc).date()
        run_monday = monday_of(raw_date)
        compare_monday = run_monday - timedelta(weeks=1)

        path = snapshot_path(run_monday)
        if path.exists() and not args.force:
            print(f"skip {run_monday}: snapshot exists")
            return 0

        rows: list[dict] = []
        for device in DEVICES:
            got = collect_device(device, run_monday, compare_monday, config, key)
            print(f"{device}: {len(got)} rows ({sum(1 for r in got if r['position'] is not None)} ranked)")
            rows.extend(got)

        if args.dry_run:
            print(f"dry run: {len(rows)} rows total, nothing written")
            return 0

        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source": "ahrefs_rank_tracker_api",
            "project_id": settings["ahrefs_project_id"],
            "location": settings.get("ahrefs_location", "Singapore"),
            "run_date": run_monday.isoformat(),
            "compared_to": compare_monday.isoformat(),
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "row_count": len(rows),
            "rows": rows,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
        tmp.replace(path)
        print(f"wrote {path}")

        update_meta(
            ahrefs_last_run_status="ok",
            ahrefs_last_run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ahrefs_last_success_run_date=run_monday.isoformat(),
            ahrefs_last_error=None,
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - must surface as a dashboard error
        if not args.dry_run:
            update_meta(
                ahrefs_last_run_status="error",
                ahrefs_last_run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ahrefs_last_error=f"{type(exc).__name__}: {exc}",
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
