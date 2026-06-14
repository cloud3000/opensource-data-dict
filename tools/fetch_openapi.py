#!/usr/bin/env python3
"""
tools/fetch_openapi.py - Generate seeds/openapi.py from public OpenAPI /
Swagger specifications of open projects.

Generic ingester: for each configured spec it locates the schema map
(`components.schemas` for OpenAPI 3, `definitions` for Swagger 2), and for the
selected object schemas extracts each property (type, format, description,
maxLength, enum) plus the schema-level `required` list, mapping to SQL types.

Configured spec(s):
  * Stripe API - github.com/stripe/openapi, MIT License. A publicly published,
    openly-licensed (MIT) OpenAPI document. Business objects: customer,
    product, price, invoice, charge, payout, refund, payment_intent, quote,
    subscription. (Commercial vendor, but the spec artifact is open-source.)

Adding another spec = one more entry in SPECS. JSON specs only (no YAML dep).

Re-run to refresh:
    python3 tools/fetch_openapi.py
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "openapi.py")

SPECS = [
    {
        "source_standard": "Stripe API",
        "version": "stripe/openapi spec3",
        "license": "MIT",
        "url": "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
        "blob": "https://github.com/stripe/openapi/blob/master/openapi/spec3.json",
        # schema name -> business category
        "schemas": {
            "customer": "Customer Relationship Management (CRM)",
            "product": "Product Master Data",
            "price": "Product Master Data",
            "invoice": "Finance / Accounting",
            "invoiceitem": "Finance / Accounting",
            "charge": "Finance / Accounting",
            "payout": "Finance / Accounting",
            "refund": "Finance / Accounting",
            "payment_intent": "Finance / Accounting",
            "quote": "Sales / Order Management",
            "subscription": "Sales / Order Management",
        },
    },
]

CATEGORIES = [
    ("Customer Relationship Management (CRM)",
     "Customers and parties.", "Stripe API (MIT); Microsoft CDM; Schema.org"),
    ("Product Master Data",
     "Products and prices.", "Stripe API (MIT); Schema.org; GS1"),
    ("Finance / Accounting",
     "Invoices, charges, payouts, refunds and payments.",
     "Stripe API (MIT); Microsoft CDM; Tryton; HL7 FHIR"),
    ("Sales / Order Management",
     "Quotes and subscriptions.", "Stripe API (MIT); Microsoft CDM"),
]

FMT_MAP = {"date": "DATE", "date-time": "DATETIME", "byte": "BLOB",
           "binary": "BLOB", "uuid": "VARCHAR"}
TYPE_MAP = {"string": "VARCHAR", "integer": "INTEGER", "number": "DECIMAL",
            "boolean": "BOOLEAN", "array": "RELATION", "object": "OBJECT"}


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def resolve_type(prop):
    """Map an OpenAPI property schema to (sql_type)."""
    fmt = prop.get("format")
    if fmt in FMT_MAP and prop.get("type") == "string":
        return FMT_MAP[fmt]
    t = prop.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if t in TYPE_MAP:
        return TYPE_MAP[t]
    # No direct type: look inside anyOf/oneOf/allOf for a primitive, else ref.
    for key in ("anyOf", "oneOf", "allOf"):
        for member in prop.get(key, []) or []:
            mt = member.get("type")
            if mt in TYPE_MAP:
                return TYPE_MAP[mt]
            if "$ref" in member:
                return "RELATION"
    if "$ref" in prop:
        return "RELATION"
    return "VARCHAR"


def parse_schema(name, schema, category, blob):
    props = schema.get("properties", {})
    required = set(schema.get("required", []) or [])
    items = []
    for fname, prop in props.items():
        if not isinstance(prop, dict):
            continue
        enum = prop.get("enum")
        items.append({
            "category": category,
            "name": f"{name}.{fname}",
            "title": fname,
            "description": prop.get("description"),
            "data_type": resolve_type(prop),
            "byte_length": prop.get("maxLength"),
            "is_required": fname in required,
            "is_nullable": fname not in required,
            "allowed_values": json.dumps(enum) if enum else None,
            "source_url": blob,
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
    print("Generating OpenAPI seed from public specs...")
    all_items = []
    counts = {}
    meta_lines = []
    for spec in SPECS:
        try:
            doc = fetch(spec["url"])
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {spec['source_standard']}: {e}", file=sys.stderr)
            continue
        schema_map = (doc.get("components", {}).get("schemas")
                      or doc.get("definitions") or {})
        std = spec["source_standard"]
        meta_lines.append(f"  {std} ({spec['license']}): {spec['url']}")
        print(f"  {std}  ({len(schema_map)} schemas in spec)")
        for sname, category in spec["schemas"].items():
            schema = schema_map.get(sname)
            if not schema:
                print(f"    ! schema '{sname}' not found", file=sys.stderr)
                continue
            items = parse_schema(sname, schema, category, spec["blob"])
            for it in items:
                it["_src"] = std
                it["_ver"] = spec["version"]
            counts[f"{std}:{sname}"] = len(items)
            print(f"    {sname:<18} {len(items):>3} props  [{category}]")
            all_items.extend(items)
    write_module(all_items, counts, meta_lines)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts, meta_lines):
    L = ['"""',
         "Seed: public OpenAPI / Swagger specifications (open projects).",
         "",
         "AUTO-GENERATED by tools/fetch_openapi.py - do not edit by hand.",
         "Sources:"]
    L += meta_lines
    L += ["",
          "Schemas & property counts:"]
    for k, c in counts.items():
        L.append(f"    {k}: {c}")
    L += ['"""', "", "CATEGORIES = ["]
    for name, desc, src in CATEGORIES:
        L.append(f"    {{\"name\": {py(name)}, \"description\": {py(desc)}, "
                 f"\"source\": {py(src)}}},")
    L += ["]", "", "_RAW = ["]
    for it in items:
        L.append("    {")
        for k in ("category", "name", "title", "description", "data_type",
                  "byte_length", "is_required", "is_nullable", "allowed_values",
                  "source_url", "_src", "_ver"):
            L.append(f"        {py(k)}: {py(it[k])},")
        L.append("    },")
    L += ["]", "",
          "ITEMS = [dict({k: v for k, v in it.items() if k not in ('_src', '_ver')},",
          "              source_standard=it['_src'], version=it['_ver'])",
          "         for it in _RAW]",
          ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
