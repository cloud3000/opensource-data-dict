#!/usr/bin/env python3
"""
tools/find.py - Find data items by a business term, and optionally emit DDL.

A term is resolved through four layers, in order, stopping at the first that
yields results (the layer is reported so you know how clean the match is):

  1. category  - the term names one of the 12 categories (e.g. "inventory",
                 "accounting"). Returns every item in that category.
  2. entity    - the term names an entity, i.e. the part before the last dot of
                 an item Name (e.g. "patient", "work_order", "invoice"). Returns
                 that entity's fields (and its `<term>_*` / `<term>.*` family).
  3. alias     - the term is business vocabulary the source systems don't use as
                 a category/entity name (e.g. "billing", "payee"). SEARCH_ALIASES
                 maps it to real categories/entities, which are then resolved.
  4. keyword   - last resort: substring match across Name / Title / Description.
                 Noisy and incomplete; surfaced so empty/weak terms are visible.

Aliases live HERE (entity/category level), not on each of the ~3,700 items:
one `billing -> [invoice, ...]` entry covers all of invoice's fields, survives
rebuilds, and stays reviewable in one place.

Usage:
    python3 tools/find.py inventory
    python3 tools/find.py patient billing payee      # multiple terms (union)
    python3 tools/find.py work_order --ddl           # emit CREATE TABLE
    python3 tools/find.py invoice --limit 20
"""

import argparse
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "datadict.db")

# ---------------------------------------------------------------------------
# Business-term alias map (DELIBERATE, REVIEWABLE).
#
# Keys are lowercase business terms; values are lists of targets, each a
# category fragment or an entity name that already exists in the dictionary.
# Only add terms the source systems DON'T already expose as a category/entity
# name -- those resolve on their own via layers 1-2.
# ---------------------------------------------------------------------------
SEARCH_ALIASES = {
    # --- Finance / billing ---
    "billing":      ["invoice", "invoiceitem", "charge", "payment_intent"],
    "payee":        ["payout", "refund"],
    "payer":        ["customer", "charge"],
    "receivable":   ["invoice", "invoiceitem"],
    "payable":      ["purchase_order", "payout"],
    "ap":           ["purchase_order", "payout"],
    "ledger":       ["account.move", "account.move.line"],
    "journal":      ["account.move", "account.move.line"],
    "gl":           ["account.move", "account.move.line"],
    "tax":          ["account.invoice.tax", "invoice"],
    # --- CRM / parties ---
    "client":       ["customer", "account", "party.party", "organization"],
    "company":      ["organization", "account"],
    "partner":      ["party.party", "organization", "account"],
    "prospect":     ["lead", "opportunity"],
    "address":      ["party.address"],
    # --- Sales ---
    "quotation":    ["quote", "offer"],
    "deal":         ["opportunity", "quote"],
    "pricing":      ["price", "offer"],
    # --- Procurement ---
    "po":           ["purchase_order"],
    "rfq":          ["purchase_order"],
    "vendor":       ["purchase_order", "payout"],
    "supplier":     ["purchase_order"],
    # --- Inventory / supply chain ---
    "shipping":     ["stock.picking", "stock.move"],
    "delivery":     ["stock.picking", "stock.move"],
    "transfer":     ["stock.picking", "stock.move"],
    "fulfillment":  ["stock.picking", "order"],
    "lot":          ["stock.lot", "material_lot"],
    "batch":        ["stock.lot", "material_lot"],
    "serial":       ["stock.lot", "material_lot"],
    # --- Human Resources ---
    "employee":     ["hr.employee", "person", "personnel_class"],
    "staff":        ["hr.employee", "person"],
    "worker":       ["hr.employee", "person"],
    "department":   ["hr.department"],
    "position":     ["hr.job"],
    "people":       ["person", "patient", "customer", "hr.employee"],
    # --- Healthcare ---
    "appointment":  ["patient_appointment"],
    "visit":        ["patient_encounter", "encounter"],
    "vitals":       ["vital_signs"],
    "diagnosis":    ["clinical_procedure", "observation"],
    "doctor":       ["practitioner"],
    "physician":    ["practitioner"],
    "provider":     ["practitioner"],
    "insurance":    ["coverage"],
    # --- Manufacturing ---
    "mfg":          ["Manufacturing"],
    "workcenter":   ["mrp.workcenter", "workstation"],
    "assembly":     ["bom", "mrp.bom", "work_order"],
    # --- Quality ---
    "qa":           ["Quality Management"],
    "qc":           ["Quality Management"],
    "inspection":   ["quality_inspection", "quality_inspection_reading"],
    "defect":       ["non_conformance"],
    "nonconformance": ["non_conformance"],
    # --- Product ---
    "sku":          ["product", "price"],
    "catalog":      ["product", "price"],
    "item":         ["product", "price"],
    "barcode":      ["gs1"],
}

FIELD_COLS = ("Name", "Title", "Description", "DataType", "ByteLength",
              "DecimalScale", "IsRequired", "AllowedValues", "SourceStandard")


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def entity_of(name):
    return name.rsplit(".", 1)[0] if "." in name else name


def _items_for_category(conn, term):
    return conn.execute(
        f"""SELECT {", ".join("d."+c for c in FIELD_COLS)}, c.Name AS Category
            FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
            WHERE lower(c.Name) LIKE '%'||?||'%' ORDER BY d.Name""",
        (term.lower(),)).fetchall()


def _items_for_entity(conn, term):
    """Exact entity, plus the `<term>_*` / `<term>.*` family (with boundaries)."""
    t = term.lower()
    rows = conn.execute(
        f"""SELECT {", ".join("d."+c for c in FIELD_COLS)}, c.Name AS Category
            FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
            ORDER BY d.Name""").fetchall()
    out = []
    for r in rows:
        e = entity_of(r["Name"]).lower()
        if e == t or e.startswith(t + "_") or e.startswith(t + "."):
            out.append(r)
    return out


