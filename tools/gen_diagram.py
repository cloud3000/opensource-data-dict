#!/usr/bin/env python3
"""
tools/gen_diagram.py - Generate DATA_MODEL.md: Mermaid ER diagram + category
and source-contribution diagrams, read live from datadict.db so they stay
accurate.

Mermaid renders directly on GitHub / most Markdown viewers; the source is plain
text and diffable.

Usage:
    python3 tools/gen_diagram.py
"""

import collections
import os
import sqlite3
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "..", "datadict.db")
OUT = os.path.join(HERE, "..", "DATA_MODEL.md")

# Schema columns for the ER diagram (type, name, key, comment).
CATEGORIES_COLS = [
    ("INTEGER", "CategoryID", "PK", ""),
    ("TEXT", "Name", "UK", "Manufacturing, Finance, ..."),
    ("TEXT", "Description", "", ""),
    ("TEXT", "Source", "", ""),
]
DATAITEMS_COLS = [
    ("INTEGER", "DataItemID", "PK", ""),
    ("INTEGER", "CategoryID", "FK", "-> Categories"),
    ("TEXT", "Name", "", "entity.field (snake_case)"),
    ("TEXT", "Title", "", ""),
    ("TEXT", "Description", "", ""),
    ("TEXT", "DataType", "", "VARCHAR INTEGER DATE ..."),
    ("INTEGER", "ByteLength", "", ""),
    ("INTEGER", "DecimalScale", "", ""),
    ("BOOLEAN", "IsRequired", "", ""),
    ("BOOLEAN", "IsNullable", "", ""),
    ("TEXT", "DefaultValue", "", ""),
    ("TEXT", "AllowedValues", "", "JSON array or per-source object"),
    ("TEXT", "FormatMask", "", ""),
    ("TEXT", "SourceStandard", "", "one or more, '; '-joined"),
    ("TEXT", "SourceURL", "", "one or more, ' | '-joined"),
    ("TEXT", "Version", "", ""),
    ("DATETIME", "CreatedAt", "", ""),
    ("DATETIME", "UpdatedAt", "", ""),
]


def slug(s):
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")


def gather(conn):
    cats = conn.execute(
        """SELECT c.Name AS name, COUNT(d.DataItemID) AS n
           FROM Categories c LEFT JOIN DataItems d ON d.CategoryID=c.CategoryID
           GROUP BY c.CategoryID ORDER BY n DESC"""
    ).fetchall()
    # source x category contribution (split merged "; " source lists)
    matrix = collections.defaultdict(lambda: collections.Counter())
    src_tot = collections.Counter()
    for cat, ss in conn.execute(
            """SELECT c.Name, d.SourceStandard FROM DataItems d
               JOIN Categories c ON c.CategoryID=d.CategoryID"""):
        for s in (ss or "").split("; "):
            s = s.strip()
            if s:
                matrix[cat][s] += 1
                src_tot[s] += 1
    total = conn.execute("SELECT COUNT(*) FROM DataItems").fetchone()[0]
    return cats, matrix, src_tot, total


def coverage(conn):
    """Classify every item's description as from-source, curated, or missing.

    An item is 'curated' when its Name is in tools/curated_descriptions.py and
    its stored Description matches that editorial text; non-empty otherwise =
    'from source'; empty = 'missing'. Returns (per_category, totals)."""
    try:
        from curated_descriptions import CURATED
    except Exception:  # noqa: BLE001
        CURATED = {}
    per_cat = collections.defaultdict(
        lambda: {"total": 0, "source": 0, "curated": 0, "missing": 0})
    tot = {"source": 0, "curated": 0, "missing": 0}
    for cat, name, descr in conn.execute(
            """SELECT c.Name, d.Name, d.Description FROM DataItems d
               JOIN Categories c ON c.CategoryID=d.CategoryID"""):
        pc = per_cat[cat]
        pc["total"] += 1
        if not (descr or "").strip():
            pc["missing"] += 1
            tot["missing"] += 1
        elif name in CURATED and descr == CURATED[name]:
            pc["curated"] += 1
            tot["curated"] += 1
        else:
            pc["source"] += 1
            tot["source"] += 1
    return per_cat, tot


def coverage_block(per_cat, tot, total):
    """Provenance pie + per-category coverage table."""
    lines = ['```mermaid', 'pie showData title Description provenance']
    lines.append(f'    "From source" : {tot["source"]}')
    lines.append(f'    "Curated (editorial)" : {tot["curated"]}')
    if tot["missing"]:
        lines.append(f'    "Missing" : {tot["missing"]}')
    lines.append('```')
    pie = "\n".join(lines) + "\n"

    cats = sorted(per_cat, key=lambda c: -per_cat[c]["total"])
    rows = ["| Category | Items | From source | Curated | Coverage |",
            "|---|---:|---:|---:|---:|"]
    for c in cats:
        d = per_cat[c]
        cov = 100.0 * (d["source"] + d["curated"]) / d["total"] if d["total"] else 0
        rows.append(f"| {c} | {d['total']} | {d['source']} | {d['curated']} "
                    f"| {cov:.0f}% |")
    described = tot["source"] + tot["curated"]
    pct = 100.0 * described / total if total else 0
    rows.append(f"| **All** | **{total}** | **{tot['source']}** "
                f"| **{tot['curated']}** | **{pct:.0f}%** |")
    return pie, "\n".join(rows), pct


