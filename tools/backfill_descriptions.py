#!/usr/bin/env python3
"""
tools/backfill_descriptions.py - Fill in descriptions for items whose upstream
source provided none.

Some open-source models expose a human-readable label (Title) but no help/
description text (e.g. Odoo fields without `help=`, ERPNext DocType fields
without `description`). For a data dictionary an empty Description is a real
gap, yet we have no external text to cite. This tool synthesises a factual
description from the item's *own* metadata only -- its entity, its Title, and
its AllowedValues -- so no unsourced claim is introduced; we are merely
restating what the field already declares.

Durability: build_dict.py upserts Description with
    Description = COALESCE(excluded.Description, DataItems.Description)
and the seeds carry NULL for these fields, so a value written here survives
re-running build_dict.py and is only ever replaced if the upstream source later
gains real help text.

Idempotent: only rows with a NULL/empty Description are touched.

Usage:
    python3 tools/backfill_descriptions.py            # backfill Manufacturing
    python3 tools/backfill_descriptions.py --category "Finance / Accounting"
    python3 tools/backfill_descriptions.py --all      # every category
    python3 tools/backfill_descriptions.py --dry-run  # preview only
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from build_dict import connect, export_sql  # noqa: E402

# Human-readable names for the manufacturing entities (entity = everything
# before the last dot of an item Name). Anything not listed falls back to a
# title-cased humanisation of the entity token.
ENTITY_NAMES = {
    # ERPNext / Frappe DocTypes
    "work_order": "Work Order",
    "bom": "Bill of Materials (BOM)",
    "bom_item": "BOM line item",
    "bom_operation": "BOM operation",
    "job_card": "Job Card",
    "operation": "Operation",
    "workstation": "Workstation",
    "routing": "Routing",
    "production_plan": "Production Plan",
    # Odoo mrp models
    "mrp.production": "Manufacturing order",
    "mrp.bom": "Bill of Materials (BOM)",
    "mrp.bom.line": "BOM line",
    "mrp.workcenter": "Work center",
    "mrp.workorder": "Work order",
    "mrp.unbuild": "Unbuild order",
    "mrp.routing.workcenter": "Routing operation",
    # Tryton production models
    "production": "Production order",
    "production.bom": "Bill of Materials (BOM)",
    "production.bom.input": "BOM input",
    "production.bom.output": "BOM output",
    "production.routing": "Routing",
    "production.operation": "Operation",
    "production.work": "Work step",
    # ISA-95
    "process_segment": "Process segment",
    # --- Other categories ---
    # Healthcare (Frappe Health)
    "patient": "Patient",
    "patient_appointment": "Patient appointment",
    "patient_encounter": "Patient encounter",
    "clinical_procedure": "Clinical procedure",
    "lab_test": "Lab test",
    "vital_signs": "Vital signs",
    # Quality Management (ERPNext)
    "quality_inspection": "Quality inspection",
    "quality_inspection_reading": "Quality inspection reading",
    "non_conformance": "Non-conformance",
    "quality_goal": "Quality goal",
    "quality_action": "Quality action",
    "quality_procedure": "Quality procedure",
    "quality_review": "Quality review",
    # Odoo (stock / HR / purchase)
    "stock.picking": "Stock transfer / picking",
    "stock.picking.type": "Operation (picking) type",
    "stock.quant": "Stock quantity (on-hand)",
    "stock.lot": "Lot / serial number",
    "hr.employee": "Employee",
    "hr.department": "Department",
    "hr.job": "Job position",
    "purchase_order": "Purchase order",
    # Stripe API
    "customer": "Customer",
    "invoice": "Invoice",
    "invoiceitem": "Invoice line item",
    "quote": "Quote",
    "subscription": "Subscription",
    "charge": "Charge",
    "refund": "Refund",
    "payment_intent": "Payment intent",
    # Microsoft CDM / Schema.org
    "lead": "Lead",
    "order": "Order",
    "product": "Product",
}


def humanise(entity):
    """Fallback human name for an entity not in ENTITY_NAMES."""
    return ENTITY_NAMES.get(entity, entity.replace(".", " ").replace("_", " ").strip().capitalize())


def entity_of(name):
    return name.rsplit(".", 1)[0] if "." in name else name


def _allowed_list(av):
    """Parse AllowedValues into a flat list of display strings, or []."""
    if not av:
        return []
    try:
        parsed = json.loads(av)
    except (ValueError, TypeError):
        return [av]
    if isinstance(parsed, list):
        return [str(v) for v in parsed]
    if isinstance(parsed, dict):  # per-source object {src: [vals]}
        flat = []
        for vals in parsed.values():
            flat.extend(str(v) for v in (vals if isinstance(vals, list) else [vals]))
        return flat
    return [str(parsed)]


def synthesize(name, title, allowed_values):
    """Build a factual description from the field's own metadata."""
    entity = humanise(entity_of(name))
    label = (title or name.rsplit(".", 1)[-1]).strip()
    desc = f"{entity}: {label}."
    vals = _allowed_list(allowed_values)
    if vals:
        # de-dupe, preserve order, cap to keep the cell readable
        seen, shown = set(), []
        for v in vals:
            if v and v not in seen:
                seen.add(v)
                shown.append(v)
        capped = shown[:12]
        more = "" if len(shown) <= 12 else f", ... (+{len(shown) - 12} more)"
        desc += " Allowed values: " + ", ".join(capped) + more + "."
    return desc


