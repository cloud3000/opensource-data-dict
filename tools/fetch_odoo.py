#!/usr/bin/env python3
"""
tools/fetch_odoo.py - Generate seeds/odoo.py from Odoo open-source models.

Odoo Community Edition is licensed LGPL-3.0
(https://github.com/odoo/odoo). This generator downloads selected model
source files, parses their `fields.*` declarations with Python's `ast`
module (robust to multi-line definitions), and emits a self-contained seed
module for build_dict.py.

Re-run to refresh:
    python3 tools/fetch_odoo.py
"""

import ast
import json
import os
import sys
import urllib.request

BRANCH = "17.0"
RAW = f"https://raw.githubusercontent.com/odoo/odoo/{BRANCH}/"
BLOB = f"https://github.com/odoo/odoo/blob/{BRANCH}/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "odoo.py")

# file path -> target category (all models in the file go to this category)
TARGETS = {
    "addons/hr/models/hr_employee.py": "Human Resources",
    "addons/hr/models/hr_department.py": "Human Resources",
    "addons/hr/models/hr_job.py": "Human Resources",
    "addons/purchase/models/purchase_order.py": "Procurement / Purchasing",
    "addons/stock/models/stock_picking.py": "Supply Chain / Logistics",
    "addons/stock/models/stock_lot.py": "Inventory / Warehouse",
    "addons/stock/models/stock_quant.py": "Inventory / Warehouse",
}

# Odoo field class -> (SQL DataType, decimal_scale default or None)
FIELD_MAP = {
    "Char": "VARCHAR",
    "Text": "TEXT",
    "Html": "TEXT",
    "Integer": "INTEGER",
    "Float": "DECIMAL",
    "Monetary": "DECIMAL",
    "Boolean": "BOOLEAN",
    "Date": "DATE",
    "Datetime": "DATETIME",
    "Selection": "VARCHAR",
    "Many2one": "INTEGER",      # stored as FK id
    "One2many": "RELATION",
    "Many2many": "RELATION",
    "Binary": "BLOB",
    "Reference": "VARCHAR",
    "Json": "TEXT",
}

CATEGORIES = [
    ("Human Resources", "Employees, departments and job positions.",
     "Odoo (LGPL-3.0); ISA-95"),
    ("Procurement / Purchasing", "Purchase orders, RFQs and order lines.",
     "Odoo (LGPL-3.0); ERPNext"),
    ("Inventory / Warehouse", "Stock lots/serials and on-hand quantities.",
     "Odoo (LGPL-3.0); ISA-95"),
    ("Supply Chain / Logistics", "Transfers, pickings and shipment movements.",
     "Odoo (LGPL-3.0)"),
]


def fetch(path):
    with urllib.request.urlopen(RAW + path, timeout=60) as r:
        return r.read().decode("utf-8")


def _const(node):
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _selection_values(node):
    """Extract codes from a Selection list literal [(code, label), ...]."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    codes = []
    for elt in node.elts:
        if isinstance(elt, ast.Tuple) and elt.elts:
            c = _const(elt.elts[0])
            if c is not None:
                codes.append(str(c))
    return codes or None


def parse_model_file(src, path, category):
    tree = ast.parse(src)
    items = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        # Determine the Odoo model name (_name) or inherited (_inherit).
        model_name = None
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name) and tgt.id in ("_name", "_inherit"):
                        v = stmt.value
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            if tgt.id == "_name" or model_name is None:
                                model_name = v.value
        if not model_name:
            continue

        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if not (len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
                continue
            field_name = stmt.targets[0].id
            call = stmt.value
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                continue
            if not (isinstance(call.func.value, ast.Name) and call.func.value.id == "fields"):
                continue
            ftype = call.func.attr
            if ftype not in FIELD_MAP:
                continue

            kw = {k.arg: k.value for k in call.keywords if k.arg}
            label = None
            comodel = None
            allowed = None
            size = None
            help_text = None
            required = False

            # First positional arg: label for most types, comodel for relational.
            pos = call.args
            if ftype in ("Many2one", "One2many", "Many2many"):
                if pos:
                    comodel = _const(pos[0])
            elif ftype == "Selection":
                if pos:
                    allowed = _selection_values(pos[0])
            else:
                if pos:
                    label = _const(pos[0])

            if "string" in kw:
                label = _const(kw["string"]) or label
            if "comodel_name" in kw:
                comodel = _const(kw["comodel_name"]) or comodel
            if "selection" in kw and allowed is None:
                allowed = _selection_values(kw["selection"])
            if "size" in kw:
                size = _const(kw["size"])
            if "help" in kw:
                help_text = _const(kw["help"])
            if "required" in kw:
                required = (_const(kw["required"]) is True)

            desc = help_text or label
            if comodel:
                rel = "references" if ftype == "Many2one" else "collection of"
                extra = f"({rel} {comodel})"
                desc = f"{desc} {extra}" if desc else extra

            items.append({
                "category": category,
                "name": f"{model_name}.{field_name}",
                "title": label or field_name,
                "description": desc,
                "data_type": FIELD_MAP[ftype],
                "byte_length": size if isinstance(size, int) else None,
                "is_required": required,
                "is_nullable": not required,
                "allowed_values": json.dumps(allowed) if allowed else None,
                "source_url": BLOB + path,
            })
    return items


def py(v):
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def main():
    print(f"Generating Odoo seed from branch {BRANCH}...")
    all_items = []
    counts = {}
    for path, category in TARGETS.items():
        try:
            src = fetch(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {path}: {e}", file=sys.stderr)
            continue
        items = parse_model_file(src, path, category)
        counts[path.split("/")[-1]] = len(items)
        print(f"  {path.split('/')[-1]:<22} {len(items):>3} fields")
        all_items.extend(items)

    write_module(all_items, counts)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts):
    L = [
        '"""',
        "Seed: Odoo (Community Edition) model fields.",
        "",
        "AUTO-GENERATED by tools/fetch_odoo.py - do not edit by hand.",
        f"Source : https://github.com/odoo/odoo (branch {BRANCH})",
        "License: LGPL-3.0.",
        "",
        "Files & field counts:",
    ]
    for f, c in counts.items():
        L.append(f"    {f}: {c}")
    L += ['"""', "",
          'SRC_STD = "Odoo"',
          f'VERSION = "Odoo {BRANCH}"',
          "",
          "CATEGORIES = ["]
    for name, desc, src in CATEGORIES:
        L.append(f"    {{\"name\": {py(name)}, \"description\": {py(desc)}, \"source\": {py(src)}}},")
    L += ["]", "", "_RAW = ["]
    for it in items:
        L.append("    {")
        for k in ("category", "name", "title", "description", "data_type",
                  "byte_length", "is_required", "is_nullable",
                  "allowed_values", "source_url"):
            L.append(f"        {py(k)}: {py(it[k])},")
        L.append("    },")
    L += ["]", "",
          "ITEMS = [dict(it, source_standard=SRC_STD, version=VERSION) for it in _RAW]",
          ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
