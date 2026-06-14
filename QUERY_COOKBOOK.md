# Query Cookbook

Ready-to-run SQL for `datadict.db`. Every query below was executed against the
current database. Run them with, e.g.:

```bash
sqlite3 datadict.db "SELECT ... ;"      # one-off
sqlite3 -box datadict.db < query.sql    # pretty output
```

Tip: start `sqlite3 datadict.db` then `.mode box` and `.headers on` for
readable interactive output.

---

## 1. Orientation

**List the categories with item counts**
```sql
SELECT c.Name AS category, COUNT(d.DataItemID) AS items
FROM Categories c
LEFT JOIN DataItems d ON d.CategoryID = c.CategoryID
GROUP BY c.CategoryID
ORDER BY items DESC;
```

**Headline totals**
```sql
SELECT (SELECT COUNT(*) FROM DataItems)  AS data_items,
       (SELECT COUNT(*) FROM Categories) AS categories;
```

**Look up a category's ID by name**
```sql
SELECT CategoryID, Name FROM Categories WHERE Name = 'Healthcare';
```

---

## 2. Browsing data items

**All items in a category** (the canonical query from the project brief)
```sql
SELECT Name, Title, DataType, IsRequired
FROM DataItems
WHERE CategoryID = (SELECT CategoryID FROM Categories WHERE Name = 'Finance / Accounting')
ORDER BY Name;
```

**All fields of one entity** (entity = text before the last dot in `Name`)
```sql
SELECT Name, DataType, ByteLength, Description
FROM DataItems
WHERE Name LIKE 'invoice.%'
ORDER BY Name;
```

**Keyword search across name, title and description**
```sql
SELECT Name, Title, SourceStandard
FROM DataItems
WHERE Name LIKE '%gtin%' OR Title LIKE '%GTIN%' OR Description LIKE '%GTIN%';
```

**Entities and their field counts** (entity = everything before the last dot).
Standard SQLite has no `reverse()`/right-find, so split on the last dot with a
small recursive CTE that strips leading segments until none remain:
```sql
WITH RECURSIVE split(id, field) AS (
  SELECT DataItemID, Name FROM DataItems
  UNION ALL
  SELECT id, substr(field, instr(field, '.') + 1) FROM split WHERE instr(field, '.') > 0
),
last AS (SELECT id, field FROM split WHERE instr(field, '.') = 0)
SELECT substr(d.Name, 1, length(d.Name) - length(l.field) - 1) AS entity,
       COUNT(*) AS fields
FROM DataItems d JOIN last l ON l.id = d.DataItemID
GROUP BY entity
ORDER BY fields DESC
LIMIT 20;
-- top entities: invoice (224), gs1 (218), product (149), order (143), lead (119)
```

---

## 3. Data types, lengths, requiredness

**Data-type distribution**
```sql
SELECT DataType, COUNT(*) AS n
FROM DataItems
GROUP BY DataType
ORDER BY n DESC;
```

**Required fields only**
```sql
SELECT Name, DataType, ByteLength
FROM DataItems
WHERE IsRequired = 1
ORDER BY Name;
```

**String fields with a declared max length**
```sql
SELECT Name, ByteLength
FROM DataItems
WHERE DataType = 'VARCHAR' AND ByteLength IS NOT NULL
ORDER BY ByteLength DESC
LIMIT 20;
```

---

## 4. Allowed values (enumerations)

`AllowedValues` is a **JSON array** for normal enums, or a **JSON object keyed
by source** when merged sources diverge.

**All items that define allowed values**
```sql
SELECT Name, AllowedValues
FROM DataItems
WHERE AllowedValues IS NOT NULL
ORDER BY Name;
```

**Only the per-source (divergent) enums**
```sql
SELECT Name, SourceStandard, AllowedValues
FROM DataItems
WHERE AllowedValues LIKE '{%}';      -- object form
-- e.g. purchase_order.state -> {"Odoo":[...], "Tryton":[...]}
```

**Expand a flat enum into rows** (uses SQLite JSON1)
```sql
SELECT d.Name, j.value AS allowed_value
FROM DataItems d, json_each(d.AllowedValues) j
WHERE d.Name = 'order.order_status';
```

**Expand a per-source enum object into (source, value) rows**
```sql
SELECT k.key AS source, v.value AS allowed_value
FROM DataItems d
JOIN json_each(d.AllowedValues) k ON json_valid(d.AllowedValues)
JOIN json_each(k.value)         v
WHERE d.Name = 'purchase_order.state' AND d.AllowedValues LIKE '{%}';
```

