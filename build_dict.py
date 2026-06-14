#!/usr/bin/env python3
"""
build_dict.py - Business Application Data Dictionary builder.

Creates and maintains `datadict.db` (SQLite) plus exports `datadict.sql`.
The dictionary collects standardized business data items from public /
open-source resources only (B2MML/ISA-95, Microsoft CDM, Odoo, ERPNext,
Tryton, Schema.org, public JSON Schemas, etc.).

Design notes
------------
* Idempotent: re-running the script will not create duplicates. Categories
  are keyed by Name (UNIQUE per the schema); DataItems are keyed by the
  natural composite (CategoryID, Name, SourceStandard) via a UNIQUE index
  added for upsert safety.
* No heavy third-party dependencies -- only the standard library.
* Seed data lives in the `seeds/` package, one module per source. Each
  module exposes `CATEGORIES` and `ITEMS` lists that this script loads.

Usage
-----
    python3 build_dict.py            # build/update datadict.db and export .sql
    python3 build_dict.py --stats    # print summary statistics only
"""

import argparse
import importlib
import os
import pkgutil
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "datadict.db")
SQL_PATH = os.path.join(HERE, "datadict.sql")

# ---------------------------------------------------------------------------
# Schema (matches CLAUDE.md "Core Database Schema") + idempotency index.
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS Categories (
    CategoryID  INTEGER PRIMARY KEY,
    Name        TEXT NOT NULL UNIQUE,        -- e.g., "Manufacturing", "Finance"
    Description TEXT,
    Source      TEXT
);

