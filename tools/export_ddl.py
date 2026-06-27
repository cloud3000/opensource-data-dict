#!/usr/bin/env python3
"""
tools/export_ddl.py - Export CREATE TABLE DDL (with FOREIGN KEYs) for a set of
entities resolved from business terms, in SQLite / PostgreSQL / MySQL dialects.

Builds on tools/find.py's resolver: a term (category, entity, alias, or keyword)
selects items; items group by entity into one table each. Column types, lengths,
NOT NULL, and enum CHECKs come from the dictionary metadata.

Foreign keys
------------
The dictionary encodes relationships in descriptions:
  * "(links to X)"      - ERPNext Link  -> single FK
  * "(references X)"     - Odoo/Tryton Many2One -> single FK
                          (FHIR Reference may list several targets -> polymorphic,
                          kept as a plain column, not a FK)
  * "(collection of X)" - One2many/Many2many reverse relation -> NOT a column
                          on this table (listed as a comment instead)

A FK column is modeled with a surrogate-key convention: it becomes an INTEGER
referencing the parent's `<table>_id`, regardless of the source field's own type
(ERPNext links by name, etc.), so the generated schema is internally consistent.
A FK is only emitted when its target table is part of the same export (or a self
reference); otherwise the column is kept with an "external ref" comment.

Tables are emitted in dependency order (topological sort) so the DDL loads under
strict dialects (PostgreSQL/MySQL) too.

Usage
-----
    python3 tools/export_ddl.py work_order
    python3 tools/export_ddl.py manufacturing --dialect postgres
    python3 tools/export_ddl.py billing patient --out schema.sql
    python3 tools/export_ddl.py inventory --dialect mysql
"""

import argparse
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import find  # noqa: E402  (reuse the resolver)

_HINT = re.compile(r"\((?:links to|references)\s+([^)]*)\)", re.I)


