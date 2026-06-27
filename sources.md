# Sources

Every data item in `datadict.db` originates from a **public / open-source**
resource. No paywalled, proprietary, or scraped commercial content is used.

**Licensing:** code is MIT ([`LICENSE`](LICENSE)); the data compilation is
CC BY-SA 4.0 ([`DATA_LICENSE`](DATA_LICENSE)); each item additionally remains
under its upstream license (the table below). See README → "License &
attribution".

> **`AllowedValues` format.** Usually a JSON **array** of permitted values
> (e.g. `["male","female","other"]`). When a cross-source merge combines items
> whose vocabularies **diverge**, the cell instead holds a JSON **object keyed
> by source** so each vocabulary stays attributable, e.g.
> `purchase_order.state` →
> `{"Odoo":["draft","sent",...], "Tryton":["draft","quotation",...]}`.
> Consumers should handle both array and object shapes.

| # | Source | Standard tag | License | What we extracted | Repo / URL |
|---|--------|--------------|---------|-------------------|------------|
| 1 | **B2MML / ISA-95** (MESA International) | `ISA-95 (B2MML)` | Royalty-free (MESA International license in repo) | Part 2 object-model attributes: Person, PersonnelClass, Equipment, EquipmentClass, MaterialClass, MaterialDefinition, MaterialLot, MaterialSubLot, ProcessSegment | https://github.com/MESAInternational/B2MML-BatchML |
| 2 | **Microsoft Common Data Model (CDM)** | `Microsoft CDM` | CDLA-Permissive-2.0 | Canonical entity attributes: Account, Contact, Lead, Opportunity, Order, OrderProduct, Quote, Invoice, InvoiceProduct, Product | https://github.com/microsoft/CDM |
| 3 | **Odoo Community Edition** | `Odoo` | LGPL-3.0 | Model fields: hr.employee, hr.department, hr.job, purchase.order(.line), stock.picking, stock.lot, stock.quant; mrp.production, mrp.bom(.line), mrp.routing.workcenter, mrp.workcenter, mrp.workorder, mrp.unbuild (Manufacturing) | https://github.com/odoo/odoo |
| 4 | **ERPNext + Frappe Health** | `ERPNext / Frappe Health` | GPL-3.0 | DocType fields: Quality Inspection (+Reading), Non Conformance, Quality Goal/Action/Procedure/Review; Work Order, BOM, BOM Item/Operation, Job Card, Operation, Workstation, Routing, Production Plan (Manufacturing); Patient, Patient Appointment/Encounter, Vital Signs, Clinical Procedure, Lab Test | https://github.com/frappe/erpnext , https://github.com/frappe/health |
| 5 | **Schema.org** | `Schema.org` | CC BY-SA 3.0 | Properties (incl. inherited) of types: Product, Order, Offer, Invoice, Organization, Person. Enumeration ranges captured as AllowedValues | https://schema.org |
| 6 | **Tryton** | `Tryton` | GPL-3.0 | Model fields: party.party, party.address, account.invoice(.line), account.move(.line), product.template/product, sale.sale(.line), purchase.purchase(.line), stock.move, stock.location; production, production.bom, production.routing, production.work (Manufacturing) | https://github.com/tryton/tryton |
| 7 | **GS1 Application Identifiers** | `GS1` | Apache-2.0 | 220 GS1 AIs from the GS1 Barcode Syntax Dictionary: GTIN, SSCC, batch/lot, serial, expiry/prod dates, net weight & measures, GLN locations, amounts/prices, GRAI/GIAI assets. Exact GS1 format preserved in `FormatMask` | https://github.com/gs1/gs1-syntax-dictionary |
| 8 | **HL7 FHIR (R4)** — public JSON Schema / spec | `HL7 FHIR` | CC0 1.0 (public domain) | Top-level fields of resources Patient, Practitioner, Encounter, Observation, Coverage (Healthcare), Organization (CRM), Invoice (Finance), parsed from StructureDefinition snapshots; value-set bindings & Reference targets noted | https://hl7.org/fhir/R4/ |
| 9 | **Stripe API** — public OpenAPI spec | `Stripe API` | MIT | Object schemas from the openly-licensed (MIT) OpenAPI document: customer (CRM), product, price (Product), invoice, invoiceitem, charge, payout, refund, payment_intent (Finance), quote, subscription (Sales). Enums → AllowedValues | https://github.com/stripe/openapi |

## Extraction method

- **ISA-95 / B2MML** — XSD `complexType` element definitions parsed directly
  from `Schema/*.xsd` (V0701). Base types verified against
  `B2MML-CoreComponents.xsd` (`IdentifierType`→string, `DateTimeType`→dateTime,
  etc.). See `seeds/isa95_b2mml.py`.