def _items_for_keyword(conn, term):
    like = f"%{term.lower()}%"
    return conn.execute(
        f"""SELECT {", ".join("d."+c for c in FIELD_COLS)}, c.Name AS Category
            FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
            WHERE lower(d.Name) LIKE ? OR lower(coalesce(d.Title,'')) LIKE ?
               OR lower(coalesce(d.Description,'')) LIKE ?
            ORDER BY d.Name""", (like, like, like)).fetchall()


def resolve(conn, term):
    """Resolve one term. Returns (level, items, detail)."""
    # 1. category
    rows = _items_for_category(conn, term)
    if rows:
        return ("category", rows, term)
    # 2. entity
    rows = _items_for_entity(conn, term)
    if rows:
        return ("entity", rows, term)
    # 3. alias -> resolve each target as category-or-entity
    if term.lower() in SEARCH_ALIASES:
        seen, items, targets = set(), [], []
        for tgt in SEARCH_ALIASES[term.lower()]:
            # entity-first: a target like "order" means the order entity, not
            # the whole "Sales / Order Management" category. Multi-word category
            # names (e.g. "Quality Management") won't match an entity and fall
            # through to the category lookup.
            sub = _items_for_entity(conn, tgt) or _items_for_category(conn, tgt)
            if sub:
                targets.append(tgt)
            for r in sub:
                if r["Name"] not in seen:
                    seen.add(r["Name"]); items.append(r)
        if items:
            return ("alias", items, " -> [" + ", ".join(targets) + "]")
    # 4. keyword fallback
    rows = _items_for_keyword(conn, term)
    return ("keyword", rows, term)


# ---------------------------------------------------------------------------
# DDL emission (reuses the dictionary's type/length/required/enum metadata)
# ---------------------------------------------------------------------------

def _sqltype(r):
    t, n, s = r["DataType"], r["ByteLength"], r["DecimalScale"]
    return {"VARCHAR": f"VARCHAR({n or 255})", "TEXT": "TEXT", "INTEGER": "INTEGER",
            "DECIMAL": f"DECIMAL(18,{s if s is not None else 2})", "BOOLEAN": "BOOLEAN",
            "DATE": "DATE", "DATETIME": "DATETIME", "TIME": "TIME",
            "RELATION": "INTEGER"}.get(t, "TEXT")


def emit_ddl(items):
    """Emit one CREATE TABLE per distinct entity present in `items`."""
    by_entity = {}
    for r in items:
        by_entity.setdefault(entity_of(r["Name"]), []).append(r)
    out = []
    for ent, rows in sorted(by_entity.items()):
        table = re.sub(r"[^0-9a-z_]", "_", ent.lower())
        out.append(f"-- {ent} ({len(rows)} fields)")
        out.append(f"CREATE TABLE {table} (")
        out.append(f"    {table}_id INTEGER PRIMARY KEY,")
        rows = sorted(rows, key=lambda r: (0 if r["IsRequired"] else 1, r["Name"]))
        defs = []
        for r in rows:
            col = r["Name"].split(".", 1)[1] if "." in r["Name"] else r["Name"]
            col = re.sub(r"[^0-9a-z_]", "_", col.lower())
            d = f"{col} {_sqltype(r)}"
            if r["IsRequired"]:
                d += " NOT NULL"
            av = r["AllowedValues"]
            if av:
                try:
                    vals = json.loads(av)
                except (ValueError, TypeError):
                    vals = None
                if isinstance(vals, list) and vals and all(isinstance(v, str) for v in vals):
                    q = ", ".join("'" + v.replace("'", "''") + "'" for v in vals)
                    if len(q) <= 110:
                        d += f" CHECK ({col} IN ({q}))"
            defs.append(d)
        for i, d in enumerate(defs):
            comma = "," if i < len(defs) - 1 else ""
            out.append(f"    {d}{comma}")
        out.append(");")
        out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find data items by business term.")
    ap.add_argument("terms", nargs="+", help="one or more business terms")
    ap.add_argument("--ddl", action="store_true",
                    help="emit CREATE TABLE per matched entity instead of a listing")
    ap.add_argument("--limit", type=int, default=12,
                    help="max sample rows to list per term (default 12; 0 = all)")
    args = ap.parse_args(argv)

    conn = connect()
    all_items, seen = [], set()
    for term in args.terms:
        level, items, detail = resolve(conn, term)
        ents = sorted({entity_of(r["Name"]) for r in items})
        cats = sorted({r["Category"] for r in items})
        tag = {"category": "✓ category", "entity": "✓ entity",
               "alias": "~ alias", "keyword": "? keyword"}[level]
        note = "" if items else "  (no matches)"
        if not args.ddl:
            print(f"\n=== {term!r}  [{tag}{detail if level=='alias' else ''}]  "
                  f"{len(items)} items, {len(ents)} entities, "
                  f"{len(cats)} categories{note}")
            if level == "keyword" and items:
                print("    (keyword fallback — scattered; consider a SEARCH_ALIASES entry)")
            lim = items if args.limit == 0 else items[:args.limit]
            for r in lim:
                t = (r["Title"] or "").strip()
                print(f"    {r['Name']:<48} {r['DataType']:<9} {t[:40]}")
            if args.limit and len(items) > args.limit:
                print(f"    ... +{len(items)-args.limit} more")
        for r in items:
            if r["Name"] not in seen:
                seen.add(r["Name"]); all_items.append(r)

    if args.ddl:
        print(emit_ddl(all_items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
