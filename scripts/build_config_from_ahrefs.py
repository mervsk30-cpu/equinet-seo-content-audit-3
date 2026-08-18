#!/usr/bin/env python3
"""Generate data/keywords-config.json from the team's curated keyword list.

Input:  data/sources/ahrefs-tracked-keywords-2026-08-17.json
        (keyword text + team tags only -- no ranking metrics)
Output: data/keywords-config.json

The course catalogue (names + URLs) was taken from the live site's
/digital-marketing-courses/ page on 2026-08-17. The tag->course mapping
below encodes the team's own Ahrefs tag codes. Edit the mapping or the
generated config freely; the collector re-reads the config on every run.

Keyword type rules (deterministic, documented in README):
  - tag "(Bottom Funnel)" + course-intent wording  -> primary
  - tag "(Bottom Funnel)" without course intent    -> secondary
  - tag "(Top Funnel)"                             -> related
  - bare tag + course-intent wording               -> primary
  - bare tag without course intent                 -> related
A keyword tagged for several courses is listed under each of them.
"""

import html
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "sources" / "ahrefs-tracked-keywords-2026-08-17.json"
DISCOVERED = ROOT / "data" / "discovered-pages.json"
OUTPUT = ROOT / "data" / "keywords-config.json"

SITE = "https://www.equinetacademy.com"

# Course catalogue from the live site (2026-08-17). "aliases" are legacy
# URL paths (pre-/course/ migration, still present in the site's JSON-LD)
# so historical GSC page URLs map to the right course.
COURSES = [
    # code, name, path, extra aliases
    ("seo", "SEO, AEO, GEO Course", "/course/seo-training-course-singapore/", []),
    ("advanced-seo", "Advanced SEO, AEO & GEO Course", "/course/advanced-seo-course/", []),
    ("cseos", "Certified SEO Specialist (CSEOS) 2.0", "/course/certified-seo-specialist-programme/", []),
    ("dms", "AI-Driven Digital Marketing Strategy Course", "/course/digital-marketing-strategy-course/", []),
    ("smm", "Social Media Marketing Strategy & Optimisation Course", "/course/social-media-marketing-training-course/", []),
    ("advanced-smm", "Advanced Social Media Management Course", "/course/advanced-social-media-management-course/", []),
    ("csmms", "Certified Social Media Marketing Specialist 2.0", "/course/certified-social-media-marketing-specialist/", []),
    ("cms", "Content Marketing Strategy Course", "/course/content-marketing-course/", []),
    ("gad", "Google Ads Strategy and Optimisation Course", "/course/google-ads-strategy-and-optimisation-course/", []),
    ("dma", "Digital Marketing Analytics & Optimisation (GA4) Course", "/course/digital-web-analytics-google-analytics-training-course/", []),
    ("advanced-dma", "Advanced Digital Marketing Analytics (Google Analytics) Course", "/course/advanced-digital-marketing-analytics-course/", []),
    ("cdma", "Certified Digital Marketing Analyst 2.0", "/course/certified-digital-marketing-analyst/", []),
    ("fbma", "Meta Marketing (Facebook and Instagram) Course", "/course/facebook-instagram-marketing-course/", []),
    ("da", "Digital Advertising Strategy Course", "/course/digital-advertising-course/", []),
    ("lim", "LinkedIn Sales and Marketing Course", "/course/linkedin-marketing-course/", []),
    ("wp", "WordPress Website & Landing Page Creation Course", "/course/wordpress-website-landing-page-creation-course-singapore/", []),
    ("ccw", "Digital Copywriting and Content Writing Course", "/course/copywriting-course/", []),
    ("em", "Email Marketing and Marketing Automation Course", "/course/email-marketing-and-marketing-automation-course/", []),
    ("gtm", "Google Tag Manager Course", "/course/google-tag-manager-certification-course/", []),
    ("cro", "Conversion Rate Optimisation Course", "/course/conversion-rate-optimisation-course/", []),
    ("bbs", "Digital Branding and Brand Strategy Course", "/course/branding-brand-strategy-course/", []),
    ("lpd", "Landing Page Design Course", "/course/landing-page-design/", []),
    ("tiktok", "TikTok Marketing Course", "/course/tiktok-marketing/", []),
    ("ai-dm", "AI in Digital Marketing Course", "/course/ai-in-digital-marketing/", []),
    ("caicc", "Certified AI Content Creator", "/course/certified-ai-content-creator/", []),
    ("caidm", "Certified AI-Enabled Digital Marketer", "/course/certified-ai-enabled-digital-marketer/", []),
    ("dcc", "Digital Content Creation For Content Creators Course", "/course/digital-content-creation-course/", []),
    ("dmf", "Digital Marketing Foundations (Fundamentals) Course", "/course/digital-marketing-foundations-fundamentals-course/", []),
    ("dpr", "Digital Public Relations Course", "/course/digital-public-relations-course/", []),
    ("pms", "Performance Marketing Strategy (Lead Generation) Course", "/course/performance-marketing-strategy-lead-generation-course/", []),
    ("dm-capstone", "Digital Marketing Capstone Course", "/course/digital-marketing-capstone-course/", []),
    ("cc-capstone", "Content Creation Capstone Course", "/course/content-creation-capstone-course/", []),
    ("hub", "Digital Marketing Courses (Hub Page)", "/digital-marketing-courses/", ["/courses/"]),
    ("career", "Digital Marketing Career Programme", "/hiring-career-programme/digital-marketing-career-programme-singapore/", []),
]