- **Microsoft CDM** — entity attributes (`name`, `dataType`, `maximumLength`,
  `isNullable`, `description`) extracted from canonical `*.cdm.json` files and
  mapped to SQL data types. Regenerate with `python3 tools/fetch_cdm.py`.
  See `seeds/cdm_microsoft.py` (auto-generated).
- **Odoo** — `fields.*` declarations parsed via Python `ast` (handles
  multi-line definitions); `Selection` options captured into `AllowedValues`.
  Regenerate with `python3 tools/fetch_odoo.py`. See `seeds/odoo.py`.
- **ERPNext / Frappe Health** — DocType JSON `fields` arrays parsed; `Select`
  options captured into `AllowedValues`, `Link` targets noted in description.
  Regenerate with `python3 tools/fetch_frappe.py`. See `seeds/frappe.py`.
- **Schema.org** — JSON-LD vocabulary parsed; for each target type, properties
  whose `domainIncludes` is the type or a Schema.org ancestor are collected,
  `rangeIncludes` mapped to SQL types, and Enumeration ranges (e.g.
  `OrderStatus`) captured as `AllowedValues`. Regenerate with
  `python3 tools/fetch_schemaorg.py`. See `seeds/schemaorg.py`.
- **Tryton** — `fields.*` declarations parsed via Python `ast` (model name from
  `__name__`, `fields.Function(...)` wrappers unwrapped, per-type positional
  arg layout); `Selection` options captured into `AllowedValues`. Regenerate
  with `python3 tools/fetch_tryton.py`. See `seeds/tryton.py`.
- **GS1** — the GS1 Barcode Syntax Dictionary text file is parsed line-by-line;
  each Application Identifier yields one data element. The GS1 format spec
  (e.g. `N14,csum,gcppos2`) is kept verbatim in `FormatMask`; AI codes are
  mapped to a primary SQL type/length and a best-fit category. AIs live under a
  `gs1.` namespace (an authoritative element catalog). Regenerate with
  `python3 tools/fetch_gs1.py`. See `seeds/gs1.py`. A small, reviewable
  `FIELD_ALIASES` map then folds the GS1 identifiers that have direct
  counterparts into canonical fields (`gs1.gtin`→`product.gtin`,
  `gs1.nsn`→`product.nsn`), so they corroborate the Schema.org product
  properties (GS1's exact format/length wins on the merged row).
- **HL7 FHIR (R4)** — our representative public JSON-Schema/spec source. Each
  resource's `StructureDefinition` snapshot is parsed; top-level elements
  become items (FHIR primitive types → SQL types, complex types → OBJECT,
  `Reference(...)` → RELATION with targets noted, required value-set bindings
  noted). Regenerate with `python3 tools/fetch_fhir.py`. See `seeds/fhir.py`.
- **OpenAPI / Swagger** — generic ingester (`tools/fetch_openapi.py`): locates
  the schema map (`components.schemas` for OpenAPI 3, `definitions` for
  Swagger 2), parses each selected object's properties (type+format → SQL type,
  `enum` → AllowedValues, `maxLength` → ByteLength, schema-level `required`).
  Adding another JSON spec is one entry in `SPECS`. Currently configured with
  the **Stripe** OpenAPI document (MIT-licensed open-source artifact published
  by Stripe; used as an open spec, not scraped). See `seeds/openapi.py`.

## Description provenance

Every data item carries a `Description` (**100% coverage**), drawn from one of
two places:

- **From source** (3,234 items) — the description shipped with the upstream
  model (Odoo `help=`, ERPNext DocType `description`, CDM `description`, FHIR
  element definitions, etc.) and is used verbatim.
- **Curated editorial** (454 items) — where the source exposed only a label and
  no description text, a factual description was written from the field's own
  metadata (entity + Title + AllowedValues). These live in
  [`tools/curated_descriptions.py`](tools/curated_descriptions.py) as a
  reviewable `CURATED` map keyed by item Name, applied with
  `python3 tools/backfill_descriptions.py --curated`. They restate what the
  field already declares, so no external claim is introduced, and they are
  **durable** — `build_dict.py` only fills a NULL description, so curated text
  survives rebuilds and yields automatically if the source later gains real
  help text.

The from-source / curated split is charted per category in
[`DATA_MODEL.md`](DATA_MODEL.md) §3 ("Description coverage & provenance"), with
a static export at
[`diagrams/description-coverage.svg`](diagrams/description-coverage.svg).

## Planned / candidate sources (future expansion)

- More OpenAPI specs from open projects (drop-in via `SPECS` in fetch_openapi.py)
