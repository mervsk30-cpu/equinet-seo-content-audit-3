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
  no_baseline     ranked in the only snapshot we have (no previous week yet)

Absence of GSC data is not evidence of absence from the SERP - GSC only reports
a query once it has been seen, so a #1 page for a low-volume term never shows
up. Ahrefs Rank Tracker is consulted as a second source before we call anything
non-ranking:
  ranking_no_impressions  no GSC rows, but Ahrefs has a real SERP position
  not_ranking             Ahrefs checked it and found no position
  not_checked             neither source has data for it

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
AHREFS_SNAPSHOT_DIR = ROOT / "data" / "ahrefs-snapshots"
META_PATH = ROOT / "data" / "meta.json"
OUT_JS = ROOT / "data" / "dashboard-data.js"
OUT_JSON = ROOT / "data" / "dashboard-data.json"

HISTORY_WEEKS = 26
STALE_AFTER_DAYS = 8  # a weekly cadence means anything older than this is stale
MIN_DISCOVERED_IMPRESSIONS = 5  # see discovered_totals below

STATUS_ORDER = [
    "dropped", "lost", "improved", "newly_ranking", "stable", "no_baseline",
    "ranking_no_impressions", "not_ranking", "not_checked",
]

# Statuses that mean "this keyword is currently in Google's results".
RANKING_STATUSES = {
    "improved", "dropped", "stable", "newly_ranking", "no_baseline",
    "ranking_no_impressions",
}

# Display order for keyword types. The UI groups by this order and skips any
# type with no keywords for the selected course.
TYPE_ORDER = ["primary", "secondary", "supporting", "discovered"]


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


def load_ahrefs_snapshots(snapshot_dir: Path) -> list[dict]:
    snaps = []
    for path in sorted(snapshot_dir.glob("ahrefs-*.json")):
        if re.fullmatch(r"ahrefs-\d{4}-\d{2}-\d{2}\.json", path.name):
            snaps.append(json.loads(path.read_text()))
    snaps.sort(key=lambda s: s["run_date"])
    return snaps


def index_ahrefs(snap: dict) -> dict:
    """(keyword, device) -> Ahrefs Rank Tracker row."""
    out: dict[tuple, dict] = {}
    for row in snap.get("rows", []):
        out[(row["keyword"], row["device"])] = row
    return out


def ahrefs_cell(idx: dict, keyword: str, course_code: str) -> dict | None:
    """Ahrefs view of one keyword: real SERP position, volume, difficulty.

    Kept in its own field, never merged into the Search Console numbers -
    GSC reports an average position across impressions, Ahrefs reports the
    position an actual SERP check returned. Both are real; they are simply
    different measurements.
    """
    desktop = idx.get((keyword, "desktop"))
    mobile = idx.get((keyword, "mobile"))
    if desktop is None and mobile is None:
        return None
    primary = desktop or mobile
    cell: dict = {
        "volume": primary.get("volume"),
        "difficulty": primary.get("keyword_difficulty"),
        "url": primary.get("url"),
        # Ahrefs reports where the site actually ranks for this keyword. If that
        # is not this course's page, the keyword is being served by other
        # content - useful signal, so surface it rather than hiding it.
        "on_this_course": primary.get("course") == course_code,
        "ranking_course": primary.get("course"),
    }
    for label, row in (("desktop", desktop), ("mobile", mobile)):
        if row is None:
            continue
        cur, prev = row.get("position"), row.get("position_prev")
        entry = {"position": cur, "previous": prev}
        if cur is not None and prev is not None:
            # dashboard convention: positive = improved (moved up the SERP)
            entry["change"] = prev - cur
        cell[label] = entry
    return cell


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


def status_for(cur, prev, has_prev_snapshot: bool, ever_ranked_before: bool,
               ahrefs_position=None, ahrefs_checked: bool = False):
    """Classify a keyword using BOTH sources.

    Search Console only reports a query that received at least one impression,
    so "no GSC row" does NOT mean "not ranking" - a keyword can sit at #1 with
    10 searches a month and still be invisible to GSC in a 7-day window. Ahrefs
    performs an actual SERP check, so it can tell "ranking but no impressions"
    apart from "genuinely absent from the SERP" and from "never checked".
    Collapsing those three into one bucket previously mislabelled hundreds of
    real #1 rankings as "No Ranking Data".
    """
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
    # No Search Console activity at all - let Ahrefs decide which of the three
    # genuinely different situations this is.
    if ahrefs_position is not None:
        return "ranking_no_impressions"
    if ahrefs_checked:
        return "not_ranking"
    return "not_checked"


