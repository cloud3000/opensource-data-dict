# Progress Log - Business Data Dictionary

## Architecture
- `build_dict.py` — idempotent builder. Creates schema, loads every module in
  `seeds/`, upserts via `insert_or_update_category` / `insert_or_update_item`
  (natural key = `CategoryID + Name + SourceStandard`), exports `datadict.sql`,
  prints stats. Run: `python3 build_dict.py` (or `--stats`, `--no-export`).
- `seeds/` — one module per source, each exposing `CATEGORIES` and `ITEMS`.
- `tools/` — generators that (re)build seed modules from upstream repos.

## Status by phase
- **Phase 1 Discovery** — ✅ all 12 scope categories sourced from open repos.
- **Phase 2 Extraction** — ISA-95 ✅, CDM ✅, Odoo ✅, ERPNext+Health ✅.
- **Phase 3 Normalization** — ✅ DONE. All Names normalized to consistent
  `entity.field` **snake_case** via `normalize.py` (integrated into the build).
  Cross-source dedup rule active (merges identical `entity.field` items, keeps
  best version, joins all sources/URLs). Run result: 1428 → 1428 (0 merges —
  each source models distinct entities; verified by analysis). 3 related
  concepts flagged but kept separate (different entities). See
  `NORMALIZATION_REPORT.md`. Merge logic unit-tested with a synthetic dup.
- **Phase 4 SQLite** — `datadict.db` + `datadict.sql` generated & verified
  (reloads cleanly into a fresh DB). ✅

## Run log
- 2026-06-14 — Bootstrapped builder + schema. Added ISA-95/B2MML seed
  (122 items: Person, PersonnelClass, Equipment, EquipmentClass, Material*,
  ProcessSegment).
- 2026-06-14 — Added Microsoft CDM seed via `tools/fetch_cdm.py`
  (712 items: Account, Contact, Lead, Opportunity, Order, OrderProduct,
  Quote, Invoice, InvoiceProduct, Product).
- 2026-06-14 — Added Odoo seed via `tools/fetch_odoo.py` (275 items: HR,
  Procurement, Stock/Inventory, Logistics).
- 2026-06-14 — Added ERPNext + Frappe Health seed via `tools/fetch_frappe.py`
  (319 items: Quality Management + Healthcare).
- 2026-06-14 — Phase 3: added `normalize.py` (snake_case naming + conservative
  cross-source merge), integrated into `build_dict.py`. Rebuilt clean; emits
  `NORMALIZATION_REPORT.md`. Names now uniform snake_case; 0 unsafe merges.
- 2026-06-14 — Added Schema.org seed via `tools/fetch_schemaorg.py` (373 items:
  Product, Order, Offer, Invoice, Organization, Person; enums → AllowedValues).
  This exercised the dedup path: **11 cross-source merges** (product/order/
  invoice/person fields shared with CDM & ISA-95), each keeping both sources.
- 2026-06-14 — Added Tryton seed via `tools/fetch_tryton.py` (562 items: party,
  address, account.invoice/move, product, sale, purchase, stock). Initially no
  new merges (namespaced model names) — balanced the categories.
- 2026-06-14 — Added `ENTITY_ALIASES` map to `normalize.py` (deliberate,
  reviewable entity equivalences): account.invoice→invoice,
  product.template/product→product, sale.sale→order,
  purchase.order/purchase.purchase→purchase_order. This lifted cross-source
  merges from 11 → **13** (Tryton now corroborates invoice/product/order;
  Odoo↔Tryton merge on purchase_order.origin & state). Report now lists every
  alias applied + item counts. NOTE: merging concepts with divergent enums
  (e.g. purchase_order.state) keeps one source's AllowedValues; both sources
  remain recorded for traceability.
- 2026-06-14 — Replaced "pick-first" enum merge with `merge_allowed_values`:
  unions AllowedValues per source. Agreeing/single-source → flat JSON array;
  divergent vocabularies → JSON object keyed by source (e.g.
  `purchase_order.state` keeps both Odoo & Tryton code sets). Unit-tested the
  none/agree(diff order)/diverge cases; fixed a set-vs-ordered comparison bug.
  `AllowedValues` is now array-or-object (documented in `sources.md`).
- 2026-06-14 — Added GS1 seed via `tools/fetch_gs1.py` (220 items from the GS1
  Barcode Syntax Dictionary, Apache-2.0). Each Application Identifier (GTIN,
  SSCC, batch/lot, dates, measures, GLNs, amounts, GRAI/GIAI) becomes a data
  element under the `gs1.` namespace; exact GS1 format kept in FormatMask.
  Filled Supply Chain & Product.
- 2026-06-14 — Added `FIELD_ALIASES` (field-level alias map) to `normalize.py`:
  folds standalone GS1 identifiers into a canonical entity field
  (`gs1.gtin`→`product.gtin`, `gs1.nsn`→`product.nsn`). Cross-source merges
  13 → **15**; GS1's precise FormatMask/ByteLength carried onto the merged
  Schema.org product fields. Report now lists field aliases separately.
