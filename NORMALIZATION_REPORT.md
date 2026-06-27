# Phase 3 - Normalization & Deduplication Report

_Generated 2026-06-27T07:55:08.729525+00:00 (UTC) by build_dict.py._

## Summary

- Raw seed items: **3729**
- Items after normalization + dedup: **3688**
- Cross-source merges performed: **31**
- Related concepts flagged (not merged): **75**

All Names normalized to consistent `entity.field` snake_case.

## Entity aliases applied

Deliberate equivalences (see `ENTITY_ALIASES` in `normalize.py`) that fold a source's namespaced entity into a canonical entity so matching fields can merge across sources.

| Source entity | Canonical entity | Items remapped |
|---|---|---|
| `account.invoice` | `invoice` | 51 |
| `product.product` | `product` | 14 |
| `product.template` | `product` | 13 |
| `purchase.order` | `purchase_order` | 35 |
| `purchase.purchase` | `purchase_order` | 30 |
| `sale.sale` | `order` | 39 |

## Field aliases applied

Single-element equivalences (see `FIELD_ALIASES` in `normalize.py`) that fold a source's standalone data element into a specific field of a canonical entity (e.g. GS1 AIs).

| Source field | Canonical field | Items remapped |
|---|---|---|
| `gs1.gtin` | `product.gtin` | 1 |
| `gs1.nsn` | `product.nsn` | 1 |

## Cross-source merges (kept best version, all sources noted)

| Category | Item | Sources | #rows merged |
|---|---|---|---|
| Sales / Order Management | `order.name` | Microsoft CDM; Schema.org | 2 |
| Sales / Order Management | `order.description` | Microsoft CDM; Schema.org; Tryton | 3 |
| Sales / Order Management | `order.order_number` | Microsoft CDM; Schema.org | 2 |
| Sales / Order Management | `quote.description` | Microsoft CDM; Stripe API | 2 |
| Finance / Accounting | `invoice.name` | Microsoft CDM; Schema.org | 2 |
| Finance / Accounting | `invoice.description` | Microsoft CDM; Stripe API; Schema.org; Tryton | 4 |
| Finance / Accounting | `invoice.due_date` | Microsoft CDM; Stripe API | 2 |
| Finance / Accounting | `invoice.account_id` | Microsoft CDM; Schema.org | 2 |
| Product Master Data | `product.product_id` | Microsoft CDM; Schema.org | 2 |
| Product Master Data | `product.name` | Microsoft CDM; Stripe API; Schema.org; Tryton | 4 |
| Product Master Data | `product.description` | Microsoft CDM; Stripe API; Schema.org; Tryton | 4 |
| Product Master Data | `product.size` | Microsoft CDM; Schema.org | 2 |
| Healthcare | `patient.marital_status` | HL7 FHIR; ERPNext / Frappe Health | 2 |
| Customer Relationship Management (CRM) | `organization.identifier` | HL7 FHIR; Schema.org | 2 |
| Customer Relationship Management (CRM) | `organization.name` | HL7 FHIR; Schema.org | 2 |
| Customer Relationship Management (CRM) | `organization.address` | HL7 FHIR; Schema.org | 2 |
| Finance / Accounting | `invoice.identifier` | HL7 FHIR; Schema.org | 2 |
| Finance / Accounting | `invoice.status` | HL7 FHIR; Stripe API | 2 |
| Finance / Accounting | `invoice.type` | HL7 FHIR; Tryton | 2 |
| Finance / Accounting | `invoice.issuer` | HL7 FHIR; Stripe API | 2 |
| Finance / Accounting | `invoice.account` | HL7 FHIR; Tryton | 2 |
| Product Master Data | `product.gtin` | GS1; Schema.org | 2 |
| Product Master Data | `product.nsn` | GS1; Schema.org | 2 |
| Human Resources | `person.description` | ISA-95 (B2MML); Schema.org | 2 |
| Procurement / Purchasing | `purchase_order.origin` | Odoo; Tryton | 2 |
| Procurement / Purchasing | `purchase_order.state` | Odoo; Tryton | 2 |
| Product Master Data | `product.url` | Stripe API; Schema.org | 2 |
| Finance / Accounting | `invoice.currency` | Stripe API; Tryton | 2 |
| Finance / Accounting | `invoice.customer` | Stripe API; Schema.org | 2 |
| Finance / Accounting | `invoice.lines` | Stripe API; Tryton | 2 |
| Finance / Accounting | `invoice.number` | Stripe API; Tryton | 2 |

