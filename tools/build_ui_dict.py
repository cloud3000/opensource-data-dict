#!/usr/bin/env python3
"""
tools/build_ui_dict.py - Derive ui_datadict.db from datadict.db.

A UI / resource-governance projection of the dictionary:

  * Every item belongs to a **Group** = its entity (everything left of the last
    dot in the source Name). The 43 transient wizard / relation (junction)
    entities are collapsed into one catch-all group named **Wizard**.
  * `Name` is reduced to the field (the part after the group); Wizard-group
    items keep their full source path (no single prefix to strip).
  * All items are treated as UTF-8 with an *implied* `DataType`. `CharLength`
    is set per a default policy (declared VARCHAR length, else by type);
    `ByteLength = CharLength * 4` (UTF-8 worst case) for resource governance.
  * `ValidationSpecs` reuses the source FormatMask (e.g. GS1) when present,
    otherwise is generated from the type / allowed values / scale.

Schema: Categories (copied) -> Groups -> UI_DataItems. CategoryID lives on
Groups (each group is one category; multi-category groups gs1/Wizard use their
modal category).

datadict.db is read-only here. Re-run any time; output is rebuilt from scratch.

    python3 tools/build_ui_dict.py
"""

import collections
import json
import os
import re
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "datadict.db")
DST = os.path.join(ROOT, "ui_datadict.db")
SQL = os.path.join(ROOT, "ui_datadict.sql")

WIZARD = {"ask", "start", "result", "preview", "context", "default", "show"}

SCHEMA = """
CREATE TABLE Categories (
    CategoryID  INTEGER PRIMARY KEY,
    Name        TEXT NOT NULL UNIQUE,
    Description TEXT,
    Source      TEXT
);
CREATE TABLE Groups (
    GroupID     INTEGER PRIMARY KEY,
    Groupname   TEXT NOT NULL UNIQUE,
    CategoryID  INTEGER NOT NULL REFERENCES Categories(CategoryID),
    Description TEXT,
    Source      TEXT
);
CREATE TABLE UI_DataItems (
    DataItemID    INTEGER PRIMARY KEY,
    GroupID       INTEGER NOT NULL REFERENCES Groups(GroupID),
    Name          TEXT NOT NULL,
    Title         TEXT,
    Description   TEXT,
    DataType      TEXT,
    CharLength    INTEGER,
    ByteLength    INTEGER,
    DecimalScale  INTEGER,
    IsRequired    BOOLEAN DEFAULT FALSE,
    IsNullable    BOOLEAN DEFAULT TRUE,
    DefaultValue  TEXT,
    AllowedValues TEXT,
    ValidationSpecs TEXT,
    Version       TEXT,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ui_group ON UI_DataItems(GroupID);
CREATE INDEX idx_ui_name  ON UI_DataItems(Name);
CREATE UNIQUE INDEX ux_ui_natural ON UI_DataItems(GroupID, Name);
"""


def entity_of(name):
    return name.rsplit(".", 1)[0] if "." in name else name


def bucket(e):
    """table | component | catalog | noise (same classifier as the analysis)."""
    segs = e.split(".")
    if e == "gs1":
        return "catalog"
    if any(s in WIZARD for s in segs):
        return "noise"
    if any("_" in s for s in segs[:-1]):
        return "noise"
    return "entity"   # table or component — both are real per-entity groups


def char_length(dt, byte_len, scale):
    dt = (dt or "").upper()
    if dt == "VARCHAR":
        return byte_len if isinstance(byte_len, int) and byte_len > 0 else 255
    if dt in ("TEXT", "OBJECT"):
        return 4000
    if dt == "INTEGER":
        return 11
    if dt == "BIGINT":
        return 20
    if dt in ("DECIMAL", "DOUBLE"):
        s = scale if isinstance(scale, int) and scale > 0 else 0
        return 18 + 1 + (1 if s else 0)        # digits + sign + decimal point
    if dt == "BOOLEAN":
        return 5
    if dt == "DATE":
        return 10
    if dt == "DATETIME":
        return 25
    if dt == "TIME":
        return 8
    if dt == "RELATION":
        return 64
    if dt == "BLOB":
        return 8000
    return 255


