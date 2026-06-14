#!/usr/bin/env python3
"""
tools/fetch_schemaorg.py - Generate seeds/schemaorg.py from the Schema.org
vocabulary.

Schema.org terms are published under the Creative Commons Attribution-ShareAlike
(CC BY-SA 3.0) license. The full vocabulary is downloaded as JSON-LD, and for a
curated set of business types the generator collects every property whose
`domainIncludes` is that type (or one of its Schema.org ancestors), maps the
`rangeIncludes` to a SQL data type, and captures Enumeration ranges as
AllowedValues.

Re-run to refresh:
    python3 tools/fetch_schemaorg.py
"""

import json
import os
import re
import sys
import urllib.request

URL = "https://schema.org/version/latest/schemaorg-current-https.jsonld"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "schemaorg.py")

# Schema.org type -> target category. Order chosen so overlapping entities
# (product / order / invoice / person) line up with earlier sources.
TARGETS = [
    ("Product", "Product Master Data"),
    ("Order", "Sales / Order Management"),
    ("Offer", "Sales / Order Management"),
    ("Invoice", "Finance / Accounting"),
    ("Organization", "Customer Relationship Management (CRM)"),
    ("Person", "Human Resources"),
]

# Schema.org primitive datatype -> SQL type. Order = scalar preference.
DT_MAP = [
    ("schema:Boolean", "BOOLEAN"),
    ("schema:Integer", "INTEGER"),
    ("schema:Float", "DECIMAL"),
    ("schema:Number", "DECIMAL"),
    ("schema:DateTime", "DATETIME"),
    ("schema:Date", "DATE"),
    ("schema:Time", "TIME"),
    ("schema:URL", "VARCHAR"),
    ("schema:Text", "VARCHAR"),
]
TEXT_SUBTYPES = {"schema:URL", "schema:CssSelectorType", "schema:PronounceableText",
                 "schema:XPathType"}

TAG_RE = re.compile(r"<[^>]+>")


