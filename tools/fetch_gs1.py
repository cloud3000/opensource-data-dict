#!/usr/bin/env python3
"""
tools/fetch_gs1.py - Generate seeds/gs1.py from the GS1 Barcode Syntax
Dictionary.

The GS1 Barcode Syntax Dictionary (https://github.com/gs1/gs1-syntax-dictionary)
is published under the Apache License 2.0. It is the authoritative, machine-
readable list of GS1 Application Identifiers (AIs) - the standardized data
elements that GS1 barcodes carry: GTIN (AI 01), SSCC (00), batch/lot (10),
expiry (17), net weight (310n), GLNs (41x), price/amount (39xx), etc.

Each AI line has the form:
    <AI|range>  [flags]  <format-spec...>  [attributes]   # TITLE
e.g.
    01  *?  N14,csum,gcppos2   ex=255,37 dlpkey=22,10,21|235   # GTIN

We extract: AI code, title, the GS1 format spec (kept verbatim in FormatMask),
a primary SQL data type + length, and a best-fit business category.

Re-run to refresh:
    python3 tools/fetch_gs1.py
"""

import os
import re
import sys
import urllib.request

URL = ("https://raw.githubusercontent.com/gs1/gs1-syntax-dictionary/"
       "main/gs1-syntax-dictionary.txt")
BLOB = ("https://github.com/gs1/gs1-syntax-dictionary/blob/"
        "main/gs1-syntax-dictionary.txt")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "seeds", "gs1.py")

FLAG_RE = re.compile(r"^[*?]+$")
PRIMARY_RE = re.compile(r"\[?([NXYZ])(\.\.)?(\d+)")

CATEGORIES = [
    ("Product Master Data",
     "GS1 trade-item identifiers (GTIN), variants and physical measures.",
     "GS1 (Apache-2.0); Schema.org; Microsoft CDM"),
    ("Inventory / Warehouse",
     "GS1 batch/lot, serial numbers, counts and stock-related dates.",
     "GS1 (Apache-2.0); ISA-95"),
    ("Supply Chain / Logistics",
     "GS1 logistic unit (SSCC), GLN locations, consignment and origin AIs.",
     "GS1 (Apache-2.0)"),
    ("Finance / Accounting",
     "GS1 amount, price and pay-to AIs.",
     "GS1 (Apache-2.0)"),
    ("Maintenance / Asset Management",
     "GS1 asset identifiers (GRAI, GIAI).",
     "GS1 (Apache-2.0)"),
    ("Customer Relationship Management (CRM)",
     "GS1 service relation numbers (GSRN).",
     "GS1 (Apache-2.0)"),
]


def category_for(ai):
    a = ai.split("-")[0]
    digits = "".join(ch for ch in a if ch.isdigit())
    n = int(digits) if digits else -1

    # Assets (GRAI / GIAI / GIAI-assembly)
    if a in ("8003", "8004", "7023"):
        return "Maintenance / Asset Management"
    # Service relation numbers (GSRN)
    if a in ("8017", "8018"):
        return "Customer Relationship Management (CRM)"
    # Finance: amounts, prices, percentages, pay-to, payment slip
    if (3900 <= n <= 3999) or a in ("415", "8020", "8005", "8008"):
        return "Finance / Accounting"
    # Inventory / traceability: lot, serial, counts, stock dates
    if a in ("10", "21", "22", "235", "250", "251", "254", "30", "37",
             "7003", "7006", "7007", "7011") or (11 <= n <= 17 and len(a) == 2):
        return "Inventory / Warehouse"
    # Product master: GTIN family, variants, part numbers, measures, attrs
    if a in ("01", "02", "03", "20", "240", "241", "242", "243", "7001",
             "7002", "7004", "7005", "7008", "7009", "7010", "7020", "7021",
             "7022", "8001", "8002", "8006", "8007", "8013", "8019", "8026",
             "8200") or (710 <= n <= 716) or (3100 <= n <= 3699):
        return "Product Master Data"
    # Logistics: SSCC, consignment/shipment, GLN locations, origin, processors
    if a == "00" or (400 <= n <= 403) or (410 <= n <= 417) or \
            (420 <= n <= 427) or (7030 <= n <= 7039) or \
            a.startswith("43") or a in ("253", "255", "401", "402"):
        return "Supply Chain / Logistics"
    return "Supply Chain / Logistics"   # sensible GS1 default


def slugify(title):
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "ai"


def parse_spec(tokens):
    """Return (spec_str, primary_token) from tokens after the AI/flags,
    stopping at the first attribute token (contains '=' or is 'dlpkey')."""
    spec = []
    for t in tokens:
        if "=" in t or t == "dlpkey":
            break
        spec.append(t)
    spec_str = " ".join(spec)
    primary = spec[0] if spec else ""
    return spec_str, primary


