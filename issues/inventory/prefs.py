#!/usr/bin/env python3
"""Parse the PrefsSchema.cpp data table into rows for the inventory doc."""
import json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "src", "webapi", "PrefsSchema.cpp")
src = open(SRC).read()

enums = {}
for m in re.finditer(r'const char \*const (k\w+)\[\] = \{([^}]*)\}', src):
    enums[m.group(1)] = [x.strip().strip('"') for x in m.group(2).split(',')
                         if x.strip() and x.strip() != 'nullptr']

table = src[src.index("const PrefField kSchema[] = {"):]
table = table[:table.index("\n};")]

ROW = re.compile(r'PREF_([A-Z0-9_]+)\(([^;]*?)\),\s*$', re.M)
TYPE = {
    "BOOL": "bool", "BOOL_INGROUP": "bool", "BOOL_GATED": "bool",
    "U16": "number (uint16)", "U32": "number (uint32)",
    "STR": "string", "STRARR": "array of strings", "ENUM": "string (enum)",
    "MD4": "string (md4 hex)", "PASSWD_PLAIN": "string (write-only)",
    "PASSWD_HASHED": "string (write-only, md4 hex)",
    "TRIGGER": "bool (write-only trigger)", "REJECT": "—",
}
rows = []
for m in ROW.finditer(table):
    kind = m.group(1)
    args = [a.strip() for a in re.split(r',(?![^()]*\))', m.group(2))]
    r = {"macro": kind, "category": args[0].strip('"'), "key": args[1].strip('"'),
         "type": TYPE.get(kind, kind), "access": "", "max": "", "enum": [],
         "gate": "", "invert": False, "tag": args[2] if len(args) > 2 else ""}
    acc = [a for a in args if a.startswith("PrefAccess::")]
    r["access"] = acc[0].split("::")[1] if acc else (
        "WriteOnly" if kind.startswith(("PASSWD", "TRIGGER")) else
        "Rejected" if kind == "REJECT" else "")
    if kind in ("U16", "U32"):
        r["max"] = args[3].rstrip('u')
    if kind == "ENUM":
        r["enum"] = enums.get(args[3], [])
    if kind == "BOOL_GATED":
        r["gate"] = args[-1].strip().strip('"')
    if kind in ("BOOL", "BOOL_GATED"):
        r["invert"] = args[4] == "true"
    rows.append(r)

cats = re.search(r'const PrefCategory kCategories\[\] = \{(.*?)\n\};', src, re.S)
categories = re.findall(r'\{\s*"([^"]+)",\s*([A-Z_0-9]+)\s*\}', cats.group(1)) if cats else []

json.dump({"rows": rows, "categories": categories}, open(sys.argv[1], "w"), indent=1)
print(f"pref rows: {len(rows)}  categories: {len(categories)}")
from collections import Counter
print(Counter(r["access"] for r in rows))
print(sorted(set(r["category"] for r in rows)))
