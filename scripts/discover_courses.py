#!/usr/bin/env python3
"""Discover all live course landing pages on www.equinetacademy.com.

Runs inside GitHub Actions (the runner has open egress; the dev sandbox does
not). Sources, in order of preference:
  1. WordPress REST API (/wp-json/wp/v2/<type>) - gives URL + title directly.
  2. XML sitemaps (sitemap_index.xml -> child sitemaps) - gives URLs; titles
     are then fetched from each new page's <title> tag.

Writes data/discovered-pages.json: {fetched_at, sources, pages:[{url,title}]}.
Discovery only reports what the site itself publishes - it never touches the
tracking config; updating data/keywords-config.json stays a deliberate step.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "discovered-pages.json"
SITE = "https://www.equinetacademy.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; EquinetSEODashboard/1.0; +https://github.com/mervsk30-cpu/equinet-seo-content-audit-3)"}
TIMEOUT = 30


def get(url: str) -> requests.Response:
    return requests.get(url, headers=UA, timeout=TIMEOUT)


def from_wp_rest() -> dict[str, str]:
    """URL -> title from the WP REST API, for any exposed course-like type."""
    pages: dict[str, str] = {}
    for post_type in ("course", "courses", "pages"):
        page_no = 1
        while True:
            r = get(f"{SITE}/wp-json/wp/v2/{post_type}?per_page=100&page={page_no}&_fields=link,title")
            if r.status_code != 200:
                break
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                link = item.get("link")
                title = (item.get("title") or {}).get("rendered", "")
                if link:
                    pages[link] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()
            if len(batch) < 100:
                break
            page_no += 1
    return pages


def from_sitemaps() -> list[str]:
    urls: list[str] = []
    r = get(f"{SITE}/sitemap_index.xml")
    if r.status_code != 200:
        return urls
    child_maps = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", r.text)
    for sm in child_maps:
        if not sm.endswith(".xml"):
            urls.append(sm)
            continue
        rc = get(sm)
        if rc.status_code == 200:
            urls.extend(re.findall(r"<loc>\s*([^<]+?)\s*</loc>", rc.text))
    return [u for u in urls if not u.endswith(".xml")]


def fetch_title(url: str) -> str:
    try:
        r = get(url)
        if r.status_code == 200:
            m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            if m:
                return re.sub(r"\s+", " ", m.group(1)).strip()
    except requests.RequestException:
        pass
    return ""


def looks_like_course(url: str) -> bool:
    path = url.replace(SITE, "").lower()
    return (
        path.startswith("/course/")
        or path.startswith("/hiring-career-programme/")
        or path.endswith("-course/")
        or path.endswith("-courses/")
        or "-course-" in path
    )


def main() -> None:
    wp = from_wp_rest()
    sitemap_urls = from_sitemaps()
    sources = []
    if wp:
        sources.append("wp-rest")
    if sitemap_urls:
        sources.append("sitemaps")

    all_urls = set(wp) | set(sitemap_urls)
    course_urls = sorted(u for u in all_urls if looks_like_course(u))
    if not course_urls:
        print("ERROR: no course-like URLs discovered from any source", file=sys.stderr)
        sys.exit(1)

    pages = []
    for u in course_urls:
        title = wp.get(u) or fetch_title(u)
        pages.append({"url": u, "title": title})

    OUT.write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "count": len(pages),
        "pages": pages,
    }, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}: {len(pages)} course-like pages (sources: {', '.join(sources)})")


if __name__ == "__main__":
    main()