def apply_curated(conn, dry_run=False):
    """Overwrite item descriptions from the hand-curated map.

    Unlike synthesis (which fills only empty rows), this replaces whatever is
    there -- including previously synthesised placeholders -- with the editorial
    text in tools/curated_descriptions.py, keyed by exact item Name. Durable via
    build_dict.py's COALESCE upsert (seeds carry NULL). Idempotent: rows already
    holding the curated text are skipped.
    """
    from curated_descriptions import CURATED

    updated = missing = 0
    for name, desc in CURATED.items():
        rows = conn.execute(
            "SELECT DataItemID, Description FROM DataItems WHERE Name = ?", (name,)
        ).fetchall()
        if not rows:
            missing += 1
            print(f"  ! no item named {name}", file=sys.stderr)
            continue
        for r in rows:
            if r["Description"] == desc:
                continue
            if not dry_run:
                conn.execute(
                    "UPDATE DataItems SET Description = ?, "
                    "UpdatedAt = CURRENT_TIMESTAMP WHERE DataItemID = ?",
                    (desc, r["DataItemID"]),
                )
            updated += 1

    print(f"Curated map: {len(CURATED)} entries; "
          f"{'would update' if dry_run else 'updated'} {updated} row(s)"
          + (f"; {missing} name(s) not found in DB" if missing else "") + ".")
    return updated


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backfill missing item descriptions.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--category", default="Manufacturing",
                   help='Category to backfill (default: "Manufacturing").')
    g.add_argument("--all", action="store_true", help="Backfill every category.")
    ap.add_argument("--curated", action="store_true",
                    help="Apply hand-curated descriptions from "
                         "tools/curated_descriptions.py (overwrites placeholders).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would change without writing.")
    ap.add_argument("--no-export", action="store_true",
                    help="Skip re-exporting datadict.sql.")
    args = ap.parse_args(argv)

    conn = connect()

    if args.curated:
        apply_curated(conn, dry_run=args.dry_run)
        if args.dry_run:
            print("[dry-run] no changes written.")
            return 0
        conn.commit()
        if not args.no_export:
            export_sql(conn)
            print("Re-exported datadict.sql")
        conn.close()
        return 0

    where = "(d.Description IS NULL OR trim(d.Description) = '')"
    params = []
    if not args.all:
        where += " AND c.Name = ?"
        params.append(args.category)

    rows = conn.execute(
        f"""
        SELECT d.DataItemID, c.Name AS category, d.Name AS name,
               d.Title AS title, d.AllowedValues AS allowed
        FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
        WHERE {where}
        ORDER BY c.Name, d.Name
        """,
        params,
    ).fetchall()

    scope = "all categories" if args.all else f'category "{args.category}"'
    print(f"Found {len(rows)} item(s) without a description in {scope}.")

    updated = 0
    for r in rows:
        desc = synthesize(r["name"], r["title"], r["allowed"])
        if args.dry_run:
            if updated < 15:
                print(f"  {r['name']}\n      -> {desc}")
        else:
            conn.execute(
                "UPDATE DataItems SET Description = ?, "
                "UpdatedAt = CURRENT_TIMESTAMP WHERE DataItemID = ?",
                (desc, r["DataItemID"]),
            )
        updated += 1

    if args.dry_run:
        print(f"\n[dry-run] would update {updated} item(s). No changes written.")
        return 0

    conn.commit()
    print(f"Updated {updated} description(s).")
    if not args.no_export:
        export_sql(conn)
        print("Re-exported datadict.sql")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
