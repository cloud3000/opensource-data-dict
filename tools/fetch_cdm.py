#!/usr/bin/env python3
"""
tools/fetch_cdm.py - Generate seeds/cdm_microsoft.py from the Microsoft
Common Data Model (CDM) public schema documents.

The Microsoft CDM is published under the Community Data License Agreement -
Permissive (CDLA-Permissive-2.0) at https://github.com/microsoft/CDM .
This generator downloads selected canonical entity files, extracts their
directly-declared attributes, maps CDM data formats to SQL data types, and
writes a self-contained Python seed module consumed by build_dict.py.

Re-run to refresh from upstream:
    python3 tools/fetch_cdm.py
"""

import json
import os
import sys
import urllib.request

RAW = "https://raw.githubusercontent.com/microsoft/CDM/master/schemaDocuments/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "cdm_microsoft.py")

# (entity file path under schemaDocuments/, entity name, target category)
TARGETS = [
    ("core/applicationCommon/Account.cdm.json", "Account",
     "Customer Relationship Management (CRM)"),
    ("core/applicationCommon/Contact.cdm.json", "Contact",
     "Customer Relationship Management (CRM)"),
    ("core/applicationCommon/foundationCommon/crmCommon/Lead.cdm.json", "Lead",
     "Customer Relationship Management (CRM)"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/Opportunity.cdm.json",
     "Opportunity", "Sales / Order Management"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/Order.cdm.json",
     "Order", "Sales / Order Management"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/OrderProduct.cdm.json",
     "OrderProduct", "Sales / Order Management"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/Quote.cdm.json",
     "Quote", "Sales / Order Management"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/Invoice.cdm.json",
     "Invoice", "Finance / Accounting"),
    ("core/applicationCommon/foundationCommon/crmCommon/sales/InvoiceProduct.cdm.json",
     "InvoiceProduct", "Finance / Accounting"),
    ("core/applicationCommon/foundationCommon/Product.cdm.json", "Product",
     "Product Master Data"),
]

# CDM dataType / dataFormat -> (SQL DataType, decimal_scale or None)
TYPE_MAP = {
    "string": "VARCHAR",
    "char": "VARCHAR",
    "guid": "VARCHAR",
    "entityId": "VARCHAR",
    "entityName": "VARCHAR",
    "integer": "INTEGER",
    "smallInteger": "INTEGER",
    "bigInteger": "BIGINT",
    "boolean": "BOOLEAN",
    "decimal": "DECIMAL",
    "double": "DOUBLE",
    "float": "FLOAT",
    "money": "DECIMAL",
    "currency": "DECIMAL",
    "date": "DATE",
    "time": "TIME",
    "dateTime": "DATETIME",
    "dateTimeOffset": "DATETIME",
}


def fetch(path):
    url = RAW + path
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_format(attr):
    """Return (sql_type, is_optionset). CDM attributes carry their format in
    the 'dataType' field (string) or via a listLookup reference (option set).
    """
    dt = attr.get("dataType")
    if isinstance(dt, str):
        if dt in TYPE_MAP:
            return TYPE_MAP[dt], False
        # Common CDM semantic types resolve to strings/ids.
        return "VARCHAR", False
    if isinstance(dt, dict):
        ref = dt.get("dataTypeReference", "")
        if ref == "listLookup":
            return "INTEGER", True   # option-set code
        return "VARCHAR", False
    return "VARCHAR", False


def extract_attributes(doc, entity_name):
    ent = None
    for d in doc.get("definitions", []):
        if d.get("entityName") == entity_name:
            ent = d
            break
    if ent is None:
        return []
    attrs = []
    for grp in ent.get("hasAttributes", []):
        agr = grp.get("attributeGroupReference", {})
        for m in agr.get("members", []):
            if isinstance(m, dict) and "name" in m and "dataType" in m:
                attrs.append(m)
    return attrs


def py_str(s):
    if s is None:
        return "None"
    return json.dumps(s, ensure_ascii=False)


def main():
    print("Generating CDM seed from Microsoft CDM public schema...")
    blocks = []
    counts = {}
    for path, entity, category in TARGETS:
        try:
            doc = fetch(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {entity}: {e}", file=sys.stderr)
            continue
        attrs = extract_attributes(doc, entity)
        counts[entity] = len(attrs)
        print(f"  {entity:<16} {len(attrs):>3} attributes")
        src_url = ("https://github.com/microsoft/CDM/blob/master/"
                   "schemaDocuments/" + path)
        for a in attrs:
            sql_type, is_opt = resolve_format(a)
            desc = a.get("description") or a.get("displayName") or ""
            if is_opt:
                desc = (desc + " Option-set (enumerated integer codes).").strip()
            nullable = a.get("isNullable", True)
            blocks.append({
                "category": category,
                "name": f"{entity}.{a['name']}",
                "title": a.get("displayName") or a["name"],
                "description": desc or None,
                "data_type": sql_type,
                "byte_length": a.get("maximumLength"),
                "is_required": (nullable is False),
                "is_nullable": (nullable is not False),
                "source_url": src_url,
            })

    write_module(blocks, counts)
    print(f"\nWrote {len(blocks)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts):
    lines = [
        '"""',
        "Seed: Microsoft Common Data Model (CDM) entity attributes.",
        "",
        "AUTO-GENERATED by tools/fetch_cdm.py - do not edit by hand.",
        "Source : https://github.com/microsoft/CDM (schemaDocuments)",
        "License: Community Data License Agreement - Permissive 2.0 (CDLA-Permissive-2.0).",
        "",
        "Entities & attribute counts:",
    ]
    for e, c in counts.items():
        lines.append(f"    {e}: {c}")
    lines += [
        '"""',
        "",
        'SRC_STD = "Microsoft CDM"',
        'VERSION = "CDM schemaDocuments (master)"',
        "",
        "CATEGORIES = [",
        '    {"name": "Customer Relationship Management (CRM)",',
        '     "description": "Accounts, contacts, leads and customer relationships.",',
        '     "source": "Microsoft CDM; Odoo; ERPNext"},',
        '    {"name": "Sales / Order Management",',
        '     "description": "Quotes, opportunities, sales orders and order lines.",',
        '     "source": "Microsoft CDM; Odoo"},',
        '    {"name": "Finance / Accounting",',
        '     "description": "Invoices, invoice lines and financial postings.",',
        '     "source": "Microsoft CDM; Odoo; Tryton"},',
        '    {"name": "Product Master Data",',
        '     "description": "Product/material definitions and classifications.",',
        '     "source": "Microsoft CDM; ISA-95; Schema.org"},',
        "]",
        "",
        "_RAW = [",
    ]
    for it in items:
        lines.append("    {")
        lines.append(f'        "category": {py_str(it["category"])},')
        lines.append(f'        "name": {py_str(it["name"])},')
        lines.append(f'        "title": {py_str(it["title"])},')
        lines.append(f'        "description": {py_str(it["description"])},')
        lines.append(f'        "data_type": {py_str(it["data_type"])},')
        lines.append(f'        "byte_length": {it["byte_length"] if it["byte_length"] is not None else "None"},')
        lines.append(f'        "is_required": {it["is_required"]},')
        lines.append(f'        "is_nullable": {it["is_nullable"]},')
        lines.append(f'        "source_url": {py_str(it["source_url"])},')
        lines.append("    },")
    lines += [
        "]",
        "",
        "ITEMS = [dict(it, source_standard=SRC_STD, version=VERSION) for it in _RAW]",
        "",
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