def fetch():
    with urllib.request.urlopen(URL, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def as_list(v):
    if v is None:
        return []
    if isinstance(v, dict):
        return [v.get("@id")]
    return [x.get("@id") for x in v if isinstance(x, dict)]


def clean_text(s):
    if not s:
        return None
    s = TAG_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def build_indexes(graph):
    byid = {n["@id"]: n for n in graph if "@id" in n}
    classes = {n["@id"]: n for n in graph if n.get("@type") == "rdfs:Class"}
    props = [n for n in graph
             if n.get("@type") == "rdf:Property" and n["@id"].startswith("schema:")]
    # Enumeration members: node @type == an enumeration class id.
    enum_members = {}
    for n in graph:
        t = n.get("@type")
        for tid in ([t] if isinstance(t, str) else (t or [])):
            if isinstance(tid, str) and tid.startswith("schema:") and tid in classes:
                enum_members.setdefault(tid, []).append(n)
    return byid, classes, props, enum_members


def ancestors(class_id, classes, seen=None):
    """All Schema.org ancestor class ids (incl. self)."""
    seen = seen or set()
    if class_id in seen or class_id not in classes:
        return seen
    seen.add(class_id)
    for parent in as_list(classes[class_id].get("rdfs:subClassOf")):
        if parent and parent.startswith("schema:"):
            ancestors(parent, classes, seen)
    return seen


def is_enumeration(class_id, classes):
    return "schema:Enumeration" in ancestors(class_id, classes)


def map_range(ranges, classes, enum_members, byid):
    """Return (sql_type, allowed_values_json, ref_note)."""
    # Datatype ranges take priority for a clean scalar type.
    for dt, sql in DT_MAP:
        if dt in ranges:
            return sql, None, None
    # Enumeration range -> capture members as allowed values.
    for r in ranges:
        if r and is_enumeration(r, classes):
            members = enum_members.get(r, [])
            labels = sorted(
                (m.get("rdfs:label") for m in members if m.get("rdfs:label")))
            short = r.split(":")[-1]
            return ("VARCHAR",
                    json.dumps(labels) if labels else None,
                    f"enumeration {short}")
    # Otherwise it's a reference to another type (object/relation).
    refs = [r.split(":")[-1] for r in ranges if r and r.startswith("schema:")]
    note = f"references {', '.join(refs)}" if refs else None
    return "RELATION", None, note


def main():
    print("Generating Schema.org seed (CC BY-SA 3.0)...")
    doc = fetch()
    graph = doc["@graph"]
    byid, classes, props, enum_members = build_indexes(graph)
    print(f"  vocabulary: {len(classes)} classes, {len(props)} schema properties")

    all_items = []
    counts = {}
    for type_name, category in TARGETS:
        tid = f"schema:{type_name}"
        if tid not in classes:
            print(f"  ! missing type {type_name}", file=sys.stderr)
            continue
        anc = ancestors(tid, classes)
        type_props = []
        for p in props:
            domains = set(as_list(p.get("schema:domainIncludes")))
            if domains & anc:
                type_props.append(p)
        counts[type_name] = len(type_props)
        print(f"  {type_name:<14} {len(type_props):>3} properties "
              f"(incl. inherited)  [{category}]")
        for p in type_props:
            label = p.get("rdfs:label") or p["@id"].split(":")[-1]
            ranges = as_list(p.get("schema:rangeIncludes"))
            sql_type, allowed, note = map_range(ranges, classes, enum_members, byid)
            desc = clean_text(p.get("rdfs:comment"))
            if note:
                desc = f"{desc} ({note})" if desc else f"({note})"
            all_items.append({
                "category": category,
                "name": f"{type_name}.{label}",
                "title": label,
                "description": desc,
                "data_type": sql_type,
                "allowed_values": allowed,
                "source_url": f"https://schema.org/{label}",
            })

    write_module(all_items, counts)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def py(v):
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def write_module(items, counts):
    L = ['"""',
         "Seed: Schema.org vocabulary (business types).",
         "",
         "AUTO-GENERATED by tools/fetch_schemaorg.py - do not edit by hand.",
         "Source : https://schema.org/version/latest/schemaorg-current-https.jsonld",
         "License: Creative Commons Attribution-ShareAlike 3.0 (CC BY-SA 3.0).",
         "",
         "Types & property counts (including inherited properties):"]
    for t, c in counts.items():
        L.append(f"    {t}: {c}")
    L += ['"""', "",
          'SRC_STD = "Schema.org"',
          'VERSION = "schemaorg-current-https"',
          "", "CATEGORIES = [",
          '    {"name": "Product Master Data",'
          ' "description": "Product/material definitions and classifications.",'
          ' "source": "Schema.org; Microsoft CDM; ISA-95"},',
          '    {"name": "Sales / Order Management",'
          ' "description": "Orders, offers, quotes and order lines.",'
          ' "source": "Schema.org; Microsoft CDM; Odoo"},',
          '    {"name": "Finance / Accounting",'
          ' "description": "Invoices and financial documents.",'
          ' "source": "Schema.org; Microsoft CDM"},',
          '    {"name": "Customer Relationship Management (CRM)",'
          ' "description": "Organizations, accounts and contacts.",'
          ' "source": "Schema.org; Microsoft CDM"},',
          '    {"name": "Human Resources",'
          ' "description": "Persons and workforce master data.",'
          ' "source": "Schema.org; ISA-95; Odoo"},',
          "]", "", "_RAW = ["]
    for it in items:
        L.append("    {")
        for k in ("category", "name", "title", "description",
                  "data_type", "allowed_values", "source_url"):
            L.append(f"        {py(k)}: {py(it[k])},")
        L.append("    },")
    L += ["]", "",
          "ITEMS = [dict(it, source_standard=SRC_STD, version=VERSION) for it in _RAW]",
          ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
