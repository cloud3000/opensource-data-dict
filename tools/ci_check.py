#!/usr/bin/env python3
"""
tools/ci_check.py - CI invariant checks for the data dictionary.

Asserts *semantic* invariants, not byte-identity: a plain rebuild always
"drifts" on timestamps (the DB's CreatedAt/UpdatedAt and the normalization
report's generated-date line), so `git diff --exit-code` would fail every run.
Instead we check things that must hold regardless of how the dataset grows.

Run from anywhere:
    python3 tools/ci_check.py
Exits non-zero (failing the CI job) if any invariant is violated.
"""

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)          # so `import seeds` works when run from tools/
sys.path.insert(0, os.path.join(ROOT, "tools"))

import seeds  # noqa: E402,F401  (all seed modules must import)
from curated_descriptions import CURATED  # noqa: E402

DB = os.path.join(ROOT, "datadict.db")
UI_DB = os.path.join(ROOT, "ui_datadict.db")


def check_ui(datadict_items):
    """Invariants for the derived UI projection (ui_datadict.db)."""
    fail = []
    if not os.path.exists(UI_DB):
        return [f"{UI_DB} not found (run build_ui_dict.py)"]
    u = sqlite3.connect(UI_DB)
    u.row_factory = sqlite3.Row
    items = u.execute("SELECT COUNT(*) n FROM UI_DataItems").fetchone()["n"]
    groups = u.execute("SELECT COUNT(*) n FROM Groups").fetchone()["n"]
    orphan_group = u.execute(
        "SELECT COUNT(*) n FROM UI_DataItems x WHERE NOT EXISTS "
        "(SELECT 1 FROM Groups g WHERE g.GroupID = x.GroupID)").fetchone()["n"]
    bad_groupcat = u.execute(
        "SELECT COUNT(*) n FROM Groups g WHERE NOT EXISTS "
        "(SELECT 1 FROM Categories c WHERE c.CategoryID = g.CategoryID)"
    ).fetchone()["n"]
    bad_bytes = u.execute(
        "SELECT COUNT(*) n FROM UI_DataItems "
        "WHERE ByteLength IS NOT CharLength * 4").fetchone()["n"]
    bad_charlen = u.execute(
        "SELECT COUNT(*) n FROM UI_DataItems "
        "WHERE CharLength IS NULL OR CharLength <= 0").fetchone()["n"]
    dupes = u.execute(
        "SELECT COUNT(*) n FROM (SELECT GroupID, Name FROM UI_DataItems "
        "GROUP BY GroupID, Name HAVING COUNT(*) > 1)").fetchone()["n"]

    print(f"ui_items={items}  groups={groups}  orphan_groups={orphan_group}  "
          f"bad_group_category={bad_groupcat}  byte!=char*4={bad_bytes}  "
          f"bad_charlength={bad_charlen}  dup_(group,name)={dupes}")

    if groups < 1:
        fail.append("UI: no groups")
    if items != datadict_items:
        fail.append(f"UI: item count {items} != datadict {datadict_items} "
                    "(projection should keep every item)")
    if orphan_group:
        fail.append(f"UI: {orphan_group} items reference a missing group")
    if bad_groupcat:
        fail.append(f"UI: {bad_groupcat} groups reference a missing category")
    if bad_bytes:
        fail.append(f"UI: {bad_bytes} rows where ByteLength != CharLength*4")
    if bad_charlen:
        fail.append(f"UI: {bad_charlen} rows with null/non-positive CharLength")
    if dupes:
        fail.append(f"UI: {dupes} duplicate (GroupID, Name) pairs")
    return fail


def main():
    if not os.path.exists(DB):
        print(f"FAIL: {DB} not found (run build_dict.py first)")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) n FROM DataItems").fetchone()["n"]
    ncat = conn.execute("SELECT COUNT(*) n FROM Categories").fetchone()["n"]
    missing = conn.execute(
        "SELECT COUNT(*) n FROM DataItems "
        "WHERE Description IS NULL OR trim(Description) = ''"
    ).fetchone()["n"]
    empty_cats = conn.execute(
        "SELECT COUNT(*) n FROM Categories c WHERE NOT EXISTS "
        "(SELECT 1 FROM DataItems d WHERE d.CategoryID = c.CategoryID)"
    ).fetchone()["n"]
    # Curated map entries should still resolve to a real item (catches renames).
    orphan_curated = sum(
        1 for name in CURATED
        if conn.execute("SELECT 1 FROM DataItems WHERE Name = ? LIMIT 1",
                        (name,)).fetchone() is None
    )

    print(f"items={total}  categories={ncat}  missing_descriptions={missing}  "
          f"empty_categories={empty_cats}  curated={len(CURATED)}  "
          f"orphan_curated={orphan_curated}")

    fail = []
    if total < 1:
        fail.append("no data items")
    if ncat < 1:
        fail.append("no categories")
    if missing != 0:
        fail.append(f"{missing} items missing a description (want 0)")
    if empty_cats != 0:
        fail.append(f"{empty_cats} categories have no items")
    if orphan_curated != 0:
        fail.append(f"{orphan_curated} curated descriptions reference a "
                    "non-existent item Name")

    fail += check_ui(total)

    if fail:
        print("FAIL: " + "; ".join(fail))
        return 1
    print("OK: all invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