CREATE TABLE IF NOT EXISTS DataItems (
    DataItemID   INTEGER PRIMARY KEY,
    CategoryID   INTEGER NOT NULL REFERENCES Categories(CategoryID),

    Name         TEXT NOT NULL,              -- e.g., "CustomerID", "GTIN"
    Title        TEXT,                       -- Human readable title
    Description  TEXT,

    DataType     TEXT,                       -- VARCHAR, DECIMAL, DATE, INTEGER...
    ByteLength   INTEGER,                    -- max length / total bytes
    DecimalScale INTEGER,                    -- for numeric/decimal fields

    IsRequired   BOOLEAN DEFAULT FALSE,
    IsNullable   BOOLEAN DEFAULT TRUE,
    DefaultValue TEXT,

    AllowedValues TEXT,                      -- JSON array or comma-separated
    FormatMask    TEXT,                      -- e.g., "YYYY-MM-DD", "999.99"

    SourceStandard TEXT,                     -- "ISA-95", "Microsoft CDM", ...
    SourceURL      TEXT,
    Version        TEXT,

    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dataitems_category ON DataItems(CategoryID);
CREATE INDEX IF NOT EXISTS idx_dataitems_name     ON DataItems(Name);

-- Added for idempotent upserts: a data item is uniquely identified by the
-- combination of its category, name, and originating source standard.
CREATE UNIQUE INDEX IF NOT EXISTS ux_dataitems_natural
    ON DataItems(CategoryID, Name, SourceStandard);
"""


# ---------------------------------------------------------------------------
# Connection / schema helpers
# ---------------------------------------------------------------------------

def connect(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Idempotent upserts
# ---------------------------------------------------------------------------

def insert_or_update_category(conn, name, description=None, source=None):
    """Insert a category or update its description/source. Returns CategoryID."""
    conn.execute(
        """
        INSERT INTO Categories (Name, Description, Source)
        VALUES (:name, :description, :source)
        ON CONFLICT(Name) DO UPDATE SET
            Description = COALESCE(excluded.Description, Categories.Description),
            Source      = COALESCE(excluded.Source,      Categories.Source)
        """,
        {"name": name, "description": description, "source": source},
    )
    row = conn.execute(
        "SELECT CategoryID FROM Categories WHERE Name = ?", (name,)
    ).fetchone()
    return row["CategoryID"]


def insert_or_update_item(conn, category_id, name, **fields):
    """
    Insert or update a single data item, keyed by
    (CategoryID, Name, SourceStandard).

    Recognised keyword fields mirror the DataItems columns:
        title, description, data_type, byte_length, decimal_scale,
        is_required, is_nullable, default_value, allowed_values,
        format_mask, source_standard, source_url, version
    """
    cols = {
        "CategoryID": category_id,
        "Name": name,
        "Title": fields.get("title"),
        "Description": fields.get("description"),
        "DataType": fields.get("data_type"),
        "ByteLength": fields.get("byte_length"),
        "DecimalScale": fields.get("decimal_scale"),
        "IsRequired": int(fields["is_required"]) if "is_required" in fields else 0,
        "IsNullable": int(fields["is_nullable"]) if "is_nullable" in fields else 1,
        "DefaultValue": fields.get("default_value"),
        "AllowedValues": fields.get("allowed_values"),
        "FormatMask": fields.get("format_mask"),
        "SourceStandard": fields.get("source_standard"),
        "SourceURL": fields.get("source_url"),
        "Version": fields.get("version"),
    }
    conn.execute(
        """
        INSERT INTO DataItems
            (CategoryID, Name, Title, Description, DataType, ByteLength,
             DecimalScale, IsRequired, IsNullable, DefaultValue, AllowedValues,
             FormatMask, SourceStandard, SourceURL, Version)
        VALUES
            (:CategoryID, :Name, :Title, :Description, :DataType, :ByteLength,
             :DecimalScale, :IsRequired, :IsNullable, :DefaultValue,
             :AllowedValues, :FormatMask, :SourceStandard, :SourceURL, :Version)
        ON CONFLICT(CategoryID, Name, SourceStandard) DO UPDATE SET
            Title         = COALESCE(excluded.Title,         DataItems.Title),
            Description   = COALESCE(excluded.Description,   DataItems.Description),
            DataType      = COALESCE(excluded.DataType,      DataItems.DataType),
            ByteLength    = COALESCE(excluded.ByteLength,    DataItems.ByteLength),
            DecimalScale  = COALESCE(excluded.DecimalScale,  DataItems.DecimalScale),
            IsRequired    = excluded.IsRequired,
            IsNullable    = excluded.IsNullable,
            DefaultValue  = COALESCE(excluded.DefaultValue,  DataItems.DefaultValue),
            AllowedValues = COALESCE(excluded.AllowedValues, DataItems.AllowedValues),
            FormatMask    = COALESCE(excluded.FormatMask,    DataItems.FormatMask),
            SourceURL     = COALESCE(excluded.SourceURL,     DataItems.SourceURL),
            Version       = COALESCE(excluded.Version,       DataItems.Version),
            UpdatedAt     = CURRENT_TIMESTAMP
        """,
        cols,
    )


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------

def load_seeds(conn):
    """Discover and load every module in the `seeds` package.

    Each seed module may define:
        CATEGORIES : list of dicts {name, description, source}
        ITEMS      : list of dicts {category, name, ...item fields...}
    where ITEMS[*]["category"] is the category Name.

    All raw items pass through Phase 3 normalization + cross-source
    deduplication (normalize.normalize_and_dedupe) before insertion.
    Returns (loaded_modules, raw_count, report).
    """
    import seeds  # noqa: F401  (package import)
    from normalize import normalize_and_dedupe

    cat_ids = {}
    loaded_modules = []
    raw_items = []

    for mod_info in sorted(pkgutil.iter_modules(seeds.__path__)):
        module = importlib.import_module(f"seeds.{mod_info.name}")
        loaded_modules.append(mod_info.name)

        for cat in getattr(module, "CATEGORIES", []):
            cid = insert_or_update_category(
                conn, cat["name"], cat.get("description"), cat.get("source")
            )
            cat_ids[cat["name"]] = cid

        for item in getattr(module, "ITEMS", []):
            raw_items.append(dict(item))

    # Phase 3: normalize naming + merge genuinely identical items.
    clean_items, report = normalize_and_dedupe(raw_items)

    for item in clean_items:
        cat_name = item["category"]
        if cat_name not in cat_ids:
            cat_ids[cat_name] = insert_or_update_category(conn, cat_name)
        fields = {k: v for k, v in item.items()
                  if k not in ("category", "name")}
        insert_or_update_item(conn, cat_ids[cat_name], item["name"], **fields)

    conn.commit()
    return loaded_modules, len(raw_items), report


# ---------------------------------------------------------------------------
# Export & reporting
# ---------------------------------------------------------------------------

def export_sql(conn, sql_path=SQL_PATH):
    """Dump the full schema + data to datadict.sql."""
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("-- datadict.sql - Business Data Dictionary\n")
        f.write(f"-- Generated {datetime.now(timezone.utc).isoformat()} (UTC)\n")
        f.write("-- Source: build_dict.py (open-source data only)\n\n")
        f.write("PRAGMA foreign_keys = ON;\n\n")
        for line in conn.iterdump():
            f.write(f"{line}\n")


def write_normalization_report(report, path=None):
    """Write the Phase 3 normalization/dedup report to NORMALIZATION_REPORT.md."""
    path = path or os.path.join(HERE, "NORMALIZATION_REPORT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Phase 3 - Normalization & Deduplication Report\n\n")
        f.write(f"_Generated {datetime.now(timezone.utc).isoformat()} (UTC) "
                "by build_dict.py._\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Raw seed items: **{report['input_items']}**\n")
        f.write(f"- Items after normalization + dedup: **{report['output_items']}**\n")
        f.write(f"- Cross-source merges performed: **{report['merged_concepts']}**\n")
        f.write(f"- Related concepts flagged (not merged): "
                f"**{len(report['related_concepts'])}**\n\n")
        f.write("All Names normalized to consistent `entity.field` snake_case.\n\n")

        f.write("## Entity aliases applied\n\n")
        f.write("Deliberate equivalences (see `ENTITY_ALIASES` in `normalize.py`) "
                "that fold a source's namespaced entity into a canonical entity so "
                "matching fields can merge across sources.\n\n")
        if report.get("aliases_applied"):
            f.write("| Source entity | Canonical entity | Items remapped |\n")
            f.write("|---|---|---|\n")
            for a in report["aliases_applied"]:
                f.write(f"| `{a['source_entity']}` | `{a['canonical']}` "
                        f"| {a['items']} |\n")
        else:
            f.write("_None applied._\n")
        f.write("\n")

        f.write("## Field aliases applied\n\n")
        f.write("Single-element equivalences (see `FIELD_ALIASES` in "
                "`normalize.py`) that fold a source's standalone data element "
                "into a specific field of a canonical entity (e.g. GS1 AIs).\n\n")
        if report.get("field_aliases_applied"):
            f.write("| Source field | Canonical field | Items remapped |\n")
            f.write("|---|---|---|\n")
            for a in report["field_aliases_applied"]:
                f.write(f"| `{a['source_field']}` | `{a['canonical']}` "
                        f"| {a['items']} |\n")
        else:
            f.write("_None applied._\n")
        f.write("\n")

        f.write("## Cross-source merges (kept best version, all sources noted)\n\n")
        if report["merges"]:
            f.write("| Category | Item | Sources | #rows merged |\n")
            f.write("|---|---|---|---|\n")
            for m in report["merges"]:
                f.write(f"| {m['category']} | `{m['name']}` | {m['sources']} "
                        f"| {m['count']} |\n")
        else:
            f.write("_None._ Each source standard models a distinct set of "
                    "entities, so no two items describe the exact same "
                    "`entity.field`. No rows were merged (accuracy over "
                    "quantity). The merge rule remains active for future "
                    "sources.\n")
        f.write("\n")

        f.write("## Related concepts (same field name, different entities)\n\n")
        f.write("These share a field *name* across sources but belong to "
                "**different entities**, so they are deliberately kept "
                "separate. Listed for cross-reference only.\n\n")
        if report["related_concepts"]:
            f.write("| Category | Field | Entities | Sources |\n")
            f.write("|---|---|---|---|\n")
            for r in report["related_concepts"]:
                f.write(f"| {r['category']} | `{r['field']}` | "
                        f"{', '.join(r['entities'])} | "
                        f"{', '.join(r['sources'])} |\n")
        else:
            f.write("_None._\n")
        f.write("\n")


def print_stats(conn):
    rows = conn.execute(
        """
        SELECT c.Name AS category, COUNT(d.DataItemID) AS n
        FROM Categories c
        LEFT JOIN DataItems d ON d.CategoryID = c.CategoryID
        GROUP BY c.CategoryID
        ORDER BY n DESC, c.Name
        """
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) AS n FROM DataItems").fetchone()["n"]
    n_cat = conn.execute("SELECT COUNT(*) AS n FROM Categories").fetchone()["n"]
    # SourceStandard may hold a merged "A; B" list; count atomic standards.
    atomic = set()
    for r in conn.execute("SELECT DISTINCT SourceStandard FROM DataItems"):
        for s in (r["SourceStandard"] or "").split(";"):
            if s.strip():
                atomic.add(s.strip())
    n_src = len(atomic)

    print(f"\n=== Data Dictionary Statistics ===")
    print(f"Categories: {n_cat}   Data items: {total}   Source standards: {n_src}\n")
    for r in rows:
        print(f"  {r['category']:<32} {r['n']:>5} items")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the business data dictionary.")
    parser.add_argument("--stats", action="store_true",
                        help="Print statistics from the existing DB and exit.")
    parser.add_argument("--no-export", action="store_true",
                        help="Skip writing datadict.sql.")
    args = parser.parse_args(argv)

    conn = connect()
    init_schema(conn)

    if args.stats:
        print_stats(conn)
        return 0

    modules, n, report = load_seeds(conn)
    print(f"Loaded {len(modules)} seed module(s): {', '.join(modules) or '(none)'}")
    print(f"Phase 3 normalization: {report['input_items']} raw -> "
          f"{report['output_items']} items "
          f"({report['merged_concepts']} cross-source merges, "
          f"{len(report['related_concepts'])} related concepts flagged).")

    write_normalization_report(report)

    if not args.no_export:
        export_sql(conn)
        print(f"Exported schema + data -> {os.path.relpath(SQL_PATH, HERE)}")

    print_stats(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
