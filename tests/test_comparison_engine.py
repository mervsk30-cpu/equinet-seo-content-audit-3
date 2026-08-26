"""Unit tests for the weekly comparison / status engine.

Fixtures here are SYNTHETIC (sc-domain:example.com, 'testkw ...' queries).
They exist only to prove the status logic; the dashboard itself reads
exclusively from data/snapshots/, which only the GSC collector writes.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_dashboard_data import build_payload, rnd  # noqa: E402
from collect_gsc import compute_window, monday_of, normalize_path  # noqa: E402

CONFIG = {
    "settings": {
        "gsc_property": "sc-domain:example.com",
        "country": "sgp",
        "search_type": "web",
        "window_days": 7,
        "window_lag_days": 3,
    },
    "courses": [
        {
            "code": "alpha",
            "name": "Alpha Course",
            "url": "https://www.example.com/course/alpha/",
            "aliases": ["/alpha/"],
            "keywords": [
                {"keyword": "testkw improved", "type": "primary"},
                {"keyword": "testkw dropped", "type": "primary"},
                {"keyword": "testkw stable", "type": "secondary"},
                {"keyword": "testkw newly", "type": "related"},
                {"keyword": "testkw lost", "type": "primary"},
                {"keyword": "testkw lost long ago", "type": "related"},
                {"keyword": "testkw never", "type": "primary"},
            ],
        }
    ],
}


def row(query, position, device="all", page="https://www.example.com/course/alpha/",
        clicks=5, impressions=100):
    return {
        "course": "alpha", "query": query, "page": page, "device": device,
        "clicks": clicks, "impressions": impressions,
        "ctr": clicks / impressions, "position": position,
    }


def snap(run_date, rows):
    return {
        "schema_version": 1, "source": "google_search_console_api",
        "property": "sc-domain:example.com", "country": "sgp",
        "search_type": "web", "run_date": run_date,
        "window": {"start": "x", "end": "y"},
        "collected_at": run_date + "T01:00:00+00:00",
        "row_count": len(rows), "rows": rows,
    }


def course_rows(payload):
    return {r["keyword"]: r for r in payload["courses"][0]["keywords"]}


def build(snapshots, today=date(2026, 8, 18)):
    return build_payload(CONFIG, snapshots, {"last_run_status": "ok"}, today)


def test_statuses_across_two_weeks():
    week1 = snap("2026-08-10", [
        row("testkw improved", 10.2),
        row("testkw dropped", 5.4),
        row("testkw stable", 8.6),           # rounds to 9
        row("testkw lost", 12.0),
        row("testkw lost long ago", 30.0),
    ])
    week2 = snap("2026-08-17", [
        row("testkw improved", 7.1),
        row("testkw dropped", 9.0),
        row("testkw stable", 9.4),           # rounds to 9 -> stable
        row("testkw newly", 15.0),
    ])
    rows = course_rows(build([week1, week2]))

    assert rows["testkw improved"]["status"] == "improved"
    assert rows["testkw improved"]["change"] == 3          # 10 -> 7
    assert rows["testkw dropped"]["status"] == "dropped"
    assert rows["testkw dropped"]["change"] == -4          # 5 -> 9
    assert rows["testkw stable"]["status"] == "stable"
    assert rows["testkw stable"]["change"] == 0
    assert rows["testkw newly"]["status"] == "newly_ranking"
    assert rows["testkw newly"]["previous"] is None
    assert rows["testkw lost"]["status"] == "lost"
    assert rows["testkw lost"]["current"] is None
    assert rows["testkw lost"]["lost_since"] == "2026-08-10"
    assert rows["testkw never"]["status"] == "no_ranking_data"
    assert rows["testkw never"]["current"] is None
    assert rows["testkw never"]["previous"] is None


def test_lost_older_than_previous_week():
    week1 = snap("2026-08-03", [row("testkw lost long ago", 18.0)])
    week2 = snap("2026-08-10", [row("testkw improved", 10.0)])
    week3 = snap("2026-08-17", [row("testkw improved", 9.0)])
    rows = course_rows(build([week1, week2, week3]))
    r = rows["testkw lost long ago"]
    assert r["status"] == "lost"
    assert r["lost_since"] == "2026-08-03"


def test_single_snapshot_has_no_baseline_not_newly_ranking():
    only = snap("2026-08-17", [row("testkw improved", 4.0)])
    rows = course_rows(build([only]))
    assert rows["testkw improved"]["status"] == "no_baseline"
    assert rows["testkw improved"]["change"] is None
    assert rows["testkw never"]["status"] == "no_ranking_data"


def test_no_snapshots_is_no_data_yet_with_all_blank():
    payload = build([])
    assert payload["state"] == "no_data_yet"
    rows = course_rows(payload)
    for r in rows.values():
        assert r["current"] is None and r["previous"] is None
        assert r["status"] == "no_ranking_data"


def test_device_split_and_discovered_keywords():
    week1 = snap("2026-08-10", [
        row("testkw improved", 10.0),
        row("testkw improved", 12.4, device="desktop"),
        row("testkw improved", 9.6, device="mobile"),
    ])
    week2 = snap("2026-08-17", [
        row("testkw improved", 7.0),
        row("testkw improved", 9.8, device="desktop"),
        row("testkw improved", 6.9, device="mobile"),
        row("testkw discovered only", 20.0),
    ])
    rows = course_rows(build([week1, week2]))
    r = rows["testkw improved"]
    assert rnd(r["desktop"]["position"]) == 10 and rnd(r["desktop"]["previous"]) == 12
    assert r["desktop"]["change"] == 2
    assert rnd(r["mobile"]["position"]) == 7 and r["mobile"]["change"] == 3
    d = rows["testkw discovered only"]
    assert d["type"] == "discovered"
    assert d["status"] == "newly_ranking"


def test_low_impression_discovered_keywords_are_filtered():
    week1 = snap("2026-08-10", [
        row("testkw discovered only", 20.0, impressions=100),   # survives: well above threshold
        row("testkw one impression", 30.0, impressions=1),      # noise: filtered out
        row("testkw two impressions week1", 40.0, impressions=2),
    ])
    week2 = snap("2026-08-17", [
        row("testkw discovered only", 18.0, impressions=100),
        row("testkw two impressions week1", 42.0, impressions=2),  # 2+2=4, still under threshold (5)
        row("testkw accumulates", 50.0, impressions=3),
    ])
    week3 = snap("2026-08-24", [
        row("testkw accumulates", 48.0, impressions=3),  # 3+3=6, clears threshold cumulatively
    ])
    rows = course_rows(build([week1, week2, week3]))
    assert "testkw discovered only" in rows
    assert "testkw one impression" not in rows
    assert "testkw two impressions week1" not in rows          # 4 total < 5
    assert "testkw accumulates" in rows                        # 6 total >= 5
    # configured keywords are never filtered, regardless of impressions
    assert "testkw never" in rows


def test_dominant_page_and_metric_aggregation():
    week = snap("2026-08-17", [
        row("testkw improved", 6.0, page="https://www.example.com/course/alpha/", impressions=500, clicks=25),
        row("testkw improved", 40.0, page="https://www.example.com/alpha/", impressions=20, clicks=0),
    ])
    rows = course_rows(build([week]))
    r = rows["testkw improved"]
    assert r["current"]["page"].endswith("/course/alpha/")   # dominant by impressions
    assert r["current"]["impressions"] == 520                # metrics aggregated
    assert r["current"]["clicks"] == 25
    assert rnd(r["current"]["position"]) == 6


def test_history_preserved_across_weeks():
    snaps = [
        snap("2026-07-27", [row("testkw improved", 15.0)]),
        snap("2026-08-03", [row("testkw improved", 12.0)]),
        snap("2026-08-10", [row("testkw improved", 9.0)]),
        snap("2026-08-17", [row("testkw improved", 7.0)]),
    ]
    rows = course_rows(build(snaps))
    hist = rows["testkw improved"]["history"]
    assert [h["week"] for h in hist] == ["2026-07-27", "2026-08-03", "2026-08-10", "2026-08-17"]
    assert [rnd(h["position"]) for h in hist] == [15, 12, 9, 7]


def test_error_with_zero_snapshots_surfaces_as_error_not_no_data():
    p = build_payload(CONFIG, [], {"last_run_status": "error", "last_error": "403 permission denied"},
                      date(2026, 8, 17))
    assert p["state"] == "error"
    assert p["error"] == "403 permission denied"
    assert p["last_updated"] is None


def test_lost_older_than_history_cap_stays_lost():
    from datetime import timedelta
    base = date(2026, 1, 5)  # a Monday
    snaps = [snap(base.isoformat(), [row("testkw lost long ago", 12.0)])]
    for i in range(1, 30):  # 29 more weeks, keyword never ranks again
        snaps.append(snap((base + timedelta(weeks=i)).isoformat(),
                          [row("testkw improved", 5.0)]))
    rows = course_rows(build(snaps, today=date(2026, 8, 4)))
    r = rows["testkw lost long ago"]
    assert r["status"] == "lost"                      # not no_ranking_data
    assert r["lost_since"] == "2026-01-05"            # from before the 26-week cap
    assert len(r["history"]) == 26                    # history itself stays capped


def test_state_stale_and_error():
    old = snap("2026-08-03", [row("testkw improved", 5.0)])
    p = build_payload(CONFIG, [old], {"last_run_status": "ok"}, date(2026, 8, 18))
    assert p["state"] == "stale"
    p = build_payload(CONFIG, [old], {"last_run_status": "error", "last_error": "boom"}, date(2026, 8, 18))
    assert p["state"] == "error" and p["error"] == "boom"
    assert p["next_refresh"]["date"] >= "2026-08-18"


def test_rounding_display_rule():
    assert rnd(6.5) == 7 and rnd(6.4) == 6 and rnd(1.5) == 2 and rnd(None) is None


def test_window_math():
    assert monday_of(date(2026, 8, 17)) == date(2026, 8, 17)
    assert monday_of(date(2026, 8, 20)) == date(2026, 8, 17)
    start, end = compute_window(date(2026, 8, 24), CONFIG["settings"])
    assert (start.isoformat(), end.isoformat()) == ("2026-08-15", "2026-08-21")


def test_url_normalization():
    assert normalize_path("https://www.example.com/Course/Alpha") == "/course/alpha/"
    assert normalize_path("/alpha/?utm_source=x#frag") == "/alpha/"
    assert normalize_path("https://example.com") == "/"