## Related concepts (same field name, different entities)

These share a field *name* across sources but belong to **different entities**, so they are deliberately kept separate. Listed for cross-reference only.

| Category | Field | Entities | Sources |
|---|---|---|---|
| Customer Relationship Management (CRM) | `address` | customer, organization, party.identifier | HL7 FHIR, Schema.org, Stripe API, Tryton |
| Customer Relationship Management (CRM) | `department` | contact, organization | Microsoft CDM, Schema.org |
| Customer Relationship Management (CRM) | `description` | account, contact, customer, lead, organization | Microsoft CDM, Schema.org, Stripe API |
| Customer Relationship Management (CRM) | `email` | customer, organization, party.party | Schema.org, Stripe API, Tryton |
| Customer Relationship Management (CRM) | `fax` | account, contact, lead, party.party | Microsoft CDM, Tryton |
| Customer Relationship Management (CRM) | `full_name` | contact, lead, party.party | Microsoft CDM, Tryton |
| Customer Relationship Management (CRM) | `name` | account, customer, organization, party.party | HL7 FHIR, Microsoft CDM, Schema.org, Stripe API, Tryton |
| Customer Relationship Management (CRM) | `number_of_employees` | account, lead, organization | Microsoft CDM, Schema.org |
| Customer Relationship Management (CRM) | `phone` | customer, party.party | Stripe API, Tryton |
| Customer Relationship Management (CRM) | `type` | organization, party.identifier | HL7 FHIR, Tryton |
| Finance / Accounting | `account` | account.invoice.line, account.invoice.tax, account.move.line, account.reconcile.show, invoice | HL7 FHIR, Tryton |
| Finance / Accounting | `amount` | charge, gs1, invoiceitem, payment_intent, payout, refund | GS1, Stripe API |
| Finance / Accounting | `automatic` | account.reconcile.start, payout | Stripe API, Tryton |
| Finance / Accounting | `currency` | account.invoice.line, account.invoice.pay.ask, account.invoice.pay.start, account.invoice.payment.mean.rule, account.invoice.tax, account.move.line, account.move.line.reschedule.preview, account.move.line.reschedule.start, account.move.line.reschedule.term, account.move.reconcile_lines.writeoff, account.reconcile.show, charge, invoice, invoiceitem, payment_intent, payout, refund | Stripe API, Tryton |
| Finance / Accounting | `customer` | charge, invoice, invoiceitem, payment_intent | Schema.org, Stripe API |
| Finance / Accounting | `date` | account.invoice.pay.start, account.invoice.report.revision, account.move, account.move.line, account.move.line.reschedule.term, account.move.reconcile_lines.writeoff, account.move.reconciliation, account.reconcile.show, invoice, invoiceitem | HL7 FHIR, Stripe API, Tryton |
| Finance / Accounting | `description` | account.invoice.line, account.invoice.pay.start, account.invoice.tax, account.move, account.move.cancel.default, account.move.line, account.move.line.delegate.start, account.move.line.group.start, account.move.line.reschedule.preview, account.move.reconcile_lines.writeoff, account.reconcile.show, charge, invoice, invoice_product, invoiceitem, payment_intent, payout, refund | Microsoft CDM, Schema.org, Stripe API, Tryton |
| Finance / Accounting | `invoice` | account.invoice.alternative_payee, account.invoice.line, account.invoice.pay.ask, account.invoice.payment.mean, account.invoice.report.revision, account.invoice.tax, account.invoice_account.move.line, account.invoice_additional_account.move, invoiceitem | Stripe API, Tryton |
| Finance / Accounting | `lines` | account.invoice.pay.ask, account.move, account.move.reconciliation, account.reconcile.show, invoice | Stripe API, Tryton |
| Finance / Accounting | `name` | account.invoice.payment.method, account.move.reconcile.write_off, invoice | Microsoft CDM, Schema.org, Tryton |
| Finance / Accounting | `note` | account.invoice.line, invoice | HL7 FHIR, Tryton |
| Finance / Accounting | `number` | account.move, account.move.line.reschedule.start, account.move.reconciliation, invoice | Stripe API, Tryton |
| Finance / Accounting | `payment_method` | account.invoice.pay.start, charge, invoice, payment_intent | Schema.org, Stripe API, Tryton |
| Finance / Accounting | `period` | account.move, account.move.line, account.move.open_journal.ask, invoiceitem | Stripe API, Tryton |
| Finance / Accounting | `price_per_unit` | gs1, invoice_product | GS1, Microsoft CDM |
| Finance / Accounting | `quantity` | account.invoice.line, invoice_product, invoiceitem | Microsoft CDM, Stripe API, Tryton |
| Finance / Accounting | `sequence_number` | account.invoice.tax, invoice_product | Microsoft CDM, Tryton |
| Finance / Accounting | `status` | charge, invoice, payment_intent, payout, refund | HL7 FHIR, Stripe API |
| Finance / Accounting | `tax` | account.invoice.line_account.tax, account.invoice.tax, invoice_product | Microsoft CDM, Tryton |
| Finance / Accounting | `total_amount` | account.move.line.reschedule.start, invoice | Microsoft CDM, Tryton |
| Finance / Accounting | `type` | account.invoice.line, account.invoice.pay.ask, invoice, payout | HL7 FHIR, Stripe API, Tryton |
| Healthcare | `appointment` | clinical_procedure, encounter, patient_encounter, vital_signs | ERPNext / Frappe Health, HL7 FHIR |
| Healthcare | `diagnosis` | encounter, patient_encounter | ERPNext / Frappe Health, HL7 FHIR |
| Healthcare | `encounter` | observation, vital_signs | ERPNext / Frappe Health, HL7 FHIR |
| Healthcare | `status` | clinical_procedure, coverage, encounter, lab_test, observation, patient, patient_appointment, patient_encounter | ERPNext / Frappe Health, HL7 FHIR |
| Human Resources | `children` | hr.employee, person | Odoo, Schema.org |
| Human Resources | `description` | hr.job, person, personnel_class | ISA-95 (B2MML), Odoo, Schema.org |
| Human Resources | `gender` | hr.employee, person | Odoo, Schema.org |
| Human Resources | `name` | hr.department, hr.employee, hr.job, person | Odoo, Schema.org |
| Inventory / Warehouse | `name` | stock.location, stock.lot, stock.quant.package | Odoo, Tryton |
| Inventory / Warehouse | `pack_date` | gs1, stock.quant.package | GS1, Odoo |
| Inventory / Warehouse | `quantity` | material_lot, material_sub_lot, stock.location, stock.products_by_locations, stock.quant | ISA-95 (B2MML), Odoo, Tryton |
| Inventory / Warehouse | `storage_location` | material_lot, material_sub_lot, stock.location | ISA-95 (B2MML), Tryton |
| Manufacturing | `code` | mrp.bom, mrp.workcenter, production.bom | Odoo, Tryton |
| Manufacturing | `company` | bom, job_card, production, production.work, production.work.center, production.work.cycle, production_plan, work_order | ERPNext / Frappe Health, Tryton |
| Manufacturing | `description` | bom, bom_item, bom_operation, mrp.workcenter.productivity, operation, process_segment, work_order, workstation | ERPNext / Frappe Health, ISA-95 (B2MML), Odoo |
| Manufacturing | `duration` | mrp.production, mrp.workcenter.productivity, mrp.workorder, production.work.cycle | Odoo, Tryton |
| Manufacturing | `effective_start_date` | process_segment, production | ISA-95 (B2MML), Tryton |
| Manufacturing | `name` | mrp.production, mrp.routing.workcenter, mrp.unbuild, mrp.workcenter, mrp.workcenter.productivity.loss, mrp.workcenter.tag, mrp.workorder, production.bom, production.routing, production.routing.operation, production.work.center, production.work.center.category | Odoo, Tryton |
| Manufacturing | `operation` | bom_item, bom_operation, job_card, production.routing.step, production.work | ERPNext / Frappe Health, Tryton |
| Manufacturing | `operation_id` | job_card, mrp.bom.byproduct, mrp.bom.line, mrp.workorder | ERPNext / Frappe Health, Odoo |
| Manufacturing | `origin` | mrp.production, production | Odoo, Tryton |
| Manufacturing | `planned_start_date` | production, work_order | ERPNext / Frappe Health, Tryton |
| Manufacturing | `production_capacity` | mrp.production, workstation | ERPNext / Frappe Health, Odoo |
| Manufacturing | `quantity` | bom, production, production.bom.input, production.bom.tree, production.bom.tree.open.start | ERPNext / Frappe Health, Tryton |
| Manufacturing | `routing` | bom, production.routing.step, production.routing_production.bom | ERPNext / Frappe Health, Tryton |
| Manufacturing | `state` | mrp.production, mrp.unbuild, mrp.workorder, production, production.work, production.work.cycle | Odoo, Tryton |
| Manufacturing | `type` | mrp.bom, production | Odoo, Tryton |
| Manufacturing | `warehouse` | production, production.work, production.work.center, production_plan, workstation | ERPNext / Frappe Health, Tryton |
| Product Master Data | `category` | product, product.template_product.category, product.template_product.category.all | Schema.org, Tryton |
| Product Master Data | `description` | material_class, material_definition, product | ISA-95 (B2MML), Microsoft CDM, Schema.org, Stripe API, Tryton |
| Product Master Data | `id` | material_class, material_definition, price, product | ISA-95 (B2MML), Stripe API |
| Product Master Data | `product` | price, product.cost_price, product.identifier, product.list_price | Stripe API, Tryton |
| Product Master Data | `product_url` | gs1, product | GS1, Microsoft CDM |
| Product Master Data | `type` | price, product, product.identifier | Stripe API, Tryton |
| Sales / Order Management | `currency` | order, quote, sale.line, subscription | Stripe API, Tryton |
| Sales / Order Management | `customer` | order, quote, sale.line, subscription | Schema.org, Stripe API, Tryton |
| Sales / Order Management | `description` | offer, opportunity, order, order_product, quote, sale.line, subscription | Microsoft CDM, Schema.org, Stripe API, Tryton |
| Sales / Order Management | `invoice` | quote, sale.sale_ignored_account.invoice, sale.sale_recreated_account.invoice | Stripe API, Tryton |
| Sales / Order Management | `name` | offer, opportunity, order, quote | Microsoft CDM, Schema.org |
| Sales / Order Management | `number` | order, quote | Stripe API, Tryton |
| Sales / Order Management | `quantity` | order_product, sale.line | Microsoft CDM, Tryton |
| Sales / Order Management | `tax` | order_product, sale.line_account.tax | Microsoft CDM, Tryton |
| Supply Chain / Logistics | `origin` | gs1, stock.move, stock.picking | GS1, Odoo, Tryton |
| Supply Chain / Logistics | `state` | stock.move, stock.picking | Odoo, Tryton |

