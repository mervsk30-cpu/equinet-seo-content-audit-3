#!/usr/bin/env python3
"""Weekly Google Search Console collector.

Pulls real Search Analytics data (query + page, plus device split) from the
Google Search Console API for the course landing pages defined in
data/keywords-config.json, and writes an immutable weekly snapshot to
data/snapshots/gsc-<run-date>.json.

Data policy (non-negotiable):
  - Only rows returned by the GSC API are written. Nothing is estimated,
    interpolated, or invented. If the API returns no row for a keyword,
    that keyword simply has no data for the week.
  - Existing snapshots are never overwritten (unless --force is passed
    explicitly, e.g. to repair a corrupted file).
  - On any failure the script records the error in data/meta.json and exits
    non-zero WITHOUT touching existing snapshots, so the dashboard shows an
    explicit error instead of passing stale data off as current.

Auth: a Google service account with access to the GSC property.
  Set GSC_SERVICE_ACCOUNT_JSON to the JSON key (the content, not a path),
  or GSC_SERVICE_ACCOUNT_FILE to a path to the key file.

Windows: each run labelled by its Monday run date covers the 7-day window
ending `window_lag_days` (default 3) before the run date, because GSC data
takes ~2-3 days to finalise. Example: run Monday 2026-08-24 -> window
Sat 2026-08-15 .. Fri 2026-08-21.

Usage:
  python scripts/collect_gsc.py                    # this week's snapshot
  python scripts/collect_gsc.py --backfill 8       # also create the 8 prior weekly snapshots (real historical GSC data)
  python scripts/collect_gsc.py --run-date 2026-08-24
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "data" / "keywords-config.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
META_PATH = ROOT / "data" / "meta.json"

GSC_ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
ROW_LIMIT = 25000
SCHEMA_VERSION = 1


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def normalize_path(url_or_path: str) -> str:
    """Return a normalised URL path: lowercase, no query/fragment, trailing slash."""
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        path = urlsplit(url_or_path).path
    else:
        path = url_or_path.split("?", 1)[0].split("#", 1)[0]
    path = path.lower() or "/"
    if not path.endswith("/"):
        path += "/"
    return path


def build_page_index(config: dict) -> dict[str, str]:
    """Map normalised path -> course code, for canonical URLs and aliases."""
    index: dict[str, str] = {}
    for course in config["courses"]:
        for candidate in [course["url"], *course.get("aliases", [])]:
            index[normalize_path(candidate)] = course["code"]
    return index


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def compute_window(run_date: date, settings: dict) -> tuple[date, date]:
    lag = int(settings.get("window_lag_days", 3))
    days = int(settings.get("window_days", 7))
    end = run_date - timedelta(days=lag)
    start = end - timedelta(days=days - 1)
    return start, end


def get_access_token() -> str:
    """Fetch an OAuth2 access token for the service account."""
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
    except ImportError:
        raise RuntimeError(
            "google-auth is not installed. Run: pip install -r requirements.txt"
        )

    raw = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
    key_file = os.environ.get("GSC_SERVICE_ACCOUNT_FILE")
    if raw:
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    elif key_file:
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
    else:
        raise RuntimeError(
            "No GSC credentials. Set GSC_SERVICE_ACCOUNT_JSON (key content) or "
            "GSC_SERVICE_ACCOUNT_FILE (path to key file). See README.md."
        )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def gsc_query(token: str, site: str, body: dict) -> list[dict]:
    """Run one paginated Search Analytics query, returning all rows."""
    import requests

    rows: list[dict] = []
    start_row = 0
    from urllib.parse import quote
    url = GSC_ENDPOINT.format(site=quote(site, safe=""))
    while True:
        payload = dict(body, rowLimit=ROW_LIMIT, startRow=start_row)
        resp = None
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=120,
                )
            except requests.exceptions.RequestException as exc:  # network blip: retry
                last_exc = exc
                resp = None
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in (408, 429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            break
        if resp is None:
            raise RuntimeError(f"GSC API unreachable after retries: {last_exc}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"GSC API error {resp.status_code} for {site}: {resp.text[:500]}"
            )
        batch = resp.json().get("rows", [])
        rows.extend(batch)
        if len(batch) < ROW_LIMIT:
            return rows
        start_row += ROW_LIMIT


def country_filter(settings: dict) -> list[dict]:
    country = settings.get("country")
    if not country:
        return []
    return [{"dimension": "country", "operator": "equals", "expression": country}]


def collect_window(token: str, config: dict, start: date, end: date) -> list[dict]:
    """Pull overall + device rows for one window, filtered to course pages."""
    settings = config["settings"]
    site = settings["gsc_property"]
    page_index = build_page_index(config)
    filters = country_filter(settings)

    base = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "type": settings.get("search_type", "web"),
    }
    if filters:
        base["dimensionFilterGroups"] = [{"filters": filters}]

    out: list[dict] = []
    for dims, device_mode in ((["query", "page"], "all"), (["query", "page", "device"], "split")):
        for row in gsc_query(token, site, dict(base, dimensions=dims)):
            keys = row["keys"]
            query, page = keys[0], keys[1]
            device = "all" if device_mode == "all" else keys[2].lower()
            course = page_index.get(normalize_path(page))
            if course is None:
                continue
            out.append(
                {
                    "course": course,
                    "query": " ".join(query.lower().split()),
                    "page": page,
                    "device": device,
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0.0),
                    "position": row.get("position"),
                }
            )
    return out


def snapshot_path(run_date: date) -> Path:
    return SNAPSHOT_DIR / f"gsc-{run_date.isoformat()}.json"


def write_snapshot(run_date: date, start: date, end: date, rows: list[dict], config: dict, force: bool) -> Path:
    path = snapshot_path(run_date)
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists. Snapshots are immutable weekly records; "
            "pass --force only to repair a corrupted file."
        )
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": "google_search_console_api",
        "property": config["settings"]["gsc_property"],
        "country": config["settings"].get("country"),
        "search_type": config["settings"].get("search_type", "web"),
        "run_date": run_date.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "row_count": len(rows),
        "rows": rows,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


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
    ap.add_argument("--run-date", help="Run date (YYYY-MM-DD); defaults to today (UTC). Normalised to that week's Monday.")
    ap.add_argument("--backfill", type=int, default=0, metavar="N",
                    help="Also collect the N weekly windows before the run date (skips weeks that already have a snapshot).")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing snapshot for the same week (repair only).")
    ap.add_argument("--dry-run", action="store_true", help="Query GSC and report row counts without writing files.")
    args = ap.parse_args()

    try:
        # everything - config parsing included - must fail into meta.json so
        # the dashboard reports the error instead of quietly staying "ok"
        config = load_config()
        settings = config["settings"]
        raw_date = date.fromisoformat(args.run_date) if args.run_date else datetime.now(timezone.utc).date()
        run_monday = monday_of(raw_date)

        token = get_access_token()
        run_dates = [run_monday - timedelta(weeks=k) for k in range(args.backfill, -1, -1)]
        written = []
        for rd in run_dates:
            start, end = compute_window(rd, settings)
            if snapshot_path(rd).exists() and not args.force:
                print(f"skip {rd}: snapshot exists")
                continue
            rows = collect_window(token, config, start, end)
            print(f"{rd}: window {start}..{end} -> {len(rows)} course-page rows")
            if args.dry_run:
                continue
            written.append(str(write_snapshot(rd, start, end, rows, config, args.force)))
        if not args.dry_run:
            update_meta(
                last_run_status="ok",
                last_run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                last_success_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                last_success_run_date=run_monday.isoformat(),
                last_error=None,
                property=settings["gsc_property"],
                country=settings.get("country"),
            )
        for p in written:
            print(f"wrote {p}")
        return 0
    except Exception as exc:  # noqa: BLE001 - anything must surface as a dashboard error
        if not args.dry_run:  # --dry-run promises to write nothing
            update_meta(
                last_run_status="error",
                last_run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                last_error=f"{type(exc).__name__}: {exc}",
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
