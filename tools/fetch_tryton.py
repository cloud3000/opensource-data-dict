#!/usr/bin/env python3
"""
tools/fetch_tryton.py - Generate seeds/tryton.py from Tryton open-source models.

Tryton is a GPL-3.0 business/ERP framework (https://www.tryton.org). Its model
source is mirrored at https://github.com/tryton/tryton . This generator
downloads selected `modules/<mod>/<file>.py` model files, parses their
`fields.*` declarations with Python's `ast`, and emits a self-contained seed
module for build_dict.py.

Tryton specifics handled here:
  * model name comes from the class attribute `__name__` (not `_name`);
  * field classes use capital-O relational names (Many2One, One2Many, ...);
  * `fields.Function(<real field>, 'getter')` wrappers are unwrapped to the
    inner field for type/label;
  * positional argument layout differs per field type (see POSITIONS).

Re-run to refresh:
    python3 tools/fetch_tryton.py
"""

import ast
import json
import os
import sys
import urllib.request

BRANCH = "main"
RAW = f"https://raw.githubusercontent.com/tryton/tryton/{BRANCH}/"
BLOB = f"https://github.com/tryton/tryton/blob/{BRANCH}/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "tryton.py")

# module file path -> target category
TARGETS = {
    "modules/party/party.py": "Customer Relationship Management (CRM)",
    "modules/party/address.py": "Customer Relationship Management (CRM)",
    "modules/account_invoice/invoice.py": "Finance / Accounting",
    "modules/account/move.py": "Finance / Accounting",
    "modules/product/product.py": "Product Master Data",
    "modules/sale/sale.py": "Sales / Order Management",
    "modules/purchase/purchase.py": "Procurement / Purchasing",
    "modules/stock/move.py": "Supply Chain / Logistics",
    "modules/stock/location.py": "Inventory / Warehouse",
}

FIELD_MAP = {
    "Char": "VARCHAR", "Text": "TEXT", "FullText": "TEXT", "MultiSelection": "VARCHAR",
    "Integer": "INTEGER", "BigInteger": "BIGINT", "Float": "DECIMAL",
    "Numeric": "DECIMAL", "Boolean": "BOOLEAN", "Date": "DATE",
    "DateTime": "DATETIME", "Timestamp": "DATETIME", "Time": "TIME",
    "TimeDelta": "INTEGER", "Selection": "VARCHAR", "Many2One": "INTEGER",
    "One2Many": "RELATION", "Many2Many": "RELATION", "One2One": "RELATION",
    "Reference": "VARCHAR", "Binary": "BLOB", "Dict": "TEXT",
}

# field type -> {label: positional index, comodel: idx, selection: idx}
POSITIONS = {
    "Many2One": {"comodel": 0, "label": 1},
    "One2One": {"comodel": 0, "label": 1},
    "One2Many": {"comodel": 0, "label": 2},
    "Many2Many": {"comodel": 0, "label": 3},
    "Selection": {"selection": 0, "label": 1},
    "MultiSelection": {"selection": 0, "label": 1},
}
DEFAULT_LABEL_IDX = 0   # for scalar fields

CATEGORIES = [
    ("Customer Relationship Management (CRM)",
     "Parties (organizations/persons), addresses and contacts.",
     "Tryton (GPL-3.0); Microsoft CDM; Schema.org"),
    ("Finance / Accounting", "Invoices, accounts and accounting moves.",
     "Tryton (GPL-3.0); Microsoft CDM"),
    ("Product Master Data", "Product templates and variants.",
     "Tryton (GPL-3.0); Schema.org; Microsoft CDM"),
    ("Sales / Order Management", "Sales orders and sale lines.",
     "Tryton (GPL-3.0); Microsoft CDM"),
    ("Procurement / Purchasing", "Purchase orders and purchase lines.",
     "Tryton (GPL-3.0); Odoo"),
    ("Supply Chain / Logistics", "Stock moves and shipments.",
     "Tryton (GPL-3.0)"),
    ("Inventory / Warehouse", "Stock locations and warehouses.",
     "Tryton (GPL-3.0); ISA-95"),
]


def fetch(path):
    with urllib.request.urlopen(RAW + path, timeout=60) as r:
        return r.read().decode("utf-8")


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _selection_codes(node):
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    codes = []
    for elt in node.elts:
        if isinstance(elt, ast.Tuple) and elt.elts:
            c = _const(elt.elts[0])
            if c is not None:
                codes.append(str(c))
    return codes or None


def _unwrap_field(call):
    """Return the effective fields.* Call, unwrapping fields.Function(...)."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
        return None
    if not (isinstance(call.func.value, ast.Name) and call.func.value.id == "fields"):
        return None
    if call.func.attr == "Function" and call.args:
        return _unwrap_field(call.args[0])
    return call


def parse_file(src, path, category):
    tree = ast.parse(src)
    items = []
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        model_name = None
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == "__name__":
                        v = _const(stmt.value)
                        if isinstance(v, str):
                            model_name = v
        if not model_name:
            continue

        for stmt in cls.body:
            if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)):
                continue
            field_name = stmt.targets[0].id
            if field_name.startswith("__"):
                continue
            call = _unwrap_field(stmt.value)
            if call is None:
                continue
            ftype = call.func.attr
            if ftype not in FIELD_MAP:
                continue

            pos = call.args
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            spec = POSITIONS.get(ftype, {"label": DEFAULT_LABEL_IDX})

            label = None
            if "label" in spec and len(pos) > spec["label"]:
                label = _const(pos[spec["label"]])
            comodel = None
            if "comodel" in spec and len(pos) > spec["comodel"]:
                comodel = _const(pos[spec["comodel"]])
            allowed = None
            if "selection" in spec and len(pos) > spec["selection"]:
                allowed = _selection_codes(pos[spec["selection"]])

            if "string" in kw:
                label = _const(kw["string"]) or label
            if "help" in kw:
                help_text = _const(kw["help"])
            else:
                help_text = None
            size = _const(kw["size"]) if "size" in kw else None
            required = (_const(kw["required"]) is True) if "required" in kw else False

            desc = help_text or label
            if comodel:
                rel = "references" if ftype in ("Many2One", "One2One") else "collection of"
                note = f"({rel} {comodel})"
                desc = f"{desc} {note}" if desc else note

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
    print(f"Generating Tryton seed from branch {BRANCH}...")
    all_items = []
    counts = {}
    for path, category in TARGETS.items():
        try:
            src = fetch(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {path}: {e}", file=sys.stderr)
            continue
        items = parse_file(src, path, category)
        counts[path.split("/")[-1]] = len(items)
        print(f"  {path.split('modules/')[-1]:<28} {len(items):>3} fields")
        all_items.extend(items)
    write_module(all_items, counts)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts):
    L = ['"""',
         "Seed: Tryton (Community) model fields.",
         "",
         "AUTO-GENERATED by tools/fetch_tryton.py - do not edit by hand.",
         f"Source : https://github.com/tryton/tryton (branch {BRANCH})",
         "License: GPL-3.0.",
         "",
         "Files & field counts:"]
    for f, c in counts.items():
        L.append(f"    {f}: {c}")
    L += ['"""', "",
          'SRC_STD = "Tryton"',
          f'VERSION = "Tryton {BRANCH}"',
          "", "CATEGORIES = ["]
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