- 2026-06-14 — Added HL7 FHIR (R4) seed via `tools/fetch_fhir.py` (116 items;
  CC0 public domain) as the public JSON-Schema/spec source: Patient,
  Practitioner, Encounter, Observation, Coverage, Organization, Invoice. Parsed
  from StructureDefinition snapshots. Cross-source merges 15 → **22** (new:
  organization.name/address/identifier with Schema.org; invoice.type/account
  with Tryton; invoice.identifier with Schema.org; patient.marital_status with
  Frappe Health).

- 2026-06-14 — Added generic OpenAPI/Swagger ingester `tools/fetch_openapi.py`
  (`components.schemas`/`definitions` → properties; enum→AllowedValues;
  required; type+format→SQL). Configured with the Stripe OpenAPI spec (MIT;
  393 items: customer, product, price, invoice, invoiceitem, charge, payout,
  refund, payment_intent, quote, subscription). Cross-source merges 22 → **31**:
  `product.name`/`product.description`/`invoice.description` now carry 4 sources
  (CDM+Stripe+Schema.org+Tryton); 8 new invoice.* merges across
  Stripe/Tryton/FHIR/CDM. Adding more specs = one entry in `SPECS`.

- 2026-06-14 — Added `README.md` (overview, schema, build/usage, conventions)
  and `QUERY_COOKBOOK.md` (40+ runnable SQL recipes, all tested against the DB;
  recursive-CTE entity/field split since this SQLite build lacks `reverse()`).
- 2026-06-14 — Added `tools/gen_diagram.py` → `DATA_MODEL.md`: Mermaid ER
  diagram, category pie, source→category flowchart, and contribution matrix,
  generated live from `datadict.db` (re-run after each build to refresh).
- 2026-06-14 — Added `CONTRIBUTING.md` (seed-module contract, how to add a
  source, alias/merge rules, pre-PR checklist, inbound=outbound licensing) and
  a Contributing pointer in README.
- 2026-06-14 — Added licensing: `LICENSE` (MIT, code) + `DATA_LICENSE`
  (CC BY-SA 4.0, official text, for the data compilation). README "License &
  attribution" + sources.md document the dual setup and that per-item upstream
  licenses still apply (attribution via SourceStandard/SourceURL + sources.md).
- 2026-06-14 — Added `tools/render_diagrams.py` → `diagrams/*.svg` + `*.png`.
  No Node/`mmdc` available, so it renders via headless Chromium + the Mermaid
  browser library (cached in `diagrams/_build/mermaid.min.js`) — fully local,
  no external rendering service. SVG extracted from rendered DOM; PNG via a
  size-matched screenshot at 2x. Verified images (ER 764x1332, categories
  1804x932, source-map 1462x3766).
- 2026-06-27 — Filled out the **Manufacturing** category (was 15, all ISA-95
  `process_segment`). Added the manufacturing modules of the three open ERPs to
  their fetchers: Odoo `mrp` (production, BOM, routing, work center, work order,
  unbuild), Tryton `production`/`production_routing`/`production_work`, and
  ERPNext Manufacturing DocTypes (Work Order, BOM, BOM Item/Operation, Job Card,
  Operation, Workstation, Routing, Production Plan). Manufacturing 15 → 648.
- 2026-06-27 — Added `tools/backfill_descriptions.py` and backfilled the 198
  Manufacturing items that had no upstream description, synthesising factual
  text from each field's own metadata (entity + Title + AllowedValues). Manu-
  facturing now has 0 items without a description.

## Current totals
- **3,688 data items, 12 categories, 9 source standards** (3729 raw → 3688
  after merges; 6 entity + 2 field aliases applied).
  - Manufacturing 648, Finance/Accounting 612, Sales/Order Mgmt 538, CRM 484,
    Healthcare 331, Product Master 299, Supply Chain/Logistics 226, HR 195,
    Inventory/Warehouse 131, Procurement 111, Quality Mgmt 81,
    Maintenance/Asset 32.

## TODO (future expansion)
- [x] Phase 3 dedup pass: merge rule implemented + naming normalized (done).
- [ ] Tryton / Schema.org / GS1 for cross-source corroboration — these WILL
      trigger real merges (e.g. Product/Material concepts) once added.
- [~] Backfill descriptions for items lacking one (mostly Odoo fields without
      `help=` / ERPNext fields without `description`); Title is always
      populated. Tool added: `tools/backfill_descriptions.py` synthesises a
      factual description from the item's own metadata (entity + Title +
      AllowedValues) and survives rebuilds via the `COALESCE` upsert. Done for
      **Manufacturing** (198 filled, 0 remaining). ~256 remain in other
      categories (Healthcare 130, Quality 50, ...) — run
      `python3 tools/backfill_descriptions.py --all` (or `--category NAME`).