def er_block():
    def cols(rows):
        out = []
        for typ, name, key, comment in rows:
            line = f"        {typ} {name}"
            if key:
                line += f" {key}"
            if comment:
                line += f' "{comment}"'
            out.append(line)
        return "\n".join(out)
    return (
        "```mermaid\nerDiagram\n"
        '    Categories ||--o{ DataItems : "categorizes"\n'
        "    Categories {\n" + cols(CATEGORIES_COLS) + "\n    }\n"
        "    DataItems {\n" + cols(DATAITEMS_COLS) + "\n    }\n"
        "```\n"
    )


def pie_block(cats):
    lines = ['```mermaid', 'pie showData title Data items by category']
    for r in cats:
        lines.append(f'    "{r["name"]}" : {r["n"]}')
    lines.append('```')
    return "\n".join(lines) + "\n"


def flow_block(matrix, src_tot):
    # Bipartite: sources (left) -> categories (right), edge label = count.
    sources = [s for s, _ in src_tot.most_common()]
    cats = sorted(matrix.keys(), key=lambda c: -sum(matrix[c].values()))
    sid = {s: f"S{i}" for i, s in enumerate(sources)}
    cid = {c: f"C{i}" for i, c in enumerate(cats)}
    L = ["```mermaid", "flowchart LR"]
    L.append("    subgraph SOURCES")
    for s in sources:
        L.append(f'        {sid[s]}["{s}<br/>{src_tot[s]}"]')
    L.append("    end")
    L.append("    subgraph CATEGORIES")
    for c in cats:
        L.append(f'        {cid[c]}["{c}<br/>{sum(matrix[c].values())}"]')
    L.append("    end")
    for c in cats:
        for s, n in matrix[c].most_common():
            L.append(f"    {sid[s]} -->|{n}| {cid[c]}")
    L.append("```")
    return "\n".join(L) + "\n"


def matrix_table(matrix, src_tot):
    sources = [s for s, _ in src_tot.most_common()]
    cats = sorted(matrix.keys(), key=lambda c: -sum(matrix[c].values()))
    header = "| Category | " + " | ".join(sources) + " | **Total\\*** |"
    sep = "|" + "---|" * (len(sources) + 2)
    rows = [header, sep]
    for c in cats:
        cells = [str(matrix[c].get(s, "") or "") for s in sources]
        rows.append(f"| {c} | " + " | ".join(cells) +
                    f" | **{sum(matrix[c].values())}** |")
    totals = [str(src_tot[s]) for s in sources]
    rows.append("| **Total\\*** | " + " | ".join(f"**{t}**" for t in totals) +
                " | |")
    return "\n".join(rows)


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cats, matrix, src_tot, total = gather(conn)
    per_cat, cov_tot = coverage(conn)

    parts = []
    parts.append("# Data Model & Diagrams\n")
    parts.append(f"_Auto-generated by `tools/gen_diagram.py` from `datadict.db` "
                 f"on {datetime.now(timezone.utc).date()} — "
                 f"{total} items, {len(cats)} categories, "
                 f"{len(src_tot)} sources._\n")
    parts.append("> Diagrams use [Mermaid](https://mermaid.js.org/), which "
                 "renders natively on GitHub. Static **SVG/PNG** exports live "
                 "in [`diagrams/`](diagrams/) — regenerate them with "
                 "`python3 tools/render_diagrams.py`.\n")
    parts.append("| Diagram | SVG | PNG |\n|---|---|---|\n"
                 "| ER diagram | [er-diagram.svg](diagrams/er-diagram.svg) "
                 "| [er-diagram.png](diagrams/er-diagram.png) |\n"
                 "| Categories | [categories.svg](diagrams/categories.svg) "
                 "| [categories.png](diagrams/categories.png) |\n"
                 "| Description coverage "
                 "| [description-coverage.svg](diagrams/description-coverage.svg) "
                 "| [description-coverage.png](diagrams/description-coverage.png) |\n"
                 "| Source→Category map "
                 "| [source-category-map.svg](diagrams/source-category-map.svg) "
                 "| [source-category-map.png](diagrams/source-category-map.png) |\n")

    parts.append("## 1. Entity-Relationship diagram\n")
    parts.append("The dictionary is a simple two-table star: many `DataItems` "
                 "per `Category`.\n")
    parts.append(er_block())

    parts.append("\n## 2. Categories by item count\n")
    parts.append(pie_block(cats))

    cov_pie, cov_table, pct = coverage_block(per_cat, cov_tot, total)
    parts.append("\n## 3. Description coverage & provenance\n")
    parts.append(f"Every data item carries a description (**{pct:.0f}% coverage**). "
                 "Most come straight from the upstream source; the rest are "
                 "curated editorial text added where the source provided none "
                 "(see [`tools/curated_descriptions.py`](tools/curated_descriptions.py)).\n")
    parts.append(cov_pie)
    parts.append("\n" + cov_table + "\n")

    parts.append("\n## 4. Which sources feed which categories\n")
    parts.append("Edge labels = number of items each source contributes to a "
                 "category.\n")
    parts.append(flow_block(matrix, src_tot))

    parts.append("\n## 5. Source contribution matrix\n")
    parts.append(matrix_table(matrix, src_tot))
    parts.append("\n\n\\* Contribution totals count an item once **per source** "
                 "it carries, so cross-source-merged items are counted in each "
                 "contributing source; these totals therefore exceed the "
                 f"{total} distinct items.\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"Wrote {os.path.relpath(OUT)} "
          f"({total} items, {len(cats)} categories, {len(src_tot)} sources)")


if __name__ == "__main__":
    main()
