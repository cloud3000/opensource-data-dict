#!/usr/bin/env python3
"""
tools/render_diagrams.py - Render the Mermaid diagrams in DATA_MODEL.md to
static SVG and PNG in diagrams/.

The usual tool for this is the Mermaid CLI (`mmdc`, from
@mermaid-js/mermaid-cli), which needs Node.js. When Node/mmdc is unavailable
this script falls back to headless Chromium + the Mermaid browser library,
producing the same artifacts entirely locally (no external rendering service).

    python3 tools/render_diagrams.py

Outputs: diagrams/<name>.svg and diagrams/<name>.png for each ```mermaid block.
Requires: a Chromium/Chrome binary on PATH; network access on first run to
fetch the Mermaid library (cached in diagrams/_build/mermaid.min.js).
"""

import math
import os
import re
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_MD = os.path.join(ROOT, "DATA_MODEL.md")
OUT_DIR = os.path.join(ROOT, "diagrams")
BUILD = os.path.join(OUT_DIR, "_build")
MERMAID_JS = os.path.join(BUILD, "mermaid.min.js")
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

NAME_HINTS = [
    ("entity-relationship", "er-diagram"),
    ("categories by", "categories"),
    ("sources feed", "source-category-map"),
]

CHROME_CANDIDATES = ["chromium", "chromium-browser", "google-chrome",
                     "google-chrome-stable", "chrome"]


def find_chrome():
    if shutil.which("mmdc"):
        print("note: 'mmdc' is available; this script uses Chromium directly, "
              "but you could also run mmdc.", file=sys.stderr)
    for c in CHROME_CANDIDATES:
        if shutil.which(c):
            return c
    print("ERROR: no Chromium/Chrome binary found (tried: "
          f"{', '.join(CHROME_CANDIDATES)}). Install one, or install Node + "
          "@mermaid-js/mermaid-cli and run `mmdc`.", file=sys.stderr)
    sys.exit(1)


def extract_blocks(md_text):
    """Return [(name, code)] for each ```mermaid fenced block, naming each from
    the nearest preceding '## ' heading."""
    blocks = []
    heading = "diagram"
    i, n = 0, 0
    lines = md_text.splitlines()
    k = 0
    while k < len(lines):
        line = lines[k]
        if line.startswith("## "):
            heading = line[3:].strip()
        if line.strip().startswith("```mermaid"):
            code = []
            k += 1
            while k < len(lines) and not lines[k].strip().startswith("```"):
                code.append(lines[k])
                k += 1
            name = None
            hl = heading.lower()
            for hint, slug in NAME_HINTS:
                if hint in hl:
                    name = slug
                    break
            if not name:
                n += 1
                name = f"diagram-{n}"
            blocks.append((name, "\n".join(code)))
        k += 1
    return blocks


def ensure_mermaid():
    os.makedirs(BUILD, exist_ok=True)
    if not os.path.exists(MERMAID_JS) or os.path.getsize(MERMAID_JS) < 100000:
        print(f"  fetching Mermaid library -> {os.path.relpath(MERMAID_JS, ROOT)}")
        with urllib.request.urlopen(MERMAID_URL, timeout=60) as r:
            data = r.read()
        with open(MERMAID_JS, "wb") as f:
            f.write(data)


def render_html(code, theme_bg="transparent"):
    # Mermaid code is injected as text content of the .mermaid element.
    return f"""<!doctype html><html><head><meta charset="utf-8">
<script src="mermaid.min.js"></script>
<style>body{{margin:0;background:{theme_bg};}}</style></head>
<body><pre class="mermaid">{code}</pre>
<script>
mermaid.initialize({{startOnLoad:false, securityLevel:'loose'}});
mermaid.run();
</script></body></html>"""


def chrome_dump_dom(chrome, html_path):
    out = subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
         "--dump-dom", "--virtual-time-budget=12000",
         f"file://{html_path}"],
        capture_output=True, text=True, timeout=90)
    return out.stdout


def extract_svg(dom):
    start = dom.find("<svg")
    end = dom.rfind("</svg>")
    if start == -1 or end == -1:
        return None
    return dom[start:end + len("</svg>")]


def svg_size(svg):
    m = re.search(r'viewBox="([\-0-9.]+) ([\-0-9.]+) ([\-0-9.]+) ([\-0-9.]+)"', svg)
    if m:
        return float(m.group(3)), float(m.group(4))
    return 1200.0, 800.0


def chrome_screenshot(chrome, html_path, png_path, w, h, scale=2):
    subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
         f"--force-device-scale-factor={scale}",
         f"--window-size={int(math.ceil(w))},{int(math.ceil(h))}",
         f"--screenshot={png_path}", "--default-background-color=FFFFFFFF",
         "--virtual-time-budget=12000", f"file://{html_path}"],
        capture_output=True, text=True, timeout=90)


def main():
    chrome = find_chrome()
    with open(SRC_MD, encoding="utf-8") as f:
        blocks = extract_blocks(f.read())
    if not blocks:
        print("No mermaid blocks found in DATA_MODEL.md", file=sys.stderr)
        sys.exit(1)
    ensure_mermaid()
    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Rendering {len(blocks)} diagram(s) with {chrome}...")
    for name, code in blocks:
        # Pass 1: render in page, grab the SVG from the DOM.
        html1 = os.path.join(BUILD, f"{name}.svg.html")
        with open(html1, "w", encoding="utf-8") as f:
            f.write(render_html(code))
        dom = chrome_dump_dom(chrome, html1)
        svg = extract_svg(dom)
        if not svg:
            print(f"  ! {name}: no SVG produced (skipped)", file=sys.stderr)
            continue
        svg_path = os.path.join(OUT_DIR, f"{name}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + svg)
        w, h = svg_size(svg)

        # Pass 2: standalone page with the SVG sized to its viewBox -> PNG.
        html2 = os.path.join(BUILD, f"{name}.png.html")
        sized = re.sub(r'(<svg\b)', rf'\1 width="{w}" height="{h}"', svg, count=1)
        with open(html2, "w", encoding="utf-8") as f:
            f.write('<!doctype html><html><head><meta charset="utf-8">'
                    '<style>body{margin:0;background:#fff;}</style></head>'
                    f'<body>{sized}</body></html>')
        png_path = os.path.join(OUT_DIR, f"{name}.png")
        chrome_screenshot(chrome, html2, png_path, w + 16, h + 16)

        ssz = os.path.getsize(svg_path)
        psz = os.path.getsize(png_path) if os.path.exists(png_path) else 0
        print(f"  {name:<20} svg={ssz:>7}B  png={psz:>7}B  "
              f"({int(w)}x{int(h)})")

    print(f"\nDiagrams written to {os.path.relpath(OUT_DIR, ROOT)}/")


if __name__ == "__main__":
    main()