# The site migrated course URLs to a /course/ prefix in 2026; the un-prefixed
# paths still appear in older GSC data and in the site's own JSON-LD.
def legacy_aliases(path: str) -> list[str]:
    if path.startswith("/course/"):
        return [path.replace("/course/", "/", 1)]
    return []


def normalize(url_or_path: str) -> str:
    p = url_or_path
    if p.startswith("http"):
        p = "/" + p.split("equinetacademy.com", 1)[-1].lstrip("/")
    p = p.split("?", 1)[0].split("#", 1)[0].lower()
    return p if p.endswith("/") else p + "/"

# Team tag code -> course code. "review" marks mappings the team should
# double-check; "unassigned" keeps keywords visible in the config without
# attaching them to a course page.
TAG_MAP = {
    "SEO": ("seo", False),
    "DMS": ("dms", False),
    "SMM": ("smm", False),
    "CMS": ("cms", False),
    "GAD": ("gad", False),
    "DMA": ("dma", False),
    "FBMA": ("fbma", False),
    "DA": ("da", False),
    "LIM": ("lim", False),
    "WP": ("wp", False),
    "CCW": ("ccw", False),
    "EM": ("em", False),
    "GTM": ("gtm", False),
    "CRO": ("cro", False),
    "BBS": ("bbs", False),
    "Web Design": ("web-design-course-singapore", True),  # web-design discipline hub
    "UI/UX": ("wsq-user-experience-user-interface-ux-ui-design-essentials", True),
    "DMC": ("hub", False),
    "General Courses": ("hub", False),
    "WSQ Courses": ("hub", False),
    "digital marketing career": ("career", False),
    "EBE": ("ecommerce-courses", True),       # general e-commerce keywords -> discipline hub
    # No current course page -- kept in unassigned for the team to triage:
    "Content": (None, False),                 # blog/informational content keywords
    "DME": (None, False),
    "CDMS": (None, False),                    # CDMS programme URL not on current catalogue page
    "digital marketing agency": (None, False),
    "Equinet Academy Brand": (None, False),   # brand/navigational queries
}

# Pages from data/discovered-pages.json matching this are not course landing
# pages (registration funnels, thank-you pages, tests, blog/event posts).
DISCOVERY_EXCLUDE = re.compile(
    r"thank|registration|/blog/|/event/|utm-test|/eblh/|-old/$|course-selector",
    re.I,
)


def clean_title(raw: str, path: str) -> str:
    t = html.unescape(raw or "")
    t = re.sub(r"\s*[-|–·]\s*Equinet Academy\s*$", "", t).strip()
    if not t:
        t = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
    return re.sub(r"\s+", " ", t)


def discovered_courses(existing_paths: set[str]) -> list[dict]:
    """Landing pages from the discovery inventory not already tracked."""
    if not DISCOVERED.exists():
        return []
    inv = json.loads(DISCOVERED.read_text())
    out, seen_codes = [], set(existing_paths)
    for page in inv.get("pages", []):
        url = page["url"].split("?")[0].split("#")[0]
        path = "/" + url.split("equinetacademy.com", 1)[-1].strip("/").lower() + "/"
        if path == "//":
            continue
        if DISCOVERY_EXCLUDE.search(path):
            continue
        candidates = {path, *legacy_aliases(path)}
        if candidates & existing_paths:
            continue
        code = path.rstrip("/").rsplit("/", 1)[-1] or path.strip("/").replace("/", "-")
        while code in seen_codes:
            code = "x-" + code
        seen_codes.add(code)
        existing_paths.update(candidates)
        out.append({
            "code": code,
            "name": clean_title(page.get("title", ""), path),
            "url": SITE + path,
            "aliases": sorted(set(legacy_aliases(path))),
            "keywords": [],
            "source": "discovered",
        })
    out.sort(key=lambda c: c["name"].lower())
    return out