def fmt_date_long(d: date) -> str:
    return d.strftime("%A, %d %b %Y")


def build_payload(config: dict, snapshots: list[dict], meta: dict, today: date,
                  ahrefs_snapshots: list[dict] | None = None) -> dict:
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

    ahrefs_snapshots = ahrefs_snapshots or []
    ahrefs_current = ahrefs_snapshots[-1] if ahrefs_snapshots else None
    ahrefs_idx = index_ahrefs(ahrefs_current) if ahrefs_current else {}

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
            ah_desktop = ahrefs_idx.get((kw, "desktop"))
            ah_mobile = ahrefs_idx.get((kw, "mobile"))
            ah_pos = None
            for _cand in (ah_desktop, ah_mobile):
                if _cand and _cand.get("position") is not None:
                    ah_pos = _cand["position"]
                    break
            status = status_for(cur, prev, previous is not None, ever_before,
                                ahrefs_position=ah_pos,
                                ahrefs_checked=(ah_desktop is not None or ah_mobile is not None))

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
            ah = ahrefs_cell(ahrefs_idx, kw, code) if ahrefs_idx else None
            if ah:
                row["ahrefs"] = ah
            rows.append(row)

        # Primary > Secondary > Supporting > Discovered, then best position first.
        rows.sort(key=lambda r: (
            TYPE_ORDER.index(r["type"]) if r["type"] in TYPE_ORDER else len(TYPE_ORDER),
            rnd(r["current"]["position"]) if r["current"] else 10_000,
            r["keyword"],
        ))

        summary = {s: 0 for s in STATUS_ORDER}
        for r in rows:
            summary[r["status"]] += 1
        summary["ranking"] = sum(1 for r in rows if r["status"] in RANKING_STATUSES)
        summary["ranking_gsc"] = sum(1 for r in rows if r["current"] is not None)
        summary["total"] = len(rows)
        # per-type counts drive the UI's type sections (empty types are skipped)
        summary["by_type"] = {t: sum(1 for r in rows if r["type"] == t) for t in TYPE_ORDER}
        summary["with_ahrefs"] = sum(1 for r in rows if r.get("ahrefs"))

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
        "type_order": TYPE_ORDER,
        # Live Google rank is fetched by the browser from a Worker that holds the
        # SERP API key; only the public endpoint travels in this payload.
        "live_rank": {
            k: v for k, v in (settings.get("live_rank") or {}).items()
            if k in ("endpoint", "token", "auto_fetch_on_open", "device")
        },
        "ahrefs": (
            {
                "source": "Ahrefs Rank Tracker",
                "project_id": ahrefs_current.get("project_id"),
                "location": ahrefs_current.get("location"),
                "run_date": ahrefs_current["run_date"],
                "display": fmt_date_long(date.fromisoformat(ahrefs_current["run_date"])),
                "compared_to": ahrefs_current.get("compared_to"),
                "collected_at": ahrefs_current.get("collected_at"),
                "row_count": ahrefs_current.get("row_count"),
                "note": (
                    "Ahrefs reports the actual SERP position from a real search check "
                    "(a whole number), plus search volume and keyword difficulty. Search "
                    "Console reports average position across impressions, plus impressions, "
                    "clicks and CTR. Both are real measurements and are shown side by side, "
                    "never averaged together."
                ),
            }
            if ahrefs_current
            else None
        ),
        "courses": courses_out,
    }
    return payload


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text())
    meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    snapshots = load_snapshots(SNAPSHOT_DIR)
    ahrefs_snapshots = load_ahrefs_snapshots(AHREFS_SNAPSHOT_DIR)
    payload = build_payload(config, snapshots, meta, datetime.now(timezone.utc).date(),
                            ahrefs_snapshots=ahrefs_snapshots)

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT_JS.write_text("window.DASHBOARD_DATA = " + body + ";\n")
    OUT_JSON.write_text(body + "\n")
    n_kw = sum(len(c["keywords"]) for c in payload["courses"])
    print(f"state={payload['state']} weeks={len(payload['weeks'])} courses={len(payload['courses'])} keyword rows={n_kw}")
    print(f"wrote {OUT_JS} and {OUT_JSON}")


if __name__ == "__main__":
    main()