---

## 5. Sources & provenance

**Item count per atomic source** (splits merged `"A; B"` strings)
```sql
SELECT TRIM(j.value) AS source, COUNT(*) AS items
FROM DataItems d,
     json_each('["' || REPLACE(d.SourceStandard, '; ', '","') || '"]') j
GROUP BY source
ORDER BY items DESC;
```

**Everything from one source**
```sql
SELECT Name, DataType
FROM DataItems
WHERE SourceStandard LIKE '%HL7 FHIR%'
ORDER BY Name;
```

**Trace an item back to its source document(s)**
```sql
SELECT Name, SourceStandard, SourceURL, Version
FROM DataItems
WHERE Name = 'product.gtin';
-- SourceStandard: "GS1; Schema.org"; SourceURL holds both, " | "-joined
```

---

## 6. Cross-source corroboration (merged items)

**Items confirmed by more than one source, most-corroborated first**
```sql
SELECT Name, SourceStandard,
       (length(SourceStandard) - length(replace(SourceStandard, ';', ''))) + 1
         AS n_sources
FROM DataItems
WHERE SourceStandard LIKE '%;%'
ORDER BY n_sources DESC, Name;
-- top rows: invoice.description / product.description / product.name (4 sources)
```

**How many items are multi-source, by category**
```sql
SELECT c.Name AS category, COUNT(*) AS corroborated
FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
WHERE d.SourceStandard LIKE '%;%'
GROUP BY c.Name
ORDER BY corroborated DESC;
```

---

## 7. Format masks (e.g. GS1)

**Items carrying an explicit format mask**
```sql
SELECT Name, DataType, FormatMask
FROM DataItems
WHERE FormatMask IS NOT NULL
ORDER BY Name;
```

**The GS1 element catalog with its barcode formats**
```sql
SELECT Name, Title, FormatMask, ByteLength
FROM DataItems
WHERE SourceStandard LIKE '%GS1%'
ORDER BY Name;
```

---

## 8. Data-quality / coverage checks

**Items missing a description**
```sql
SELECT COUNT(*) AS missing_description
FROM DataItems
WHERE Description IS NULL OR Description = '';
```

**Coverage summary per category** (with/without description, with enums)
```sql
SELECT c.Name AS category,
       COUNT(*) AS items,
       SUM(d.Description IS NOT NULL AND d.Description <> '') AS with_desc,
       SUM(d.AllowedValues IS NOT NULL)                      AS with_enum,
       SUM(d.IsRequired = 1)                                 AS required
FROM DataItems d JOIN Categories c ON c.CategoryID = d.CategoryID
GROUP BY c.Name
ORDER BY items DESC;
```

**Field names shared across sources in a category** (same field name, possibly
different entities — useful for spotting harmonization candidates; see also
`NORMALIZATION_REPORT.md` "related concepts")
```sql
WITH RECURSIVE split(id, field) AS (
  SELECT DataItemID, Name FROM DataItems
  UNION ALL
  SELECT id, substr(field, instr(field, '.') + 1) FROM split WHERE instr(field, '.') > 0
),
last AS (SELECT id, field FROM split WHERE instr(field, '.') = 0)
SELECT c.Name AS category, l.field,
       COUNT(DISTINCT d.SourceStandard) AS sources,
       COUNT(*) AS occurrences
FROM DataItems d
JOIN Categories c ON c.CategoryID = d.CategoryID
JOIN last l       ON l.id = d.DataItemID
GROUP BY category, l.field
HAVING occurrences > 1 AND sources > 1
ORDER BY occurrences DESC
LIMIT 20;
```

---

## 9. Export helpers

**CSV of one category**
```bash
sqlite3 -header -csv datadict.db \
  "SELECT Name, Title, DataType, ByteLength, IsRequired, AllowedValues, SourceStandard
   FROM DataItems
   WHERE CategoryID = (SELECT CategoryID FROM Categories WHERE Name='Product Master Data')
   ORDER BY Name;" > product_master_data.csv
```

**JSON of an entity's fields** (SQLite JSON1)
```sql
SELECT json_group_array(json_object(
         'name', Name, 'type', DataType, 'required', IsRequired,
         'description', Description))
FROM DataItems
WHERE Name LIKE 'patient.%';
```
