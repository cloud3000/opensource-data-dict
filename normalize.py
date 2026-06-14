#!/usr/bin/env python3
"""
normalize.py - Phase 3 normalization & cross-source deduplication.

Used by build_dict.py to turn the raw, per-source seed items into a clean,
deduplicated set before they are written to the database.

Two operations, both deliberately conservative (accuracy over quantity):

1. Naming standardization
   Every data item Name is rewritten to a consistent `entity.field` form
   where the entity (segment before the LAST dot) and the field (after it)
   are snake_case. Dots inside an entity (e.g. the Odoo model `hr.employee`)
   are preserved as namespace separators.
       Account.accountId      -> account.account_id
       Person.ID              -> person.id
       MaterialLot.Quantity   -> material_lot.quantity
       hr.employee.gender     -> hr.employee.gender   (unchanged)
       Quality Inspection.x   -> quality_inspection.x

2. Cross-source deduplication
   Items are grouped by their canonical key (CategoryID-name, i.e.
   category + normalized Name). Only items that describe the *same entity's
   same field* collapse together. A merged item keeps the richest available
   metadata and records EVERY contributing source in SourceStandard /
   SourceURL. Items that merely share a generic field name (e.g. `description`)
   but belong to different entities are NOT merged - they stay distinct.
"""

import json
import re
from collections import defaultdict


def _snake(s):
    """snake_case a single token (handles camelCase, spaces, hyphens)."""
    s = s.strip()
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)   # camelCase boundary
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)  # ACRONYMWord boundary
    s = s.replace(" ", "_").replace("-", "_")
    s = re.sub(r"_+", "_", s)
    return s.lower().strip("_")


# ---------------------------------------------------------------------------
# Entity-alias map (DELIBERATE, REVIEWABLE).
#
# Different open-source standards name the *same* business entity differently
# (Tryton uses dotted, module-namespaced model names; CDM/Schema.org use a
# single word). Each entry below asserts an explicit equivalence so that items
# describing the same field of the same concept can merge across sources.
#
# Rule for adding an entry: only when the two entities genuinely model the
# SAME business object. Keys are post-snake_case source entity names; values
# are the canonical entity name. When in doubt, leave it out (accuracy over
# quantity) - unaliased entities simply stay distinct and are surfaced as
# "related concepts" in the report instead.
# ---------------------------------------------------------------------------
ENTITY_ALIASES = {
    # Invoice  (Tryton account.invoice  ==  CDM/Schema.org Invoice)
    "account.invoice": "invoice",
    # Product  (Tryton product template + variant  ==  CDM/Schema.org Product)
    "product.template": "product",
    "product.product": "product",
    # Sales order  (Tryton sale.sale  ==  CDM/Schema.org Order)
    "sale.sale": "order",
    # Purchase order  (Odoo purchase.order  ==  Tryton purchase.purchase)
    "purchase.order": "purchase_order",
    "purchase.purchase": "purchase_order",
}


# ---------------------------------------------------------------------------
# Field-alias map (DELIBERATE, REVIEWABLE).
#
# Where ENTITY_ALIASES remaps a whole entity, FIELD_ALIASES remaps a single
# fully-qualified `entity.field` to a canonical one. This is needed for sources
# whose items are a flat catalog of standalone elements (e.g. GS1 Application
# Identifiers under the `gs1.` namespace) that nonetheless correspond to a
# specific field of another source's entity.
#
# Same rule: only when the two genuinely denote the SAME data element, and only
# when the canonical target already exists in the SAME category (otherwise the
# merge key won't match and the alias is a harmless no-op). Keys/values are
# post-snake_case, post-entity-alias names.
# ---------------------------------------------------------------------------
FIELD_ALIASES = {
    # GS1 AI 01 GTIN  ==  Schema.org Product.gtin   (Product Master Data)
    "gs1.gtin": "product.gtin",
    # GS1 AI 7001 NSN ==  Schema.org Product.nsn    (Product Master Data)
    "gs1.nsn": "product.nsn",
}


def canonical_entity(entity):
    """Apply the entity-alias map to a snake_cased entity name."""
    return ENTITY_ALIASES.get(entity, entity)


def _normalize_entity_field(name):
    """snake_case + entity-alias, without field aliasing."""
    if "." not in name:
        return _snake(name)
    entity, field = name.rsplit(".", 1)
    entity = ".".join(_snake(seg) for seg in entity.split("."))
    entity = canonical_entity(entity)
    return f"{entity}.{_snake(field)}"


def normalize_name(name):
    """Full normalization: snake_case, entity alias, then field alias."""
    base = _normalize_entity_field(name)
    return FIELD_ALIASES.get(base, base)


def _completeness(item):
    """Score how 'complete' an item is, to pick a merge primary."""
    score = 0
    if item.get("description"):
        score += 3
    if item.get("title"):
        score += 1
    if item.get("data_type") and item["data_type"] != "RELATION":
        score += 1
    if item.get("byte_length") is not None:
        score += 1
    if item.get("allowed_values"):
        score += 2
    return score


def _join_distinct(values, sep="; "):
    seen, out = set(), []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return sep.join(out) if out else None