def validation_spec(dt, fmtmask, allowed, scale, clen):
    if fmtmask:
        return fmtmask                         # preserve source mask (e.g. GS1)
    dt = (dt or "").upper()
    if allowed:
        try:
            vals = json.loads(allowed)
        except (ValueError, TypeError):
            vals = None
        if isinstance(vals, list) and vals and all(isinstance(v, str) for v in vals):
            shown = vals[:12]
            s = "one of: " + "|".join(shown) + ("|…" if len(vals) > 12 else "")
            if len(s) <= 200:
                return s
    if dt == "DATE":
        return r"^\d{4}-\d{2}-\d{2}$"
    if dt == "DATETIME":
        return r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?"
    if dt == "TIME":
        return r"^\d{2}:\d{2}(:\d{2})?$"
    if dt == "BOOLEAN":
        return r"^(true|false|0|1)$"
    if dt in ("INTEGER", "BIGINT"):
        return r"^-?\d+$"
    if dt in ("DECIMAL", "DOUBLE"):
        s = scale if isinstance(scale, int) and scale > 0 else 0
        return (r"^-?\d+(\.\d{1,%d})?$" % s) if s else r"^-?\d+$"
    if dt == "RELATION":
        return "key reference"
    if dt in ("VARCHAR", "TEXT", "OBJECT"):
        return "maxlength: %d" % clen
    return None


def ui_name(orig, groupname):
    if groupname == "Wizard":
        return orig                            # no single prefix to strip
    pref = groupname + "."
    return orig[len(pref):] if orig.startswith(pref) else orig.rsplit(".", 1)[-1]


def group_name(name):
    e = entity_of(name)
    return "Wizard" if bucket(e) == "noise" else e


def main():
    src = sqlite3.connect(SRC); src.row_factory = sqlite3.Row
    rows = src.execute("""SELECT d.*, c.Name AS CategoryName
                          FROM DataItems d JOIN Categories c
                          ON c.CategoryID = d.CategoryID""").fetchall()
    cats = src.execute("SELECT * FROM Categories").fetchall()

    # entity -> parent (for component descriptions)
    entities = {entity_of(r["Name"]) for r in rows}
    def parent(e):
        ps = [p for p in entities if e.startswith(p + ".")]
        return max(ps, key=len) if ps else None

    # Aggregate groups
    g_items = collections.defaultdict(list)
    for r in rows:
        g_items[group_name(r["Name"])].append(r)

    if os.path.exists(DST):
        os.remove(DST)
    dst = sqlite3.connect(DST)
    dst.executescript(SCHEMA)

    for c in cats:
        dst.execute("INSERT INTO Categories (CategoryID,Name,Description,Source) "
                    "VALUES (?,?,?,?)", (c["CategoryID"], c["Name"],
                                         c["Description"], c["Source"]))

    # Groups: modal category + joined sources + description
    gid = {}
    for i, (gname, items) in enumerate(sorted(g_items.items()), start=1):
        modal_cat = collections.Counter(it["CategoryID"] for it in items).most_common(1)[0][0]
        srcs = []
        for it in items:
            for s in (it["SourceStandard"] or "").split(";"):
                s = s.strip()
                if s and s not in srcs:
                    srcs.append(s)
        if gname == "Wizard":
            desc = ("Transient wizard and junction (relation) models, grouped "
                    "together; Name keeps the full source path.")
        elif gname == "gs1":
            desc = "GS1 Application Identifier catalog."
        else:
            p = parent(gname)
            desc = f"Component (sub-entity) of {p}." if p else None
        dst.execute("INSERT INTO Groups (GroupID,Groupname,CategoryID,Description,Source)"
                    " VALUES (?,?,?,?,?)",
                    (i, gname, modal_cat, desc, "; ".join(srcs) or None))
        gid[gname] = i

    # Items
    for r in rows:
        gname = group_name(r["Name"])
        dt, bl, sc = r["DataType"], r["ByteLength"], r["DecimalScale"]
        clen = char_length(dt, bl, sc)
        dst.execute(
            """INSERT INTO UI_DataItems
               (GroupID,Name,Title,Description,DataType,CharLength,ByteLength,
                DecimalScale,IsRequired,IsNullable,DefaultValue,AllowedValues,
                ValidationSpecs,Version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (gid[gname], ui_name(r["Name"], gname), r["Title"], r["Description"],
             dt, clen, clen * 4, sc, r["IsRequired"], r["IsNullable"],
             r["DefaultValue"], r["AllowedValues"],
             validation_spec(dt, r["FormatMask"], r["AllowedValues"], sc, clen),
             r["Version"]))
    dst.commit()

    # Export SQL
    with open(SQL, "w", encoding="utf-8") as f:
        f.write("-- ui_datadict.sql - UI/governance projection of datadict.db\n")
        f.write("-- Generated by tools/build_ui_dict.py\n\n")
        for line in dst.iterdump():
            f.write(line + "\n")

    ng = dst.execute("SELECT COUNT(*) FROM Groups").fetchone()[0]
    ni = dst.execute("SELECT COUNT(*) FROM UI_DataItems").fetchone()[0]
    nc = dst.execute("SELECT COUNT(*) FROM Categories").fetchone()[0]
    print(f"Wrote {os.path.relpath(DST)} and {os.path.relpath(SQL)}")
    print(f"  {nc} categories, {ng} groups, {ni} UI data items")


if __name__ == "__main__":
    main()
