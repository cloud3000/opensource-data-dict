#!/usr/bin/env python3
"""
tools/fetch_fhir.py - Generate seeds/fhir.py from HL7 FHIR (R4) resource
definitions - our representative "public JSON Schema / structured spec" source.

HL7 FHIR is published under Creative Commons "No Rights Reserved" (CC0 1.0,
public domain): https://www.hl7.org/fhir/license.html . Each resource ships a
StructureDefinition (`<resource>.profile.json`) whose `snapshot.element[]`
lists every element with path, cardinality (min/max), data type(s),
descriptions and value-set bindings - effectively a JSON Schema for the
resource. We extract the top-level business fields of selected resources.

Re-run to refresh:
    python3 tools/fetch_fhir.py
"""

import json
import os
import sys
import urllib.request

BASE = "https://hl7.org/fhir/R4/"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "fhir.py")

# (resource, target category)
TARGETS = [
    ("Patient", "Healthcare"),
    ("Practitioner", "Healthcare"),
    ("Encounter", "Healthcare"),
    ("Observation", "Healthcare"),
    ("Coverage", "Healthcare"),
    ("Organization", "Customer Relationship Management (CRM)"),
    ("Invoice", "Finance / Accounting"),
]

# FHIR primitive type -> SQL type. Complex (CapitalCase) types -> OBJECT;
# "Reference" -> RELATION.
PRIM_MAP = {
    "string": "VARCHAR", "code": "VARCHAR", "id": "VARCHAR", "markdown": "TEXT",
    "uri": "VARCHAR", "url": "VARCHAR", "canonical": "VARCHAR", "oid": "VARCHAR",
    "uuid": "VARCHAR", "base64binary": "BLOB", "boolean": "BOOLEAN",
    "integer": "INTEGER", "positiveint": "INTEGER", "unsignedint": "INTEGER",
    "decimal": "DECIMAL", "date": "DATE", "datetime": "DATETIME",
    "instant": "DATETIME", "time": "TIME",
}
# Base DomainResource/Resource infrastructure fields - not business data.
SKIP_FIELDS = {"id", "meta", "implicitRules", "language", "text", "contained",
               "extension", "modifierExtension"}


def fetch(resource):
    url = f"{BASE}{resource.lower()}.profile.json"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def map_type(types):
    """types = element['type'] list. Return (sql_type, ref_note)."""
    if not types:
        return "OBJECT", None
    codes = [t.get("code", "") for t in types]
    # Reference(...) -> relation; collect targets for the note.
    if any(c == "Reference" for c in codes):
        targets = []
        for t in types:
            for tp in t.get("targetProfile", []) or []:
                targets.append(tp.rsplit("/", 1)[-1])
        note = f"references {', '.join(sorted(set(targets)))}" if targets else "reference"
        return "RELATION", note
    code = codes[0]
    key = code.rsplit(".", 1)[-1].lower()      # System.String -> string
    if key in PRIM_MAP:
        return PRIM_MAP[key], None
    if code and code[0].isupper():             # HumanName, CodeableConcept, ...
        return "OBJECT", f"FHIR complex type {code}"
    return "VARCHAR", None


def binding_note(element):
    b = element.get("binding")
    if not b:
        return None
    strength = b.get("strength")
    vs = (b.get("valueSet") or "").split("|")[0].rsplit("/", 1)[-1]
    if vs and strength in ("required", "extensible"):
        return f"Bound to value set '{vs}' ({strength})."
    return None


def parse_resource(doc, resource, category):
    elements = doc.get("snapshot", {}).get("element", [])
    items = []
    for e in elements:
        path = e.get("path", "")
        parts = path.split(".")
        if len(parts) != 2:          # top-level fields only (Resource.field)
            continue
        field = parts[1]
        if field in SKIP_FIELDS:
            continue
        sql_type, ref_note = map_type(e.get("type"))
        desc = e.get("definition") or e.get("short")
        for extra in (ref_note, binding_note(e)):
            if extra:
                desc = f"{desc} ({extra})" if desc else extra
        required = (e.get("min", 0) or 0) > 0
        items.append({
            "category": category,
            "name": f"{resource}.{field}",
            "title": e.get("short") or field,
            "description": desc,
            "data_type": sql_type,
            "is_required": required,
            "is_nullable": not required,
            "source_url": f"{BASE}{resource.lower()}.html",
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
    print("Generating FHIR seed (HL7 FHIR R4, CC0 public domain)...")
    all_items = []
    counts = {}
    for resource, category in TARGETS:
        try:
            doc = fetch(resource)
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {resource}: {e}", file=sys.stderr)
            continue
        items = parse_resource(doc, resource, category)
        counts[resource] = len(items)
        print(f"  {resource:<14} {len(items):>3} fields  [{category}]")
        all_items.extend(items)
    write_module(all_items, counts)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts):
    L = ['"""',
         "Seed: HL7 FHIR (R4) resource fields.",
         "",
         "AUTO-GENERATED by tools/fetch_fhir.py - do not edit by hand.",
         "Source : https://hl7.org/fhir/R4/ (StructureDefinition snapshots)",
         "License: Creative Commons 'No Rights Reserved' (CC0 1.0, public domain).",
         "",
         "Representative public JSON-Schema / structured-spec source.",
         "",
         "Resources & top-level field counts:"]
    for r, c in counts.items():
        L.append(f"    {r}: {c}")
    L += ['"""', "",
          'SRC_STD = "HL7 FHIR"',
          'VERSION = "FHIR R4 (4.0.1)"',
          "", "CATEGORIES = [",
          '    {"name": "Healthcare",'
          ' "description": "Patients, practitioners, encounters, observations and coverage.",'
          ' "source": "HL7 FHIR (CC0); Frappe Health"},',
          '    {"name": "Customer Relationship Management (CRM)",'
          ' "description": "Organizations and parties.",'
          ' "source": "HL7 FHIR (CC0); Schema.org; Microsoft CDM"},',
          '    {"name": "Finance / Accounting",'
          ' "description": "Invoices and billing.",'
          ' "source": "HL7 FHIR (CC0); Microsoft CDM; Tryton"},',
          "]", "", "_RAW = ["]
    for it in items:
        L.append("    {")
        for k in ("category", "name", "title", "description",
                  "data_type", "is_required", "is_nullable", "source_url"):
            L.append(f"        {py(k)}: {py(it[k])},")
        L.append("    },")
    L += ["]", "",
          "ITEMS = [dict(it, source_standard=SRC_STD, version=VERSION) for it in _RAW]",
          ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
