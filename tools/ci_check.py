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

    if fail:
        print("FAIL: " + "; ".join(fail))
        return 1
    print("OK: all invariants hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