def classify(ai, spec_str, primary):
    spec_l = spec_str.lower()
    is_date = "yymmd" in spec_l
    is_time = "hhmi" in spec_l or "hhmm" in spec_l
    a = ai.split("-")[0]
    digits = "".join(ch for ch in a if ch.isdigit())
    n = int(digits) if digits else -1

    if is_date and is_time:
        dtype = "DATETIME"
    elif is_date:
        dtype = "DATE"
    elif (3100 <= n <= 3699) or (3900 <= n <= 3949):
        dtype = "DECIMAL"
    else:
        dtype = "VARCHAR"

    length = None
    m = PRIMARY_RE.match(primary)
    if m:
        length = int(m.group(3))
        # For currency/country-qualified amounts the value is the 2nd part;
        # take the larger component length as the indicative size.
        for mm in PRIMARY_RE.finditer(spec_str):
            length = max(length, int(mm.group(3)))
    return dtype, length


def main():
    print("Generating GS1 seed from GS1 Barcode Syntax Dictionary (Apache-2.0)...")
    with urllib.request.urlopen(URL, timeout=60) as r:
        text = r.read().decode("utf-8")

    items = []
    seen = {}
    cat_counts = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "#" not in line:
            continue
        defn, title = line.split("#", 1)
        title = title.strip()
        tokens = defn.split()
        if not tokens:
            continue
        ai = tokens[0]
        rest = tokens[1:]
        if rest and FLAG_RE.match(rest[0]):
            rest = rest[1:]
        spec_str, primary = parse_spec(rest)
        if not spec_str:
            continue
        # Skip internal / mutually-agreed AIs (90-99): no standard semantics.
        if ai.split("-")[0] in ("90", "91", "92", "93", "94", "95", "96", "97",
                                 "98", "99"):
            continue

        category = category_for(ai)
        dtype, length = classify(ai, spec_str, primary)

        slug = slugify(title)
        name = f"gs1.{slug}"
        if name in seen:                      # guarantee uniqueness
            name = f"gs1.{slug}_{ai.replace('-', '_')}"
        seen[name] = True

        desc = f"GS1 Application Identifier ({ai}) - {title}. GS1 format: {spec_str}."
        if dtype == "DECIMAL" and ("310" <= ai[:3] <= "369" or ai[:2] == "39"):
            desc += " The last AI digit indicates the number of implied decimal places."

        cat_counts[category] = cat_counts.get(category, 0) + 1
        items.append({
            "category": category,
            "name": name,
            "title": title,
            "description": desc,
            "data_type": dtype,
            "byte_length": length,
            "format_mask": spec_str,
            "source_url": BLOB,
        })

    write_module(items, cat_counts)
    print(f"  parsed {len(items)} GS1 Application Identifiers")
    for c, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"    {c:<40} {n}")
    print(f"\nWrote {len(items)} items -> {os.path.relpath(OUT)}")


def py(v):
    if v is None:
        return "None"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    return repr(v) if not isinstance(v, str) else _q(v)


def _q(s):
    import json
    return json.dumps(s, ensure_ascii=False)


def write_module(items, counts):
    L = ['"""',
         "Seed: GS1 Application Identifiers (Barcode Syntax Dictionary).",
         "",
         "AUTO-GENERATED by tools/fetch_gs1.py - do not edit by hand.",
         "Source : https://github.com/gs1/gs1-syntax-dictionary",
         "License: Apache License 2.0.",
         "",
         "Each item is one GS1 Application Identifier (AI). The exact GS1 format",
         "specification is preserved verbatim in FormatMask.",
         "",
         "AIs per category:"]
    for c, n in counts.items():
        L.append(f"    {c}: {n}")
    L += ['"""', "",
          'SRC_STD = "GS1"',
          'VERSION = "GS1 Barcode Syntax Dictionary"',
          "", "CATEGORIES = ["]
    for name, desc, src in CATEGORIES:
        L.append(f"    {{\"name\": {_q(name)}, \"description\": {_q(desc)}, "
                 f"\"source\": {_q(src)}}},")
    L += ["]", "", "_RAW = ["]
    for it in items:
        L.append("    {")
        for k in ("category", "name", "title", "description", "data_type",
                  "byte_length", "format_mask", "source_url"):
            L.append(f"        {_q(k)}: {py(it[k])},")
        L.append("    },")
    L += ["]", "",
          "ITEMS = [dict(it, source_standard=SRC_STD, version=VERSION) for it in _RAW]",
          ""]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