COURSE_INTENT = re.compile(
    r"\b(course|courses|training|class|classes|certification|certifications|"
    r"certificate|certified|workshop|workshops|lesson|lessons|programme|"
    r"program|bootcamp|masterclass|diploma|skillsfuture|wsq|learn|study)\b",
    re.I,
)

FUNNEL_RE = re.compile(r"^(.*?)\s*\((Top|Bottom) Funnel\)$")


def classify(tag_funnel: str | None, keyword: str) -> str:
    has_intent = bool(COURSE_INTENT.search(keyword))
    if tag_funnel == "Bottom":
        return "primary" if has_intent else "secondary"
    if tag_funnel == "Top":
        return "related"
    return "primary" if has_intent else "related"


def main() -> None:
    src = json.loads(SOURCE.read_text())
    course_index = OrderedDict()
    existing_paths: set[str] = set()
    for code, name, path, extra in COURSES:
        aliases = sorted(set(extra + legacy_aliases(path)))
        course_index[code] = {
            "code": code,
            "name": name,
            "url": SITE + path,
            "aliases": aliases,
            "keywords": [],
        }
        existing_paths.add(normalize(path))
        existing_paths.update(normalize(a) for a in aliases)

    # every other live course-like landing page from the discovery inventory
    for course in discovered_courses(existing_paths):
        course_index[course["code"]] = course

    unassigned = []
    unknown_tags = {}
    seen_per_course = {code: set() for code in course_index}

    untagged = 0
    for row in src["keywords"]:
        kw = " ".join(row["keyword"].lower().split())
        tags = row.get("tags") or []
        if not tags:
            # keep untagged tracked keywords visible for triage instead of dropping them
            untagged += 1
            unassigned.append({"keyword": kw, "team_tag": "(untagged)", "type": classify(None, kw)})
            continue
        for tag in tags:
            m = FUNNEL_RE.match(tag)
            base, funnel = (m.group(1), m.group(2)) if m else (tag, None)
            if base not in TAG_MAP:
                unknown_tags.setdefault(base, 0)
                unknown_tags[base] += 1
                continue
            course_code, review = TAG_MAP[base]
            ktype = classify(funnel, kw)
            if course_code is None:
                unassigned.append({"keyword": kw, "team_tag": tag, "type": ktype})
                continue
            if kw in seen_per_course[course_code]:
                continue
            seen_per_course[course_code].add(kw)
            entry = {"keyword": kw, "type": ktype, "team_tag": tag}
            if review:
                entry["mapping_review"] = True
            course_index[course_code]["keywords"].append(entry)

    for course in course_index.values():
        course["keywords"].sort(key=lambda e: ({"primary": 0, "secondary": 1, "related": 2}[e["type"]], e["keyword"]))

    config = {
        "generated_at": "2026-08-17",
        "generated_by": "scripts/build_config_from_ahrefs.py",
        "settings": {
            "gsc_property": "sc-domain:equinetacademy.com",
            "site": SITE,
            "country": "sgp",
            "country_note": "ISO-3166-1 alpha-3, lowercase, as required by the GSC API. Set to null to track worldwide positions.",
            "search_type": "web",
            "refresh_day": "Monday",
            "timezone": "Asia/Singapore",
            "window_days": 7,
            "window_lag_days": 3,
            "window_note": "Each weekly snapshot covers the 7-day window ending 3 days before the Monday run, because Search Console data needs ~2-3 days to finalise.",
        },
        "keyword_type_rules": {
            "primary": "Bottom-funnel or course-intent keyword that names the course offering (e.g. 'seo course singapore').",
            "secondary": "Bottom-funnel commercial keyword without explicit course wording.",
            "related": "Top-funnel / informational keyword relevant to the course topic.",
            "discovered": "Assigned automatically by the collector to real GSC queries not present in this config.",
        },
        "courses": list(course_index.values()),
        "unassigned_keywords": {
            "note": "Tracked by the team in Ahrefs but with no matching course page on the current catalogue. Assign them to a course above (or delete) as needed.",
            "keywords": sorted(unassigned, key=lambda e: (e["team_tag"], e["keyword"])),
        },
    }

    OUTPUT.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")

    total = sum(len(c["keywords"]) for c in course_index.values())
    print(f"Wrote {OUTPUT}")
    print(f"  source keywords: {len(src['keywords'])} (untagged: {untagged})")
    print(f"  courses: {len(course_index)}  assigned keyword rows: {total}  unassigned: {len(unassigned)}")
    if unknown_tags:
        print(f"  WARNING unknown tags skipped: {unknown_tags}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
