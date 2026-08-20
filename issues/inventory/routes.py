#!/usr/bin/env python3
"""Extract the route table straight out of CApiDispatcher::DispatchToHandler.

A "route block" starts at either `if (path == "..."` or `ParsePattern("..."`
and runs to the next such marker. Within a block we collect the path
literal(s), the methods compared against, the Handle*/Serve* calls, and the
error responses (405 / 404 texts).
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apiscan

funcs = apiscan.index(["Api.cpp"])
body = funcs["DispatchToHandler"][0]["body"]
start_line = funcs["DispatchToHandler"][0]["start"]
lines = body.split("\n")

MARK = re.compile(r'(?:path == "([^"]+)")|(?:ParsePattern\("([^"]+)"\))|(?:path\.compare\(0,\s*\d+,\s*"([^"]+)"\))')
METH = re.compile(r'req\.method (==|!=) "([A-Z]+)"')
HANDLER = re.compile(r'\b(Handle[A-Za-z0-9_]+|Serve[A-Za-z0-9_]+)\s*\(')
ERR = re.compile(r'ErrorResponse\(\s*(\d+),\s*"([^"]*)",\s*((?:[^();]|\([^()]*\))*)\)', re.S)

marks = []
for i, l in enumerate(lines):
    for m in MARK.finditer(l):
        p = m.group(1) or m.group(2) or m.group(3)
        marks.append((i, p, "literal" if m.group(1) else ("pattern" if m.group(2) else "prefix")))

blocks = []
for k, (i, p, kind) in enumerate(marks):
    end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
    txt = "\n".join(lines[i:end])
    methods = sorted(set(m for op, m in METH.findall(txt) if op == "=="))
    excluded = sorted(set(m for op, m in METH.findall(txt) if op == "!="))
    handlers = list(dict.fromkeys(HANDLER.findall(txt)))
    errs = [[int(s), c, re.sub(r'\s+', ' ', re.sub(r'"\s*"', '', msg)).strip().strip('"')]
            for s, c, msg in ERR.findall(txt)]
    blocks.append({
        "path": p, "kind": kind, "line": start_line + i,
        "methods_eq": methods, "methods_ne": excluded,
        "handlers": handlers, "errors": errs,
        "src": txt,
    })

# merge consecutive blocks that share a path literal (pattern decl + match)
merged = []
for b in blocks:
    if merged and merged[-1]["path"] == b["path"]:
        prev = merged[-1]
        prev["methods_eq"] = sorted(set(prev["methods_eq"]) | set(b["methods_eq"]))
        prev["methods_ne"] = sorted(set(prev["methods_ne"]) | set(b["methods_ne"]))
        prev["handlers"] = list(dict.fromkeys(prev["handlers"] + b["handlers"]))
        prev["errors"] += b["errors"]
        prev["src"] += "\n" + b["src"]
    else:
        merged.append(b)

json.dump(merged, open(sys.argv[1], "w"), indent=1)
print(f"route blocks: {len(merged)}")
for b in merged:
    print(f"{b['line']:6d} {b['kind'][:3]} {b['path']:46s} eq={','.join(b['methods_eq']) or '-':22s} ne={','.join(b['methods_ne']) or '-':16s} {','.join(b['handlers'])}")