def _parse_values(av):
    """Parse a stored AllowedValues cell into a list of values."""
    if not av:
        return []
    try:
        parsed = json.loads(av)
    except (ValueError, TypeError):
        return [av]
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):       # already a per-source object
        flat = []
        for vals in parsed.values():
            flat.extend(vals if isinstance(vals, list) else [vals])
        return flat
    return [parsed]


def merge_allowed_values(members):
    """
    Union the AllowedValues of merged members, grouped per source.

    * No member has allowed values            -> None
    * One source, or all sources agree         -> flat JSON array (the union)
    * Sources diverge                          -> JSON object {source: [values]}
                                                  so each vocabulary stays
                                                  attributable and visible.
    """
    per_source = {}   # source_standard -> ordered, de-duplicated list
    for m in members:
        vals = _parse_values(m.get("allowed_values"))
        if not vals:
            continue
        src = m.get("source_standard") or "unknown"
        bucket = per_source.setdefault(src, [])
        for v in vals:
            if v not in bucket:
                bucket.append(v)

    if not per_source:
        return None

    distinct = {frozenset(v) for v in per_source.values()}
    if len(per_source) == 1 or len(distinct) == 1:
        flat = []
        for vals in per_source.values():
            for v in vals:
                if v not in flat:
                    flat.append(v)
        return json.dumps(flat, ensure_ascii=False)

    # Divergent vocabularies: keep them separated by source.
    return json.dumps(per_source, ensure_ascii=False, sort_keys=True)


def normalize_and_dedupe(items):
    """
    Input  : list of raw seed item dicts (with a 'category' key + item fields).
    Output : (clean_items, report) where report describes what happened.
    """
    # 1. Normalize names; track which entity/field aliases actually fired.
    alias_usage = defaultdict(lambda: {"items": 0, "canonical": None})
    field_alias_usage = defaultdict(lambda: {"items": 0, "canonical": None})
    for it in items:
        raw = it["name"]
        if "." in raw:
            entity, _ = raw.rsplit(".", 1)
            entity = ".".join(_snake(seg) for seg in entity.split("."))
            canon = canonical_entity(entity)
            if canon != entity:
                alias_usage[entity]["items"] += 1
                alias_usage[entity]["canonical"] = canon
        base = _normalize_entity_field(raw)
        if base in FIELD_ALIASES:
            field_alias_usage[base]["items"] += 1
            field_alias_usage[base]["canonical"] = FIELD_ALIASES[base]
        it["name"] = normalize_name(raw)

    # 2. Group by canonical concept key = (category, normalized name).
    groups = defaultdict(list)
    for it in items:
        groups[(it["category"], it["name"])].append(it)

    clean = []
    merges = []      # concept keys that combined >1 source
    for (category, name), members in groups.items():
        if len(members) == 1:
            clean.append(members[0])
            continue

        sources = _join_distinct(m.get("source_standard") for m in members)
        n_src = len({m.get("source_standard") for m in members})
        primary = max(members, key=_completeness)

        merged = dict(primary)
        merged["description"] = max(
            (m.get("description") or "" for m in members), key=len) or None
        merged["title"] = primary.get("title") or next(
            (m.get("title") for m in members if m.get("title")), None)
        merged["byte_length"] = max(
            (m["byte_length"] for m in members if m.get("byte_length") is not None),
            default=None)
        merged["is_required"] = any(m.get("is_required") for m in members)
        merged["is_nullable"] = not merged["is_required"]
        merged["allowed_values"] = merge_allowed_values(members)
        merged["source_standard"] = sources
        merged["source_url"] = _join_distinct(
            (m.get("source_url") for m in members), sep=" | ")
        merged["version"] = _join_distinct(m.get("version") for m in members)
        clean.append(merged)
        if n_src > 1:
            merges.append({"category": category, "name": name,
                           "sources": sources, "count": len(members)})

    # 3. Report: related concepts that share a field name across sources but
    #    belong to different entities (NOT merged - surfaced for review).
    field_index = defaultdict(set)   # (category, field) -> set(source_standard)
    field_objs = defaultdict(set)    # (category, field) -> set(entity)
    for it in clean:
        entity, field = it["name"].rsplit(".", 1) if "." in it["name"] else ("", it["name"])
        field_index[(it["category"], field)].add(it.get("source_standard"))
        field_objs[(it["category"], field)].add(entity)
    related = []
    for (cat, field), srcs in field_index.items():
        flat = set()
        for s in srcs:
            flat.update((s or "").split("; "))
        if len(flat) > 1 and len(field_objs[(cat, field)]) > 1:
            related.append({"category": cat, "field": field,
                            "entities": sorted(field_objs[(cat, field)]),
                            "sources": sorted(flat)})

    aliases = sorted(
        ({"source_entity": k, "canonical": v["canonical"], "items": v["items"]}
         for k, v in alias_usage.items()),
        key=lambda a: a["source_entity"])
    field_aliases = sorted(
        ({"source_field": k, "canonical": v["canonical"], "items": v["items"]}
         for k, v in field_alias_usage.items()),
        key=lambda a: a["source_field"])

    report = {
        "input_items": len(items),
        "output_items": len(clean),
        "merged_concepts": len(merges),
        "merges": merges,
        "related_concepts": sorted(related, key=lambda r: (r["category"], r["field"])),
        "aliases_applied": aliases,
        "field_aliases_applied": field_aliases,
    }
    return clean, report
