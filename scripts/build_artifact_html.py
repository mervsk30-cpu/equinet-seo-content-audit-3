#!/usr/bin/env python3
"""Build the self-contained claude.ai artifact version of the dashboard.

Takes the repo's index.html, inlines the committed data
(data/dashboard-data.json) in place of the external script tag, strips the
document wrapper (the artifact host supplies its own skeleton), removes the
in-page theme toggle (the artifact viewer has its own), and adds a footer
note marking the page as a published snapshot.

Data honesty: this script performs a mechanical transform only. It must never
alter the data payload or suppress the dashboard's error/stale/no-data
banners - a failed refresh gets published as a failed refresh.

Usage: python3 scripts/build_artifact_html.py <output.html>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "Equinet Keyword Rankings"

TOGGLE_BUTTON = "'<button class=\"ghost\" id=\"themeBtn\">Toggle theme</button></header>'"
TOGGLE_HANDLER = re.compile(
    r'\s*document\.getElementById\("themeBtn"\)\.onclick = \(\) => \{.*?\};\n',
    re.S,
)
FOOTER_ANCHOR = 'esc(D.data_policy) + "</footer>";'
FOOTER_NOTE = (
    'esc(D.data_policy) + " · This page is a published snapshot of the repo dashboard '
    "(equinet-seo-content-audit-3); the data updates when the weekly refresh commits "
    'and the page is republished.</footer>";'
)


def fail(msg: str) -> None:
    sys.exit(f"build_artifact_html: {msg} - index.html changed shape; update this script.")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out_path = Path(sys.argv[1])

    html = (ROOT / "index.html").read_text()
    data = json.loads((ROOT / "data" / "dashboard-data.json").read_text())

    style = re.search(r"<style>.*?</style>", html, re.S)
    body = re.search(r"<body>\n(.*)\n</body>", html, re.S)
    if not style or not body:
        fail("could not locate <style> or <body>")
    content = body.group(1)

    src_tag = '<script src="data/dashboard-data.js"></script>'
    if src_tag not in content:
        fail("data script tag not found")
    content = content.replace(
        src_tag,
        "<script>window.DASHBOARD_DATA = "
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + ";</script>",
    )

    if TOGGLE_BUTTON not in content:
        fail("theme toggle button markup not found")
    content = content.replace(TOGGLE_BUTTON, "'</header>'")
    content, n = TOGGLE_HANDLER.subn("\n", content)
    if n != 1:
        fail(f"expected exactly 1 theme toggle handler, found {n}")

    if FOOTER_ANCHOR not in content:
        fail("footer anchor not found")
    content = content.replace(FOOTER_ANCHOR, FOOTER_NOTE)

    if "themeBtn" in content:
        fail("themeBtn still referenced after transform")

    out_path.write_text(f"<title>{TITLE}</title>\n{style.group(0)}\n{content}\n")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes, "
          f"data state={data.get('state')}, generated_at={data.get('generated_at')})")


if __name__ == "__main__":
    main()
