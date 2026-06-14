# CLAUDE.md - Business Application Data Dictionary Builder

## Project Goal
Build a comprehensive, open-source **Business Data Dictionary** stored in SQLite as `datadict.db` (with schema exported to `datadict.sql`).  
The database should collect standardized business data items across all major industries and functional areas from **public/open-source resources only**.

### Core Database Schema (Master_Data.Dict)

```sql
CREATE TABLE Categories (
    CategoryID INTEGER PRIMARY KEY,
    Name TEXT NOT NULL UNIQUE,           -- e.g., "Manufacturing", "Finance", "Sales", ...
    Description TEXT,
    Source TEXT
);

CREATE TABLE DataItems (
    DataItemID INTEGER PRIMARY KEY,
    CategoryID INTEGER NOT NULL REFERENCES Categories(CategoryID),
    
    Name TEXT NOT NULL,                  -- e.g., "CustomerID", "OrderDate", "GTIN"
    Title TEXT,                          -- Human readable title
    Description TEXT,
    
    DataType TEXT,                       -- "VARCHAR", "DECIMAL", "DATE", "INTEGER", "BOOLEAN", ...
    ByteLength INTEGER,                  -- max length for strings, or total bytes
    DecimalScale INTEGER,                -- for numeric/decimal fields
    
    IsRequired BOOLEAN DEFAULT FALSE,
    IsNullable BOOLEAN DEFAULT TRUE,
    DefaultValue TEXT,
    
    AllowedValues TEXT,                  -- JSON array or comma-separated list
    FormatMask TEXT,                     -- e.g., "YYYY-MM-DD", "999.99"
    
    SourceStandard TEXT,                 -- e.g., "ISA-95", "Microsoft CDM", "Odoo", "Schema.org", "EDIFACT", ...
    SourceURL TEXT,
    Version TEXT,
    
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_dataitems_category ON DataItems(CategoryID);
CREATE INDEX idx_dataitems_name ON DataItems(Name);

```

## Scope - Collect data items for these categories (add more if found):
 - Manufacturing
 - Finance / Accounting
 - Sales / Order Management
 - Inventory / Warehouse
 - Procurement / Purchasing
 - Human Resources
 - Healthcare
 - Supply Chain / Logistics
 - Customer Relationship Management (CRM)
 - Product Master Data
 - Quality Management
 - Maintenance / Asset Management



## Allowed Sources (Strictly Open-Source / Public Only)Microsoft Common Data Model (GitHub)
B2MML / ISA-95 XML schemas (GitHub)
Odoo source code & documentation
ERPNext / Frappe DocTypes
Tryton models
Schema.org
Public JSON Schemas, OpenAPI specs from open projects
Public domain or openly licensed glossaries

## Never use paywalled content, X12 Glass, proprietary SAP tables, or scraped commercial sites.Your Task (Step-by-Step Instructions)

# Phase 1: Discovery
Explore the allowed GitHub repos and documentation. List all major modules/entities found.

# Phase 2: Extraction
For every business object (Customer, Product, Order, WorkOrder, Invoice, Employee, etc.), extract:
Field names
Data types + lengths/scales
Required/Optional flags
Descriptions
Allowed values / enums
Map them to the correct Category

# Phase 3: Normalization  
Standardize naming (use camelCase or snake_case consistently)
Deduplicate similar items across systems (keep best version with multiple sources)
Add meaningful Title and Description

# Phase 4: SQLite Generation
Generate and maintain:datadict.sql (full schema + INSERT statements)
datadict.db (actual database)
sources.md (list of every source used)

## Output Requirements
Always show the SQL you are about to run or have run.
Provide summary statistics: "X items in Manufacturing, Y in Finance..."
Keep a running log of progress.
Make the final database easily queryable (SELECT * FROM DataItems WHERE CategoryID = ?).

## Coding Guidelines
Use Python + sqlite3 (no external heavy dependencies if possible).
Make the script idempotent (can be re-run safely).
Include functions like insert_or_update_item(...)
Output clean, well-commented code.

## Tone & Style
Be systematic, thorough, and conservative with data quality. Prefer accuracy over quantity. When in doubt, include the item with its original source noted.
Start by exploring the B2MML / ISA-95 XML schemas (GitHub), then Microsoft CDM and Odoo repositories, then expand to others.

Let's begin.
