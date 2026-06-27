# Contributing

[![Build](https://github.com/cloud3000/opensource-data-dict/actions/workflows/build.yml/badge.svg)](https://github.com/cloud3000/opensource-data-dict/actions/workflows/build.yml)
[![Descriptions](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcloud3000%2Fopensource-data-dict%2Fmain%2Fdiagrams%2Fcoverage-badge.json)](DATA_MODEL.md#3-description-coverage--provenance)

Thanks for your interest in improving the **Business Application Data
Dictionary**! Contributions of new sources, corrections, better descriptions,
and tooling are all welcome.

## Ground rules

1. **Open-source / public sources only.** Every data item must come from a
   publicly available, openly-licensed resource (open-source software schemas,
   open standards, public JSON Schema / OpenAPI specs, public-domain
   glossaries). **No** paywalled content, proprietary vendor tables (e.g. SAP),
   X12 Glass, or scraped commercial sites.
2. **Accuracy over quantity.** Prefer fewer, well-sourced items over many
   uncertain ones. When in doubt, include the item *with its original source
   noted* rather than guessing.
3. **Always record provenance.** Each item needs a `source_standard` and a
   `source_url` so it can be traced back and attributed.
4. **License compatibility.** Only add data from sources whose license is
   compatible with this project (see [README → License & attribution](README.md)).
   Note the source's license in `sources.md`.

## Project layout

```
build_dict.py       # idempotent builder (schema, load seeds, normalize, export, stats)
normalize.py        # Phase 3: snake_case naming, entity/field aliases, cross-source merge
seeds/              # one module per source: each exposes CATEGORIES + ITEMS
tools/fetch_*.py    # generators that (re)build seed modules from upstream
tools/gen_diagram.py, render_diagrams.py   # diagrams
sources.md          # provenance + licenses (update when adding a source)
PROGRESS.md         # running build log (add an entry per change)
```

## Adding a new source

A "seed module" is any `seeds/<name>.py` exposing two lists:

```python
CATEGORIES = [
    {"name": "Finance / Accounting", "description": "...", "source": "..."},
]

ITEMS = [
    {
        "category": "Finance / Accounting",   # must match a category Name
        "name": "invoice.total",              # "entity.field" (any case; normalized later)
        "title": "Invoice total",
        "description": "Total amount of the invoice.",
        "data_type": "DECIMAL",               # VARCHAR, INTEGER, DATE, BOOLEAN, ...
        "byte_length": None,
        "is_required": True,
        "allowed_values": None,               # JSON array string, e.g. '["draft","open"]'
        "format_mask": None,
        "source_standard": "Example Std",
        "source_url": "https://example.org/...",
        "version": "1.0",
    },
]
```

Two ways to produce one:

- **Generated** (preferred for large/maintainable sources): add a
  `tools/fetch_<source>.py` that downloads the upstream schema and writes
  `seeds/<source>.py`. Follow an existing generator as a template
  (`fetch_cdm.py` for JSON, `fetch_odoo.py`/`fetch_tryton.py` for Python `ast`,
  `fetch_frappe.py` for DocType JSON, `fetch_openapi.py` for OpenAPI/Swagger).
  For a new OpenAPI/Swagger spec you usually only need a new entry in `SPECS`
  inside `tools/fetch_openapi.py`.
- **Hand-written**: for small/curated sources, write `seeds/<source>.py`
  directly (see `seeds/isa95_b2mml.py`).

Then rebuild: `python3 build_dict.py`.

### Naming, aliases & merging

- `Name` is normalized to `entity.field` **snake_case** automatically — don't
  pre-normalize; just be consistent.
- Cross-source **merging** happens only when two items share the same
  `(category, entity.field)`. If a source uses a namespaced/different entity
  name for the *same* concept, add a **deliberate, reviewable** entry to
  `ENTITY_ALIASES` (e.g. `account.invoice` → `invoice`) or `FIELD_ALIASES`
  (e.g. `gs1.gtin` → `product.gtin`) in `normalize.py`. **Only alias genuinely
  equivalent concepts** — when unsure, leave them separate (they'll surface as
  "related concepts" in the report).

## Before you open a PR

Run and check:

```bash
python3 build_dict.py            # rebuild; review the printed stats
# (optional) full clean rebuild to catch stale rows:
rm -f datadict.db && python3 build_dict.py
sqlite3 /tmp/check.db < datadict.sql && echo "datadict.sql reloads OK"
python3 tools/gen_diagram.py     # refresh DATA_MODEL.md if categories/sources changed
python3 tools/ci_check.py        # same invariant gate CI runs (see below)
```

**CI runs automatically on every PR** ([`.github/workflows/build.yml`](.github/workflows/build.yml)):
it builds the DB from the committed seeds, regenerates the data model, and runs
`tools/ci_check.py` (asserts seeds import, the curated map resolves, 0 missing
descriptions, no empty categories). The build badge above reflects `main`'s
status — keep it green.

Checklist:

- [ ] `build_dict.py` runs cleanly and is **idempotent** (re-running doesn't
      change counts).
- [ ] `datadict.sql` reloads into a fresh SQLite DB without error.
- [ ] New/changed data items have `source_standard` + `source_url`.
- [ ] `sources.md` updated (new source row + license + extraction note).
- [ ] `PROGRESS.md` has a dated entry describing the change. (`PROGRESS.md` is
      the granular dev log; `CHANGELOG.md` is the curated, per-release summary —
      add a `## [Unreleased]` entry there only for release-worthy changes.)
- [ ] Reviewed `NORMALIZATION_REPORT.md` for unexpected merges/aliases.
- [ ] Committed the regenerated `datadict.db` / `datadict.sql` (and diagrams
      if changed).

## Coding guidelines

- **Python 3 standard library only** — no third-party runtime dependencies.
- Keep generators **re-runnable** and the build **idempotent**.
- Match the surrounding style; comment non-obvious parsing logic.

## Commits & PRs

- Branch off `main`; use clear, descriptive commit messages.
- Keep changes focused; describe the source(s) touched and item-count deltas.
- Open a PR against `main` with a short summary and any caveats (e.g. licensing
  judgment calls).

## Licensing of contributions

By contributing, you agree that:

- your **code** contributions are licensed under the **MIT License**, and
- your **data** contributions (and original descriptions) are licensed under
  **CC BY-SA 4.0**,

matching this project's outbound licensing (inbound = outbound), and that any
data you add is sourced from a license-compatible open resource with its
provenance recorded. A `Signed-off-by` line (DCO style) is appreciated but not
required.
