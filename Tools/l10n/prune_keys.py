#!/usr/bin/env python3
"""Remove catalog entries and translation rows for keys the app no longer uses.

`merge.py` copies every row of every `chunk*.tsv` into the catalog, including
rows written for strings that were later removed from the source. Running it
therefore resurrects pruned keys. This script is the second half of that
workflow:

    python3 Tools/l10n/merge.py && python3 Tools/l10n/prune_keys.py

It uses the same definition of "referenced" as `audit_keys.py` (`L("…")` calls
plus SwiftUI literals), drops the orphan catalog entries and rewrites the chunk
files without those rows, so the next merge stays clean too.

Usage:  python3 Tools/l10n/prune_keys.py [--dry]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOG = ROOT / "Resilix" / "Resources" / "Localizable.xcstrings"
TABLES = sorted((ROOT / "Tools" / "l10n").glob("chunk*.tsv"))

L_CALL = re.compile(r'\bL\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
VIEWS = [
    "Text", "Label", "Button", "navigationTitle", "Section", "Picker", "TextField",
    "SecureField", "Toggle", "Menu", "ContentUnavailableView", "confirmationDialog",
    "alert", "DisclosureGroup", "Link", "GroupBox", "Tab", "toolbarTitle",
    "NavigationLink", "LabeledContent", "ToolbarItem", "ShareLink", "EditButton",
]
PLAIN = re.compile(r"\b(" + "|".join(VIEWS) + r")\s*\(\s*\"((?:[^\"\\]|\\.)*)\"\s*[,)]")
INTERP = re.compile(r"\\\((?:[^()]|\([^()]*\))*\)")


def unescape(literal: str) -> str:
    return literal.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")


def to_key(literal: str) -> str:
    return unescape(INTERP.sub("%@", literal))


def referenced_keys() -> set[str]:
    keys: set[str] = set()
    for path in sorted(ROOT.rglob("*.swift")):
        text = path.read_text()
        for match in L_CALL.finditer(text):
            key = unescape(match.group(1))
            if key.strip():
                keys.add(key)
        for match in PLAIN.finditer(text):
            key = to_key(match.group(2))
            if key.strip():
                keys.add(key)
    return keys


def main() -> int:
    dry = "--dry" in sys.argv
    referenced = referenced_keys()

    catalog = json.loads(CATALOG.read_text())
    strings = catalog.get("strings", {})
    orphans = sorted(key for key in strings if key not in referenced)
    for key in orphans:
        del strings[key]
    if not dry:
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    removed_rows = 0
    for table in TABLES:
        kept: list[str] = []
        for line in table.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                kept.append(line)
                continue
            key = line.split("\t")[0].strip()
            if key in referenced:
                kept.append(line)
            else:
                removed_rows += 1
        if not dry:
            table.write_text("\n".join(kept) + ("\n" if kept else ""))

    print(f"referenced keys: {len(referenced)}")
    print(f"catalog keys:    {len(strings)}")
    print(f"pruned catalog entries: {len(orphans)}")
    for key in orphans:
        print("  PRUNED:", key)
    print(f"pruned translation rows: {removed_rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
