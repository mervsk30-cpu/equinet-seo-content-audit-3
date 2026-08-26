#!/usr/bin/env python3
"""Build the dashboard payload from weekly GSC snapshots.

Reads  data/keywords-config.json, data/snapshots/gsc-*.json, data/meta.json
Writes data/dashboard-data.js (window.DASHBOARD_DATA = ...) and
       data/dashboard-data.json

Comparison rules (positions rounded to whole numbers, lower = better):
  improved        ranked both weeks, current < previous
  dropped         ranked both weeks, current > previous
  stable          ranked both weeks, same rounded position
  newly_ranking   ranked this week, not last week (a previous week exists)
  lost            ranked before (last week or earlier), no rank this week
  no_ranking_data never appeared in any snapshot
  no_baseline     ranked in the only snapshot we have (no previous week yet)

No fabrication: every number comes from a snapshot row the GSC API returned.
Keywords without API rows stay blank. When collection failed or data is
stale the payload says so explicitly so the UI can show an error banner.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "data" / "keywords-config.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
META_PATH = ROOT / "data" / "meta.json"
OUT_JS = ROOT / "data" / "dashboard-data.js"
OUT_JSON = ROOT / "data" / "dashboard-data.json"

HISTORY_WEEKS = 26
STALE_AFTER_DAYS = 8  # a weekly cadence means anything older than this is stale
MIN_DISCOVERED_IMPRESSIONS = 5  # see discovered_totals below

STATUS_ORDER = [
    "dropped", "lost", "improved", "newly_ranking", "stable", "no_baseline", "no_ranking_data",
]


def rnd(pos: float | None) -> int | None:
    """Round a GSC average position to the whole number shown in the UI."""
    if pos is None:
        return None
    return int(math.floor(pos + 0.5))


def load_snapshots(snapshot_dir: Path) -> list[dict]:
    snaps = []
    for path in sorted(snapshot_dir.glob("gsc-*.json")):
        if re.fullmatch(r"gsc-\d{4}-\d{2}-\d{2}\.json", path.name):
            snaps.append(json.loads(path.read_text()))
    snaps.sort(key=lambda s: s["run_date"])
    return snaps


def index_snapshot(snap: dict) -> dict:
    """(course, query, device) -> aggregated entry with dominant page."""
    out: dict[tuple, dict] = {}
    for row in snap.get("rows", []):
        if row.get("position") is None:
            continue
        key = (row["course"], row["query"], row["device"])
        entry = out.get(key)
        if entry is None:
            out[key] = {
                "position": row["position"],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "page": row["page"],
                "_dom_impressions": row["impressions"],
            }
            continue
        # aggregate metrics across the course's pages for this query
        entry["clicks"] += row["clicks"]
        entry["impressions"] += row["impressions"]
        # dominant page (most impressions, then best position) provides
        # the representative position and ranking URL
        better = row["impressions"] > entry["_dom_impressions"] or (
            row["impressions"] == entry["_dom_impressions"] and row["position"] < entry["position"]
        )
        if better:
            entry["position"] = row["position"]
            entry["page"] = row["page"]
            entry["_dom_impressions"] = row["impressions"]
    for entry in out.values():
        entry.pop("_dom_impressions", None)
        entry["ctr"] = (entry["clicks"] / entry["impressions"]) if entry["impressions"] else 0.0
    return out


def device_cell(idx_cur: dict, idx_prev: dict | None, course: str, query: str, device: str) -> dict | None:
    cur = idx_cur.get((course, query, device))
    prev = idx_prev.get((course, query, device)) if idx_prev is not None else None
    if cur is None and prev is None:
        return None
    cell: dict = {}
    if cur is not None:
        cell["position"] = cur["position"]
    if prev is not None:
        cell["previous"] = prev["position"]
    if cur is not None and prev is not None:
        cell["change"] = rnd(prev["position"]) - rnd(cur["position"])
    return cell


def status_for(cur, prev, has_prev_snapshot: bool, ever_ranked_before: bool):
    if cur is not None and prev is not None:
        c, p = rnd(cur["position"]), rnd(prev["position"])
        if c < p:
            return "improved"
        if c > p:
            return "dropped"
        return "stable"
    if cur is not None:
        return "newly_ranking" if has_prev_snapshot else "no_baseline"
    if prev is not None or ever_ranked_before:
        return "lost"
    return "no_ranking_data"


def fmt_date_long(d: date) -> str:
    return d.strftime("%A, %d %b %Y")


def build_payload(config: dict, snapshots: list[dict], meta: dict, today: date) -> dict:
    settings = config["settings"]

    # last week each (course, query) ranked, over the FULL snapshot list, so a
    # keyword lost >HISTORY_WEEKS ago still reads "lost", never "no data"
    last_ranked_week: dict[tuple, str] = {}
    for s in snapshots:  # sorted ascending, so later weeks overwrite
        for r in s.get("rows", []):
            if r["device"] == "all" and r.get("position") is not None:
                last_ranked_week[(r["course"], r["query"])] = s["run_date"]

    snapshots = snapshots[-HISTORY_WEEKS:]
    current = snapshots[-1] if snapshots else None
    previous = snapshots[-2] if len(snapshots) >= 2 else None

    idx_cur = index_snapshot(current) if current else {}
    idx_prev = index_snapshot(previous) if previous else {}
    all_indexes = [(s["run_date"], index_snapshot(s)) for s in snapshots]

    # ---- global state -------------------------------------------------
    error = meta.get("last_error") if meta.get("last_run_status") == "error" else None
    if current is None:
        # a failed pull must surface as an error even before the first snapshot
        state = "error" if error else "no_data_yet"
    else:
        run_d = date.fromisoformat(current["run_date"])
        stale = (today - run_d).days > STALE_AFTER_DAYS
        if error:
            state = "error"
        elif stale:
            state = "stale"
        else:
            state = "ok"

    if current is not None:
        next_refresh = date.fromisoformat(current["run_date"]) + timedelta(weeks=1)
        while next_refresh < today:  # schedule slipped: advance to the next Monday
            next_refresh += timedelta(weeks=1)
    else:
        next_refresh = today if today.weekday() == 0 else today + timedelta(days=7 - today.weekday())

    # ---- per-course keyword rows -------------------------------------
    courses_out = []
    for course in config["courses"]:
        code = course["code"]
        configured = {k["keyword"]: k for k in course.get("keywords", [])}
        # Auto-discovered queries (real GSC rows not in the team's config) are
        # cheap noise: most course pages pick up dozens of one-off, single-
        # impression long-tail queries with no real signal. Require a modest
        # cumulative impression total before surfacing one as a tracked
        # "discovered" keyword, so the table isn't dominated by statistical
        # flukes. This only affects what's DISPLAYED - the underlying GSC
        # snapshot rows are untouched and remain available for any future re-run.
        discovered_totals: dict[str, int] = {}
        for _, idx in all_indexes:
            for (c, q, dev), entry in idx.items():
                if c == code and dev == "all" and q not in configured:
                    discovered_totals[q] = discovered_totals.get(q, 0) + entry["impressions"]
        discovered = {q for q, total in discovered_totals.items() if total >= MIN_DISCOVERED_IMPRESSIONS}

        rows = []
        for kw in list(configured.keys()) + sorted(discovered):
            conf = configured.get(kw)
            cur = idx_cur.get((code, kw, "all"))
            prev = idx_prev.get((code, kw, "all"))

            history = []
            for run_date_s, idx in all_indexes:
                e = idx.get((code, kw, "all"))
                history.append({
                    "week": run_date_s,
                    "position": e["position"] if e else None,
                    "clicks": e["clicks"] if e else None,
                    "impressions": e["impressions"] if e else None,
                })

            last_ranked = last_ranked_week.get((code, kw))
            ever_before = last_ranked is not None and (current is None or last_ranked < current["run_date"])
            status = status_for(cur, prev, previous is not None, ever_before)

            row = {
                "keyword": kw,
                "type": conf["type"] if conf else "discovered",
                "team_tag": conf.get("team_tag") if conf else None,
                "status": status,
                "current": cur,
                "previous": {"position": prev["position"], "page": prev["page"]} if prev else None,
                "change": (rnd(prev["position"]) - rnd(cur["position"])) if cur and prev else None,
                "desktop": device_cell(idx_cur, idx_prev if previous else None, code, kw, "desktop"),
                "mobile": device_cell(idx_cur, idx_prev if previous else None, code, kw, "mobile"),
                "history": history,
            }
            if status == "lost" and last_ranked:
                row["lost_since"] = last_ranked
            if conf and conf.get("mapping_review"):
                row["mapping_review"] = True
            rows.append(row)

        summary = {s: 0 for s in STATUS_ORDER}
        for r in rows:
            summary[r["status"]] += 1
        summary["ranking"] = sum(1 for r in rows if r["current"] is not None)
        summary["total"] = len(rows)

        courses_out.append({
            "code": code,
            "name": course["name"],
            "url": course["url"],
            "summary": summary,
            "keywords": rows,
        })

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state": state,
        "error": error,
        "property": settings["gsc_property"],
        "country": settings.get("country"),
        "search_type": settings.get("search_type", "web"),
        "data_policy": "Real Google Search Console data only. Blank cells mean the GSC API returned no data; nothing is estimated.",
        "discovered_keyword_policy": f"Auto-discovered keywords (queries not in the team's keyword list) are shown only once they accumulate {MIN_DISCOVERED_IMPRESSIONS}+ impressions across recorded weeks, to keep single-impression long-tail noise out of the table. Configured (Primary/Secondary/Related) keywords are always shown regardless of impressions.",
        "last_updated": (
            {
                "run_date": current["run_date"],
                "display": fmt_date_long(date.fromisoformat(current["run_date"])),
                "collected_at": current["collected_at"],
                "window": current["window"],
            }
            if current
            else None
        ),
        "next_refresh": {
            "date": next_refresh.isoformat(),
            "display": fmt_date_long(next_refresh),
        },
        "weeks": [s["run_date"] for s in snapshots],
        "courses": courses_out,
    }
    return payload


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text())
    meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    snapshots = load_snapshots(SNAPSHOT_DIR)
    payload = build_payload(config, snapshots, meta, datetime.now(timezone.utc).date())

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT_JS.write_text("window.DASHBOARD_DATA = " + body + ";\n")
    OUT_JSON.write_text(body + "\n")
    n_kw = sum(len(c["keywords"]) for c in payload["courses"])
    print(f"state={payload['state']} weeks={len(payload['weeks'])} courses={len(payload['courses'])} keyword rows={n_kw}")
    print(f"wrote {OUT_JS} and {OUT_JSON}")


if __name__ == "__main__":
    main()
