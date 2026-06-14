#!/usr/bin/env python3
"""
tools/fetch_frappe.py - Generate seeds/frappe.py from Frappe/ERPNext-family
DocType definitions (ERPNext + the Frappe Health app).

Both apps are GPL-3.0 open source:
  * ERPNext        https://github.com/frappe/erpnext
  * Frappe Health  https://github.com/frappe/health
DocTypes are JSON with a `fields` array (fieldname, fieldtype, label, reqd,
options, description, length); this generator parses them and emits a
self-contained seed module for build_dict.py.

Re-run to refresh:
    python3 tools/fetch_frappe.py
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "frappe.py")

# (repo, branch, doctype_path, category)
TARGETS = [
    # --- Quality Management (ERPNext) ---
    ("frappe/erpnext", "develop",
     "erpnext/stock/doctype/quality_inspection/quality_inspection.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/stock/doctype/quality_inspection_reading/quality_inspection_reading.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/quality_management/doctype/non_conformance/non_conformance.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/quality_management/doctype/quality_goal/quality_goal.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/quality_management/doctype/quality_action/quality_action.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/quality_management/doctype/quality_procedure/quality_procedure.json",
     "Quality Management"),
    ("frappe/erpnext", "develop",
     "erpnext/quality_management/doctype/quality_review/quality_review.json",
     "Quality Management"),
    # --- Healthcare (Frappe Health) ---
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/patient/patient.json", "Healthcare"),
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/patient_appointment/patient_appointment.json",
     "Healthcare"),
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/patient_encounter/patient_encounter.json",
     "Healthcare"),
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/vital_signs/vital_signs.json", "Healthcare"),
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/clinical_procedure/clinical_procedure.json",
     "Healthcare"),
    ("frappe/health", "develop",
     "healthcare/healthcare/doctype/lab_test/lab_test.json", "Healthcare"),
]

FIELD_MAP = {
    "Data": "VARCHAR", "Small Text": "TEXT", "Text": "TEXT", "Long Text": "TEXT",
    "Text Editor": "TEXT", "Code": "TEXT", "Markdown Editor": "TEXT", "HTML Editor": "TEXT",
    "Int": "INTEGER", "Float": "DECIMAL", "Percent": "DECIMAL", "Currency": "DECIMAL",
    "Check": "BOOLEAN", "Date": "DATE", "Datetime": "DATETIME", "Time": "TIME",
    "Duration": "INTEGER", "Select": "VARCHAR", "Link": "VARCHAR",
    "Dynamic Link": "VARCHAR", "Table": "RELATION", "Table MultiSelect": "RELATION",
    "Attach": "VARCHAR", "Attach Image": "VARCHAR", "Phone": "VARCHAR",
    "Read Only": "VARCHAR", "Rating": "DECIMAL", "Color": "VARCHAR",
    "Password": "VARCHAR", "Signature": "TEXT", "Geolocation": "TEXT",
}
SKIP = {"Section Break", "Column Break", "Tab Break", "HTML", "Heading",
        "Fold", "Image", "Button"}

CATEGORIES = [
    ("Quality Management",
     "Quality inspections, non-conformances, goals and corrective actions.",
     "ERPNext (GPL-3.0)"),
    ("Healthcare",
     "Patients, appointments, encounters, vitals and clinical procedures.",
     "Frappe Health (GPL-3.0)"),
]


def fetch(repo, branch, path):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_doctype(doc, repo, branch, path, category):
    name = doc.get("name", path.split("/")[-1].replace(".json", ""))
    blob = f"https://github.com/{repo}/blob/{branch}/{path}"
    items = []
    for f in doc.get("fields", []):
        ft = f.get("fieldtype")
        if ft in SKIP or ft not in FIELD_MAP:
            continue
        fieldname = f.get("fieldname")
        if not fieldname:
            continue
        options = f.get("options")
        allowed = None
        desc = f.get("description") or None
        if ft == "Select" and options:
            vals = [o for o in str(options).split("\n") if o.strip()]
            allowed = json.dumps(vals) if vals else None
        elif ft in ("Link", "Dynamic Link", "Table", "Table MultiSelect") and options:
            link_note = f"(links to {options})"
            desc = f"{desc} {link_note}" if desc else link_note
        items.append({
            "category": category,
            "name": f"{name}.{fieldname}",
            "title": f.get("label") or fieldname,
            "description": desc,
            "data_type": FIELD_MAP[ft],
            "byte_length": f.get("length") or None,
            "is_required": (f.get("reqd") in (1, True)),
            "is_nullable": not (f.get("reqd") in (1, True)),
            "allowed_values": allowed,
            "source_url": blob,
        })
    return name, items


def py(v):
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def main():
    print("Generating Frappe/ERPNext + Health seed...")
    all_items = []
    counts = {}
    for repo, branch, path, category in TARGETS:
        try:
            doc = fetch(repo, branch, path)
        except Exception as e:  # noqa: BLE001
            print(f"  ! skip {path.split('/')[-1]}: {e}", file=sys.stderr)
            continue
        name, items = parse_doctype(doc, repo, branch, path, category)
        counts[name] = len(items)
        print(f"  {name:<28} {len(items):>3} fields  [{category}]")
        all_items.extend(items)
    write_module(all_items, counts)
    print(f"\nWrote {len(all_items)} items -> {os.path.relpath(OUT)}")


def write_module(items, counts):
    L = ['"""',
         "Seed: Frappe / ERPNext + Frappe Health DocType fields.",
         "",
         "AUTO-GENERATED by tools/fetch_frappe.py - do not edit by hand.",
         "Sources: https://github.com/frappe/erpnext (GPL-3.0),",
         "         https://github.com/frappe/health  (GPL-3.0).",
         "",
         "DocTypes & field counts:"]
    for n, c in counts.items():
        L.append(f"    {n}: {c}")
    L += ['"""', "",
          'SRC_STD = "ERPNext / Frappe Health"',
          'VERSION = "develop"',
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
