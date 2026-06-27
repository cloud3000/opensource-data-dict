# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This is the **release-facing** summary, grouped by version. For the granular,
chronological development log see [`PROGRESS.md`](PROGRESS.md).

## [Unreleased]

_No unreleased changes yet._

## [1.1.0] - 2026-06-27

### Added

- `tools/find.py` — find data items by a business term via a layered resolver
  (category → entity → alias → keyword), with a reviewable `SEARCH_ALIASES` map
  of ~55 business terms (billing, payee, receivable, shipping, employee,
  appointment, inspection, …) and a `--ddl` flag that emits a validated
  `CREATE TABLE` per matched entity. Alias targets resolve entity-first for
  precision.
- README "Find fields by business term" section documenting the resolver, the
  alias map, CLI examples, and the `--ddl` scaffolding output.

## [1.0.0] - 2026-06-27

First tagged release.

### Added

- **Data dictionary** — `datadict.db` (SQLite) plus a full schema + data dump in
  `datadict.sql`: **3,688 data items across 12 categories**, extracted from
  **9 public / open-source standards** (Microsoft CDM, Tryton, ERPNext / Frappe
  Health, Odoo, Stripe API, Schema.org, GS1, ISA-95 / B2MML, HL7 FHIR).
- **Manufacturing coverage** — built out the Manufacturing category from the
  open ERPs' manufacturing modules (Odoo `mrp`, Tryton `production*`, ERPNext
  manufacturing DocTypes): 15 → 648 items.
- **100% description coverage** — every item has a description: 3,234 sourced
  from upstream and 454 hand-curated editorial descriptions
  (`tools/curated_descriptions.py`) where the source provided none.
- **Build pipeline** — idempotent `build_dict.py` (schema, seed load, Phase 3
  normalization + cross-source dedup, SQL export, stats); per-source seed
  modules under `seeds/`; upstream generators under `tools/fetch_*.py`.
- **Documentation & diagrams** — `DATA_MODEL.md` (Mermaid ER diagram, category
  pie, **description coverage/provenance chart**, source→category map,
  contribution matrix) with SVG/PNG exports in `diagrams/`; `sources.md`,
  `QUERY_COOKBOOK.md`, `NORMALIZATION_REPORT.md`.
- **Continuous integration** — `.github/workflows/build.yml` builds from the
  committed seeds and runs `tools/ci_check.py` (semantic invariant gate) on
  every push and pull request.
- **Badges** — live CI build badge, dynamic description-coverage badge
  (shields endpoint, regenerated from the DB), and dual-license badges.
- **Licensing** — MIT for code ([`LICENSE`](LICENSE)), CC BY-SA 4.0 for the data
  compilation ([`DATA_LICENSE`](DATA_LICENSE)); per-item upstream licenses
  recorded in `sources.md`.

[Unreleased]: https://github.com/cloud3000/opensource-data-dict/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/cloud3000/opensource-data-dict/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/cloud3000/opensource-data-dict/releases/tag/v1.0.0