def norm(s):
    """Canonical table/identifier name: lower, non-alnum -> _, collapse, strip."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-z]+", "_", s.lower())).strip("_")


def fk_target(desc):
    """Return a single FK target name from a description, or None.

    None when there's no link hint, when it's a 'collection of' (reverse), or
    when several targets are listed (polymorphic reference)."""
    if not desc:
        return None
    m = _HINT.search(desc)
    if not m:
        return None
    targets = [t.strip() for t in m.group(1).split(",") if t.strip()]
    return norm(targets[0]) if len(targets) == 1 else None


def is_collection(desc):
    return bool(desc) and "collection of" in desc.lower()


# Per-dialect type rendering ------------------------------------------------
def _pk(dialect, table):
    return {"sqlite": f"{table}_id INTEGER PRIMARY KEY",
            "postgres": f"{table}_id SERIAL PRIMARY KEY",
            "mysql": f"{table}_id INT AUTO_INCREMENT PRIMARY KEY"}[dialect]


def _coltype(dialect, r, is_fk):
    if is_fk:
        return {"sqlite": "INTEGER", "postgres": "INTEGER", "mysql": "INT"}[dialect]
    t, n, s = r["DataType"], r["ByteLength"], r["DecimalScale"]
    n = n if (isinstance(n, int) and 0 < n <= 65535) else 255
    s = s if s is not None else 2
    table = {
        "VARCHAR":  {"sqlite": f"VARCHAR({n})", "postgres": f"VARCHAR({n})", "mysql": f"VARCHAR({n})"},
        "TEXT":     {"sqlite": "TEXT", "postgres": "TEXT", "mysql": "TEXT"},
        "INTEGER":  {"sqlite": "INTEGER", "postgres": "INTEGER", "mysql": "INT"},
        "DECIMAL":  {"sqlite": f"DECIMAL(18,{s})", "postgres": f"DECIMAL(18,{s})", "mysql": f"DECIMAL(18,{s})"},
        "BOOLEAN":  {"sqlite": "BOOLEAN", "postgres": "BOOLEAN", "mysql": "TINYINT(1)"},
        "DATE":     {"sqlite": "DATE", "postgres": "DATE", "mysql": "DATE"},
        "DATETIME": {"sqlite": "DATETIME", "postgres": "TIMESTAMP", "mysql": "DATETIME"},
        "TIME":     {"sqlite": "TIME", "postgres": "TIME", "mysql": "TIME"},
        "RELATION": {"sqlite": "INTEGER", "postgres": "INTEGER", "mysql": "INT"},
        "OBJECT":   {"sqlite": "TEXT", "postgres": "JSONB", "mysql": "JSON"},
        "BLOB":     {"sqlite": "BLOB", "postgres": "BYTEA", "mysql": "BLOB"},
    }.get(t, {"sqlite": "TEXT", "postgres": "TEXT", "mysql": "TEXT"})
    return table[dialect]


def _enum_check(col, av):
    if not av:
        return None
    try:
        vals = json.loads(av)
    except (ValueError, TypeError):
        return None
    if isinstance(vals, list) and vals and all(isinstance(v, str) for v in vals):
        q = ", ".join("'" + v.replace("'", "''") + "'" for v in vals)
        if len(q) <= 110:
            return f"CHECK ({col} IN ({q}))"
    return None


def build_tables(items):
    """Group items by entity -> {table: {cols, fks, reverse, source}}."""
    by_entity = {}
    for r in items:
        by_entity.setdefault(find.entity_of(r["Name"]), []).append(r)
    emitted = {norm(e) for e in by_entity}
    tables = {}
    for ent, rows in by_entity.items():
        table = norm(ent)
        cols, fks, reverse = [], [], []
        seen = set()
        for r in sorted(rows, key=lambda r: (0 if r["IsRequired"] else 1, r["Name"])):
            field = r["Name"].split(".", 1)[1] if "." in r["Name"] else r["Name"]
            col = norm(field)
            if not col or col == f"{table}_id" or col in seen:
                continue
            if is_collection(r["Description"]):
                reverse.append((col, r["Description"]))
                continue
            seen.add(col)
            tgt = fk_target(r["Description"])
            is_fk = bool(tgt) and (tgt in emitted)
            cols.append((col, r, is_fk, tgt))
            if is_fk:
                fks.append((col, tgt))
        tables[table] = {"entity": ent, "cols": cols, "fks": fks,
                         "reverse": reverse, "source": rows[0]["SourceStandard"]}
    return tables, emitted


def topo_order(tables):
    """Order tables so a table's FK targets are created first (self-refs ignored).
    Leftover cycles are appended in name order."""
    deps = {t: {tgt for _, tgt in tables[t]["fks"] if tgt != t and tgt in tables}
            for t in tables}
    order, ready = [], sorted(t for t in tables if not deps[t])
    placed = set()
    while ready:
        t = ready.pop(0)
        order.append(t); placed.add(t)
        for u in sorted(tables):
            if u not in placed and u not in order and deps[u] <= placed and u not in ready:
                ready.append(u)
    for t in sorted(tables):  # any remaining (cycles)
        if t not in order:
            order.append(t)
    return order


def render(tables, dialect):
    out = []
    if dialect == "sqlite":
        out.append("PRAGMA foreign_keys = ON;\n")
    elif dialect == "mysql":
        out.append("SET FOREIGN_KEY_CHECKS = 1;\n")
    for table in topo_order(tables):
        info = tables[table]
        out.append(f"-- {info['entity']}  ({len(info['cols'])} columns, "
                   f"{len(info['fks'])} FKs)  [source: {info['source']}]")
        for col, desc in info["reverse"]:
            out.append(f"--   reverse relation: {col}  {desc}")
        out.append(f"CREATE TABLE {table} (")
        lines = [f"    {_pk(dialect, table)}"]
        for col, r, is_fk, tgt in info["cols"]:
            d = f"{col} {_coltype(dialect, r, is_fk)}"
            if r["IsRequired"]:
                d += " NOT NULL"
            chk = None if is_fk else _enum_check(col, r["AllowedValues"])
            if chk:
                d += " " + chk
            cmt = ""
            if is_fk:
                cmt = ""  # FK shown as constraint below
            elif fk_target(r["Description"]) and not is_fk:
                cmt = "  -- external ref: " + (r["Description"] or "")[:50]
            lines.append(f"    {d}{cmt}")
        for col, tgt in info["fks"]:
            lines.append(f"    FOREIGN KEY ({col}) REFERENCES {tgt}({tgt}_id)")
        out.append("\n".join(_strip_dup_comma(lines)))
        out.append(");\n")
    return "\n".join(out)


def _strip_dup_comma(lines):
    """Join helper: comments must not swallow the comma, so move any '  --' to
    after the comma at print time."""
    fixed = []
    for ln in lines:
        if "  --" in ln:
            body, _, cmt = ln.partition("  --")
            fixed.append((body.rstrip(), "  --" + cmt))
        else:
            fixed.append((ln, ""))
    out = []
    for i, (body, cmt) in enumerate(fixed):
        comma = "," if i < len(fixed) - 1 else ""
        out.append(f"{body}{comma}{cmt}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export CREATE TABLE DDL with FKs.")
    ap.add_argument("terms", nargs="+", help="business term(s): category/entity/alias")
    ap.add_argument("--dialect", choices=["sqlite", "postgres", "mysql"],
                    default="sqlite")
    ap.add_argument("--out", help="write to this file instead of stdout")
    args = ap.parse_args(argv)

    conn = find.connect()
    items, seen = [], set()
    for term in args.terms:
        _, rows, _ = find.resolve(conn, term)
        for r in rows:
            if r["Name"] not in seen:
                seen.add(r["Name"]); items.append(r)
    if not items:
        print("No items matched.", file=sys.stderr)
        return 1

    tables, _ = build_tables(items)
    ddl = render(tables, args.dialect)
    header = (f"-- DDL generated by tools/export_ddl.py ({args.dialect})\n"
              f"-- terms: {', '.join(args.terms)}\n"
              f"-- {len(tables)} tables, {len(items)} items\n\n")
    ddl = header + ddl

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(ddl)
        print(f"Wrote {args.out} ({len(tables)} tables).")
    else:
        print(ddl)

    if args.dialect == "sqlite":
        try:
            sqlite3.connect(":memory:").executescript(ddl)
            print("-- validated: loads cleanly in SQLite", file=sys.stderr)
        except sqlite3.Error as e:
            print(f"-- VALIDATION FAILED: {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
